"""
Gradio Web 界面 — 公文写作 Agent（分步引导式 V2）

设计原则：
1. 一次只显示当前步骤，用户完成后才显示下一步
2. 顶部有步骤进度条，随时知道在哪
3. 每个步骤有明确的"上一步/下一步"按钮
4. URL导入和项目管理作为独立功能页，不干扰主流程
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import gradio as gr
from typing import List, Dict, Optional, Tuple, Any

from src.core.orchestrator import Orchestrator, OrchestratorState
from src.core.personalized_db import PersonalizedDB, ProjectStatus
from src.core.writing_mode import WritingMode, get_mode_profile
from src.utils.url_importer import URLDocumentImporter

STEPS = [
    ("1. 用户", "创建或选择你的身份"),
    ("2. 项目", "创建写作项目"),
    ("3. 场景", "选择最接近你的场景"),
    ("4. 问卷", "回答专属问题"),
    ("5. 方案", "确认写作方案"),
    ("6. 初稿", "生成文章初稿"),
    ("7. 审查", "自动审查与修正"),
    ("8. 完成", "导出最终结果"),
]

STEP_KEYS = [s[0] for s in STEPS]


def build_progress_bar(current_step: str) -> str:
    parts = []
    idx = STEP_KEYS.index(current_step) if current_step in STEP_KEYS else 0
    for i, (key, desc) in enumerate(STEPS):
        if i == idx:
            parts.append(f"**{key}**")
        elif i < idx:
            parts.append(f"~~{key}~~")
        else:
            parts.append(key)
    return " **→** ".join(parts)


class GradioApp:
    def __init__(self):
        self.orchestrator = Orchestrator()
        self.pdb = PersonalizedDB()
        self.current_user_id: Optional[str] = None
        self.current_project_id: Optional[str] = None
        self.brief = None

    def _get_state(self, session: dict) -> dict:
        return session.setdefault("state", {
            "step": "1. 用户",
            "answers": {},
            "skipped": [],
            "url_docs": [],
        })

    def _visibility(self, session: dict) -> list:
        s = self._get_state(session)
        current = s["step"]
        return [current == k for k in STEP_KEYS]

    # ═══ 业务逻辑 ═══

    def create_or_select_user(self, name: str, session: dict) -> Tuple[str, str, dict]:
        name = name.strip()
        if not name:
            return build_progress_bar("1. 用户"), "请输入用户名", session

        for uid, profile in self.pdb.profiles.items():
            if profile.name == name:
                self.current_user_id = uid
                self.pdb.set_current_user(uid)
                s = self._get_state(session)
                s["step"] = "2. 项目"
                projects_count = len(profile.projects)
                return (
                    build_progress_bar("2. 项目"),
                    f"欢迎回来，{name}！你有 {projects_count} 个项目。",
                    session
                )

        profile = self.pdb.create_user(name)
        self.current_user_id = profile.id
        s = self._get_state(session)
        s["step"] = "2. 项目"
        return (
            build_progress_bar("2. 项目"),
            f"你好，{name}！已创建新用户。",
            session
        )

    def create_project(self, proj_name: str, proj_desc: str, session: dict) -> Tuple[str, str, str, dict]:
        if not self.current_user_id:
            return build_progress_bar("1. 用户"), "", "请先创建用户", session

        proj_name = proj_name.strip()
        if not proj_name:
            return build_progress_bar("2. 项目"), "", "请输入项目名称", session

        project = self.pdb.create_project(proj_name, description=proj_desc)
        self.current_project_id = project.id
        self.orchestrator = Orchestrator()

        result = self.orchestrator.start_routing()
        choices = result.get("choices", [])
        choices_text = "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)])

        s = self._get_state(session)
        s["step"] = "3. 场景"
        s["routing_choices"] = choices
        s["routing_display"] = choices_text

        return (
            build_progress_bar("3. 场景"),
            "",
            choices_text,
            session
        )

    def submit_routing(self, choice_text: str, session: dict) -> Tuple[str, str, str, str, dict]:
        s = self._get_state(session)

        try:
            choice_index = int(choice_text.strip()) - 1
        except ValueError:
            return build_progress_bar("3. 场景"), "请输入选项数字", "", "", session

        result = self.orchestrator.submit_routing_choice(choice_index)

        if result.get("phase") == "routing_complete":
            mode = result.get("mode", "")
            mode_name = get_mode_profile(WritingMode(mode)).name if mode else mode
            s["step"] = "4. 问卷"

            next_q = self.orchestrator.get_current_mode_question()
            if next_q:
                s["current_q_index"] = next_q.get("index", 1)
                s["total_q"] = next_q.get("total", 1)
                progress = f"（{s['current_q_index']}/{s['total_q']}）"
                return (
                    build_progress_bar("4. 问卷"),
                    f"已选择 → {mode_name}模式 {progress}",
                    next_q.get("text", ""),
                    f"💡 {next_q.get('teaching', '')}",
                    session
                )

        return build_progress_bar("4. 问卷"), "", "", "", session

    def submit_answer(self, answer: str, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        s = self._get_state(session)
        answer = answer.strip()

        if answer.lower() == "skip":
            has_next = self.orchestrator.questionnaire.skip_current()
            qid = f"q_{s.get('current_q_index', 0)}"
            s.setdefault("skipped", []).append(qid)
            s.setdefault("answers", {})[qid] = "[已跳过]"

            if not has_next:
                return self._finish_questions(session)

            next_q = self.orchestrator.get_current_mode_question()
            if next_q:
                s["current_q_index"] = next_q.get("index", 1)
                s["total_q"] = next_q.get("total", 1)
                return (
                    build_progress_bar("4. 问卷"),
                    f"已跳过（{s['current_q_index']}/{s['total_q']}）",
                    next_q.get("text", ""),
                    f"💡 {next_q.get('teaching', '')}",
                    "",
                    "",
                    session
                )

        if answer.lower() == "back":
            prev = self.orchestrator.questionnaire.go_back()
            if prev:
                s["current_q_index"] = prev.get("index", 1)
                return (
                    build_progress_bar("4. 问卷"),
                    f"已回退到第 {prev['index']} 题",
                    prev.get("question", ""),
                    "",
                    "",
                    f"上一题：{prev.get('previous_answer', '')[:50]}...",
                    session
                )

        if answer.lower() == "finish":
            return self._finish_questions(session)

        has_next, next_q = self.orchestrator.submit_mode_answer(answer)

        if not has_next:
            return self._finish_questions(session)

        if next_q:
            s["current_q_index"] = next_q.get("index", 1)
            s["total_q"] = next_q.get("total", 1)
            return (
                build_progress_bar("4. 问卷"),
                "答案已保存",
                next_q.get("text", ""),
                f"💡 {next_q.get('teaching', '')}",
                "",
                "",
                session
            )

        return build_progress_bar("4. 问卷"), "", "", "", "", "", session

    def _finish_questions(self, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        self.brief = self.orchestrator.questionnaire.finish()
        s = self._get_state(session)

        try:
            plan = self.orchestrator.generate_plan()
            s["step"] = "5. 方案"
            return (
                build_progress_bar("5. 方案"),
                "问卷完成，方案已生成",
                "",
                "",
                plan.display(),
                "",
                session
            )
        except Exception as e:
            return build_progress_bar("4. 问卷"), f"生成方案失败: {e}", "", "", "", "", session

    def generate_draft(self, session: dict) -> Tuple[str, str, str, dict]:
        if not self.brief:
            return build_progress_bar("4. 问卷"), "请先完成问卷", "", session
        try:
            draft = self.orchestrator.write()
            s = self._get_state(session)
            s["step"] = "6. 初稿"
            return (build_progress_bar("6. 初稿"), "初稿已生成", draft, session)
        except Exception as e:
            return build_progress_bar("6. 初稿"), f"生成失败: {e}", "", session

    def run_review(self, session: dict) -> Tuple[str, str, str, dict]:
        if not self.orchestrator.draft:
            return build_progress_bar("6. 初稿"), "请先生成初稿", "", session
        try:
            summaries = self.orchestrator.review()
            s = self._get_state(session)
            s["step"] = "7. 审查"

            lines = ["【审查结果】"]
            for summary in summaries:
                status = "✅ 通过" if summary.passed else "❌ 未通过"
                lines.append(f"\n{summary.round_name}：{status}")
                for finding in summary.findings:
                    lines.append(f"  • {finding.severity.value}: {finding.issue}")
                    if finding.suggestion:
                        lines.append(f"    建议：{finding.suggestion}")

            return (build_progress_bar("7. 审查"), "审查完成", "\n".join(lines), session)
        except Exception as e:
            return build_progress_bar("7. 审查"), f"审查失败: {e}", "", session

    def finalize(self, session: dict) -> Tuple[str, str, dict]:
        try:
            output = self.orchestrator.finalize()
            s = self._get_state(session)
            s["step"] = "8. 完成"

            lines = ["═══════════════════════════════════════"]
            lines.append("  最终输出")
            lines.append("═══════════════════════════════════════\n")
            if output.get("draft"):
                lines.append(output["draft"])
            else:
                lines.append("（无草稿）")

            lines.append("\n═══════════════════════════════════════")
            lines.append(f"审查轮次：{output.get('review_count', 0)}")
            lines.append(f"审查通过：{output.get('review_passed', False)}")
            lines.append(f"写作模式：{output.get('plan', {}).get('mode_name', '')}")
            lines.append("═══════════════════════════════════════")

            if self.current_project_id:
                self.pdb.update_project_status(self.current_project_id, ProjectStatus.COMPLETED)

            return (build_progress_bar("8. 完成"), "\n".join(lines), session)
        except Exception as e:
            return build_progress_bar("8. 完成"), f"完成失败: {e}", session

    def restart(self, session: dict) -> Tuple[str, dict]:
        s = self._get_state(session)
        s["step"] = "1. 用户"
        s["answers"] = {}
        s["skipped"] = []
        self.orchestrator = Orchestrator()
        self.brief = None
        return build_progress_bar("1. 用户"), session

    # ═══ URL 导入 ═══

    def import_url(self, url: str, session: dict) -> Tuple[str, str, dict]:
        url = url.strip()
        if not url:
            return "", "请输入 URL", session
        try:
            importer = URLDocumentImporter()
            doc = importer.import_from_url(url)
            lines = ["【文档导入结果】", f"标题：{doc.title}", f"来源：{doc.source_site}",
                     f"字数：{doc.word_count}", f"格式：{doc.format.value}"]
            if doc.author: lines.append(f"作者：{doc.author}")
            if doc.publish_date: lines.append(f"发布时间：{doc.publish_date}")
            if doc.keywords: lines.append(f"\n关键词：{', '.join(doc.keywords[:10])}")
            if doc.style_patterns:
                lines.append("\n风格模式：")
                for p in doc.style_patterns: lines.append(f"  • {p}")
            if doc.content:
                lines.append(f"\n正文预览（前500字）：\n{doc.content[:500]}{'...' if len(doc.content) > 500 else ''}")
            if doc.import_notes: lines.append(f"\n备注：{doc.import_notes}")
            s = self._get_state(session)
            s.setdefault("url_docs", []).append(doc)
            return "\n".join(lines), "导入成功", session
        except Exception as e:
            return str(e), "导入失败", session

    def import_urls_batch(self, urls_text: str, session: dict) -> Tuple[str, str, dict]:
        urls = [u.strip() for u in urls_text.split("\n") if u.strip()]
        if not urls:
            return "", "请输入至少一个 URL", session
        lines = ["【批量导入结果】"]
        for i, url in enumerate(urls):
            try:
                doc = URLDocumentImporter().import_from_url(url)
                lines.append(f"\n{i+1}. {url}\n   标题：{doc.title}\n   字数：{doc.word_count}\n   格式：{doc.format.value}")
                if doc.import_notes: lines.append(f"   备注：{doc.import_notes}")
                s = self._get_state(session)
                s.setdefault("url_docs", []).append(doc)
            except Exception as e:
                lines.append(f"\n{i+1}. {url} - 失败：{e}")
        return "\n".join(lines), f"已处理 {len(urls)} 个 URL", session

    def add_url_to_project(self, url: str, proj_name: str, session: dict) -> Tuple[str, dict]:
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        target = next((p for p in projects if p.name == proj_name), None)
        if not target:
            return f"未找到项目「{proj_name}」", session
        try:
            article = self.pdb.add_url_reference(target.id, url, auto_fetch=True)
            return f"已将「{article.title}」添加到项目", session
        except Exception as e:
            return f"添加失败：{e}", session

    def list_projects(self, session: dict) -> Tuple[str, dict]:
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        if not projects:
            return "暂无项目", session
        lines = ["【项目列表】"]
        for p in projects:
            lines.append(f"  • {p.name} [{p.status.value}] - {p.description[:30]}...")
        return "\n".join(lines), session

    def get_memory_summary(self, session: dict) -> Tuple[str, dict]:
        if not self.current_user_id:
            return "请先创建用户", session
        return self.pdb.get_memory_summary(self.current_project_id), session


def create_ui() -> gr.Blocks:
    app = GradioApp()

    with gr.Blocks(title="公文写作 Agent", theme=gr.themes.Soft()) as demo:
        session_state = gr.State({})
        progress_bar = gr.Markdown(build_progress_bar("1. 用户"))

        with gr.Tabs():
            # ═══ Tab 1: 写作 ═══
            with gr.Tab("写作"):

                # 步骤1: 用户
                step_user = gr.Group(visible=True)
                with step_user:
                    gr.Markdown("### 第1步：创建或选择用户")
                    user_name = gr.Textbox(label="用户名", placeholder="输入你的姓名或昵称")
                    with gr.Row():
                        user_btn = gr.Button("确认", variant="primary")
                    user_msg = gr.Markdown("")

                # 步骤2: 项目
                step_proj = gr.Group(visible=False)
                with step_proj:
                    gr.Markdown("### 第2步：创建写作项目")
                    proj_name = gr.Textbox(label="项目名称", placeholder="例如：2026年人才培养总结")
                    proj_desc = gr.Textbox(label="项目描述", lines=2, placeholder="简要描述这个项目...")
                    with gr.Row():
                        proj_back = gr.Button("← 返回")
                        proj_btn = gr.Button("创建并继续", variant="primary")
                    proj_msg = gr.Markdown("")

                # 步骤3: 场景
                step_routing = gr.Group(visible=False)
                with step_routing:
                    gr.Markdown("### 第3步：选择你的场景")
                    routing_display = gr.Markdown("选择最接近你当前情况的场景。")
                    routing_choice = gr.Textbox(label="输入对应数字", placeholder="例如：1")
                    with gr.Row():
                        routing_back = gr.Button("← 返回")
                        routing_btn = gr.Button("确认选择", variant="primary")
                    routing_msg = gr.Markdown("")

                # 步骤4: 问卷
                step_questions = gr.Group(visible=False)
                with step_questions:
                    gr.Markdown("### 第4步：回答专属问题")
                    question_text = gr.Markdown("")
                    teaching_text = gr.Markdown("")
                    answer_input = gr.Textbox(label="你的回答", lines=3, placeholder="输入答案，或使用下方按钮回退/跳过/完成")
                    with gr.Row():
                        q_back = gr.Button("← 回退")
                        q_skip = gr.Button("跳过")
                        q_submit = gr.Button("提交", variant="primary")
                        q_finish = gr.Button("完成问卷", variant="stop")
                    q_msg = gr.Markdown("")
                    q_prev = gr.Markdown("")

                # 步骤5: 方案
                step_plan = gr.Group(visible=False)
                with step_plan:
                    gr.Markdown("### 第5步：写作方案")
                    plan_output = gr.Textbox(label="方案详情", lines=12, interactive=False)
                    with gr.Row():
                        plan_back = gr.Button("← 返回")
                        plan_btn = gr.Button("生成初稿", variant="primary")

                # 步骤6: 初稿
                step_draft = gr.Group(visible=False)
                with step_draft:
                    gr.Markdown("### 第6步：初稿预览")
                    draft_output = gr.Textbox(label="初稿", lines=15, interactive=False)
                    with gr.Row():
                        draft_back = gr.Button("← 返回")
                        draft_btn = gr.Button("执行审查", variant="primary")
                    draft_msg = gr.Markdown("")

                # 步骤7: 审查
                step_review = gr.Group(visible=False)
                with step_review:
                    gr.Markdown("### 第7步：审查结果")
                    review_output = gr.Textbox(label="审查详情", lines=12, interactive=False)
                    with gr.Row():
                        review_back = gr.Button("← 返回")
                        review_btn = gr.Button("重新审查", variant="secondary")
                        review_final = gr.Button("完成并导出", variant="primary")
                    review_msg = gr.Markdown("")

                # 步骤8: 完成
                step_done = gr.Group(visible=False)
                with step_done:
                    gr.Markdown("### 第8步：最终输出")
                    final_output = gr.Textbox(label="最终文章", lines=20, interactive=False)
                    with gr.Row():
                        done_restart = gr.Button("重新开始", variant="secondary")

                # ─── 可见性更新函数 ───
                def update_vis(progress: str, session: dict):
                    vis = app._visibility(session)
                    return {
                        progress_bar: progress,
                        step_user: vis[0],
                        step_proj: vis[1],
                        step_routing: vis[2],
                        step_questions: vis[3],
                        step_plan: vis[4],
                        step_draft: vis[5],
                        step_review: vis[6],
                        step_done: vis[7],
                    }

                # ─── 用户确认 ───
                def user_confirm_fn(name: str, session: dict):
                    progress, msg, new_session = app.create_or_select_user(name, session)
                    return {
                        progress_bar: progress,
                        user_msg: gr.Markdown(msg),
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                user_btn.click(
                    fn=user_confirm_fn,
                    inputs=[user_name, session_state],
                    outputs=[progress_bar, user_msg, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state]
                )

                # ─── 项目创建 ───
                def proj_create_fn(name: str, desc: str, session: dict):
                    progress, _, choices, new_session = app.create_project(name, desc, session)
                    return {
                        progress_bar: progress,
                        routing_display: gr.Markdown(f"选择最接近你当前情况的场景：\n\n{choices}"),
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                proj_btn.click(
                    fn=proj_create_fn,
                    inputs=[proj_name, proj_desc, session_state],
                    outputs=[progress_bar, routing_display, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state]
                )

                def proj_back_fn(session: dict):
                    s = app._get_state(session)
                    s["step"] = "2. 项目"
                    progress = build_progress_bar("2. 项目")
                    return {
                        progress_bar: progress,
                        **update_vis(progress, session),
                        session_state: session,
                    }
                proj_back.click(fn=proj_back_fn, inputs=[session_state],
                    outputs=[progress_bar, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                # ─── 路由选择 ───
                def routing_fn(choice: str, session: dict):
                    progress, msg, q, teach, new_session = app.submit_routing(choice, session)
                    return {
                        progress_bar: progress,
                        routing_msg: gr.Markdown(msg),
                        question_text: gr.Markdown(q),
                        teaching_text: gr.Markdown(teach),
                        q_msg: gr.Markdown(""),
                        q_prev: gr.Markdown(""),
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                routing_btn.click(
                    fn=routing_fn,
                    inputs=[routing_choice, session_state],
                    outputs=[progress_bar, routing_msg, question_text, teaching_text, q_msg, q_prev, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state]
                )

                def routing_back_fn(session: dict):
                    s = app._get_state(session)
                    s["step"] = "3. 场景"
                    progress = build_progress_bar("3. 场景")
                    return {progress_bar: progress, **update_vis(progress, session), session_state: session}
                routing_back.click(fn=routing_back_fn, inputs=[session_state],
                    outputs=[progress_bar, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                # ─── 问卷提交 ───
                def question_fn(answer: str, session: dict):
                    progress, msg, q, teach, plan, prev, new_session = app.submit_answer(answer, session)
                    return {
                        progress_bar: progress,
                        q_msg: gr.Markdown(msg),
                        question_text: gr.Markdown(q),
                        teaching_text: gr.Markdown(teach),
                        plan_output: plan or gr.Textbox(),
                        q_prev: gr.Markdown(prev),
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                q_submit.click(
                    fn=question_fn,
                    inputs=[answer_input, session_state],
                    outputs=[progress_bar, q_msg, question_text, teaching_text, plan_output, q_prev, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state]
                )

                def q_back_fn(answer: str, session: dict):
                    return question_fn("back", session)
                def q_skip_fn(answer: str, session: dict):
                    return question_fn("skip", session)
                def q_finish_fn(answer: str, session: dict):
                    return question_fn("finish", session)

                q_back.click(fn=q_back_fn, inputs=[answer_input, session_state],
                    outputs=[progress_bar, q_msg, question_text, teaching_text, plan_output, q_prev, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])
                q_skip.click(fn=q_skip_fn, inputs=[answer_input, session_state],
                    outputs=[progress_bar, q_msg, question_text, teaching_text, plan_output, q_prev, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])
                q_finish.click(fn=q_finish_fn, inputs=[answer_input, session_state],
                    outputs=[progress_bar, q_msg, question_text, teaching_text, plan_output, q_prev, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                # ─── 方案确认 → 初稿 ───
                def plan_to_draft_fn(session: dict):
                    progress, msg, draft, new_session = app.generate_draft(session)
                    return {
                        progress_bar: progress,
                        draft_output: draft,
                        draft_msg: gr.Markdown(msg),
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                plan_btn.click(fn=plan_to_draft_fn, inputs=[session_state],
                    outputs=[progress_bar, draft_output, draft_msg, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                def plan_back_fn(session: dict):
                    s = app._get_state(session)
                    s["step"] = "5. 方案"
                    progress = build_progress_bar("5. 方案")
                    return {progress_bar: progress, **update_vis(progress, session), session_state: session}
                plan_back.click(fn=plan_back_fn, inputs=[session_state],
                    outputs=[progress_bar, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                # ─── 初稿 → 审查 ───
                def draft_to_review_fn(session: dict):
                    progress, msg, review, new_session = app.run_review(session)
                    return {
                        progress_bar: progress,
                        review_output: review,
                        review_msg: gr.Markdown(msg),
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                draft_btn.click(fn=draft_to_review_fn, inputs=[session_state],
                    outputs=[progress_bar, review_output, review_msg, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                def draft_back_fn(session: dict):
                    s = app._get_state(session)
                    s["step"] = "6. 初稿"
                    progress = build_progress_bar("6. 初稿")
                    return {progress_bar: progress, **update_vis(progress, session), session_state: session}
                draft_back.click(fn=draft_back_fn, inputs=[session_state],
                    outputs=[progress_bar, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                # ─── 审查 → 完成 ───
                def review_to_done_fn(session: dict):
                    progress, final, new_session = app.finalize(session)
                    return {
                        progress_bar: progress,
                        final_output: final,
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                review_final.click(fn=review_to_done_fn, inputs=[session_state],
                    outputs=[progress_bar, final_output, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                def review_back_fn(session: dict):
                    s = app._get_state(session)
                    s["step"] = "7. 审查"
                    progress = build_progress_bar("7. 审查")
                    return {progress_bar: progress, **update_vis(progress, session), session_state: session}
                review_back.click(fn=review_back_fn, inputs=[session_state],
                    outputs=[progress_bar, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                def review_rerun_fn(session: dict):
                    return draft_to_review_fn(session)
                review_btn.click(fn=review_rerun_fn, inputs=[session_state],
                    outputs=[progress_bar, review_output, review_msg, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

                # ─── 重新开始 ───
                def restart_fn(session: dict):
                    progress, new_session = app.restart(session)
                    return {
                        progress_bar: progress,
                        **update_vis(progress, new_session),
                        session_state: new_session,
                    }

                done_restart.click(fn=restart_fn, inputs=[session_state],
                    outputs=[progress_bar, step_user, step_proj, step_routing, step_questions, step_plan, step_draft, step_review, step_done, session_state])

            # ═══ Tab 2: URL导入 ═══
            with gr.Tab("URL导入"):
                gr.Markdown("### 从网页自动抓取参考文档")
                gr.Markdown("输入新闻、公文、报告等网页链接，系统会自动提取正文并分析风格特征。")

                with gr.Row():
                    with gr.Column():
                        url_input = gr.Textbox(label="URL", placeholder="https://example.com/article")
                        url_btn = gr.Button("导入", variant="primary")
                    with gr.Column():
                        url_status = gr.Markdown("")

                url_output = gr.Textbox(label="文档详情", lines=15, interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 批量导入")
                urls_batch = gr.Textbox(label="URL列表（每行一个）", lines=4, placeholder="https://...\nhttps://...")
                urls_btn = gr.Button("批量导入")
                urls_status = gr.Markdown("")
                urls_output = gr.Textbox(label="批量结果", lines=10, interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 添加到项目")
                with gr.Row():
                    proj_for_url = gr.Textbox(label="目标项目名称", scale=2)
                    url_to_proj_btn = gr.Button("添加", variant="primary", scale=1)
                add_status = gr.Markdown("")

                def url_fn(url: str, session: dict):
                    result, status, new_session = app.import_url(url, session)
                    return {url_output: result, url_status: gr.Markdown(status), session_state: new_session}

                url_btn.click(fn=url_fn, inputs=[url_input, session_state],
                    outputs=[url_output, url_status, session_state])

                def urls_fn(text: str, session: dict):
                    result, status, new_session = app.import_urls_batch(text, session)
                    return {urls_output: result, urls_status: gr.Markdown(status), session_state: new_session}

                urls_btn.click(fn=urls_fn, inputs=[urls_batch, session_state],
                    outputs=[urls_output, urls_status, session_state])

                def url_proj_fn(url: str, proj: str, session: dict):
                    status, new_session = app.add_url_to_project(url, proj, session)
                    return {add_status: gr.Markdown(status), session_state: new_session}

                url_to_proj_btn.click(fn=url_proj_fn, inputs=[url_input, proj_for_url, session_state],
                    outputs=[add_status, session_state])

            # ═══ Tab 3: 项目 ═══
            with gr.Tab("项目"):
                gr.Markdown("### 项目管理与记忆摘要")

                with gr.Row():
                    with gr.Column():
                        list_btn = gr.Button("列出所有项目", variant="primary")
                        projects_list = gr.Textbox(label="项目列表", lines=8, interactive=False)
                    with gr.Column():
                        memory_btn = gr.Button("查看记忆摘要", variant="primary")
                        memory_output = gr.Textbox(label="记忆摘要", lines=12, interactive=False)

                def list_fn(session: dict):
                    result, new_session = app.list_projects(session)
                    return {projects_list: result, session_state: new_session}

                list_btn.click(fn=list_fn, inputs=[session_state], outputs=[projects_list, session_state])

                def mem_fn(session: dict):
                    result, new_session = app.get_memory_summary(session)
                    return {memory_output: result, session_state: new_session}

                memory_btn.click(fn=mem_fn, inputs=[session_state], outputs=[memory_output, session_state])

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
    )
