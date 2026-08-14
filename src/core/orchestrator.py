"""
协调者 Agent — 多Agent调度的总指挥（V3：模式感知版 · 已按职责拆分）

V3 重构（阶段1）：
- LLM 调用/工具闭环/API统计 → LLMClient（组合，self.llm_client 委托）
- 审查迭代/辩论/HITL → ReviewPipeline（Mixin）
- 展示格式化 → UIFormatter（Mixin）
本文件保留纯协调逻辑：状态机、问卷路由、规划、写作编排、收尾输出。

工作流：
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 决策树路由│ →   │ 模式问卷  │ →  │ 规划方案   │ →  │ 写作+审查 │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
  确定WritingMode  WritingBrief   HITL-1确认     HITL-2输出
"""

from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Callable, Tuple
from enum import Enum

from ..questionnaire.questionnaire import (
    Questionnaire, WritingBrief,
    QuestionnairePhase,
)
from .style_adapter import (
    StyleAdapter, MediaStyle, STYLE_PROFILES
)
from .document_type import (
    DocumentTypeIdentifier, DocumentType, DocTypeProfile, DOC_TYPE_PROFILES
)
from .writer_agent import WriterAgent, WriterConfig
from .reviewer_agent import ReviewerAgent, ReviewResult
from .agent_coordinator import AgentCoordinator, AgentRole, role_display_name
from .multi_doc_generator import MultiDocGenerator
from .writing_mode import (
    WritingMode,
    get_mode_profile,
)
from ..questionnaire.questionnaire import get_mode_questions as _get_mode_questions

from .llm_client import LLMClient
from .review_pipeline import ReviewPipeline
from .ui_formatter import UIFormatter


class OrchestratorState(Enum):
    IDLE = "idle"
    ROUTING = "routing"
    MODE_QUESTIONING = "mode_questioning"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    WRITING = "writing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    ERROR = "error"


@dataclass
class WritingPlan:
    document_type: DocumentType
    doc_type_name: str
    media_style: MediaStyle
    style_name: str
    audience_focus: str
    estimated_length: str
    structure_outline: str
    key_materials_to_use: str
    brief_summary: str
    writing_mode: WritingMode = WritingMode.STRATEGIC_NARRATIVE
    mode_name: str = "战略叙事模式"

    def display(self) -> str:
        return f"""
╔═══════════════════════════════════════════╗
║          ✍️  写 作 方 案                    ║
╠═══════════════════════════════════════════╣
║                                            ║
║  🏷️  写作模式：{self.mode_name}
║  📄 文　　种：{self.doc_type_name}（{self.estimated_length}）
║  🎨 写作风格：{self.style_name}
║  👤 目标受众：{self.audience_focus}
║                                            ║
║  📋 结构规划：                              ║
║  {self.structure_outline.replace(chr(10), chr(10) + '  ')}
║                                            ║
║  📎 关键素材：                              ║
║  {self.key_materials_to_use}
║                                            ║
╚═══════════════════════════════════════════╝
"""


class Orchestrator(UIFormatter, ReviewPipeline):

    def __init__(self, api_manager=None, knowledge_base=None, style_adapter=None):
        self.questionnaire = Questionnaire()
        # 优先使用传入的 style_adapter，否则创建默认实例
        self.style_adapter = style_adapter if style_adapter is not None else StyleAdapter()
        self.doc_identifier = DocumentTypeIdentifier()

        # 知识库：优先使用传入的，否则懒加载（首次使用时创建）
        self._knowledge_base = knowledge_base

        self.writer = WriterAgent(knowledge_base=self._get_knowledge_base())
        self.reviewer = ReviewerAgent()
        self.coordinator = AgentCoordinator()
        self.multi_doc_gen = MultiDocGenerator()

        # LLM 客户端（组合）：封装 LLM 调用、工具闭环、API 统计
        self.llm_client = LLMClient(host=self, api_manager=api_manager)

        self.state = OrchestratorState.IDLE
        self.brief: Optional[WritingBrief] = self.questionnaire.brief
        self.plan: Optional[WritingPlan] = None
        self.draft: Optional[str] = None
        self.review_results: List[ReviewResult] = []
        self.final_draft: Optional[str] = None
        self.writing_mode: WritingMode = WritingMode.STRATEGIC_NARRATIVE

        self._on_question: Optional[Callable] = None
        self._on_plan_ready: Optional[Callable] = None
        self._on_draft_ready: Optional[Callable] = None
        self._on_review_done: Optional[Callable] = None

        self.agent_log: List[str] = []
        self.multi_versions: Dict[str, str] = {}
        self.review_summary_display: str = ""
        self.temperature: float = 0.7
        self._on_complete: Optional[Callable] = None
        # 用户记忆（跨会话个性化，由外部注入）
        self.user_memory: str = ""
        # 个性化数据库（由 GradioApp 等外部注入持久化实例，避免工具内新建实例读不到数据）
        self._pdb: Optional[Any] = None
        # 最近一次审查的轮次数据（含 LLM 结构化审查结果）
        self._last_iteration_results: List[Dict[str, Any]] = []

    def set_user_memory(self, memory_text: str):
        """注入用户记忆文本（偏好/历史/常见错误），将在写作时写入 prompt"""
        self.user_memory = memory_text or ""

    def set_personalized_db(self, pdb):
        """注入持久化个性化数据库实例（与 UI 侧同一实例，保证工具能读到项目数据）"""
        self._pdb = pdb

    def _get_pdb(self):
        """获取个性化数据库实例：优先使用注入的持久化实例，否则懒加载并缓存"""
        if self._pdb is None:
            try:
                from .personalized_db import PersonalizedDB
                self._pdb = PersonalizedDB()
            except Exception:
                self._pdb = False  # 加载失败则永久禁用，避免反复尝试
        return self._pdb if self._pdb is not False else None

    def _get_knowledge_base(self):
        """懒加载知识库实例（避免导入时即加载）"""
        if self._knowledge_base is None:
            try:
                from ..knowledge.knowledge_base import KnowledgeBase
                self._knowledge_base = KnowledgeBase()
            except Exception:
                return None
        return self._knowledge_base

    def _detect_style_conflict(self) -> bool:
        """检测写作模式与用户风格偏好是否冲突（修复 M-8：不再硬编码 False）"""
        try:
            if not self.plan or not self.style_adapter:
                return False
            mode_value = self.writing_mode.value if hasattr(self.writing_mode, 'value') else str(self.writing_mode)
            media_style = getattr(self.plan, 'media_style', None)
            # 行政公文模式不应搭配媒体/文学性风格
            if mode_value == "administrative" and media_style in (
                MediaStyle.PEOPLE_DAILY, MediaStyle.XINHUA,
                MediaStyle.CCTV, MediaStyle.GUANGMING,
            ):
                return True
            # 战略叙事模式不应搭配纯行政风格
            if mode_value == "strategic_narrative" and media_style == MediaStyle.GOVERNMENT_ADMIN:
                return True
            return False
        except Exception:
            return False

    def _compute_style_blend(self):
        """基于简报的多受众计算混合风格建议（供 Writer 风格注入消费，修复 N6）"""
        try:
            if not self.brief or not getattr(self.brief, "secondary_audiences", None):
                return None
            return self.style_adapter.suggest_blend(
                getattr(self.brief, "primary_audience", "") or "",
                getattr(self.brief, "purpose", "") or "",
                self.brief.secondary_audiences,
            )
        except Exception:
            return None

    def _build_env_state(self, stage: str) -> "EnvState":
        """构建当前流程阶段的 EnvState（写/审/协商共用，消除手工拼装分叉）"""
        from ..config.system_prompt import EnvState
        mode_profile = get_mode_profile(self.writing_mode)
        doc_type_value = ""
        doc_type_name = ""
        if self.plan and self.plan.document_type:
            doc_type_value = self.plan.document_type.value
            doc_type_name = getattr(self.plan, "doc_type_name", "") or ""
        return EnvState(
            writing_mode=mode_profile.name,
            mode_value=self.writing_mode.value,
            subtype=doc_type_value,
            stage=stage,
            doc_type=doc_type_name,
            media_style=self.plan.style_name if self.plan else "",
            style_intensity=self.style_adapter.intensity,
            purpose=getattr(self.brief, "purpose", "") if self.brief else "",
            primary_audience=getattr(self.brief, "primary_audience", "") if self.brief else "",
            length_hint=getattr(self.brief, "length_hint", None) if self.brief else None,
        )

    def on(self, event: str, callback: Callable):
        if event == "question":
            self._on_question = callback
        elif event == "plan_ready":
            self._on_plan_ready = callback
        elif event == "draft_ready":
            self._on_draft_ready = callback
        elif event == "review_done":
            self._on_review_done = callback
        elif event == "complete":
            self._on_complete = callback

    # ═══════════════════════════════════════════════════════════
    # 新版问卷流程：决策树路由 → 模式专属问题
    # ═══════════════════════════════════════════════════════════

    def start_routing(self) -> Dict[str, Any]:
        """启动决策树路由，返回第一个分流问题"""
        self.state = OrchestratorState.ROUTING
        self.questionnaire = Questionnaire()
        self.brief = self.questionnaire.brief
        q = self.questionnaire.get_routing_question()
        if self._on_question:
            self._on_question(q)
        return q

    def submit_routing_choice(self, choice_index: int) -> Dict[str, Any]:
        """提交路由选择，返回下一步或模式确认"""
        if self.state != OrchestratorState.ROUTING:
            return {"phase": "error", "message": "当前不在路由阶段"}

        result = self.questionnaire.submit_routing_choice(choice_index)

        if result["phase"] == "routing_complete":
            # result["mode"] is already a WritingMode enum member
            self.writing_mode = result["mode"] if isinstance(result["mode"], WritingMode) else WritingMode(result["mode"])
            self.state = OrchestratorState.MODE_QUESTIONING
            return result

        return result

    def get_current_mode_question(self) -> Optional[Dict[str, Any]]:
        """获取当前模式专属问题"""
        return self.questionnaire.get_current_mode_question()

    def submit_mode_answer(self, answer: str) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """提交模式问题答案"""
        if self.state != OrchestratorState.MODE_QUESTIONING:
            return (False, None)

        has_next = self.questionnaire.submit_mode_answer(answer)

        if not has_next:
            self.brief = self.questionnaire.finish()
            return (False, None)

        next_q = self.questionnaire.get_current_mode_question()
        return (True, next_q)

    # ═══════════════════════════════════════════════════════════
    # 旧版兼容接口
    # ═══════════════════════════════════════════════════════════

    def start(self) -> Any:
        """启动旧版问卷（兼容旧版API），返回第一个问题"""
        self.state = OrchestratorState.MODE_QUESTIONING
        self.writing_mode = WritingMode.STRATEGIC_NARRATIVE

        # 加载当前模式的问卷问题（修复 M-7：不再返回 None）
        self.questionnaire._mode_questions = _get_mode_questions(self.writing_mode)
        self.questionnaire.phase = QuestionnairePhase.MODE_QUESTIONS
        self.questionnaire._mode_question_index = 0

        return self.questionnaire.get_current_mode_question()

    def answer_question(self, answer: str) -> Optional[Any]:
        """旧版回答问题接口"""
        if self.state != OrchestratorState.MODE_QUESTIONING:
            return None

        has_next = self.questionnaire.submit_mode_answer(answer)

        if not has_next:
            self.brief = self.questionnaire.finish()
            return None

        return self.questionnaire.get_current_mode_question()

    def skip_questionnaire(
        self,
        brief_data: Dict[str, str] = None,
        mode: WritingMode = WritingMode.STRATEGIC_NARRATIVE,
        **kwargs,
    ) -> WritingBrief:
        """跳过问卷，直接注入写作简报"""
        self.writing_mode = mode

        if brief_data:
            self.brief = self.questionnaire.skip_questionnaire(
                mode=mode,
                purpose=brief_data.get("purpose", ""),
                primary_audience=brief_data.get("primary_audience", ""),
                deep_meaning=brief_data.get("deep_meaning", ""),
                strategic_anchor=brief_data.get("strategic_anchor", ""),
                opportunity_context=brief_data.get("opportunity_context", ""),
                key_materials=brief_data.get("key_materials", ""),
                differentiator=brief_data.get("differentiator", ""),
            )
        else:
            self.brief = self.questionnaire.skip_questionnaire(mode=mode, **kwargs)

        if brief_data:
            if "length_hint" in brief_data and brief_data["length_hint"]:
                try:
                    self.brief.length_hint = int(brief_data["length_hint"])
                except (ValueError, TypeError):
                    pass
            if "style_intensity" in brief_data and brief_data["style_intensity"]:
                try:
                    self.brief.style_intensity = float(brief_data["style_intensity"])
                except (ValueError, TypeError):
                    pass
            if "target_doc_types" in brief_data:
                self.brief.target_doc_types = brief_data["target_doc_types"]

        return self.brief

    # ═══════════════════════════════════════════════════════════
    # 规划阶段
    # ═══════════════════════════════════════════════════════════

    def generate_plan(
        self,
        preferred_style: Optional[MediaStyle] = None,
        preferred_doc_type: Optional[DocumentType] = None,
    ) -> WritingPlan:
        if not self.brief or not self.brief.is_complete():
            raise ValueError("写作简报未完成，请先完成问卷或调用skip_questionnaire()")

        self.state = OrchestratorState.PLANNING

        if preferred_style:
            style = preferred_style
        else:
            style = self.style_adapter.auto_select_style(
                f"{self.brief.primary_audience} {self.brief.deep_meaning}",
                self.brief.purpose,
            )
        intensity = self.brief.style_intensity if self.brief.style_intensity else 1.0
        style_profile = self.style_adapter.select_style(style, intensity=intensity)

        if preferred_doc_type:
            doc_type = preferred_doc_type
        else:
            ranked = self.doc_identifier.identify(self.brief)
            if not ranked:
                raise ValueError("无法识别文档类型，请检查简报内容或手动指定文档类型")
            doc_type = ranked[0][0].doc_type
        doc_profile = self.doc_identifier.get_profile(doc_type)

        audience = self._determine_audience_focus()
        mode_profile = get_mode_profile(self.writing_mode)

        self.plan = WritingPlan(
            document_type=doc_type,
            doc_type_name=doc_profile.name_cn,
            media_style=style,
            style_name=style_profile.name,
            audience_focus=audience,
            estimated_length=f"{doc_profile.typical_length_range[0]}-{doc_profile.typical_length_range[1]}字",
            structure_outline=self._build_structure_outline(doc_profile),
            key_materials_to_use=self.brief.key_materials,
            brief_summary=self.questionnaire.generate_brief_summary(),
            writing_mode=self.writing_mode,
            mode_name=mode_profile.name,
        )

        self.state = OrchestratorState.WAITING_APPROVAL

        if self._on_plan_ready:
            self._on_plan_ready(self.plan)

        return self.plan

    def _determine_audience_focus(self) -> str:
        audience = (self.brief.primary_audience or "").lower()
        if any(kw in audience for kw in ["领导", "上级", "汇报"]):
            return "upward"
        elif any(kw in audience for kw in ["媒体", "记者", "通稿"]):
            return "external"
        elif any(kw in audience for kw in ["学生", "家长", "团队", "成员", "内部"]):
            return "internal"
        elif any(kw in audience for kw in ["同行", "对标", "竞争"]):
            return "peer"
        return "external"

    def _build_structure_outline(self, doc_profile: DocTypeProfile) -> str:
        lines = []
        lines.append(f"【开篇】{doc_profile.opening_template.split(chr(10))[0]}")
        body_lines = doc_profile.body_template.split("\n")[:3]
        lines.append(f"【正文】{body_lines[0] if body_lines else '...'}")
        lines.append(f"【结尾】{doc_profile.closing_template.split(chr(10))[0]}")
        return "\n".join(lines)

    # ═══════════════════════════════════════════════════════════
    # 写作阶段
    # ═══════════════════════════════════════════════════════════

    def write(self, raw_materials: str = "", progress_callback=None) -> str:
        """
        多智能体协作写作流程（V3 核心改进）

        流程：
          1. 注册所有 Agent 到 Coordinator
          2. 多智能体协商确定写作方案
          3. 使用 MultiDocGenerator 生成多版本文稿（通讯/消息/简报）
          4. 返回主版本，其他版本存入 multi_versions

        progress_callback: 可选回调，签名 (progress: float, desc: str) -> None
        """
        def _notify(progress, desc):
            if progress_callback:
                progress_callback(progress, desc)

        if not self.plan:
            raise ValueError("请先调用generate_plan()生成写作方案")

        try:
            self.state = OrchestratorState.WRITING
            self.agent_log = []
            self.multi_versions = {}

            _notify(0.1, "正在配置写作智能体...")

            # 第1步：Writer 配置
            mode_profile = get_mode_profile(self.writing_mode)
            doc_profile = DOC_TYPE_PROFILES[self.plan.document_type]
            env_state = self._build_env_state(
                "写作阶段：正在生成初稿。你输出的内容将作为第一版草稿提交审查，后续会有审稿人提出修改建议。"
            )
            config = WriterConfig(
                writing_brief=self.brief,
                style_profile=STYLE_PROFILES[self.plan.media_style],
                doc_type_profile=DOC_TYPE_PROFILES[self.plan.document_type],
                raw_materials=raw_materials,
                audience=self.plan.audience_focus,
                writing_mode=self.writing_mode,
                env_state=env_state,
                user_memory=self.user_memory,
                style_adapter=self.style_adapter,
                style_blend=self._compute_style_blend(),
            )
            self.writer.configure(config)

            self._log_agent("系统", f"写作模式: {get_mode_profile(self.writing_mode).name}")
            self._log_agent("系统", f"文种: {self.plan.doc_type_name}, 风格: {self.plan.style_name}")

            _notify(0.2, "多智能体协商中（主笔/审稿人/格式专家/知识库）...")
            # 传递完整的 plan 信息，确保语义完整性，避免摘要引入 bias
            context_info = {
                "brief": str(self.brief) if self.brief else "",
                "plan": self.plan.display(),
                "writing_mode": self.writing_mode.value,
                "env_state": env_state.render(
                    exclude_fields=["purpose", "primary_audience", "doc_type", "length_hint"]
                ),
                "user_memory": self.user_memory or "",
            }

            # 注入上下文用于真实预警检测
            mode_value = self.writing_mode.value if hasattr(self.writing_mode, 'value') else str(self.writing_mode)
            self.coordinator.set_context(
                raw_materials=raw_materials,
                writing_mode=mode_value,
                draft_word_count=0,  # 写作前尚无草稿
                has_style_conflict=self._detect_style_conflict(),
            )

            consult_responses = self.coordinator.consult_before_decision(
                decision_topic="写作方案评审",
                participants=[
                    AgentRole.WRITER,
                    AgentRole.REVIEWER,
                    AgentRole.STYLE_ADAPTER,
                    AgentRole.KNOWLEDGE_BASE,
                    AgentRole.DOC_TYPE_IDENTIFIER,
                    AgentRole.PERSONALIZED_DB,
                ],
                context=context_info,
                llm_call=self._call_llm,
                max_rounds=2,  # 真多轮协商：第2轮各方回应彼此意见
            )

            for role, response in consult_responses.items():
                concerns = response.get("concerns", [])
                suggestions = response.get("suggestions", [])
                lines = []
                if concerns:
                    lines.extend([f"  ⚠️ {c}" for c in concerns])
                if suggestions:
                    lines.extend([f"  💡 {s}" for s in suggestions])
                if lines:
                    self._log_agent(role.value, "\n".join(lines))
                else:
                    self._log_agent(role.value, "无意见")

            # 第3步：所有 Agent 主动预警（自检）
            _notify(0.35, "各智能体自检与预警中...")
            warnings = self.coordinator.collect_proactive_reports()
            for w in warnings:
                self._log_agent(f"{w.get('agent', 'Agent')} 预警", w.get("alert", ""))

            # 第3.5步：民主集中制决策 - 综合协商意见做最终裁决
            _notify(0.38, "Orchestrator 综合各方意见做最终决策...")
            decision = self.coordinator.make_decision(
                topic="写作方案最终决策",
                consultation_responses=consult_responses,
                proactive_reports=warnings,
                llm_call=self._call_llm,  # LLM 基于各方意见做最终裁决（替代模板匹配）
            )
            self._log_agent("Orchestrator", f"决策: {decision.get('decision', '')}")

            # 将决策中的关注点和建议注入 Writer，确保协商结果真正影响写作
            decision_context = self._build_decision_context(decision)

            # 第4步：生成主版本（Writer Agent，注入协商决策上下文）
            _notify(0.5, "主笔正在起草正文（通常需要30-60秒）...")
            system_prompt = self.writer.build_system_prompt()
            user_prompt = self.writer.build_user_prompt()

            # 在 user_prompt 末尾追加协商决策摘要，让 Writer 知晓各方意见
            if decision_context:
                user_prompt = f"{user_prompt}\n\n【多智能体协商决策摘要】\n{decision_context}"

            self.draft = self._call_llm_with_tool_loop(system_prompt, user_prompt, use_cache=False)
            if self.draft:
                self._log_agent("Writer", f"初稿已生成（{len(self.draft)} 字，已注入协商决策）")
            else:
                self._log_agent("Writer", "初稿生成失败，返回空内容")

            # 降级/占位文本检测：若 LLM 不可用，跳过多版本生成
            if self.draft and ("占位文本" in self.draft or "API 未配置" in self.draft):
                self._log_agent("Writer", "检测到降级/占位文本，跳过多版本生成")
                self.state = OrchestratorState.ERROR
                if self._on_draft_ready:
                    self._on_draft_ready(self.draft)
                return self.draft

            # 第4步：一文多体生成（MultiDocGenerator）
            _notify(0.8, "正在生成多版本文稿（一文多体）...")
            self._generate_multi_versions()

            _notify(0.95, "写作完成，正在整理结果...")
            self.state = OrchestratorState.REVIEWING

            if self._on_draft_ready:
                self._on_draft_ready(self.draft)

            return self.draft
        except Exception as e:
            self.state = OrchestratorState.ERROR
            self._log_agent("系统", f"写作流程异常: {e}")
            return self.draft or ""

    def _build_decision_context(self, decision: Dict[str, Any]) -> str:
        """
        将民主协商决策结果转换为 Writer 可理解的上下文摘要（带角色归属）

        确保协商不是空转：各方意见（谁说的、基于什么立场说的）真正注入到写作过程中
        """
        parts = []
        role_opinions = decision.get("role_opinions") or {}
        if role_opinions:
            parts.append("【各方意见（按角色，供你判断采纳）】")
            for role_value, opinions in role_opinions.items():
                try:
                    name = role_display_name(AgentRole(role_value))
                except ValueError:
                    name = role_value
                lines = [f"- {name}"]
                for c in (opinions.get("concerns") or [])[:2]:
                    lines.append(f"   关注：{c}")
                for s in (opinions.get("suggestions") or [])[:2]:
                    lines.append(f"   建议：{s}")
                if len(lines) > 1:
                    parts.append("\n".join(lines))
        else:
            # 兜底：无角色归属时按扁平列表输出（保持旧行为）
            concerns = decision.get("concerns", [])
            suggestions = decision.get("suggestions", [])
            alerts = decision.get("alerts", [])
            if concerns:
                parts.append("【各方关注点】")
                for c in concerns[:5]:
                    parts.append(f"- {c}")
            if suggestions:
                parts.append("\n【改进建议】")
                for s in suggestions[:5]:
                    parts.append(f"- {s}")
            if alerts:
                parts.append("\n【预警提示】")
                for a in alerts[:3]:
                    parts.append(f"- {a}")

        if decision.get("decision"):
            parts.append(f"\n【最终决策】{decision['decision']}")
        if decision.get("rationale"):
            parts.append(f"决策依据：{decision['rationale']}")

        return "\n".join(parts)

    def _generate_multi_versions(self):
        """使用 MultiDocGenerator 生成多版本文稿"""
        try:
            if not self.brief:
                self._log_agent("MultiDoc", "简报为空，跳过一文体生成")
                return

            output = self.multi_doc_gen.generate_multi_doc(
                brief=self.brief,
                llm_call=self._call_llm,
            )
            for version in output.versions:
                label = version.doc_type_name
                content = version.content
                if content:
                    self.multi_versions[label] = content
                    self._log_agent("MultiDoc", f"已生成 [{label}] 版本（{version.word_count} 字）")
        except Exception as e:
            self._log_agent("MultiDoc", f"多版本生成失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # LLM 委托（公开 API 兼容：保留原方法签名，转发到 llm_client）
    # ═══════════════════════════════════════════════════════════

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None, max_tokens: int = 8000, history: Optional[List[Dict[str, str]]] = None, use_cache: bool = True) -> str:
        """调用 LLM API（委托给 llm_client）"""
        return self.llm_client.call_llm(system_prompt, user_prompt, temperature, max_tokens, history, use_cache)

    def _call_llm_with_tool_loop(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None, max_tokens: int = 8000, max_tool_rounds: int = 3, use_cache: bool = True) -> str:
        """工具闭环调用 LLM（委托给 llm_client）"""
        return self.llm_client.call_llm_with_tool_loop(system_prompt, user_prompt, temperature, max_tokens, max_tool_rounds, use_cache)

    def get_api_stats(self) -> Dict[str, Any]:
        """获取 API 调用统计与 Token 优化报告（委托给 llm_client）"""
        return self.llm_client.get_api_stats()

    def get_tool_execution_log(self) -> List[Dict[str, Any]]:
        """获取工具执行日志（供前端展示，委托给 llm_client）"""
        return self.llm_client.get_tool_execution_log()

    # ═══════════════════════════════════════════════════════════
    # 完成阶段
    # ═══════════════════════════════════════════════════════════

    def finalize(self) -> Dict[str, Any]:
        self.state = OrchestratorState.COMPLETED

        mode_profile = get_mode_profile(self.writing_mode)

        # 获取完整的协调统计
        coordination = self.coordinator.get_coordination_report()

        output = {
            "brief": self.brief.to_dict() if self.brief else {},
            "plan": {
                "document_type": self.plan.doc_type_name if self.plan else "",
                "style": self.plan.style_name if self.plan else "",
                "audience": self.plan.audience_focus if self.plan else "",
                "writing_mode": self.writing_mode.value,
                "mode_name": mode_profile.name,
            } if self.plan else {},
            "draft": self.draft,
            "multi_versions": self.multi_versions,
            "agent_log": self.agent_log,
            "review_count": len(self.review_results),
            "review_passed": all(r.passed for r in self.review_results) if self.review_results else False,
            "mode_principles": [p["name"] for p in mode_profile.principles],
            "coordination_report": coordination,
            "api_stats": self.get_api_stats(),
            # 工具执行日志：LLM 主动调用了哪些工具（agent 化程度的体现）
            "tool_execution_log": self.get_tool_execution_log(),
            # AI 审查思考链（教学场景：让用户看到审查员的推理过程）
            "llm_reasonings": self.llm_client._llm_reasonings,
        }

        if self._on_complete:
            self._on_complete(output)

        return output

    def get_llm_prompts(self) -> Dict[str, Any]:
        if not self.writer.config:
            raise ValueError("请先完成规划并调用write()")

        prompts = {
            "mode": get_mode_profile(self.writing_mode).name,
            "write": self.writer.get_full_prompt(),
            "reviews": [],
        }

        current_draft = self.draft or ""
        dimensions = self.reviewer.get_dimensions()
        for i, dim in enumerate(dimensions):
            prompts["reviews"].append({
                "round": dim["name"],
                "weight": dim["weight"],
                "input_draft": "迭代修复后的当前稿本" if i > 0 else "原始初稿",
                "prompt": self.reviewer.build_review_prompt(
                    current_draft, i, self.brief
                ),
            })

        return prompts
