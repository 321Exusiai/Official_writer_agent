"""
Gradio Web 界面 — 公文写作 Agent V8
完整集成所有核心功能：智能体协作、风格选择、文种识别、知识库、HITL审查、一文多体
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import gradio as gr
from typing import List, Dict, Optional, Tuple, Any

from src.core.orchestrator import Orchestrator, OrchestratorState, WritingPlan
from src.core.personalized_db import PersonalizedDB, ProjectStatus
from src.core.writing_mode import WritingMode, get_mode_profile
from src.core.style_adapter import MediaStyle, StyleAdapter, STYLE_PROFILES
from src.core.document_type import DocumentType, DocumentTypeIdentifier, DOC_TYPE_PROFILES
from src.core.agent_coordinator import AgentCoordinator, AgentRole
from src.core.multi_doc_generator import MultiDocGenerator
from src.knowledge.knowledge_base import KnowledgeBase
from src.config.api_config import APIConfigManager, SUPPORTED_PROVIDERS
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

STYLE_CHOICES = [
    ("人民日报风格", MediaStyle.PEOPLE_DAILY),
    ("新华社风格", MediaStyle.XINHUA),
    ("央视新闻风格", MediaStyle.CCTV),
    ("光明日报风格", MediaStyle.GUANGMING),
    ("党政机关行文规范", MediaStyle.GOVERNMENT_ADMIN),
]
STYLE_LABEL_TO_ENUM = {label: enum for label, enum in STYLE_CHOICES}
STYLE_ENUM_TO_LABEL = {enum: label for label, enum in STYLE_CHOICES}

DOC_TYPE_CHOICES = [
    ("通讯 (1500-3000字)", DocumentType.FEATURE),
    ("消息 (500-1000字)", DocumentType.NEWS_BRIEF),
    ("侧记/特写 (800-1500字)", DocumentType.SIDELIGHT),
    ("调研报告 (2000-5000字)", DocumentType.RESEARCH_REPORT),
    ("简报 (300-800字)", DocumentType.BULLETIN),
]
DOC_TYPE_LABEL_TO_ENUM = {label: enum for label, enum in DOC_TYPE_CHOICES}
DOC_TYPE_ENUM_TO_LABEL = {enum: label for label, enum in DOC_TYPE_CHOICES}


def build_progress_bar(current_step: str) -> str:
    parts = []
    idx = STEP_KEYS.index(current_step) if current_step in STEP_KEYS else 0
    for i, (key, desc) in enumerate(STEPS):
        if i == idx:
            parts.append(f"🔵 **{key}** — {desc}")
        elif i < idx:
            parts.append(f"✅ ~~{key}~~")
        else:
            parts.append(f"⚪ {key}")
    return "  →  ".join(parts)


class GradioApp:
    def __init__(self):
        self.orchestrator: Optional[Orchestrator] = None
        self.pdb = PersonalizedDB()
        self.api_manager = APIConfigManager()
        self.knowledge_base = KnowledgeBase()
        self.style_adapter = StyleAdapter()
        self.doc_identifier = DocumentTypeIdentifier()
        self.current_user_id: Optional[str] = None
        self.current_project_id: Optional[str] = None
        self.brief = None
        self._reset_orchestrator()

    def _reset_orchestrator(self):
        self.orchestrator = Orchestrator()
        self.brief = None

    def _get_state(self, session: dict) -> dict:
        return session.setdefault("state", {
            "step": "1. 用户",
            "answers": {},
            "skipped": [],
            "url_docs": [],
            "routing_choices": [],
            "current_q_index": 0,
            "total_q": 0,
            "plan_generated": False,
            "draft_generated": False,
            "review_done": False,
        })

    # ═══════════════════════════════════════════════════════════════
    # Step 1: 用户管理
    # ═══════════════════════════════════════════════════════════════

    def create_or_select_user(self, name: str, session: dict) -> Tuple[str, str, str, dict]:
        name = name.strip()
        if not name:
            return "❌ 请输入用户名", "", build_progress_bar("1. 用户"), session

        for uid, profile in self.pdb.profiles.items():
            if profile.name == name:
                self.current_user_id = uid
                self.pdb.set_current_user(uid)
                s = self._get_state(session)
                s["step"] = "2. 项目"
                projects_count = len(profile.projects)

                # 反 bias 分析
                bias_info = ""
                try:
                    weaknesses = self.pdb.analyze_weaknesses(name)
                    if weaknesses:
                        bias_info = f"\n\n📊 **写作分析**：{weaknesses}"
                except Exception:
                    pass

                return (
                    f"✅ 欢迎回来，{name}！你有 {projects_count} 个项目。{bias_info}",
                    "",
                    build_progress_bar("2. 项目"),
                    session
                )

        profile = self.pdb.create_user(name)
        self.current_user_id = profile.id
        s = self._get_state(session)
        s["step"] = "2. 项目"
        return (
            f"✅ 你好，{name}！已为你创建新账户。准备好开始你的第一篇公文了吗？",
            "",
            build_progress_bar("2. 项目"),
            session
        )

    # ═══════════════════════════════════════════════════════════════
    # Step 2: 项目管理
    # ═══════════════════════════════════════════════════════════════

    def create_project(self, proj_name: str, proj_desc: str, session: dict) -> Tuple[str, str, str, str, dict]:
        if not self.current_user_id:
            return "请先创建用户", "", "", build_progress_bar("1. 用户"), session

        proj_name = proj_name.strip()
        if not proj_name:
            return "请输入项目名称", "", "", build_progress_bar("2. 项目"), session

        project = self.pdb.create_project(proj_name, description=proj_desc)
        self.current_project_id = project.id
        self._reset_orchestrator()

        result = self.orchestrator.start_routing()
        question = result.get("question", "")
        options = result.get("options", [])
        why_ask = result.get("why_ask", "")

        choices_text = f"### {question}\n\n> 💡 *{why_ask}*\n\n"
        for i, opt in enumerate(options):
            choices_text += f"**{i+1}.** {opt.get('label', '')} — *{opt.get('description', '')}*\n"

        s = self._get_state(session)
        s["step"] = "3. 场景"
        s["routing_choices"] = options

        return (
            f"✅ 项目「{proj_name}」已创建",
            choices_text,
            "",
            build_progress_bar("3. 场景"),
            session
        )

    # ═══════════════════════════════════════════════════════════════
    # Step 3: 场景路由
    # ═══════════════════════════════════════════════════════════════

    def submit_routing(self, choice_text: str, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        s = self._get_state(session)

        try:
            choice_index = int(choice_text.strip()) - 1
        except ValueError:
            return "请输入选项数字（如 1、2、3、4）", "", "", "", "", build_progress_bar("3. 场景"), session

        result = self.orchestrator.submit_routing_choice(choice_index)

        if result.get("phase") == "routing_complete":
            mode = result.get("mode", "")
            mode_profile = get_mode_profile(WritingMode(mode))
            s["step"] = "4. 问卷"

            next_q = self.orchestrator.get_current_mode_question()
            if next_q:
                s["current_q_index"] = next_q.get("index", 1)
                s["total_q"] = next_q.get("total", 1)
                progress = f"第 {s['current_q_index']}/{s['total_q']} 题"
                hint = next_q.get("hint", "")
                hint_text = f"💬 *示例回答：{hint}*" if hint else ""
                return (
                    f"✅ 已选择 → **{mode_profile.name}**",
                    progress,
                    f"### {next_q.get('question', '')}",
                    f"💡 *{next_q.get('why_ask', '')}*",
                    hint_text,
                    build_progress_bar("4. 问卷"),
                    session
                )

        return "请重新选择", "", "", "", "", build_progress_bar("3. 场景"), session

    # ═══════════════════════════════════════════════════════════════
    # Step 4: 问卷
    # ═══════════════════════════════════════════════════════════════

    def submit_answer(self, answer: str, session: dict) -> Tuple[str, str, str, str, str, str, str, str, str, str, str, dict]:
        s = self._get_state(session)
        answer = answer.strip()

        # 处理指令
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
                hint = next_q.get("hint", "")
                return (
                    f"⏭️ 已跳过（第 {s['current_q_index']}/{s['total_q']} 题）",
                    f"第 {s['current_q_index']}/{s['total_q']} 题",
                    f"### {next_q.get('question', '')}",
                    f"💡 *{next_q.get('why_ask', '')}*",
                    f"💬 *示例：{hint}*" if hint else "",
                    "", "", "", "", "", "",
                    session
                )

        if answer.lower() == "back":
            prev = self.orchestrator.questionnaire.go_back()
            if prev:
                s["current_q_index"] = prev.get("index", 1)
                prev_answer = prev.get("previous_answer", "")
                hint = prev.get("hint", "")
                return (
                    f"⬅️ 已回退到第 {prev['index']} 题",
                    f"第 {s['current_q_index']}/{s['total_q']} 题",
                    f"### {prev.get('question', '')}",
                    f"💡 *{prev.get('why_ask', '')}*",
                    f"💬 *示例：{hint}*" if hint else "",
                    f"📝 上一题你的回答：{prev_answer[:100]}..." if prev_answer else "",
                    "", "", "", "", "",
                    session
                )

        if answer.lower() == "finish":
            return self._finish_questions(session)

        # 正常提交答案
        has_next, next_q = self.orchestrator.submit_mode_answer(answer)

        if not has_next:
            return self._finish_questions(session)

        if next_q:
            s["current_q_index"] = next_q.get("index", 1)
            s["total_q"] = next_q.get("total", 1)
            hint = next_q.get("hint", "")
            return (
                "✅ 答案已保存",
                f"第 {s['current_q_index']}/{s['total_q']} 题",
                f"### {next_q.get('question', '')}",
                f"💡 *{next_q.get('why_ask', '')}*",
                f"💬 *示例：{hint}*" if hint else "",
                "", "", "", "", "", "",
                session
            )

        return "", "", "", "", "", "", "", "", "", "", "", session

    def _finish_questions(self, session: dict) -> Tuple[str, str, str, str, str, str, str, str, str, str, str, dict]:
        self.brief = self.orchestrator.questionnaire.finish()
        s = self._get_state(session)
        s["step"] = "5. 方案"

        # 自动生成方案
        try:
            plan = self.orchestrator.generate_plan()
            s["plan_generated"] = True

            # 自动推荐风格和文种
            auto_style_label = STYLE_ENUM_TO_LABEL.get(plan.media_style, "人民日报风格")
            auto_doc_label = DOC_TYPE_ENUM_TO_LABEL.get(plan.document_type, "通讯 (1500-3000字)")

            # 知识库范文推荐
            kb_exemplars = ""
            try:
                exemplars = self.knowledge_base.get_exemplars_for_prompt(
                    self.orchestrator.writing_mode.value, max_exemplars=2
                )
                if exemplars:
                    kb_exemplars = f"### 📚 知识库推荐范文\n\n{exemplars[:800]}..."
            except Exception:
                pass

            # 风格混合建议
            blend_info = ""
            try:
                if self.brief and self.brief.secondary_audiences:
                    blend = self.style_adapter.suggest_blend(
                        primary_audience=self.brief.primary_audience,
                        purpose=self.brief.purpose,
                        secondary_audiences=self.brief.secondary_audiences,
                    )
                    if blend and blend.ratio:
                        blend_info = f"\n\n### 🎨 风格混合建议\n\n{blend.display() if hasattr(blend, 'display') else str(blend.ratio)}"
            except Exception:
                pass

            return (
                "✅ 问卷完成！方案已自动生成，你可以调整风格和文种后确认。",
                "",  # q_msg
                "",  # q_progress
                "",  # question_text
                "",  # teaching_text
                "",  # hint_text
                plan.display(),  # plan_output
                auto_style_label,  # style_selector
                auto_doc_label,  # doc_type_selector
                f"{kb_exemplars}{blend_info}",  # kb_display
                build_progress_bar("5. 方案"),  # progress_bar
                session  # session_state
            )
        except Exception as e:
            return (
                f"❌ 生成方案失败: {e}",
                "", "", "", "", "",
                "", "", "", "",
                build_progress_bar("4. 问卷"),
                session
            )

    # ═══════════════════════════════════════════════════════════════
    # Step 5: 方案确认（支持手动调整风格和文种）
    # ═══════════════════════════════════════════════════════════════

    def regenerate_plan(self, style_label: str, doc_type_label: str, session: dict) -> Tuple[str, str, str, str, str, dict]:
        s = self._get_state(session)
        if not self.brief:
            return "请先完成问卷", style_label, doc_type_label, "", build_progress_bar("4. 问卷"), session

        try:
            preferred_style = STYLE_LABEL_TO_ENUM.get(style_label)
            preferred_doc = DOC_TYPE_LABEL_TO_ENUM.get(doc_type_label)

            plan = self.orchestrator.generate_plan(
                preferred_style=preferred_style,
                preferred_doc_type=preferred_doc,
            )
            s["plan_generated"] = True

            # 知识库范文
            kb_exemplars = ""
            try:
                exemplars = self.knowledge_base.get_exemplars_for_prompt(
                    self.orchestrator.writing_mode.value, max_exemplars=2
                )
                if exemplars:
                    kb_exemplars = f"### 📚 知识库推荐范文\n\n{exemplars[:800]}..."
            except Exception:
                pass

            return (
                plan.display(),
                style_label,
                doc_type_label,
                kb_exemplars,
                build_progress_bar("5. 方案"),
                session
            )
        except Exception as e:
            return f"❌ 更新方案失败: {e}", style_label, doc_type_label, "", build_progress_bar("5. 方案"), session

    # ═══════════════════════════════════════════════════════════════
    # Step 6: 初稿生成
    # ═══════════════════════════════════════════════════════════════

    def generate_draft(self, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        s = self._get_state(session)
        if not self.brief:
            return "请先完成问卷", "", "", "", "", build_progress_bar("4. 问卷"), session

        try:
            draft = self.orchestrator.write()
            agent_log = self.orchestrator.get_agent_log_display()
            multi_ver = self.orchestrator.get_multi_versions_display()

            # 获取系统提示词预览
            prompt_preview = ""
            try:
                prompts = self.orchestrator.get_llm_prompts()
                sys_p = prompts.get("system", "")
                if sys_p:
                    prompt_preview = f"### 🔧 系统提示词预览\n\n```\n{sys_p[:600]}...\n```"
            except Exception:
                pass

            s["step"] = "6. 初稿"
            s["draft_generated"] = True

            return (
                "✅ 初稿已生成",
                draft or "（生成失败，请检查 API 配置）",
                agent_log,
                multi_ver,
                prompt_preview,
                build_progress_bar("6. 初稿"),
                session
            )
        except Exception as e:
            return f"❌ 生成失败: {e}", "", "", "", "", build_progress_bar("6. 初稿"), session

    # ═══════════════════════════════════════════════════════════════
    # Step 7: 审查（含 HITL 交互）
    # ═══════════════════════════════════════════════════════════════

    def run_review(self, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        if not self.orchestrator.draft:
            return "请先生成初稿", "", "", "", "", build_progress_bar("6. 初稿"), session

        try:
            self.orchestrator.review()
            s = self._get_state(session)
            s["step"] = "7. 审查"
            s["review_done"] = True

            review_text = self.orchestrator.review_summary_display or "（审查完成，未发现问题）"

            # 审查问题列表（供 HITL）
            issues_display = ""
            try:
                issues = self.orchestrator.get_review_issues()
                if issues:
                    lines = ["### 🔍 发现的问题\n"]
                    for i, issue in enumerate(issues):
                        severity = issue.get("severity", "未知")
                        desc = issue.get("description", str(issue))
                        lines.append(f"**{i+1}.** [{severity}] {desc[:200]}")
                    issues_display = "\n".join(lines)
            except Exception:
                pass

            # 格式合规检查
            format_check = ""
            try:
                if self.orchestrator.draft:
                    fmt_issues = self.orchestrator.reviewer.check_format_compliance(self.orchestrator.draft)
                    if fmt_issues:
                        lines = ["### 📋 格式合规检查\n"]
                        for fi in fmt_issues:
                            lines.append(f"- ⚠️ {fi.get('description', str(fi))[:150]}")
                        format_check = "\n".join(lines)
            except Exception:
                pass

            # 知识库诊断
            kb_diagnosis = ""
            try:
                if self.orchestrator.draft:
                    findings = self.knowledge_base.diagnose_text(self.orchestrator.draft)
                    if findings:
                        lines = ["### 📖 知识库诊断\n"]
                        for f in findings[:5]:
                            lines.append(f"- {f.get('description', str(f))[:150]}")
                        kb_diagnosis = "\n".join(lines)
            except Exception:
                pass

            multi_ver = self.orchestrator.get_multi_versions_display()

            return (
                "✅ 审查完成",
                review_text,
                issues_display,
                format_check,
                kb_diagnosis,
                multi_ver,
                build_progress_bar("7. 审查"),
                session
            )
        except Exception as e:
            return f"❌ 审查失败: {e}", "", "", "", "", "", build_progress_bar("7. 审查"), session

    def apply_fix(self, round_idx: int, finding_idx: int, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        """HITL: 手动触发对某个问题的自动修复"""
        try:
            fixed = self.orchestrator.apply_manual_fix(round_idx, finding_idx)
            s = self._get_state(session)
            return (
                f"✅ 已修复第 {round_idx+1} 轮第 {finding_idx+1} 个问题",
                fixed,
                "", "", "", "",
                build_progress_bar("7. 审查"),
                session
            )
        except Exception as e:
            return f"❌ 修复失败: {e}", "", "", "", "", "", build_progress_bar("7. 审查"), session

    def update_draft_manual(self, new_draft: str, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        """HITL: 用户手动编辑草稿"""
        try:
            self.orchestrator.update_draft(new_draft)
            return (
                "✅ 草稿已手动更新，可重新审查",
                new_draft, "", "", "", "",
                build_progress_bar("7. 审查"),
                session
            )
        except Exception as e:
            return f"❌ 更新失败: {e}", "", "", "", "", "", build_progress_bar("7. 审查"), session

    def re_review(self, session: dict) -> Tuple[str, str, str, str, str, str, str, dict]:
        """HITL: 重新审查"""
        try:
            self.orchestrator.re_review()
            s = self._get_state(session)
            review_text = self.orchestrator.review_summary_display or "（重新审查完成）"
            multi_ver = self.orchestrator.get_multi_versions_display()
            return (
                "✅ 重新审查完成",
                review_text, "", "", "",
                multi_ver,
                build_progress_bar("7. 审查"),
                session
            )
        except Exception as e:
            return f"❌ 重新审查失败: {e}", "", "", "", "", "", build_progress_bar("7. 审查"), session

    # ═══════════════════════════════════════════════════════════════
    # Step 8: 完成
    # ═══════════════════════════════════════════════════════════════

    def finalize(self, session: dict) -> Tuple[str, str, str, str, str, dict]:
        try:
            output = self.orchestrator.finalize()
            s = self._get_state(session)
            s["step"] = "8. 完成"

            lines = ["═══════════════════════════════════════"]
            lines.append("  📄 最终输出")
            lines.append("═══════════════════════════════════════\n")
            if output.get("draft"):
                lines.append(output["draft"])
            else:
                lines.append("（无草稿）")

            lines.append("\n═══════════════════════════════════════")
            lines.append(f"  审查轮次：{output.get('review_count', 0)}")
            lines.append(f"  审查通过：{'✅ 是' if output.get('review_passed', False) else '⚠️ 否'}")
            lines.append(f"  写作模式：{output.get('plan', {}).get('mode_name', '')}")
            lines.append("═══════════════════════════════════════")

            if self.current_project_id:
                self.pdb.update_project_status(self.current_project_id, ProjectStatus.COMPLETED)

            multi_ver = self.orchestrator.get_multi_versions_display()
            agent_log = self.orchestrator.get_agent_log_display()

            # 工作流摘要
            workflow_summary = ""
            try:
                workflow_summary = self.orchestrator.get_workflow_summary()
            except Exception:
                pass

            return (
                "\n".join(lines),
                multi_ver,
                agent_log,
                workflow_summary,
                build_progress_bar("8. 完成"),
                session
            )
        except Exception as e:
            return f"❌ 完成失败: {e}", "", "", "", build_progress_bar("8. 完成"), session

    def restart(self, session: dict) -> Tuple[str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, str, dict]:
        s = self._get_state(session)
        s["step"] = "1. 用户"
        s["answers"] = {}
        s["skipped"] = []
        s["plan_generated"] = False
        s["draft_generated"] = False
        s["review_done"] = False
        self._reset_orchestrator()
        return (
            build_progress_bar("1. 用户"),
            "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "", "",
            "", "", "", "", "", "", "", "", "",
            session
        )

    # ═══════════════════════════════════════════════════════════════
    # URL 导入
    # ═══════════════════════════════════════════════════════════════

    def import_url(self, url: str, session: dict) -> Tuple[str, str, dict]:
        url = url.strip()
        if not url:
            return "", "请输入 URL", session
        try:
            importer = URLDocumentImporter()
            doc = importer.import_from_url(url)
            lines = ["### 📥 文档导入结果", ""]
            lines.append(f"**标题**：{doc.title}")
            lines.append(f"**来源**：{doc.source_site}")
            lines.append(f"**字数**：{doc.word_count}  |  **格式**：{doc.format.value}")
            if doc.author:
                lines.append(f"**作者**：{doc.author}")
            if doc.publish_date:
                lines.append(f"**发布时间**：{doc.publish_date}")
            if doc.keywords:
                lines.append(f"\n**关键词**：{', '.join(doc.keywords[:10])}")
            if doc.style_patterns:
                lines.append("\n**风格特征**：")
                for p in doc.style_patterns:
                    lines.append(f"  - {p}")
            if doc.content:
                lines.append(f"\n**正文预览**（前500字）：\n\n{doc.content[:500]}{'...' if len(doc.content) > 500 else ''}")
            if doc.import_notes:
                lines.append(f"\n**备注**：{doc.import_notes}")
            s = self._get_state(session)
            s.setdefault("url_docs", []).append(doc)
            return "\n".join(lines), "✅ 导入成功", session
        except Exception as e:
            return f"❌ 导入失败：{e}", "❌ 导入失败", session

    def import_urls_batch(self, urls_text: str, session: dict) -> Tuple[str, str, dict]:
        urls = [u.strip() for u in urls_text.split("\n") if u.strip()]
        if not urls:
            return "", "请输入至少一个 URL", session
        lines = ["### 📥 批量导入结果", ""]
        success = 0
        for i, url in enumerate(urls):
            try:
                doc = URLDocumentImporter().import_from_url(url)
                lines.append(f"**{i+1}.** ✅ {url}")
                lines.append(f"   > {doc.title}（{doc.word_count}字，{doc.format.value}）")
                if doc.import_notes:
                    lines.append(f"   > 备注：{doc.import_notes}")
                s = self._get_state(session)
                s.setdefault("url_docs", []).append(doc)
                success += 1
            except Exception as e:
                lines.append(f"**{i+1}.** ❌ {url} — {e}")
        return "\n".join(lines), f"✅ 成功 {success}/{len(urls)}", session

    def add_url_to_project(self, url: str, proj_name: str, session: dict) -> Tuple[str, dict]:
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        target = next((p for p in projects if p.name == proj_name), None)
        if not target:
            return f"未找到项目「{proj_name}」", session
        try:
            article = self.pdb.add_url_reference(target.id, url, auto_fetch=True)
            return f"✅ 已将「{article.title}」添加到项目「{proj_name}」", session
        except Exception as e:
            return f"❌ 添加失败：{e}", session

    def list_projects(self, session: dict) -> Tuple[str, dict]:
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        if not projects:
            return "暂无项目", session
        lines = ["### 📁 项目列表", ""]
        for p in projects:
            lines.append(f"- **{p.name}** [{p.status.value}] — {p.description[:50]}...")
        return "\n".join(lines), session

    def get_memory_summary(self, session: dict) -> Tuple[str, dict]:
        if not self.current_user_id:
            return "请先创建用户", session
        return self.pdb.get_memory_summary(self.current_project_id), session

    # ═══════════════════════════════════════════════════════════════
    # API 配置
    # ═══════════════════════════════════════════════════════════════

    def load_api_config(self) -> Tuple[str, str, str, str, float, int, bool]:
        c = self.api_manager.config
        return c.provider, c.api_base, c.api_key, c.model, c.temperature, c.max_tokens, c.enable

    def apply_provider(self, provider: str) -> Tuple[str, str, str, str, float, int, bool, str]:
        self.api_manager.apply_provider_template(provider)
        c = self.api_manager.config
        return c.provider, c.api_base, c.api_key, c.model, c.temperature, c.max_tokens, c.enable, f"✅ 已加载 {SUPPORTED_PROVIDERS.get(provider, provider)} 默认配置"

    def save_api_config(self, provider: str, api_base: str, api_key: str, model: str, temperature: float, max_tokens: int, enable: bool) -> Tuple[str, str]:
        self.api_manager.update(
            provider=provider, api_base=api_base, api_key=api_key,
            model=model, temperature=temperature, max_tokens=max_tokens, enable=enable
        )
        self.api_manager.save()
        status = "✅ 配置已保存" if enable else "⚠️ 配置已保存但未启用"
        return status, ""

    def test_api_connection(self) -> str:
        result = self.api_manager.test_connection()
        if result["success"]:
            return f"✅ {result['message']}"
        return f"❌ {result['message']}"

    def get_config_status(self) -> str:
        c = self.api_manager.config
        if c.enable and c.api_key and c.api_base:
            return f"✅ 已启用 | {SUPPORTED_PROVIDERS.get(c.provider, c.provider)} | {c.model} | {c.api_base}"
        elif c.api_base:
            return f"⚠️ 已配置但未启用 | {SUPPORTED_PROVIDERS.get(c.provider, c.provider)} | {c.model}"
        return "❌ 未配置 LLM API，当前使用本地占位文本生成"


# ═══════════════════════════════════════════════════════════════
# UI 构建
# ═══════════════════════════════════════════════════════════════

def create_ui() -> gr.Blocks:
    app = GradioApp()

    with gr.Blocks(title="公文写作 Agent V8", theme=gr.themes.Soft()) as demo:
        session_state = gr.State({})

        with gr.Tabs():
            # ═══════════════════════════════════════════════════════
            # Tab 1: 写作
            # ═══════════════════════════════════════════════════════
            with gr.Tab("✍️ 写作"):
                progress_bar = gr.Markdown(build_progress_bar("1. 用户"))

                gr.Markdown("---")

                # ─── Step 1: 用户 ───
                gr.Markdown("### 📌 第1步：创建或选择用户")
                with gr.Row():
                    user_name = gr.Textbox(label="用户名", placeholder="输入你的姓名或昵称", scale=3)
                    user_btn = gr.Button("确认", variant="primary", scale=1)
                user_msg = gr.Markdown()

                gr.Markdown("---")

                # ─── Step 2: 项目 ───
                gr.Markdown("### 📌 第2步：创建写作项目")
                with gr.Row():
                    proj_name = gr.Textbox(label="项目名称", placeholder="例如：2026年人才培养总结", scale=2)
                    proj_desc = gr.Textbox(label="项目描述（可选）", placeholder="简要描述项目背景...", scale=3)
                    proj_btn = gr.Button("创建并继续", variant="primary", scale=1)
                proj_msg = gr.Markdown()

                gr.Markdown("---")

                # ─── Step 3: 场景 ───
                gr.Markdown("### 📌 第3步：选择你的场景")
                routing_display = gr.Markdown("选择最接近你当前情况的场景。")
                with gr.Row():
                    routing_choice = gr.Textbox(label="输入对应数字", placeholder="例如：1", scale=3)
                    routing_btn = gr.Button("确认选择", variant="primary", scale=1)
                routing_msg = gr.Markdown()

                gr.Markdown("---")

                # ─── Step 4: 问卷 ───
                gr.Markdown("### 📌 第4步：回答专属问题")
                q_progress = gr.Markdown()
                question_text = gr.Markdown()
                teaching_text = gr.Markdown()
                hint_text = gr.Markdown()
                answer_input = gr.Textbox(label="你的回答", lines=3, placeholder="输入答案，或使用下方指令：skip（跳过）| back（回退）| finish（完成）")
                with gr.Row():
                    q_back = gr.Button("⬅️ 回退", size="sm")
                    q_skip = gr.Button("⏭️ 跳过", size="sm")
                    q_submit = gr.Button("✅ 提交", variant="primary")
                    q_finish = gr.Button("🏁 完成问卷", variant="stop")
                q_msg = gr.Markdown()
                q_prev = gr.Markdown()

                gr.Markdown("---")

                # ─── Step 5: 方案 ───
                gr.Markdown("### 📌 第5步：写作方案")
                with gr.Row():
                    style_selector = gr.Dropdown(
                        choices=[label for label, _ in STYLE_CHOICES],
                        value="人民日报风格",
                        label="🎨 写作风格",
                        scale=1,
                    )
                    doc_type_selector = gr.Dropdown(
                        choices=[label for label, _ in DOC_TYPE_CHOICES],
                        value="通讯 (1500-3000字)",
                        label="📄 文种",
                        scale=1,
                    )
                    plan_regenerate_btn = gr.Button("🔄 更新方案", variant="secondary", scale=1)
                plan_output = gr.Textbox(label="方案详情", lines=12, interactive=False)
                kb_display = gr.Markdown()
                with gr.Row():
                    plan_btn = gr.Button("🚀 生成初稿", variant="primary")

                gr.Markdown("---")

                # ─── Step 6: 初稿 ───
                gr.Markdown("### 📌 第6步：初稿预览 & 多智能体协作")
                with gr.Accordion("🤖 多智能体协作日志", open=True):
                    agent_log = gr.Textbox(label="协作日志", lines=8, interactive=False)
                with gr.Accordion("🔧 系统提示词预览", open=False):
                    prompt_preview = gr.Textbox(label="提示词", lines=6, interactive=False)
                draft_output = gr.Textbox(label="初稿（主版本）", lines=15, interactive=False)
                with gr.Accordion("📄 一文多体预览", open=False):
                    multi_preview_step6 = gr.Textbox(label="多版本", lines=10, interactive=False)
                with gr.Row():
                    draft_btn = gr.Button("🔍 执行审查", variant="primary")
                draft_msg = gr.Markdown()

                gr.Markdown("---")

                # ─── Step 7: 审查 ───
                gr.Markdown("### 📌 第7步：审查结果 & HITL 交互")
                review_output = gr.Textbox(label="审查详情", lines=12, interactive=False)

                with gr.Accordion("🔍 发现的问题", open=True):
                    review_issues = gr.Textbox(label="问题列表", lines=6, interactive=False)
                with gr.Accordion("📋 格式合规检查", open=False):
                    format_check_output = gr.Textbox(label="格式检查", lines=4, interactive=False)
                with gr.Accordion("📖 知识库诊断", open=False):
                    kb_diagnosis_output = gr.Textbox(label="知识库诊断", lines=4, interactive=False)

                gr.Markdown("#### 🛠️ HITL 人工介入")
                with gr.Row():
                    fix_round = gr.Number(label="审查轮次", value=0, precision=0, scale=1)
                    fix_index = gr.Number(label="问题序号", value=0, precision=0, scale=1)
                    fix_btn = gr.Button("🔧 自动修复此问题", variant="secondary", scale=1)
                with gr.Row():
                    manual_edit = gr.Textbox(label="手动编辑草稿", lines=5, placeholder="直接修改草稿内容...", scale=3)
                    manual_update_btn = gr.Button("💾 更新草稿", variant="secondary", scale=1)
                with gr.Row():
                    re_review_btn = gr.Button("🔄 重新审查", variant="secondary")
                    review_final = gr.Button("✅ 完成并导出", variant="primary")
                review_msg = gr.Markdown()

                gr.Markdown("---")

                # ─── Step 8: 完成 ───
                gr.Markdown("### 📌 第8步：最终输出")
                final_output = gr.Textbox(label="最终文章", lines=20, interactive=False)
                with gr.Accordion("📄 多版本文稿对比", open=True):
                    final_multi = gr.Textbox(label="一文多体", lines=12, interactive=False)
                with gr.Accordion("🤖 完整协作日志", open=False):
                    final_agent = gr.Textbox(label="协作日志", lines=8, interactive=False)
                with gr.Accordion("📊 工作流摘要", open=False):
                    workflow_summary = gr.Textbox(label="摘要", lines=6, interactive=False)
                with gr.Row():
                    done_restart = gr.Button("🔄 重新开始", variant="secondary")

                # ═══════════════════════════════════════════════════
                # 事件绑定
                # ═══════════════════════════════════════════════════

                # Step 1: 用户
                user_btn.click(
                    fn=lambda name, sess: app.create_or_select_user(name.strip(), sess),
                    inputs=[user_name, session_state],
                    outputs=[user_msg, proj_msg, progress_bar, session_state]
                )

                # Step 2: 项目
                proj_btn.click(
                    fn=lambda name, desc, sess: app.create_project(name, desc, sess),
                    inputs=[proj_name, proj_desc, session_state],
                    outputs=[proj_msg, routing_display, routing_msg, progress_bar, session_state]
                )

                # Step 3: 路由
                routing_btn.click(
                    fn=lambda choice, sess: app.submit_routing(choice, sess),
                    inputs=[routing_choice, session_state],
                    outputs=[routing_msg, q_progress, question_text, teaching_text, hint_text, progress_bar, session_state]
                )

                # Step 4: 问卷
                def question_fn(answer: str, session: dict):
                    msg, progress, q, teach, hint, prev, plan, style, doc, kb, bar, new_sess = app.submit_answer(answer, session)
                    return msg, progress, q, teach, hint, prev, plan, style, doc, kb, bar, new_sess, ""

                q_submit.click(
                    fn=question_fn,
                    inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input]
                )
                q_back.click(
                    fn=question_fn,
                    inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input]
                )
                q_skip.click(
                    fn=question_fn,
                    inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input]
                )
                q_finish.click(
                    fn=question_fn,
                    inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input]
                )

                # Step 5: 方案更新
                plan_regenerate_btn.click(
                    fn=lambda style, doc, sess: app.regenerate_plan(style, doc, sess),
                    inputs=[style_selector, doc_type_selector, session_state],
                    outputs=[plan_output, style_selector, doc_type_selector, kb_display, progress_bar, session_state]
                )

                # Step 5 → 6: 生成初稿
                plan_btn.click(
                    fn=lambda sess: app.generate_draft(sess),
                    inputs=[session_state],
                    outputs=[draft_msg, draft_output, agent_log, multi_preview_step6, prompt_preview, progress_bar, session_state]
                )

                # Step 6 → 7: 审查
                draft_btn.click(
                    fn=lambda sess: app.run_review(sess),
                    inputs=[session_state],
                    outputs=[review_msg, review_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                # Step 7 HITL: 修复
                fix_btn.click(
                    fn=lambda r, i, sess: app.apply_fix(int(r), int(i), sess),
                    inputs=[fix_round, fix_index, session_state],
                    outputs=[review_msg, draft_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                # Step 7 HITL: 手动编辑
                manual_update_btn.click(
                    fn=lambda d, sess: app.update_draft_manual(d, sess),
                    inputs=[manual_edit, session_state],
                    outputs=[review_msg, draft_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                # Step 7 HITL: 重新审查
                re_review_btn.click(
                    fn=lambda sess: app.re_review(sess),
                    inputs=[session_state],
                    outputs=[review_msg, review_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                # Step 7 → 8: 完成
                review_final.click(
                    fn=lambda sess: app.finalize(sess),
                    inputs=[session_state],
                    outputs=[final_output, final_multi, final_agent, workflow_summary, progress_bar, session_state]
                )

                # 重新开始
                done_restart.click(
                    fn=lambda sess: app.restart(sess),
                    inputs=[session_state],
                    outputs=[
                        progress_bar,
                        user_msg, proj_msg, routing_display, routing_msg,
                        q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                        plan_output, style_selector, doc_type_selector, kb_display,
                        draft_msg, draft_output, agent_log, multi_preview_step6, prompt_preview,
                        review_msg, review_output, review_issues, format_check_output, kb_diagnosis_output,
                        final_output, final_multi, final_agent, workflow_summary,
                        session_state
                    ]
                )

            # ═══════════════════════════════════════════════════════
            # Tab 2: URL导入
            # ═══════════════════════════════════════════════════════
            with gr.Tab("🌐 URL导入"):
                gr.Markdown("### 从网页自动抓取参考文档")
                gr.Markdown("输入新闻、公文、报告等网页链接，系统会自动提取正文并分析风格特征。")

                with gr.Row():
                    with gr.Column(scale=3):
                        url_input = gr.Textbox(label="URL", placeholder="https://example.com/article")
                    with gr.Column(scale=1):
                        url_btn = gr.Button("导入", variant="primary")
                url_status = gr.Markdown()
                url_output = gr.Textbox(label="文档详情", lines=15, interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 批量导入")
                urls_batch = gr.Textbox(label="URL列表（每行一个）", lines=4, placeholder="https://...\nhttps://...")
                urls_btn = gr.Button("批量导入")
                urls_status = gr.Markdown()
                urls_output = gr.Textbox(label="批量结果", lines=10, interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 添加到项目")
                with gr.Row():
                    proj_for_url = gr.Textbox(label="目标项目名称", scale=2)
                    url_to_proj_btn = gr.Button("添加", variant="primary", scale=1)
                add_status = gr.Markdown()

                url_btn.click(
                    fn=lambda u, s: app.import_url(u, s),
                    inputs=[url_input, session_state],
                    outputs=[url_output, url_status, session_state]
                )
                urls_btn.click(
                    fn=lambda t, s: app.import_urls_batch(t, s),
                    inputs=[urls_batch, session_state],
                    outputs=[urls_output, urls_status, session_state]
                )
                url_to_proj_btn.click(
                    fn=lambda u, p, s: app.add_url_to_project(u, p, s),
                    inputs=[url_input, proj_for_url, session_state],
                    outputs=[add_status, session_state]
                )

            # ═══════════════════════════════════════════════════════
            # Tab 3: API 配置
            # ═══════════════════════════════════════════════════════
            with gr.Tab("⚙️ API配置"):
                gr.Markdown("### LLM API 配置")
                gr.Markdown("配置大语言模型 API，启用后系统将使用真实 AI 生成公文。")

                api_status_bar = gr.Markdown(app.get_config_status())

                gr.Markdown("---")
                gr.Markdown("### 快速选择提供商")

                provider_select = gr.Dropdown(
                    choices=list(SUPPORTED_PROVIDERS.items()),
                    value=app.api_manager.config.provider,
                    label="选择提供商",
                )
                with gr.Row():
                    provider_btn = gr.Button("加载默认配置", variant="secondary")
                    provider_msg = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### 详细配置")

                api_base = gr.Textbox(label="API Base URL", placeholder="https://api.openai.com/v1")
                api_key = gr.Textbox(label="API Key", placeholder="sk-...", type="password")
                model = gr.Textbox(label="模型名称", placeholder="gpt-4o")

                with gr.Row():
                    temperature = gr.Slider(0, 2, value=0.7, step=0.1, label="Temperature (创造性)")
                    max_tokens = gr.Slider(1000, 32000, value=8000, step=1000, label="Max Tokens (最大输出)")

                enable_api = gr.Checkbox(label="启用此 API（生成时使用）", value=False)

                with gr.Row():
                    api_save_btn = gr.Button("保存配置", variant="primary")
                    api_test_btn = gr.Button("测试连接", variant="secondary")

                api_save_msg = gr.Markdown()
                api_test_msg = gr.Markdown()

                demo.load(
                    fn=app.load_api_config,
                    outputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api]
                )
                provider_btn.click(
                    fn=app.apply_provider,
                    inputs=[provider_select],
                    outputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api, provider_msg]
                )
                api_save_btn.click(
                    fn=app.save_api_config,
                    inputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api],
                    outputs=[api_save_msg, api_status_bar]
                )
                api_test_btn.click(
                    fn=app.test_api_connection,
                    outputs=[api_test_msg]
                )

            # ═══════════════════════════════════════════════════════
            # Tab 4: 项目
            # ═══════════════════════════════════════════════════════
            with gr.Tab("📁 项目"):
                gr.Markdown("### 项目管理与记忆摘要")

                with gr.Row():
                    with gr.Column():
                        list_btn = gr.Button("列出所有项目", variant="primary")
                        projects_list = gr.Textbox(label="项目列表", lines=8, interactive=False)
                    with gr.Column():
                        memory_btn = gr.Button("查看记忆摘要", variant="primary")
                        memory_output = gr.Textbox(label="记忆摘要", lines=12, interactive=False)

                list_btn.click(
                    fn=lambda s: app.list_projects(s),
                    inputs=[session_state],
                    outputs=[projects_list, session_state]
                )
                memory_btn.click(
                    fn=lambda s: app.get_memory_summary(s),
                    inputs=[session_state],
                    outputs=[memory_output, session_state]
                )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        share=False,
        show_error=True,
    )
