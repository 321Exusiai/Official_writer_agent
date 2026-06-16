"""
Gradio Web 界面 — 公文写作 Agent V9
完整集成所有核心功能：智能体协作、风格选择、文种识别、知识库、HITL审查、一文多体
V9改进：多API管理、文件夹式项目/URL管理、自定义场景、扩展风格、字数区间
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

# ── 扩展风格选项 ──
STYLE_CHOICES = [
    ("人民日报风格", MediaStyle.PEOPLE_DAILY),
    ("新华社风格", MediaStyle.XINHUA),
    ("央视新闻风格", MediaStyle.CCTV),
    ("光明日报风格", MediaStyle.GUANGMING),
    ("党政机关行文规范", MediaStyle.GOVERNMENT_ADMIN),
    ("求是杂志风格", MediaStyle.PEOPLE_DAILY),
    ("经济日报风格", MediaStyle.XINHUA),
    ("中国青年报风格", MediaStyle.GUANGMING),
    ("科技日报风格", MediaStyle.XINHUA),
    ("地方党报风格", MediaStyle.PEOPLE_DAILY),
    ("自媒体/公众号风格", MediaStyle.CCTV),
    ("学术报告风格", MediaStyle.GOVERNMENT_ADMIN),
]
STYLE_LABEL_TO_ENUM = {label: enum for label, enum in STYLE_CHOICES}
STYLE_ENUM_TO_LABEL = {enum: label for label, enum in STYLE_CHOICES}

# ── 文种选项（推荐区间替代固定限制）──
DOC_TYPE_CHOICES = [
    ("通讯（推荐1500-3000字）", DocumentType.FEATURE),
    ("消息（推荐500-1000字）", DocumentType.NEWS_BRIEF),
    ("侧记/特写（推荐800-1500字）", DocumentType.SIDELIGHT),
    ("调研报告（推荐2000-5000字）", DocumentType.RESEARCH_REPORT),
    ("简报（推荐300-800字）", DocumentType.BULLETIN),
    ("请示（推荐800-2000字）", DocumentType.REQUEST),
    ("通知（推荐500-1500字）", DocumentType.NOTIFICATION),
    ("批复（推荐300-800字）", DocumentType.REPLY),
    ("函（推荐300-1000字）", DocumentType.LETTER),
    ("会议纪要（推荐1000-3000字）", DocumentType.MEETING_MINUTES),
    ("公告（推荐300-800字）", DocumentType.ANNOUNCEMENT),
    ("决定（推荐500-1500字）", DocumentType.DECISION),
    ("报告（推荐1000-3000字）", DocumentType.REPORT),
    ("通报（推荐500-1500字）", DocumentType.CIRCULAR),
    ("意见（推荐1000-3000字）", DocumentType.OPINION),
    ("议案（推荐800-2000字）", DocumentType.MOTION),
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
        # URL 主题管理
        self.url_topics: Dict[str, List] = {}  # topic_name -> [doc, doc, ...]
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
            "custom_scenario": "",
            "custom_supplement": "",
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
        choices_text += f"\n**{len(options)+1}.** 🆕 自定义场景 — *以上都不符合？选择此项后在补充框中描述你的场景*"

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
    # Step 3: 场景路由（支持自定义场景 + 补充说明）
    # ═══════════════════════════════════════════════════════════════

    def submit_routing(self, choice_text: str, supplement: str, session: dict) -> Tuple[str, str, str, str, str, str, dict]:
        s = self._get_state(session)
        options = s.get("routing_choices", [])

        try:
            choice_index = int(choice_text.strip()) - 1
        except ValueError:
            return "请输入选项数字（如 1、2、3、4）", "", "", "", "", build_progress_bar("3. 场景"), session

        # 自定义场景处理
        if choice_index == len(options):
            custom_desc = supplement.strip()
            if not custom_desc:
                return "⚠️ 请在下方补充框中描述你的场景", "", "", "", "", build_progress_bar("3. 场景"), session
            s["custom_scenario"] = custom_desc
            # 使用最接近的写作模式（默认信息传达）
            result = self.orchestrator.submit_routing_choice(0)
            if result.get("phase") == "routing_complete":
                mode = result.get("mode", "")
                mode_profile = get_mode_profile(WritingMode(mode))
                s["step"] = "4. 问卷"
                next_q = self.orchestrator.get_current_mode_question()
                if next_q:
                    s["current_q_index"] = next_q.get("index", 1)
                    s["total_q"] = next_q.get("total", 1)
                    return (
                        f"✅ 已选择 **自定义场景**：{custom_desc[:50]}\n\n已映射到 → **{mode_profile.name}**（可后续调整）",
                        f"第 {s['current_q_index']}/{s['total_q']} 题",
                        f"### {next_q.get('question', '')}",
                        f"💡 *{next_q.get('why_ask', '')}*",
                        f"💬 *示例：{next_q.get('hint', '')}*" if next_q.get('hint') else "",
                        build_progress_bar("4. 问卷"),
                        session
                    )
            return "自定义场景映射失败，请重试", "", "", "", "", build_progress_bar("3. 场景"), session

        # 正常场景选择
        result = self.orchestrator.submit_routing_choice(choice_index)

        if result.get("phase") == "routing_complete":
            mode = result.get("mode", "")
            mode_profile = get_mode_profile(WritingMode(mode))
            s["step"] = "4. 问卷"

            # 保存补充说明
            if supplement.strip():
                s["custom_supplement"] = supplement.strip()

            next_q = self.orchestrator.get_current_mode_question()
            if next_q:
                s["current_q_index"] = next_q.get("index", 1)
                s["total_q"] = next_q.get("total", 1)
                hint = next_q.get("hint", "")
                hint_text = f"💬 *示例回答：{hint}*" if hint else ""
                supplement_note = f"\n\n📝 **补充说明**：{supplement.strip()}" if supplement.strip() else ""
                return (
                    f"✅ 已选择 → **{mode_profile.name}**{supplement_note}",
                    f"第 {s['current_q_index']}/{s['total_q']} 题",
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

        try:
            plan = self.orchestrator.generate_plan()
            s["plan_generated"] = True

            auto_style_label = STYLE_ENUM_TO_LABEL.get(plan.media_style, "人民日报风格")
            auto_doc_label = DOC_TYPE_ENUM_TO_LABEL.get(plan.document_type, "通讯（推荐1500-3000字）")

            kb_exemplars = ""
            try:
                exemplars = self.knowledge_base.get_exemplars_for_prompt(
                    self.orchestrator.writing_mode.value, max_exemplars=2
                )
                if exemplars:
                    kb_exemplars = f"### 📚 知识库推荐范文\n\n{exemplars[:800]}..."
            except Exception:
                pass

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
                "", "", "", "", "",
                plan.display(),
                auto_style_label,
                auto_doc_label,
                f"{kb_exemplars}{blend_info}",
                build_progress_bar("5. 方案"),
                session
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
    # Step 5: 方案确认
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

            format_check = ""
            try:
                if self.orchestrator.draft:
                    fmt_issues = self.orchestrator.reviewer.check_format_compliance(self.orchestrator.draft)
                    if fmt_issues:
                        lines = ["### 📋 格式合规检查\n"]
                        for fi in fmt_issues:
                            sev = fi.get("severity", "")
                            diag = fi.get("diagnosis", str(fi))
                            pres = fi.get("prescription", "")
                            icon = "🔴" if sev == "critical" else "🟡" if sev == "major" else "🟢"
                            lines.append(f"- {icon} **{diag}**\n  → {pres}")
                        format_check = "\n".join(lines)
            except Exception:
                pass

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
    # URL 导入（文件夹式多主题管理）
    # ═══════════════════════════════════════════════════════════════

    def import_url_to_topic(self, url: str, topic_name: str, session: dict) -> Tuple[str, str, dict]:
        """导入 URL 到指定主题"""
        url = url.strip()
        topic_name = topic_name.strip() or "未命名主题"
        if not url:
            return "", "请输入 URL", session
        try:
            importer = URLDocumentImporter()
            doc = importer.import_from_url(url)
            self.url_topics.setdefault(topic_name, []).append(doc)
            s = self._get_state(session)
            s.setdefault("url_docs", []).append(doc)

            lines = [f"### 📥 已导入到主题「{topic_name}」", ""]
            lines.append(f"**标题**：{doc.title}")
            lines.append(f"**来源**：{doc.source_site}  |  **字数**：{doc.word_count}")
            if doc.content:
                lines.append(f"\n**正文预览**（前300字）：\n\n{doc.content[:300]}{'...' if len(doc.content) > 300 else ''}")
            return "\n".join(lines), "✅ 导入成功", session
        except Exception as e:
            return f"❌ 导入失败：{e}", "❌ 导入失败", session

    def get_topics_display(self) -> str:
        """显示所有主题列表（文件夹式）"""
        if not self.url_topics:
            return "暂无主题，请先导入 URL 并创建主题。"
        lines = ["### 📁 参考文档主题", ""]
        for topic, docs in self.url_topics.items():
            lines.append(f"📂 **{topic}**（{len(docs)} 篇文档）")
            for i, doc in enumerate(docs):
                lines.append(f"   📄 {i+1}. {doc.title} — {doc.word_count}字 [{doc.source_site}]")
            lines.append("")
        return "\n".join(lines)

    def get_topic_detail(self, topic_name: str) -> str:
        """显示某个主题的详细内容"""
        topic_name = topic_name.strip()
        if topic_name not in self.url_topics:
            return f"未找到主题「{topic_name}」"
        docs = self.url_topics[topic_name]
        lines = [f"### 📂 主题「{topic_name}」详细内容", ""]
        for i, doc in enumerate(docs):
            lines.append(f"---\n**文档 {i+1}：{doc.title}**")
            lines.append(f"来源：{doc.source_site} | 字数：{doc.word_count} | 格式：{doc.format.value}")
            if doc.keywords:
                lines.append(f"关键词：{', '.join(doc.keywords[:10])}")
            if doc.style_patterns:
                lines.append(f"风格特征：{'；'.join(doc.style_patterns[:5])}")
            if doc.content:
                lines.append(f"\n{doc.content[:800]}{'...' if len(doc.content) > 800 else ''}")
            lines.append("")
        return "\n".join(lines)

    def rename_topic(self, old_name: str, new_name: str) -> str:
        """重命名主题"""
        old_name = old_name.strip()
        new_name = new_name.strip()
        if not old_name or old_name not in self.url_topics:
            return f"未找到主题「{old_name}」"
        if not new_name:
            return "新名称不能为空"
        if new_name in self.url_topics:
            return f"主题「{new_name}」已存在"
        self.url_topics[new_name] = self.url_topics.pop(old_name)
        return f"✅ 已将「{old_name}」重命名为「{new_name}」"

    def delete_topic(self, topic_name: str) -> str:
        """删除主题"""
        topic_name = topic_name.strip()
        if topic_name in self.url_topics:
            del self.url_topics[topic_name]
            return f"✅ 已删除主题「{topic_name}」"
        return f"未找到主题「{topic_name}」"

    def delete_topic_doc(self, topic_name: str, doc_index: int) -> str:
        """删除主题中的某篇文档"""
        topic_name = topic_name.strip()
        if topic_name not in self.url_topics:
            return f"未找到主题「{topic_name}」"
        docs = self.url_topics[topic_name]
        if 0 <= doc_index < len(docs):
            removed = docs.pop(doc_index)
            return f"✅ 已删除「{removed.title}」"
        return f"文档序号 {doc_index+1} 无效"

    def add_url_to_project_by_topic(self, topic_name: str, proj_name: str, session: dict) -> Tuple[str, dict]:
        """将主题中所有文档添加到项目"""
        if not self.current_user_id:
            return "请先创建用户", session
        topic_name = topic_name.strip()
        if topic_name not in self.url_topics:
            return f"未找到主题「{topic_name}」", session
        projects = self.pdb.list_projects()
        target = next((p for p in projects if p.name == proj_name.strip()), None)
        if not target:
            return f"未找到项目「{proj_name}」", session
        count = 0
        for doc in self.url_topics[topic_name]:
            try:
                self.pdb.add_url_reference(target.id, doc.source_url if hasattr(doc, 'source_url') else "", auto_fetch=False)
                count += 1
            except Exception:
                pass
        return f"✅ 已将主题「{topic_name}」中 {count} 篇文档添加到项目「{proj_name}」", session

    # ═══════════════════════════════════════════════════════════════
    # 项目管理（文件夹式）
    # ═══════════════════════════════════════════════════════════════

    def list_projects(self, session: dict) -> Tuple[str, dict]:
        """文件夹式项目列表"""
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        if not projects:
            return "暂无项目，请在写作页面创建项目。", session
        lines = ["### 📁 我的项目", ""]
        for p in projects:
            status_icon = {"draft": "📝", "in_progress": "🔄", "completed": "✅", "archived": "📦"}.get(p.status.value, "📄")
            desc = p.description[:60] if p.description else "无描述"
            lines.append(f"{status_icon} **{p.name}**")
            lines.append(f"   状态：{p.status.value} | 描述：{desc}")
            if hasattr(p, 'style_requirements') and p.style_requirements:
                lines.append(f"   参考文档：{len(p.style_requirements)} 篇")
            lines.append("")
        return "\n".join(lines), session

    def get_project_detail(self, proj_name: str, session: dict) -> Tuple[str, dict]:
        """查看项目详情"""
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        target = next((p for p in projects if p.name == proj_name.strip()), None)
        if not target:
            return f"未找到项目「{proj_name}」", session

        lines = [f"### 📂 项目详情：{target.name}", ""]
        lines.append(f"**状态**：{target.status.value}")
        lines.append(f"**描述**：{target.description or '无'}")
        lines.append(f"**创建时间**：{target.created_at}")
        lines.append(f"**更新时间**：{target.updated_at}")

        if hasattr(target, 'questionnaire_results') and target.questionnaire_results:
            qr = target.questionnaire_results
            lines.append(f"\n**写作模式**：{qr.writing_mode}")
            lines.append(f"**文种**：{qr.doc_type}")
            lines.append(f"**风格**：{qr.style}")

        if hasattr(target, 'style_requirements') and target.style_requirements:
            lines.append(f"\n**参考文档**（{len(target.style_requirements)} 篇）：")
            for i, ref in enumerate(target.style_requirements):
                lines.append(f"  {i+1}. {ref.title} — {ref.word_count}字")

        if hasattr(target, 'writing_history') and target.writing_history:
            lines.append(f"\n**写作历史**（{len(target.writing_history)} 次）：")
            for h in target.writing_history[-3:]:
                lines.append(f"  - {h}")

        return "\n".join(lines), session

    def delete_project(self, proj_name: str, session: dict) -> Tuple[str, dict]:
        """删除项目"""
        if not self.current_user_id:
            return "请先创建用户", session
        projects = self.pdb.list_projects()
        target = next((p for p in projects if p.name == proj_name.strip()), None)
        if not target:
            return f"未找到项目「{proj_name}」", session
        try:
            self.pdb.delete_project(target.id)
            return f"✅ 已删除项目「{proj_name}」", session
        except Exception as e:
            return f"❌ 删除失败：{e}", session

    def get_memory_summary(self, session: dict) -> Tuple[str, dict]:
        """用户记忆摘要（可查看/编辑）"""
        if not self.current_user_id:
            return "请先创建用户", session
        summary = self.pdb.get_memory_summary(self.current_project_id)
        return summary, session

    def add_memory_note(self, note: str, session: dict) -> Tuple[str, dict]:
        """添加记忆笔记"""
        if not self.current_user_id:
            return "请先创建用户", session
        note = note.strip()
        if not note:
            return "请输入笔记内容", session
        self.pdb.add_to_memory(self.current_project_id, note)
        return f"✅ 已添加笔记", session

    # ═══════════════════════════════════════════════════════════════
    # API 配置（多 API 管理）
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

    def get_api_list_display(self) -> str:
        """显示所有 API 配置列表"""
        configs = self.api_manager.get_all_configs()
        if not configs:
            return "暂无 API 配置"
        lines = ["### 🔑 API 配置列表", ""]
        for i, c in enumerate(configs):
            active = "🔵 **当前激活**" if i == self.api_manager.active_index else ""
            status = "✅" if c.enable else "⚪"
            provider_name = SUPPORTED_PROVIDERS.get(c.provider, c.provider)
            key_preview = f"{c.api_key[:6]}..." if c.api_key else "未设置"
            lines.append(f"{status} **{c.name}** {active}")
            lines.append(f"   提供商：{provider_name} | 模型：{c.model} | Key：{key_preview}")
            lines.append(f"   Base URL：{c.api_base}")
            lines.append("")
        return "\n".join(lines)

    def add_new_api(self, name: str, provider: str) -> Tuple[str, str, str, str, float, int, bool]:
        """添加新 API 配置"""
        cfg = self.api_manager.add_config(name=name, provider=provider)
        return cfg.provider, cfg.api_base, cfg.api_key, cfg.model, cfg.temperature, cfg.max_tokens, cfg.enable

    def switch_api(self, index: int) -> Tuple[str, str, str, str, float, int, bool, str]:
        """切换到指定 API 配置"""
        try:
            idx = int(index)
            cfg = self.api_manager.switch_to(idx)
            return cfg.provider, cfg.api_base, cfg.api_key, cfg.model, cfg.temperature, cfg.max_tokens, cfg.enable, f"✅ 已切换到「{cfg.name}」"
        except (ValueError, IndexError):
            c = self.api_manager.config
            return c.provider, c.api_base, c.api_key, c.model, c.temperature, c.max_tokens, c.enable, "❌ 无效的配置序号"

    def delete_api(self, index: int) -> str:
        """删除指定 API 配置"""
        try:
            idx = int(index)
            if self.api_manager.delete_config(idx):
                return f"✅ 已删除配置 #{idx+1}"
            return "❌ 无法删除（至少保留一个配置）"
        except (ValueError, IndexError):
            return "❌ 无效的配置序号"

    def rename_api(self, index: int, new_name: str) -> str:
        """重命名 API 配置"""
        try:
            idx = int(index)
            configs = self.api_manager.get_all_configs()
            if 0 <= idx < len(configs):
                configs[idx].name = new_name.strip() or f"配置 {idx+1}"
                self.api_manager.save()
                return f"✅ 已重命名为「{configs[idx].name}」"
            return "❌ 无效的配置序号"
        except (ValueError, IndexError):
            return "❌ 无效的配置序号"


# ═══════════════════════════════════════════════════════════════
# UI 构建
# ═══════════════════════════════════════════════════════════════

def create_ui() -> gr.Blocks:
    app = GradioApp()

    with gr.Blocks(title="公文写作 Agent V9", theme=gr.themes.Soft()) as demo:
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

                # ─── Step 3: 场景（支持自定义 + 补充说明）───
                gr.Markdown("### 📌 第3步：选择你的场景")
                routing_display = gr.Markdown("选择最接近你当前情况的场景。")
                with gr.Row():
                    routing_choice = gr.Textbox(label="输入对应数字", placeholder="例如：1", scale=2)
                    routing_supplement = gr.Textbox(label="补充说明（可选）", placeholder="对场景的补充描述，或自定义场景说明...", scale=3)
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
                        value="通讯（推荐1500-3000字）",
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
                with gr.Accordion("📋 格式合规检查", open=True):
                    format_check_output = gr.Textbox(label="格式检查", lines=6, interactive=False)
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
                # 事件绑定 - 写作 Tab
                # ═══════════════════════════════════════════════════

                user_btn.click(
                    fn=lambda name, sess: app.create_or_select_user(name.strip(), sess),
                    inputs=[user_name, session_state],
                    outputs=[user_msg, proj_msg, progress_bar, session_state]
                )

                proj_btn.click(
                    fn=lambda name, desc, sess: app.create_project(name, desc, sess),
                    inputs=[proj_name, proj_desc, session_state],
                    outputs=[proj_msg, routing_display, routing_msg, progress_bar, session_state]
                )

                routing_btn.click(
                    fn=lambda choice, supp, sess: app.submit_routing(choice, supp, sess),
                    inputs=[routing_choice, routing_supplement, session_state],
                    outputs=[routing_msg, q_progress, question_text, teaching_text, hint_text, progress_bar, session_state]
                )

                def question_fn(answer: str, session: dict):
                    msg, progress, q, teach, hint, prev, plan, style, doc, kb, bar, new_sess = app.submit_answer(answer, session)
                    return msg, progress, q, teach, hint, prev, plan, style, doc, kb, bar, new_sess, ""

                q_submit.click(fn=question_fn, inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input])
                q_back.click(fn=question_fn, inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input])
                q_skip.click(fn=question_fn, inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input])
                q_finish.click(fn=question_fn, inputs=[answer_input, session_state],
                    outputs=[q_msg, q_progress, question_text, teaching_text, hint_text, q_prev,
                             plan_output, style_selector, doc_type_selector, kb_display,
                             progress_bar, session_state, answer_input])

                plan_regenerate_btn.click(
                    fn=lambda style, doc, sess: app.regenerate_plan(style, doc, sess),
                    inputs=[style_selector, doc_type_selector, session_state],
                    outputs=[plan_output, style_selector, doc_type_selector, kb_display, progress_bar, session_state]
                )

                plan_btn.click(
                    fn=lambda sess: app.generate_draft(sess),
                    inputs=[session_state],
                    outputs=[draft_msg, draft_output, agent_log, multi_preview_step6, prompt_preview, progress_bar, session_state]
                )

                draft_btn.click(
                    fn=lambda sess: app.run_review(sess),
                    inputs=[session_state],
                    outputs=[review_msg, review_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                fix_btn.click(
                    fn=lambda r, i, sess: app.apply_fix(int(r), int(i), sess),
                    inputs=[fix_round, fix_index, session_state],
                    outputs=[review_msg, draft_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                manual_update_btn.click(
                    fn=lambda d, sess: app.update_draft_manual(d, sess),
                    inputs=[manual_edit, session_state],
                    outputs=[review_msg, draft_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                re_review_btn.click(
                    fn=lambda sess: app.re_review(sess),
                    inputs=[session_state],
                    outputs=[review_msg, review_output, review_issues, format_check_output, kb_diagnosis_output, multi_preview_step6, progress_bar, session_state]
                )

                review_final.click(
                    fn=lambda sess: app.finalize(sess),
                    inputs=[session_state],
                    outputs=[final_output, final_multi, final_agent, workflow_summary, progress_bar, session_state]
                )

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
            # Tab 2: URL导入（文件夹式多主题管理）
            # ═══════════════════════════════════════════════════════
            with gr.Tab("🌐 URL导入"):
                gr.Markdown("### 📂 参考文档管理")
                gr.Markdown("导入网页文档，按主题分类管理。支持自定义主题名、编辑内容、多文本导入。")

                # 主题列表
                topics_display = gr.Markdown(app.get_topics_display())
                refresh_topics_btn = gr.Button("🔄 刷新主题列表", size="sm")

                gr.Markdown("---")
                gr.Markdown("### 📥 导入文档到主题")
                with gr.Row():
                    url_input = gr.Textbox(label="URL", placeholder="https://example.com/article", scale=3)
                    topic_name_input = gr.Textbox(label="主题名称", placeholder="例如：教育改革参考", scale=2)
                    url_btn = gr.Button("导入", variant="primary", scale=1)
                url_status = gr.Markdown()
                url_output = gr.Textbox(label="导入结果", lines=8, interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 🔍 查看主题详情")
                with gr.Row():
                    topic_view_name = gr.Textbox(label="主题名称", placeholder="输入要查看的主题名", scale=3)
                    topic_view_btn = gr.Button("查看详情", scale=1)
                topic_detail_output = gr.Textbox(label="主题详情", lines=12, interactive=False)

                gr.Markdown("---")
                gr.Markdown("### 🛠️ 主题管理")
                with gr.Row():
                    topic_rename_old = gr.Textbox(label="原名称", scale=1)
                    topic_rename_new = gr.Textbox(label="新名称", scale=1)
                    topic_rename_btn = gr.Button("重命名", scale=1)
                rename_status = gr.Markdown()

                with gr.Row():
                    topic_delete_name = gr.Textbox(label="要删除的主题名", scale=2)
                    topic_delete_btn = gr.Button("🗑️ 删除主题", variant="stop", scale=1)
                delete_status = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### 📎 添加到项目")
                with gr.Row():
                    topic_for_proj = gr.Textbox(label="主题名称", scale=2)
                    proj_for_url = gr.Textbox(label="目标项目名称", scale=2)
                    url_to_proj_btn = gr.Button("添加", variant="primary", scale=1)
                add_status = gr.Markdown()

                # 事件绑定
                url_btn.click(
                    fn=lambda u, t, s: app.import_url_to_topic(u, t, s),
                    inputs=[url_input, topic_name_input, session_state],
                    outputs=[url_output, url_status, session_state]
                )
                refresh_topics_btn.click(
                    fn=lambda: app.get_topics_display(),
                    outputs=[topics_display]
                )
                topic_view_btn.click(
                    fn=lambda t: app.get_topic_detail(t),
                    inputs=[topic_view_name],
                    outputs=[topic_detail_output]
                )
                topic_rename_btn.click(
                    fn=lambda old, new: app.rename_topic(old, new),
                    inputs=[topic_rename_old, topic_rename_new],
                    outputs=[rename_status]
                )
                topic_delete_btn.click(
                    fn=lambda t: app.delete_topic(t),
                    inputs=[topic_delete_name],
                    outputs=[delete_status]
                )
                url_to_proj_btn.click(
                    fn=lambda t, p, s: app.add_url_to_project_by_topic(t, p, s),
                    inputs=[topic_for_proj, proj_for_url, session_state],
                    outputs=[add_status, session_state]
                )

            # ═══════════════════════════════════════════════════════
            # Tab 3: API配置（多 API 管理）
            # ═══════════════════════════════════════════════════════
            with gr.Tab("🔑 API配置"):
                gr.Markdown("### 🔑 LLM API 多配置管理")
                gr.Markdown("支持添加多个 API 配置，随时切换使用。")

                # API 列表
                api_list_display = gr.Markdown(app.get_api_list_display())
                refresh_api_btn = gr.Button("🔄 刷新列表", size="sm")

                gr.Markdown("---")
                gr.Markdown("### ➕ 添加新配置")
                with gr.Row():
                    new_api_name = gr.Textbox(label="配置名称", placeholder="例如：我的GPT-4", scale=2)
                    new_api_provider = gr.Dropdown(
                        choices=list(SUPPORTED_PROVIDERS.values()),
                        value="OpenAI (GPT-4/3.5)",
                        label="提供商",
                        scale=2,
                    )
                    add_api_btn = gr.Button("添加", variant="primary", scale=1)
                add_api_msg = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### 🔀 切换配置")
                with gr.Row():
                    switch_api_index = gr.Number(label="配置序号（从0开始）", value=0, precision=0, scale=2)
                    switch_api_btn = gr.Button("切换", scale=1)
                switch_api_msg = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### 🗑️ 删除配置")
                with gr.Row():
                    delete_api_index = gr.Number(label="配置序号（从0开始）", value=0, precision=0, scale=2)
                    delete_api_btn = gr.Button("删除", variant="stop", scale=1)
                delete_api_msg = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### ✏️ 编辑当前配置")
                api_status_bar = gr.Markdown(app.get_config_status())
                provider_select = gr.Dropdown(
                    choices=list(SUPPORTED_PROVIDERS.values()),
                    value="OpenAI (GPT-4/3.5)",
                    label="快速加载提供商模板",
                )
                with gr.Row():
                    provider_btn = gr.Button("加载模板", scale=1)
                provider_msg = gr.Markdown()

                with gr.Row():
                    api_base = gr.Textbox(label="API Base URL", scale=2)
                    api_key = gr.Textbox(label="API Key", type="password", scale=2)
                with gr.Row():
                    model = gr.Textbox(label="模型名称", scale=2)
                    enable_api = gr.Checkbox(label="启用此配置", value=False, scale=1)
                with gr.Row():
                    temperature = gr.Slider(0, 2, value=0.7, step=0.1, label="Temperature", scale=1)
                    max_tokens = gr.Slider(1000, 32000, value=8000, step=500, label="Max Tokens", scale=1)

                with gr.Row():
                    api_save_btn = gr.Button("💾 保存当前配置", variant="primary", scale=1)
                    api_test_btn = gr.Button("🔌 测试连接", variant="secondary", scale=1)
                api_save_msg = gr.Markdown()
                api_test_msg = gr.Markdown()

                # 事件绑定
                def _provider_key_to_label(provider: str) -> str:
                    return SUPPORTED_PROVIDERS.get(provider, provider)

                def _provider_label_to_key(label: str) -> str:
                    for k, v in SUPPORTED_PROVIDERS.items():
                        if v == label:
                            return k
                    return label

                refresh_api_btn.click(
                    fn=lambda: app.get_api_list_display(),
                    outputs=[api_list_display]
                )

                def _add_api(name, provider_label):
                    key = _provider_label_to_key(provider_label)
                    result = app.add_new_api(name, key)
                    return (*result, app.get_api_list_display(), f"✅ 已添加「{name or '新配置'}」")

                add_api_btn.click(
                    fn=_add_api,
                    inputs=[new_api_name, new_api_provider],
                    outputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api, api_list_display, add_api_msg]
                )

                def _switch_api(idx):
                    result = app.switch_api(idx)
                    return (*result, app.get_api_list_display(), app.get_config_status())

                switch_api_btn.click(
                    fn=_switch_api,
                    inputs=[switch_api_index],
                    outputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api, switch_api_msg, api_list_display, api_status_bar]
                )

                delete_api_btn.click(
                    fn=lambda idx: (app.delete_api(idx), app.get_api_list_display()),
                    inputs=[delete_api_index],
                    outputs=[delete_api_msg, api_list_display]
                )

                def _apply_provider(provider_label):
                    key = _provider_label_to_key(provider_label)
                    result = app.apply_provider(key)
                    return result

                provider_btn.click(
                    fn=_apply_provider,
                    inputs=[provider_select],
                    outputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api, provider_msg]
                )

                def _save_api(provider_label, base, key, mdl, temp, tokens, enable):
                    pkey = _provider_label_to_key(provider_label)
                    return app.save_api_config(pkey, base, key, mdl, temp, tokens, enable)

                api_save_btn.click(
                    fn=_save_api,
                    inputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api],
                    outputs=[api_save_msg, api_status_bar]
                )

                api_test_btn.click(
                    fn=lambda: app.test_api_connection(),
                    outputs=[api_test_msg]
                )

                demo.load(
                    fn=app.load_api_config,
                    outputs=[provider_select, api_base, api_key, model, temperature, max_tokens, enable_api]
                )

            # ═══════════════════════════════════════════════════════
            # Tab 4: 项目（文件夹式管理）
            # ═══════════════════════════════════════════════════════
            with gr.Tab("📁 项目"):
                gr.Markdown("### 📁 项目管理")
                gr.Markdown("查看、编辑、删除项目，管理用户记忆。")

                # 项目列表
                projects_list = gr.Markdown("点击刷新查看项目列表")
                with gr.Row():
                    list_btn = gr.Button("🔄 刷新项目列表", variant="primary")
                    memory_btn = gr.Button("📝 查看记忆摘要")

                gr.Markdown("---")
                gr.Markdown("### 🔍 项目详情")
                with gr.Row():
                    proj_detail_name = gr.Textbox(label="项目名称", placeholder="输入项目名称查看详情", scale=3)
                    proj_detail_btn = gr.Button("查看详情", scale=1)
                proj_detail_output = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### 🗑️ 删除项目")
                with gr.Row():
                    proj_delete_name = gr.Textbox(label="要删除的项目名", scale=3)
                    proj_delete_btn = gr.Button("删除项目", variant="stop", scale=1)
                proj_delete_msg = gr.Markdown()

                gr.Markdown("---")
                gr.Markdown("### 📝 用户记忆管理")
                memory_output = gr.Textbox(label="记忆摘要", lines=10, interactive=False)
                gr.Markdown("**添加新记忆笔记**：")
                with gr.Row():
                    memory_note_input = gr.Textbox(label="笔记内容", placeholder="例如：偏好使用短句，避免空话套话...", scale=3)
                    memory_add_btn = gr.Button("添加笔记", variant="primary", scale=1)
                memory_add_msg = gr.Markdown()

                # 事件绑定
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
                proj_detail_btn.click(
                    fn=lambda name, s: app.get_project_detail(name, s),
                    inputs=[proj_detail_name, session_state],
                    outputs=[proj_detail_output, session_state]
                )
                proj_delete_btn.click(
                    fn=lambda name, s: app.delete_project(name, s),
                    inputs=[proj_delete_name, session_state],
                    outputs=[proj_delete_msg, session_state]
                )
                memory_add_btn.click(
                    fn=lambda note, s: app.add_memory_note(note, s),
                    inputs=[memory_note_input, session_state],
                    outputs=[memory_add_msg, session_state]
                )

    return demo


if __name__ == "__main__":
    demo = create_ui()
    demo.launch(share=False, inbrowser=True)
