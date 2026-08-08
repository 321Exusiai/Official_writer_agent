"""
协调者 Agent — 多Agent调度的总指挥（V2：模式感知版）

核心改进：
1. 问卷阶段新增决策树路由分流，支持四模式
2. 写作方案展示写作模式信息
3. 审查轮次根据模式动态切换
4. 兼容旧版API（默认 STRATEGIC_NARRATIVE）

工作流：
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 决策树路由│ →   │ 模式问卷  │ →  │ 规划方案   │ →  │ 写作+审查 │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
  确定WritingMode  WritingBrief   HITL-1确认     HITL-2输出
"""

import json
import threading
import requests
import time
from dataclasses import dataclass
from typing import List, Dict, Optional, Any, Callable, Tuple
from enum import Enum

from ..questionnaire.questionnaire import (
    Questionnaire, WritingBrief,
    QuestionnairePhase,
)
from ..utils.response_cache import cached_prompt, store_prompt, make_cache_key
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


class Orchestrator:

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

        # API 配置管理器：优先使用传入的，否则创建默认实例
        if api_manager is not None:
            self.api_manager = api_manager
        else:
            from ..config.api_config import APIConfigManager
            self.api_manager = APIConfigManager()

        # Token 优化器集成（六大策略）
        from ..utils.token_optimizer import (
            TokenOptimizer, CacheAligner, ContextManager,
            CompressionMode,
        )
        self._token_optimizer = TokenOptimizer(mode=CompressionMode.STANDARD)
        self._cache_aligner = CacheAligner()
        self._context_manager = ContextManager()
        self._api_call_count: int = 0
        self._api_fail_count: int = 0
        self._total_tokens_saved: int = 0
        self._llm_reasonings: List[Dict[str, str]] = []
        self._tool_execution_log: List[Dict[str, Any]] = []
        self._counter_lock = threading.Lock()

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

    def get_multi_versions_display(self) -> str:
        """展示多版本文稿对比"""
        if not self.multi_versions:
            return "（未生成多版本文稿）"
        lines = ["═══════════════════════════════════════"]
        lines.append("  一文多体 — 版本对比")
        lines.append("═══════════════════════════════════════")
        for label, content in self.multi_versions.items():
            lines.append(f"\n【{label}】（{len(content)} 字）")
            lines.append(f"{content[:300]}...")
        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)

    def get_agent_log_display(self) -> str:
        """展示多智能体协作日志"""
        if not self.agent_log:
            return "（暂无协作日志）"
        lines = ["═══════════════════════════════════════"]
        lines.append("  多智能体协作日志")
        lines.append("═══════════════════════════════════════")
        for entry in self.agent_log:
            lines.append(entry)
        lines.append("═══════════════════════════════════════")
        return "\n".join(lines)

    def _log_agent(self, agent: str, message: str):
        """记录智能体日志"""
        self.agent_log.append(f"  [{agent}] {message}")

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None, max_tokens: int = 8000, history: Optional[List[Dict[str, str]]] = None, use_cache: bool = True) -> str:
        """
        调用 LLM API 生成内容（集成六大 Token 优化策略 + 健壮性机制）

        Args:
            temperature: None 时使用 self.temperature（支持 UI 温度调节，修复语义断裂）
            history: 多轮对话消息列表（由 ContextManager 组装，含 system/user/assistant/工具结果），
                     传入时跳过单轮 prompt 优化与 LRU 缓存，直接按历史调用（工具闭环用）
            use_cache: 是否启用 LLM 响应 LRU 缓存。主稿生成等"每次要全新输出"的调用传 False，
                       避免相同 prompt 直接返回上一次的旧内容；审查/协商等稳定调用保持 True 省 token。
        """
        # 优先使用传入温度，否则用实例温度（修复 temperature 语义断裂）
        if temperature is None:
            temperature = self.temperature
        with self._counter_lock:
            self._api_call_count += 1

        # ── 0. 任务分级路由（Strategy F：按复杂度分类，记录用于统计）──
        from ..utils.token_optimizer import ModelRouter
        task_desc = (system_prompt + user_prompt)[:200]
        task_level = ModelRouter.classify_task(task_desc)
        with self._counter_lock:
            self._task_level_counts = getattr(self, '_task_level_counts', {})
            level_name = task_level.name if hasattr(task_level, 'name') else str(task_level)
            self._task_level_counts[level_name] = self._task_level_counts.get(level_name, 0) + 1

        # ── 1. 配置校验 ──
        config = self.api_manager.config
        if not config.enable or not config.api_key or not config.api_base:
            return self._generate_fallback(system_prompt, user_prompt)

        if history:
            # ── 多轮历史模式：消息已由 ContextManager 组装（含 system），
            #    跳过单轮 prompt 压缩/缓存对齐/LRU，直接按历史调用 ──
            payload = {
                "model": config.model,
                "messages": history,
                "temperature": temperature,
                "max_tokens": min(max_tokens, config.max_tokens),
            }
            return self._do_llm_request(config, payload, system_prompt, user_prompt)

        # ── 2. Prompt 压缩（Strategy A）──
        original_chars = len(system_prompt) + len(user_prompt)
        system_opt, user_opt, stats = self._token_optimizer.optimize_prompt(system_prompt, user_prompt)
        with self._counter_lock:
            self._total_tokens_saved += stats.estimated_input_tokens_saved

        # ── 3. 缓存对齐（Strategy D：静态前置 + 动态后置）──
        self._cache_aligner.check_cache_hit(system_opt)

        # ── 4. LRU 缓存检查（相同 prompt 直接返回；key 含 temperature/model，防止串结果）──
        cache_key = None
        if use_cache:
            cache_key = make_cache_key(system_opt, user_opt, temperature, config.model)
            try:
                cached = cached_prompt("llm_response", cache_key)
                if cached:
                    return cached
            except Exception:
                pass

        # ── 5. API 调用（带重试 + 分类错误处理）──
        payload = {
            "model": config.model,
            "messages": [
                {"role": "system", "content": system_opt},
                {"role": "user", "content": user_opt},
            ],
            "temperature": temperature,
            "max_tokens": min(max_tokens, config.max_tokens),
        }
        return self._do_llm_request(config, payload, system_prompt, user_prompt, cache_key)

    def _do_llm_request(
        self, config, payload: Dict[str, Any], system_prompt: str, user_prompt: str, cache_key: Optional[str] = None
    ) -> str:
        """执行一次 LLM HTTP 请求（重试 + 分类错误处理 + 响应验证 + 缓存）"""
        headers = {
            "Authorization": f"Bearer {config.api_key}",
            "Content-Type": "application/json",
        }
        url = config.api_base.rstrip("/") + "/chat/completions"

        max_retries = 3
        last_error: Optional[str] = None

        for attempt in range(max_retries):
            try:
                response = requests.post(url, headers=headers, json=payload, timeout=config.timeout)

                # ── 分类 HTTP 错误 ──
                if response.status_code == 401:
                    return self._generate_fallback(system_prompt, user_prompt, "API Key 无效或已过期，请在设置中检查")
                if response.status_code == 403:
                    return self._generate_fallback(system_prompt, user_prompt, "API Key 无权限访问该模型")
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        wait = (attempt + 1) * 5
                        time.sleep(wait)
                        continue
                    return self._generate_fallback(system_prompt, user_prompt, "请求频率过高，请稍后重试")
                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(2 ** attempt)
                        continue
                    return self._generate_fallback(system_prompt, user_prompt, "API 服务器内部错误，请稍后重试")

                response.raise_for_status()

                # ── 6. 响应验证 ──
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return self._generate_fallback(system_prompt, user_prompt, "API 返回空结果")

                content = choices[0].get("message", {}).get("content", "")
                if not content or len(content.strip()) < 2:
                    return self._generate_fallback(system_prompt, user_prompt, "API 返回内容为空")

                # 提取 reasoning（如 DeepSeek-R1 的思考链），保存用于调试和教学
                reasoning = choices[0].get("message", {}).get("reasoning_content", "")
                if reasoning:
                    self._llm_reasonings.append({
                        "system_prompt_preview": system_prompt[:200],
                        "reasoning": reasoning,
                    })

                # ── 7. 缓存成功响应（仅单轮模式传入 cache_key）──
                if cache_key:
                    try:
                        store_prompt("llm_response", content, cache_key)
                    except Exception:
                        pass
                return content

            except requests.exceptions.Timeout:
                last_error = f"请求超时（{config.timeout}秒）"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except requests.exceptions.ConnectionError:
                last_error = "无法连接到 API 服务器，请检查网络或 Base URL"
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
            except json.JSONDecodeError:
                last_error = "API 返回的数据格式异常（非有效 JSON）"
                break  # JSON 解析错误不重试
            except Exception as e:
                last_error = str(e)[:200]
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue

        # ── 8. 所有重试失败，优雅降级 ──
        with self._counter_lock:
            self._api_fail_count += 1
        return self._generate_fallback(system_prompt, user_prompt, last_error)

    def _generate_fallback(self, system_prompt: str, user_prompt: str, error_msg: str = "") -> str:
        """LLM 不可用时的占位文本"""
        error_line = f"\n错误信息：{error_msg}\n" if error_msg else "\n"
        return f"""【占位文本 - LLM API 未配置或调用失败】{error_line}
系统已构建以下 Prompt 准备调用 LLM：

写作模式: {get_mode_profile(self.writing_mode).name}
System Prompt:
{system_prompt[:500]}

User Prompt:
{user_prompt[:500]}

请前往「API设置」页面配置 LLM API Key 以生成真实公文。"""

    def get_api_stats(self) -> Dict[str, Any]:
        """获取 API 调用统计与 Token 优化报告"""
        return {
            "api_calls": self._api_call_count,
            "api_failures": self._api_fail_count,
            "tokens_saved": self._total_tokens_saved,
            "cache_stats": self._cache_aligner.get_cache_stats(),
            "optimization_report": self._token_optimizer.get_optimization_report(),
            # Strategy F: 任务分级路由统计
            "task_routing": getattr(self, '_task_level_counts', {}),
        }

    # ═══════════════════════════════════════════════════════════
    # 工具执行（TR板块：解析LLM工具调用并执行，形成闭环）
    # ═══════════════════════════════════════════════════════════

    def _call_llm_with_tool_loop(self, system_prompt: str, user_prompt: str, temperature: Optional[float] = None, max_tokens: int = 8000, max_tool_rounds: int = 3, use_cache: bool = True) -> str:
        """
        工具闭环：调用 LLM，若输出含 [TOOL_CALL: ...] 标记则执行工具，
        并把工具结果经 ContextManager 作为消息回传模型，再次调用 LLM 整合，
        直到输出无工具调用或达到轮次上限。

        修复 N3：工具结果不再内联进稿件，而是回传模型由 LLM 整合；
        修复 1.5：接通 ContextManager 作为多轮对话的消息历史层（build_context 真正被调用）。

        Args:
            max_tool_rounds: 工具调用的最大后续轮次，防止死循环

        Returns:
            LLM 整合后的最终文本（不含工具调用标记）
        """
        # ── 接通 ContextManager：作为本次会话的消息历史层 ──
        self._context_manager.reset()
        self._context_manager.add_message("system", system_prompt)
        self._context_manager.add_message("user", user_prompt)

        from ..config.tool_definitions import parse_tool_call
        result = self._call_llm(system_prompt, user_prompt, temperature=temperature, max_tokens=max_tokens, use_cache=use_cache)

        for _ in range(max_tool_rounds):
            calls = parse_tool_call(result or "")
            if not calls:
                break
            # 记录 LLM 的带工具调用的回复，再回传工具结果
            self._context_manager.add_message("assistant", result or "")
            for tool_name, params in calls:
                tool_result = self._execute_tool_call(tool_name, params)
                self._tool_execution_log.append({
                    "tool": tool_name,
                    "params": params,
                    "result_preview": tool_result[:200],
                    "status": "ok" if tool_result else "empty",
                })
                self._log_agent("Tool", f"执行工具 [{tool_name}] 参数={params} -> 返回 {len(tool_result)} 字")
                self._context_manager.add_message(
                    "user", f"[工具 {tool_name} 执行结果，请基于此结果整合进正文]\n{tool_result}"
                )
            # 基于完整历史再次调用 LLM 整合工具结果
            history = self._context_manager.build_context()
            result = self._call_llm(
                system_prompt, "", temperature=temperature, max_tokens=max_tokens, history=history
            )

        # 防御：若达轮次上限仍残留工具标记，剥离避免污染最终稿件
        if result and "[TOOL_CALL:" in result:
            import re as _re
            result = _re.sub(r'\[TOOL_CALL:[^\]]*\]', '', result)
        return result or ""

    def _execute_tool_call(self, tool_name: str, params: Dict[str, str]) -> str:
        """执行单个工具调用，返回结果文本。工具不可用时返回空字符串。"""
        kb = self._get_knowledge_base()
        try:
            # ── 知识库工具 ──
            if tool_name == "lookup_term":
                term = params.get("term", "")
                info = kb.lookup_term(term) if kb else None
                if not info:
                    return f"未找到术语：{term}"
                return "\n".join([
                    f"定义：{info.get('definition', '')}",
                    f"出处：{info.get('context', '')}",
                    f"使用注意：{info.get('usage_note', '')}",
                    f"常见误用：{info.get('common_misuse', '')}",
                ])
            if tool_name == "search_exemplars":
                mode = params.get("writing_mode", "")
                doc_type = params.get("doc_type", "")
                style = params.get("style", "")
                results = kb.search_exemplars(
                    writing_mode=mode or None,
                    doc_type=doc_type or None,
                    style=style or None,
                ) if kb else []
                if not results:
                    return "未找到匹配的范文"
                lines = []
                for e in results[:3]:
                    lines.append(f"- 《{e.title}》（{e.source}）\n  结构：{e.structure_skeleton}")
                return "\n".join(lines)
            if tool_name == "get_writing_tips":
                doc_type = params.get("doc_type", "")
                style = params.get("style", "")
                tips = kb.get_writing_tips(doc_type, style) if kb else []
                return "\n".join(f"- {t}" for t in tips) if tips else "暂无该文种/风格的写作提示"
            if tool_name == "get_formulaic":
                doc_type = params.get("doc_type", "")
                return kb.get_formulaic_for_prompt(doc_type) if kb else ""
            if tool_name == "get_transitions":
                style = params.get("style", "")
                count = int(params.get("count", "3") or "3")
                phrases = kb.get_transitions(style, count) if kb else []
                return "\n".join(phrases) if phrases else "暂无该风格的过渡词"

            # ── 文种识别工具 ──
            if tool_name == "identify_doc_type":
                from ..questionnaire.questionnaire import WritingBrief as _WB
                brief = _WB(
                    purpose=params.get("purpose", ""),
                    primary_audience=params.get("audience", ""),
                    length_hint=int(params.get("length", "0") or "0"),
                    key_materials=params.get("key_materials", ""),
                )
                ranked = self.doc_identifier.identify(brief)
                lines = []
                for profile, score in ranked[:3]:
                    if score <= 0:
                        continue
                    lines.append(f"- {profile.name_cn}（匹配度{score:.0%}）：{profile.structure_mode}")
                return "\n".join(lines) if lines else "无法确定文种，请补充更多信息"
            if tool_name == "analyze_materials":
                materials = params.get("key_materials", "")
                ratio = self.doc_identifier.analyze_materials(materials)
                return "\n".join(f"{k}: {v:.0%}" for k, v in ratio.items())

            # ── 风格适配工具 ──
            if tool_name == "list_styles":
                styles = self.style_adapter.list_styles() if hasattr(self.style_adapter, "list_styles") else []
                if not styles:
                    return "暂无风格列表"
                return "\n".join(f"- {s}" for s in styles)
            if tool_name == "auto_select_style":
                result = self.style_adapter.auto_select_style(
                    audience=params.get("audience", ""),
                    purpose=params.get("purpose", ""),
                ) if hasattr(self.style_adapter, "auto_select_style") else {}
                if isinstance(result, dict):
                    return f"推荐风格：{result.get('style', result)}"
                return str(result)
            if tool_name == "suggest_style_blend":
                primary = params.get("primary_audience", "")
                purpose = params.get("purpose", "")
                secondary = [s.strip() for s in params.get("secondary_audiences", "").split("|") if s.strip()]
                blend = self.style_adapter.suggest_blend(primary, purpose, secondary or None)
                from ..core.style_adapter import STYLE_PROFILES
                primary_name = STYLE_PROFILES[blend.primary_style].name
                parts = [f"主风格：{primary_name}（{blend.primary_weight:.0%}）"]
                if blend.secondary_style and blend.secondary_weight > 0:
                    secondary_name = STYLE_PROFILES[blend.secondary_style].name
                    parts.append(f"次风格：{secondary_name}（{blend.secondary_weight:.0%}，应用于{blend.secondary_apply_to}）")
                if blend.reasoning:
                    parts.append(f"推理：{blend.reasoning}")
                return "\n".join(parts)

            # ── 个性化数据库工具 ──
            if tool_name == "get_memory_summary":
                # 修复 2.2c：尊重 project_id，从持久化实例读项目记忆，与注入的跨会话记忆合并
                pid = params.get("project_id", "")
                pdb = self._get_pdb()
                db_memory = ""
                if pdb and pid:
                    try:
                        db_memory = pdb.get_memory_summary(pid) or ""
                    except Exception:
                        db_memory = ""
                if self.user_memory and db_memory:
                    return f"{self.user_memory}\n\n【项目记忆】\n{db_memory}"
                return self.user_memory or db_memory or "暂无用户记忆数据"
            if tool_name == "get_style_recommendation":
                # 需要项目ID，从当前上下文取
                pid = params.get("project_id", "")
                rec = {}
                pdb = self._get_pdb()
                if pdb and pid:
                    try:
                        rec = pdb.get_style_recommendation(pid)
                    except Exception:
                        rec = {}
                if not rec:
                    return "暂无风格推荐数据（需要项目ID）"
                lines = []
                if rec.get("suggested_style"):
                    lines.append(f"推荐风格：{rec['suggested_style']}")
                if rec.get("suggested_vocabulary"):
                    lines.append(f"建议词汇：{', '.join(rec['suggested_vocabulary'][:5])}")
                if rec.get("bias_warnings"):
                    lines.append(f"偏见预警：{'; '.join(rec['bias_warnings'][:3])}")
                if rec.get("creative_suggestions"):
                    lines.append(f"创新建议：{'; '.join(rec['creative_suggestions'][:3])}")
                return "\n".join(lines) if lines else "暂无推荐"
            if tool_name == "analyze_weaknesses":
                draft = params.get("draft", self.draft or "")
                pid = params.get("project_id", "")
                if not draft:
                    return "无草稿可分析"
                pdb = self._get_pdb()
                if not pdb:
                    return "个性化数据库不可用，无法分析"
                if not pid:
                    return "未提供项目ID，无法分析"
                try:
                    return pdb.analyze_weaknesses(pid, draft)
                except Exception as e:
                    return f"分析异常：{e}"

            # ── 诊断工具 ──
            if tool_name == "diagnose_text":
                text = params.get("text", self.draft or "")
                if not text:
                    return "无文本可诊断"
                findings = kb.diagnose_text(text) if kb else []
                if not findings:
                    return "未发现文本错误"
                lines = []
                for f in findings[:8]:
                    lines.append(f"- [{f.get('severity', '')}] {f.get('diagnosis', '')} -> {f.get('prescription', '')}")
                return "\n".join(lines)
            if tool_name == "diagnose_format":
                text = params.get("text", self.draft or "")
                if not text:
                    return "无文本可诊断"
                findings = kb.diagnose_format(text) if kb else []
                if not findings:
                    return "格式符合规范"
                lines = []
                for f in findings[:8]:
                    lines.append(f"- [{f.get('severity', '')}] {f.get('diagnosis', '')} -> {f.get('prescription', '')}")
                return "\n".join(lines)

            # ── 导入工具 ──
            if tool_name == "import_from_url":
                url = params.get("url", "")
                if not url:
                    return "请提供URL"
                try:
                    from ..utils.url_importer import URLDocumentImporter
                    importer = URLDocumentImporter()
                    doc = importer.import_from_url(url)
                    if doc.import_notes and "无法" in doc.import_notes:
                        return doc.import_notes
                    parts = [f"标题：{doc.title}", f"来源：{doc.source_site}", f"字数：{doc.word_count}"]
                    if doc.keywords:
                        parts.append(f"关键词：{', '.join(doc.keywords[:5])}")
                    if doc.style_patterns:
                        parts.append(f"语言特征：{', '.join(doc.style_patterns[:3])}")
                    parts.append(f"正文预览：{doc.content[:200]}...")
                    return "\n".join(parts)
                except Exception as e:
                    return f"导入失败：{e}"
            if tool_name == "import_from_text":
                title = params.get("title", "未命名素材")
                content = params.get("content", "")
                if not content:
                    return "请提供文本内容"
                try:
                    from ..utils.url_importer import URLDocumentImporter
                    importer = URLDocumentImporter()
                    doc = importer.import_from_text(title, content, source=params.get("source", "手动导入"))
                    # 如定义了 project_id，同步保存到该项目资料库（修复 N8：真实存储 + 特征提取）
                    pid = params.get("project_id", "")
                    pdb = self._get_pdb()
                    if pdb and pid:
                        try:
                            pdb.add_reference_article(
                                pid,
                                title=doc.title,
                                content=doc.content,
                                style_notes="；".join((doc.style_patterns or [])[:3]),
                            )
                        except Exception:
                            pass
                    fmt = doc.format.value if hasattr(doc.format, "value") else str(doc.format)
                    parts = [f"标题：{doc.title}", f"格式类型：{fmt}", f"字数：{doc.word_count}"]
                    if doc.keywords:
                        parts.append(f"关键词：{', '.join(doc.keywords[:5])}")
                    if doc.style_patterns:
                        parts.append(f"语言特征：{', '.join(doc.style_patterns[:3])}")
                    return "\n".join(parts)
                except Exception as e:
                    return f"导入失败：{e}"

            return ""
        except Exception as e:
            self._log_agent("Tool", f"工具 [{tool_name}] 执行异常: {e}")
            return ""

    def get_tool_execution_log(self) -> List[Dict[str, Any]]:
        """获取工具执行日志（供前端展示）"""
        return self._tool_execution_log

    # ═══════════════════════════════════════════════════════════
    # 审查阶段（模式感知 + 迭代式审查 V2.1 + HITL 循环 V2.2）
    # ═══════════════════════════════════════════════════════════

    def review(self, progress_callback=None, llm_depth_review: bool = True) -> List[Dict[str, Any]]:
        """
        多智能体协作审查流程（V3.1 核心改进：辩论 + LLM 审查真正生效）

        流程：
          1. Writer 自检 + Reviewer 规则审查 + 自动修复
          2. LLM 深度审查（每轮真正调用 LLM）
          3. Writer vs Reviewer 分歧时自动触发辩论
          4. 生成审查总结

        Args:
            progress_callback: 可选进度回调
            llm_depth_review: 是否启用 LLM 深度审查（默认 True）
        """
        def _notify(progress, desc):
            if progress_callback:
                progress_callback(progress, desc)

        if not self.draft:
            raise ValueError("请先调用write()生成初稿")

        try:
            self.reviewer.set_mode(self.writing_mode)
            self.review_results = []

            self._log_agent("系统", "开始多轮迭代审查（规则诊断 + LLM 深度审查）")

            # 更新 coordinator 上下文
            mode_value = self.writing_mode.value if hasattr(self.writing_mode, 'value') else str(self.writing_mode)
            self.coordinator.set_context(
                raw_materials="",  # 审查阶段不再关注原始素材
                writing_mode=mode_value,
                draft_word_count=len(self.draft) if self.draft else 0,
                has_style_conflict=self._detect_style_conflict(),
            )

            # 第1步：规则诊断 + 自动修复
            original_draft = self.draft
            review_env_text = self._build_env_state(
                "审查阶段：规则引擎逐轮诊断并自动修复，随后进行 LLM 深度审查。"
            ).render(exclude_fields=["purpose", "primary_audience", "length_hint"])
            final_draft, iteration_results = self.reviewer.iterate_review(
                draft=original_draft,
                mode=self.writing_mode,
                brief=self.brief,
                env_state=review_env_text,
            )

            if final_draft != original_draft:
                self.draft = final_draft
                self._log_agent("Reviewer", f"规则修复完成，草稿从 {len(original_draft)} 字 → {len(final_draft)} 字")

            # 第2步：LLM 真迭代审查 — 审→改→审 闭环
            if llm_depth_review:
                _notify(0.4, "LLM 迭代审查中（审→改→审）...")
                iteration_results = self._run_llm_iterative_review(iteration_results)

            # 第3步：检测 Writer 与 Reviewer 分歧，触发辩论（共识落实到稿件）
            _notify(0.7, "检测Agent分歧，必要时启动辩论...")
            debate_triggered, _ = self._check_and_run_debate(iteration_results)
            if debate_triggered:
                self._log_agent("Debater", "辩论完成，已达成共识并记录")

            # 更新最终审查结果
            self.review_results = self.reviewer.review_history
            self.review_summary_display = self._build_review_summary_display(iteration_results)
            self._last_iteration_results = iteration_results

            self._log_agent("系统", f"审查完成，共 {len(iteration_results)} 轮（含 {'AI深度审查' if llm_depth_review else '规则审查'}）")

            if self._on_review_done:
                self._on_review_done(iteration_results)

            return iteration_results
        except Exception as e:
            self.state = OrchestratorState.ERROR
            self._log_agent("系统", f"审查流程异常: {e}")
            return []

    def _build_llm_review_prompt(
        self,
        draft: str,
        iteration_count: int,
        version: int,
        auto_findings: List[Dict[str, Any]],
    ) -> str:
        """构建 LLM 深度审查的 system prompt（核心提示词 + 环境状态 + 记忆 + 工具清单 + 审查员指令）"""
        from ..config.tool_definitions import get_tool_definitions_for_prompt
        from ..config.system_prompt import get_core_prompt
        # 1.4：注入迭代维度（总轮数/当前版本/上一轮问题），避免重复报告同一问题
        env_state = self._build_env_state(
            "审查阶段：按当前模式的多维标准逐轮检查稿件，针对上一轮发现的问题持续改进。"
        )
        env_state.iteration_count = iteration_count
        env_state.draft_version = version
        env_state.previous_issues = "；".join(
            str(f.get("diagnosis", "")) for f in (auto_findings or [])[:5]
        )
        env_text = env_state.render(exclude_fields=["purpose", "primary_audience", "length_hint"])
        # 1.3：审查只注入"常见错误"类记忆，避免偏好信息干扰审查标准
        memory_text = ""
        pdb = self._get_pdb()
        if pdb:
            try:
                mem = pdb.get_memory_summary(None, focus="errors")
                if mem and mem != "无用户数据":
                    memory_text = mem
            except Exception:
                pass
        memory_text = memory_text or self.user_memory or "（暂无历史记忆）"
        return (
            get_core_prompt()
            + "\n\n# 环境状态（审查阶段）\n" + env_text
            + "\n\n# 用户历史常见错误（审查时针对性核对，不要生硬提及）\n" + memory_text
            + "\n\n# 审查员专属指令\n"
            "你是公文审查员。按给定维度逐段检查稿件，标注问题位置、严重程度和修改建议。"
            "审查标准按文体区分：法定公文查格式规范（GB/T 9704-2012）和语言四要求（准确、简明、朴实、得体），"
            "新闻通讯查主体性和叙事质量，事务文书查信息完整性和结构，新媒体查话语方式。"
            "发现问题要具体：指出哪一段哪一句，说明为什么是问题，给出修改方向。不要泛泛而谈。"
            "\n\n可调用工具（需要查术语定义、范文、格式化用语、文种规范时，在输出末尾追加工具调用标记）：\n"
            + get_tool_definitions_for_prompt(phases=["during_writing", "post_writing"])
            + "\n工具调用标记格式：[TOOL_CALL: 工具名(参数=值, 参数=值)]\n"
            "\n\n输出格式（每个问题一段）：\n"
            "问题1：<问题描述>\n"
            "  位置：<哪一段/哪一句>\n"
            "  严重程度：<严重/重要/轻微>\n"
            "  建议：<修改方向>\n"
            "（没有问题时输出：无问题）"
        )

    def _llm_revise_draft(self, draft: str, instruction: str) -> str:
        """
        让主笔 LLM 基于审查意见/辩论共识修订稿件，返回修订后的完整文本。

        返回空串表示修订失败或修订无变化（调用方保留原稿，防死循环）。
        """
        if not draft or not instruction:
            return ""
        from ..config.system_prompt import get_core_prompt
        system_prompt = (
            get_core_prompt()
            + "\n\n# 修订员专属指令\n"
            "你是主笔（Writer Agent）。请基于给定的修订指令对稿件进行修订："
            "逐条采纳合理的意见，保留原稿的合理内容与风格，"
            "输出修订后的完整稿件。只输出正文，不要输出任何说明、列表或元信息。"
        )
        user_prompt = f"## 修订指令\n{instruction}\n\n## 当前稿件\n{draft}"
        try:
            revised = self._call_llm_with_tool_loop(
                system_prompt, user_prompt, temperature=0.4, max_tokens=8000, use_cache=False
            )
            # 防死循环/防降级污染：修订无变化或 LLM 降级占位输出均视为未修改
            if not revised or revised.strip() == draft.strip():
                return ""
            if "【占位文本" in revised or "API 未配置" in revised:
                return ""
            return revised
        except Exception:
            return ""

    def _run_llm_iterative_review(
        self,
        iteration_results: List[Dict[str, Any]],
        max_llm_rounds: int = 3,
    ) -> List[Dict[str, Any]]:
        """
        LLM 真迭代审查闭环：审→改→审

        以规则 iterate_review 的最终稿为起点：
          每轮：LLM 审查当前稿 → 无严重问题则停 → 否则 LLM 修订 → 再审修订版
        审查发现会触发新一轮修复（替代原"循环后并行审查、结果仅存储"的假迭代）。

        注意：循环有早停（无"严重/重要"问题即停），实际通常只消耗 1 轮；
        上限 3 轮仅在连续多轮仍有阻塞问题时才会用满，用于收敛顽固问题。

        Args:
            iteration_results: 规则 iterate_review 的轮次结果
            max_llm_rounds: LLM 迭代轮数上限（默认 3，有早停，控制成本）

        Returns:
            更新后的 iteration_results（在原列表上追加 LLM 迭代轮信息）
        """
        if not self.draft:
            return iteration_results

        current_draft = self.draft
        total_rounds = len(iteration_results)
        last_rule_findings = (
            iteration_results[-1].get("auto_findings_summary", [])
            if iteration_results else []
        )

        for r in range(max_llm_rounds):
            # 1. LLM 审查当前稿
            reviewer_system = self._build_llm_review_prompt(
                current_draft, total_rounds + r, total_rounds + r + 1, last_rule_findings
            )
            base_prompt = self.reviewer.build_review_prompt(current_draft, 0, self.brief)
            if not base_prompt:
                break
            full_prompt = f"{base_prompt}\n\n请按要求的格式输出审查结果。"
            # TR板块：审查阶段工具闭环（执行工具并把结果回传模型整合）
            raw = self._call_llm_with_tool_loop(reviewer_system, full_prompt, temperature=0.3, max_tokens=4000)
            parsed = self._parse_llm_review(raw)

            llm_round = {
                "round": f"LLM迭代审查第{r+1}轮",
                "draft_snapshot": current_draft,
                "findings_count": len(parsed),
                "auto_findings_summary": [],
                "fixes_applied": 0,
                "review_prompt": full_prompt,
                "passed": len(parsed) == 0,
                "llm_review": {"raw_response": raw, "parsed_findings": parsed, "round": f"LLM第{r+1}轮"},
            }
            self._log_agent("Reviewer", f"LLM迭代第{r+1}轮：发现 {len(parsed)} 个问题")

            # 2. 无阻塞问题（严重/重要）或达轮次上限 → 停
            has_blocking = any(f.get("severity") in ("严重", "重要") for f in parsed)
            if not has_blocking or r == max_llm_rounds - 1:
                iteration_results.append(llm_round)
                break

            # 3. LLM 基于审查发现修订稿件（真正的"改"）
            instruction_lines = []
            for f in parsed[:5]:
                instruction_lines.append(f"- [{f.get('severity', '')}] {f.get('issue', '')}")
                if f.get("location"):
                    instruction_lines.append(f"  位置：{f['location']}")
                if f.get("suggestion"):
                    instruction_lines.append(f"  建议：{f['suggestion']}")
            instruction = "请针对以下审查意见修订稿件：\n" + "\n".join(instruction_lines)
            revised = self._llm_revise_draft(current_draft, instruction)
            if not revised:
                iteration_results.append(llm_round)
                break

            llm_round["llm_revision"] = revised
            current_draft = revised
            self.draft = revised
            iteration_results.append(llm_round)
            self._log_agent("Writer", f"LLM迭代第{r+1}轮修订完成（{len(revised)} 字）")

        return iteration_results

    def _parse_llm_review(self, raw: str) -> List[Dict[str, str]]:
        """
        将 LLM 审查的原始文本解析为结构化问题列表。

        兼容两种格式：
        1. 规范格式（prompt中要求）：
           问题1：<问题描述>
             位置：<哪一段/哪一句>
             严重程度：<严重/重要/轻微>
             建议：<修改方向>
        2. 自由文本：按行智能拆分，尽力提取位置/严重程度/建议
        """
        if not raw or "无问题" in raw.strip():
            return []
        # LLM 不可用的降级/占位文本不应被当作审查发现（避免污染审查结果）
        if "【占位文本" in raw or "API 未配置" in raw:
            return []

        findings = []
        lines = raw.strip().splitlines()
        current = {}
        import re

        # 正则：匹配"问题N：..."或"- 问题：..."或"问题：..."
        problem_pattern = re.compile(r'^\s*(?:问题\s*\d*\s*[：:]\s*|\d+[、.．]\s*)')
        location_pattern = re.compile(r'^\s*(?:位置|出处|在哪|哪一段|哪一句)\s*[：:]\s*(.+)$')
        severity_pattern = re.compile(r'^\s*(?:严重程度|严重性|程度)\s*[：:]\s*(.+)$')
        suggestion_pattern = re.compile(r'^\s*(?:建议|修改建议|如何改|修改方向|建议修改)\s*[：:]\s*(.+)$')

        def flush():
            if current and current.get("issue"):
                findings.append(current.copy())
            current.clear()

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 严重程度行
            m = severity_pattern.match(line)
            if m:
                current["severity"] = m.group(1).strip()
                continue

            # 位置行
            m = location_pattern.match(line)
            if m:
                current["location"] = m.group(1).strip()
                continue

            # 建议行
            m = suggestion_pattern.match(line)
            if m:
                current["suggestion"] = m.group(1).strip()
                continue

            # 问题行（新问题开始）
            if problem_pattern.match(line) or line.startswith("问题"):
                flush()
                issue_text = re.sub(r'^\s*问题\s*\d*\s*[：:]\s*', '', line)
                issue_text = re.sub(r'^\s*\d+[、.．]\s*', '', issue_text)
                current = {"issue": issue_text}
                continue

            # 普通行：追加到当前问题的描述或建议
            if current:
                if current.get("suggestion"):
                    current["suggestion"] += line
                elif current.get("issue"):
                    # 无标签的后续行，归入问题描述
                    current["issue"] += line

        flush()

        # 兜底：解析不出结构化问题时返回空（宁缺毋滥），
        # 避免把 LLM 的自由输出或降级文本误当作审查发现
        if not findings:
            return []

        # 补全缺失字段
        for f in findings:
            f.setdefault("severity", "轻微")
            f.setdefault("location", "")
            f.setdefault("suggestion", "")
        return findings

    def _check_and_run_debate(
        self, iteration_results: List[Dict[str, Any]]
    ) -> Tuple[bool, str]:
        """
        检测审查结果中是否存在 Writer 与 Reviewer 的分歧，
        如果发现问题较多且未通过，自动触发辩论，并把辩论共识落实到稿件修订。

        Returns:
            (是否触发辩论, 共识文本)。触发且达成共识时，self.draft 已按共识修订。
        """
        total_findings = sum(ir.get("findings_count", 0) for ir in iteration_results)
        failed_rounds = sum(1 for ir in iteration_results if not ir.get("passed", True))

        # 触发条件：未通过轮次 >= 2 或 发现问题 >= 5
        if failed_rounds < 2 and total_findings < 5:
            return False, ""

        # 构建双方立场
        writer_position = (
            f"撰写方认为：文稿基本符合要求，{total_findings}个问题中大部分属于格式修正。"
            f"建议在保持内容完整性的前提下，选择性采纳审查意见。"
        )
        reviewer_position = (
            f"审查方认为：发现{total_findings}个问题，{failed_rounds}轮未通过。"
            f"这些问题影响文稿质量和合规性，建议全部修正后再定稿。"
        )

        try:
            debate_result = self.coordinator.run_debate(
                topic=f"审查分歧：{total_findings}个问题待决议",
                writer_position=writer_position,
                reviewer_position=reviewer_position,
                max_rounds=1,
                llm_call=self._call_llm,
            )
            # 安全访问 consensus（可能是 str 或 dict）
            consensus_text = debate_result.consensus if isinstance(debate_result.consensus, str) else str(debate_result.consensus)
            self._log_agent("Debater", f"辩论共识: {consensus_text[:150]}")

            # 共识闭环：基于共识修订稿件，让辩论结果真正作用于内容
            if consensus_text and consensus_text.strip() and consensus_text != "None":
                instruction = f"以下是审查分歧的辩论共识，请据此修订稿件：\n{consensus_text}"
                revised = self._llm_revise_draft(self.draft, instruction)
                if revised:
                    self.draft = revised
                    self._log_agent("Debater", f"已按辩论共识修订稿件（{len(revised)} 字）")

            return True, consensus_text
        except Exception as e:
            self._log_agent("Debater", f"辩论异常: {e}")
            return False, ""

    def _build_review_summary_display(self, iteration_results: List[Dict[str, Any]]) -> str:
        """构建审查总结的展示文本"""
        lines = ["【审查结果】"]
        for i, result in enumerate(self.reviewer.review_history):
            status = "✅ 通过" if result.passed else "❌ 未通过"
            lines.append(f"\n第{i+1}轮 {result.round_name}：{status}")
            if result.findings:
                for finding in result.findings:
                    lines.append(f"  • {finding.severity.value}: {finding.issue}")
                    if finding.suggestion:
                        lines.append(f"    建议：{finding.suggestion}")
            else:
                lines.append("  （无问题）")

        # 添加迭代结果信息
        lines.append("\n【迭代统计】")
        for i, ir in enumerate(iteration_results):
            lines.append(f"  第{i+1}轮 [{ir['round']}]: 发现 {ir['findings_count']} 个问题，修复 {ir['fixes_applied']} 个")
            # 草稿快照对比：展示修复前后的字数变化
            snapshot = ir.get("draft_snapshot", "")
            if snapshot and self.draft:
                lines.append(f"    📝 草稿变化：{len(snapshot)}字 → 修复后逐轮迭代")
            if ir.get("llm_review"):
                llm_data = ir["llm_review"]
                if "raw_response" in llm_data:
                    parsed = llm_data.get("parsed_findings", [])
                    lines.append(f"    🤖 AI深度审查: 发现 {len(parsed)} 个问题")
                    # 展示AI审查的具体发现摘要（前2条）
                    for pf in parsed[:2]:
                        issue_preview = pf.get("issue", "")[:60]
                        lines.append(f"       • {pf.get('severity', '')}: {issue_preview}")
                elif "error" in llm_data:
                    lines.append(f"    ⚠️ AI审查异常: {llm_data['error'][:80]}")

        # AI思考链摘要（教学价值：让用户看到AI审查的推理过程）
        if self._llm_reasonings:
            lines.append(f"\n【AI审查思考摘要】（共{len(self._llm_reasonings)}条，用于理解审查逻辑）")
            for i, r in enumerate(self._llm_reasonings[-3:], 1):  # 最近3条
                reasoning_preview = r.get("reasoning", "")[:150].replace("\n", " ")
                lines.append(f"  思考{i}: {reasoning_preview}...")

        # 添加协调统计
        coordination = self.coordinator.get_coordination_report()
        lines.append(f"\n【协同统计】")
        lines.append(f"  消息总数: {coordination['communication_stats']['total_messages']}")
        lines.append(f"  协商次数: {coordination['consultations']}")
        lines.append(f"  辩论次数: {coordination['debates']}")
        lines.append(f"  主动预警: {coordination['proactive_alerts']}")

        return "\n".join(lines)

    def get_review_issues(self) -> List[Dict[str, Any]]:
        """获取当前审查中发现的所有问题（供 HITL 展示，含规则引擎与 LLM 深度审查）"""
        issues = []
        for i, summary in enumerate(self.reviewer.review_history):
            round_name = summary.round_name
            for finding in summary.findings:
                issues.append({
                    "round_index": i,
                    "round_name": round_name,
                    "draft_version": getattr(summary, 'draft_version', i + 1),
                    "source": "规则引擎",
                    "severity": finding.severity.value,
                    "issue": finding.issue,
                    "location": finding.location,
                    "suggestion": finding.suggestion,
                    "original_text": finding.original_text,
                    "suggested_revision": finding.suggested_revision,
                })

        # 合并 LLM 深度审查的结构化发现（parsed_findings）
        if self._last_iteration_results:
            for i, ir in enumerate(self._last_iteration_results):
                llm_data = ir.get("llm_review") or {}
                parsed = llm_data.get("parsed_findings") or []
                if not parsed:
                    continue
                round_name = ir.get("round", f"第{i+1}轮")
                for f in parsed:
                    issues.append({
                        "round_index": i,
                        "round_name": f"{round_name}（AI深度审查）",
                        "draft_version": i + 1,
                        "source": "AI深度审查",
                        "severity": f.get("severity", "轻微"),
                        "issue": f.get("issue", ""),
                        "location": f.get("location", ""),
                        "suggestion": f.get("suggestion", ""),
                        "original_text": "",
                        "suggested_revision": "",
                    })
        return issues

    def apply_manual_fix(self, round_index: int, finding_index: int) -> str:
        """手动触发对某个问题的自动修复，返回修复后的草稿"""
        if round_index >= len(self.reviewer.review_history):
            raise ValueError(f"审查轮次 {round_index} 不存在")
        result = self.reviewer.review_history[round_index]
        if finding_index >= len(result.findings):
            raise ValueError(f"问题索引 {finding_index} 不存在")
        finding = result.findings[finding_index]
        self.draft = self.reviewer._apply_fix(
            self.draft,
            {
                "error_key": finding.error_key,
                "matched_pattern": finding.original_text,
                "prescription": finding.suggestion,
                "severity": finding.severity.value,
            }
        )
        return self.draft

    def re_review(self, llm_depth_review: bool = True) -> List[Dict[str, Any]]:
        """
        在用户手动修改草稿后，重新执行审查（V3.1：与 review() 对齐）

        Args:
            llm_depth_review: 是否启用 LLM 深度审查（默认 True）
        """
        if not self.draft:
            raise ValueError("当前无草稿可审查")

        self.reviewer.set_mode(self.writing_mode)
        self.review_results = []

        # 更新 coordinator 上下文
        mode_value = self.writing_mode.value if hasattr(self.writing_mode, 'value') else str(self.writing_mode)
        self.coordinator.set_context(
            raw_materials="",
            writing_mode=mode_value,
            draft_word_count=len(self.draft),
            has_style_conflict=self._detect_style_conflict(),
        )

        self._log_agent("系统", "重新执行审查（规则诊断 + LLM 深度审查）")
        original_draft = self.draft
        self.draft, iteration_results = self.reviewer.iterate_review(
            draft=original_draft,
            mode=self.writing_mode,
            brief=self.brief,
        )

        if self.draft != original_draft:
            self._log_agent("Reviewer", f"重新修复完成，{len(original_draft)} 字 -> {len(self.draft)} 字")

        # LLM 真迭代审查（审→改→审）
        if llm_depth_review:
            iteration_results = self._run_llm_iterative_review(iteration_results)

        # 分歧检测与辩论（共识落实到稿件）
        self._check_and_run_debate(iteration_results)

        self.review_results = self.reviewer.review_history
        self.review_summary_display = self._build_review_summary_display(iteration_results)
        self._last_iteration_results = iteration_results

        if self._on_review_done:
            self._on_review_done(iteration_results)
        return iteration_results

    def update_draft(self, new_draft: str):
        """用户手动替换草稿"""
        self.draft = new_draft

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
            "llm_reasonings": self._llm_reasonings,
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

    def get_workflow_summary(self) -> str:
        if not self.brief:
            return "⚠️ 工作流尚未启动。请调用start_routing()开始。"

        # 使用列表收集字符串片段，最后一次性 join，避免多次字符串拼接的内存开销
        parts = [
            "═══════════════════════════════════════════",
            "  工 作 流 摘 要",
            "═══════════════════════════════════════════\n",
            f"【状态】{self.state.value}\n",
            f"【写作模式】{get_mode_profile(self.writing_mode).name}\n",
        ]

        if self.brief:
            purpose = self.brief.purpose or "未指定"
            audience = self.brief.primary_audience or "未指定"
            deep = self.brief.deep_meaning or "未指定"

            parts.append("【写作简报】")
            parts.append(f"  核心目的：{purpose[:80]}{'...' if len(purpose) > 80 else ''}")
            parts.append(f"  第一读者：{audience}")
            parts.append(f"  深层含义/核心发现：{deep[:60]}{'...' if len(deep) > 60 else ''}\n")

        if self.plan:
            parts.append("【写作方案】")
            parts.append(f"  文种：{self.plan.doc_type_name}")
            parts.append(f"  风格：{self.plan.style_name}")
            parts.append(f"  篇幅：{self.plan.estimated_length}")
            parts.append(f"  受众：{self.plan.audience_focus}\n")

        if self.draft:
            parts.append("【初稿状态】已生成\n")

        if self.review_results:
            passed_count = sum(1 for r in self.review_results if r.passed)
            parts.append(f"【审查结果】{passed_count}/{len(self.review_results)} 轮通过")
            parts.append(f"【审查维度】{', '.join(r.round_name for r in self.review_results)}")

        parts.append("═══════════════════════════════════════════")
        return "\n".join(parts)
