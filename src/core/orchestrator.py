"""
协调者 Agent — 多Agent调度的总指挥（V2：模式感知版）

核心改进：
1. 问卷阶段新增决策树路由分流，支持四模式
2. 写作方案展示写作模式信息
3. 审查轮次根据模式动态切换
4. 兼容旧版API（默认 STRATEGIC_NARRATIVE）

工作流：
  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
  │ 决策树路由│ → │ 模式问卷 │ → │ 规划方案 │ → │ 写作+审查 │
  └──────────┘    └──────────┘    └──────────┘    └──────────┘
       │                │                │                │
       ▼                ▼                ▼                ▼
  确定WritingMode  WritingBrief   HITL-1确认     HITL-2输出
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, Tuple
from enum import Enum

from ..questionnaire.questionnaire import (
    Questionnaire, WritingBrief,
    QuestionnairePhase,
)
from .style_adapter import (
    StyleAdapter, MediaStyle, StyleProfile, STYLE_PROFILES
)
from .document_type import (
    DocumentTypeIdentifier, DocumentType, DocTypeProfile, DOC_TYPE_PROFILES
)
from .writer_agent import WriterAgent, WriterConfig
from .reviewer_agent import ReviewerAgent, ReviewResult
from .agent_coordinator import AgentCoordinator, AgentRole
from .multi_doc_generator import MultiDocGenerator
from .writing_mode import (
    WritingMode,
    ALL_PRINCIPLES,
    get_mode_profile,
    get_review_dimensions,
    get_mode_description,
)


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

    def __init__(self):
        self.questionnaire = Questionnaire()
        self.style_adapter = StyleAdapter()
        self.doc_identifier = DocumentTypeIdentifier()
        self.writer = WriterAgent()
        self.reviewer = ReviewerAgent()
        self.coordinator = AgentCoordinator()
        self.multi_doc_gen = MultiDocGenerator()
        
        # 复用 API 配置管理器实例，避免每次调用都重新加载配置
        from ..config.api_config import APIConfigManager
        self.api_manager = APIConfigManager()

        self.state = OrchestratorState.IDLE
        self.brief: Optional[WritingBrief] = None
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
        self._on_complete: Optional[Callable] = None

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
            self.writing_mode = WritingMode(result["mode"])
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

        self.questionnaire._mode_questions = getattr(
            self.questionnaire, '_mode_questions', []
        ) or []
        self.questionnaire.phase = QuestionnairePhase.MODE_QUESTIONS
        self.questionnaire._mode_question_index = 0

        return None

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

    def write(self, raw_materials: str = "") -> str:
        """
        多智能体协作写作流程（V3 核心改进）

        流程：
          1. 注册所有 Agent 到 Coordinator
          2. 多智能体协商确定写作方案
          3. 使用 MultiDocGenerator 生成多版本文稿（通讯/消息/简报）
          4. 返回主版本，其他版本存入 multi_versions
        """
        if not self.plan:
            raise ValueError("请先调用generate_plan()生成写作方案")

        self.state = OrchestratorState.WRITING
        self.agent_log = []
        self.multi_versions = {}

        # 第1步：Writer 配置
        config = WriterConfig(
            writing_brief=self.brief,
            style_profile=STYLE_PROFILES[self.plan.media_style],
            doc_type_profile=DOC_TYPE_PROFILES[self.plan.document_type],
            raw_materials=raw_materials,
            audience=self.plan.audience_focus,
            writing_mode=self.writing_mode,
        )
        self.writer.configure(config)

        self._log_agent("系统", f"写作模式: {get_mode_profile(self.writing_mode).name}")
        self._log_agent("系统", f"文种: {self.plan.doc_type_name}, 风格: {self.plan.style_name}")

        # 第2步：多智能体协商（民主协商机制）
        # 传递完整的 plan 信息，确保语义完整性，避免摘要引入 bias
        context_info = {
            "brief": str(self.brief) if self.brief else "",
            "plan": self.plan.display(),
            "writing_mode": self.writing_mode.value,
        }
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
        warnings = self.coordinator.collect_proactive_reports()
        for w in warnings:
            self._log_agent(f"{w.get('agent', 'Agent')} 预警", w.get("alert", ""))

        # 第4步：生成主版本（Writer Agent）
        system_prompt = self.writer.build_system_prompt()
        user_prompt = self.writer.build_user_prompt()

        self.draft = self._call_llm(system_prompt, user_prompt)
        if self.draft:
            self._log_agent("Writer", f"初稿已生成（{len(self.draft)} 字）")
        else:
            self._log_agent("Writer", "初稿生成失败，返回空内容")

        # 第4步：一文多体生成（MultiDocGenerator）
        self._generate_multi_versions()

        self.state = OrchestratorState.REVIEWING

        if self._on_draft_ready:
            self._on_draft_ready(self.draft)

        return self.draft

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

    def _call_llm(self, system_prompt: str, user_prompt: str, temperature: float = 0.7, max_tokens: int = 8000) -> str:
        """调用 LLM API 生成内容"""
        try:
            config = self.api_manager.config
            if not config.enable or not config.api_key or not config.api_base:
                return self._generate_fallback(system_prompt, user_prompt)

            import requests
            headers = {
                "Authorization": f"Bearer {config.api_key}",
                "Content-Type": "application/json",
            }
            payload = {
                "model": config.model,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                "temperature": config.temperature,
                "max_tokens": config.max_tokens,
            }
            url = config.api_base.rstrip("/") + "/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=config.timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                return content

            return self._generate_fallback(system_prompt, user_prompt)

        except Exception as e:
            return f"LLM API 调用失败：{e}\n\n--- 使用占位文本 ---\n\n{self._generate_fallback(system_prompt, user_prompt)}"

    def _generate_fallback(self, system_prompt: str, user_prompt: str) -> str:
        """LLM 不可用时的占位文本"""
        return f"""【占位文本 — LLM API 未配置】

系统已构建以下 Prompt 准备调用 LLM：

写作模式: {get_mode_profile(self.writing_mode).name}
System Prompt:
{system_prompt[:500]}

User Prompt:
{user_prompt[:500]}

请前往「API配置」页面配置 LLM API Key 以生成真实公文。"""

    # ═══════════════════════════════════════════════════════════
    # 审查阶段（模式感知 + 迭代式审查 V2.1 + HITL 循环 V2.2）
    # ═══════════════════════════════════════════════════════════

    def review(self) -> List[Dict[str, Any]]:
        """
        多智能体协作审查流程（V3 核心改进）

        流程：
          1. Writer 自检 + Reviewer 审查 + Debater 辩论
          2. 多轮 LLM 迭代审查
          3. 生成审查总结
        """
        if not self.draft:
            raise ValueError("请先调用write()生成初稿")

        self.reviewer.set_mode(self.writing_mode)
        self.review_results = []

        self._log_agent("系统", "开始多轮迭代审查")

        # 第1步：Reviewer 执行迭代审查（规则诊断 + 自动修复）
        original_draft = self.draft
        final_draft, iteration_results = self.reviewer.iterate_review(
            draft=original_draft,
            mode=self.writing_mode,
            brief=self.brief,
        )

        # 更新草稿为修复后的版本
        if final_draft != original_draft:
            self.draft = final_draft
            self._log_agent("Reviewer", f"自动修复完成，草稿从 {len(original_draft)} 字 → {len(final_draft)} 字")

        # 第2步：LLM 深度审查（对每轮审查结果用 LLM 生成详细报告）
        self.review_results = self.reviewer.review_history
        self.review_summary_display = self._build_review_summary_display(iteration_results)

        self._log_agent("系统", f"审查完成，共 {len(iteration_results)} 轮")

        if self._on_review_done:
            self._on_review_done(iteration_results)

        return iteration_results

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

        return "\n".join(lines)

    def get_review_issues(self) -> List[Dict[str, Any]]:
        """获取当前审查中发现的所有问题（供 HITL 展示）"""
        issues = []
        for i, summary in enumerate(self.reviewer.review_history):
            round_name = summary.round_name
            for finding in summary.findings:
                issues.append({
                    "round_index": i,
                    "round_name": round_name,
                    "severity": finding.severity.value,
                    "issue": finding.issue,
                    "location": finding.location,
                    "suggestion": finding.suggestion,
                    "original_text": finding.original_text,
                    "suggested_revision": finding.suggested_revision,
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
                "error_key": finding.round_name,
                "matched_pattern": finding.original_text,
                "prescription": finding.suggestion,
                "severity": finding.severity.value,
            }
        )
        return self.draft

    def re_review(self) -> List[Dict[str, Any]]:
        """在用户手动修改草稿后，重新执行审查"""
        if not self.draft:
            raise ValueError("当前无草稿可审查")
        self.reviewer.set_mode(self.writing_mode)
        self.review_results = []
        original_draft = self.draft
        self.draft, iteration_results = self.reviewer.iterate_review(
            draft=original_draft,
            mode=self.writing_mode,
            brief=self.brief,
        )
        self.review_results = self.reviewer.review_history
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
