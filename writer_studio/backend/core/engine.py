"""工作流引擎 —— 显式状态机 + 事件发射（SSE 载荷）。

P1 为规则版全链路（无 LLM，诚实标注 mode="rule"）；
P2 接入 LLM 后各阶段走真实 LLM 并标注 mode="llm"。
"""
import time
from enum import Enum

from ..domain.registry import Registry
from ..domain.schemas import Brief, Plan, Project, ProjectStatus, WorkflowEvent
from . import brief as brief_mod
from . import doctype, multi_doc, review, style


class EngineState(str, Enum):
    IDLE = "idle"
    ROUTING = "routing"
    QUESTIONING = "questioning"
    PLANNING = "planning"
    WAITING_APPROVAL = "waiting_approval"
    WRITING = "writing"
    REVIEWING = "reviewing"
    COMPLETED = "completed"
    ERROR = "error"


class WorkflowEngine:
    """驱动单个项目的完整工作流，事件经 `events` 列表暴露（供 SSE 推送）。"""

    def __init__(self, project: Project, llm=None):
        self.project = project
        self.state = EngineState.IDLE
        self.events: list = []
        self._seq = 0
        self._routing_node = "root"
        self._questions: list = []
        self._q_index = 0
        self.brief = Brief()
        self.plan = Plan()
        self.mode = ""
        self.llm = llm  # LLMClient 或 None

    @property
    def llm_available(self) -> bool:
        return bool(self.llm and self.llm.available)

    # ── 事件 ──
    def _emit(self, type_: str, step: str, payload: dict = None) -> WorkflowEvent:
        self._seq += 1
        ev = WorkflowEvent(seq=self._seq, type=type_, step=step, payload=payload or {}, ts=time.time())
        self.events.append(ev)
        return ev

    def _error(self, msg: str):
        self.state = EngineState.ERROR
        self._emit("error", "error", {"message": msg})

    # ── 路由 / 问卷 ──
    def start(self):
        self.state = EngineState.ROUTING
        q = brief_mod.routing_question("root")
        self._emit("routing", "routing", q)
        return q

    def answer(self, text: str):
        """统一作答入口，按状态分发。路由阶段传选项索引，问卷阶段传答案文本。"""
        if self.state == EngineState.ROUTING:
            return self._answer_routing(text)
        if self.state == EngineState.QUESTIONING:
            return self._answer_question(text)
        raise RuntimeError(f"当前状态 {self.state.value} 不接受作答")

    def _answer_routing(self, choice: str):
        try:
            idx = int(choice)
        except ValueError:
            self._error("路由选择必须是选项编号")
            return None
        try:
            next_node, result = brief_mod.submit_routing(self._routing_node, idx)
        except ValueError as e:
            self._error(str(e))
            return None
        if result:  # 路由完成 → 进入问卷
            self.mode = result["mode"]
            self.brief.writing_mode = self.mode
            self.brief.subtype = result["subtype"]
            self._emit("routing_complete", "routing", result)
            self.state = EngineState.QUESTIONING
            self._questions = brief_mod.mode_questions(self.mode)
            self._q_index = 0
            return self._next_question()
        self._routing_node = next_node
        q = brief_mod.routing_question(next_node)
        self._emit("routing", "routing", q)
        return q

    def _next_question(self):
        if self._q_index < len(self._questions):
            q = dict(self._questions[self._q_index])
            q["index"] = self._q_index + 1
            q["total"] = len(self._questions)
            self._emit("question", "questioning", q)
            return q
        return None

    def _answer_question(self, answer: str):
        if self._q_index < len(self._questions):
            brief_mod.apply_answer(self.brief, self._questions[self._q_index]["id"], answer)
            self._q_index += 1
        if self._q_index >= len(self._questions):
            self.state = EngineState.PLANNING
            return self._make_plan()
        return self._next_question()

    # ── 规划 ──
    def _make_plan(self):
        ranked = doctype.identify_doc_type(self.brief)
        doc_type_id = ranked[0][0]
        style_id = style.auto_select_style(self.brief, doc_type_id)
        doc = Registry.by_id("doctypes", doc_type_id)
        style_match = style.check_style_doc_match(style_id, doc_type_id)
        self.plan = Plan(
            doc_type=doc_type_id,
            media_style=style_id,
            audience_focus=self._audience_focus(self.brief.primary_audience),
            estimated_length=f"{doc['typical_length_range'][0]}-{doc['typical_length_range'][1]}字",
            structure_outline=doc["structure_mode"],
            writing_mode=self.mode,
        )
        self.project.plan = self.plan
        self.project.brief = self.brief
        payload = self.plan.model_dump()
        payload["doc_type_name"] = doc["name_cn"]
        payload["style_name"] = Registry.by_id("styles", style_id)["name"]
        payload["style_match"] = style_match
        self.state = EngineState.WAITING_APPROVAL
        self._emit("plan", "planning", payload)
        return payload

    def _audience_focus(self, audience: str) -> str:
        a = (audience or "").lower()
        if any(k in a for k in ("领导", "上级", "汇报")):
            return "upward"
        if any(k in a for k in ("媒体", "记者", "通稿")):
            return "external"
        if any(k in a for k in ("学生", "家长", "团队", "成员")):
            return "internal"
        return "external"

    def confirm_plan(self):
        if self.state != EngineState.WAITING_APPROVAL:
            raise RuntimeError("当前不在方案确认阶段")
        self._emit("plan_confirmed", "planning", {"confirmed": True})
        return self.write()

    # ── 写作 ──
    def write(self):
        self.state = EngineState.WRITING
        mode = "llm" if self.llm_available else "rule"
        self._emit("write_start", "writing", {"mode": mode})
        doc = Registry.by_id("doctypes", self.plan.doc_type)
        # RAG：基于简报自主检索政策/术语/范文
        from . import retrieval
        retrieved = retrieval.retrieve_for_brief(self.brief, self.plan, self.plan.media_style)
        self._emit("retrieval", "writing", {
            "terms": [t["term"] for t in retrieved["terms"]],
            "policies": [p["text"] for p in retrieved["policies"]],
            "exemplars": [e["title"] for e in retrieved["exemplars"]],
        })
        if mode == "llm":
            decision = self._consult()
            draft = self._llm_draft(doc, decision, retrieved) or self._rule_draft(doc)
        else:
            draft = self._rule_draft(doc)
        self.project.draft = draft
        self._emit("draft_ready", "writing", {"word_count": len(draft), "mode": mode})
        versions = multi_doc.generate_multi_doc(draft, self.brief, self.plan.doc_type, self.mode)
        self.project.versions = versions
        self._emit("multi_doc", "writing", {"versions": [v.model_dump() for v in versions], "mode": mode})
        self.state = EngineState.REVIEWING
        return draft

    def _consult(self) -> dict:
        """多角色协商 + 集中决策，返回 decision。"""
        from . import agents
        context = {
            "brief": self.brief.model_dump(),
            "plan": self.plan.model_dump(),
            "style_match": style.check_style_doc_match(self.plan.media_style, self.plan.doc_type),
            "user_memory": "",
        }
        responses = agents.consult(self.llm, "写作方案评审", context)
        for rid, r in responses.items():
            self._emit("consult", "writing", r.model_dump())
        decision = agents.decide(self.llm, "写作方案最终决策", responses)
        self._emit("decision", "writing", decision)
        return decision

    def _core_prompt(self, doc) -> str:
        mode_profile = Registry.by_id("modes", self.mode)
        st = Registry.by_id("styles", self.plan.media_style) or {}
        lines = [
            "你是公文写作智能体，服务学生与基层写作者，兼具教学引导与生产辅助职能。",
            "",
            f"【写作模式】{mode_profile['name']}：{mode_profile['tagline']}",
            "【核心原则】",
        ]
        for i, p in enumerate(mode_profile["principles"], 1):
            lines.append(f"{i}. {p['name']}：{p['check']}")
        lines += [
            "",
            f"【文种】{doc['name_cn']}：{doc['structure_mode']}",
            f"【开篇】{doc['opening_template']}",
            f"【正文】{doc['body_template']}",
            f"【结尾】{doc['closing_template']}",
            "",
            f"【风格】{st.get('name', '')}：{st.get('description', '')}",
            f"叙事视角：{st.get('narrative_perspective', '')}；情感基调：{st.get('emotional_tone', '')}",
            "禁用表述：" + "、".join(st.get("forbidden_patterns", [])[:5]),
            "",
            "高级行文策略：用事实、结构和细节说话，避免解释自身写作逻辑，避免AI套话。",
        ]
        return "\n".join(lines)

    def _draft_user_prompt(self, decision: dict, retrieved: dict = None) -> str:
        b = self.brief
        lines = [
            "请根据上述要求生成一篇完整公文。",
            f"核心目的：{b.purpose or '（未填）'}",
            f"第一读者：{b.primary_audience or '（未填）'}",
            f"深层含义：{b.deep_meaning or '（未填）'}",
            f"核心素材：{b.key_materials or '（未填）'}",
            f"差异化视角：{b.differentiator or '（未填）'}",
        ]
        if retrieved:
            from . import retrieval
            ctx = retrieval.format_retrieval_context(retrieved)
            if ctx:
                lines.append(f"\n【知识库检索到的参考（请自然融入，不要照抄）】\n{ctx}")
        if decision and decision.get("decision"):
            lines.append(f"\n【协商决策摘要】\n{decision['decision']}")
        lines.append("\n请直接输出正文，不要输出任何说明或元信息。")
        return "\n".join(lines)

    def _llm_draft(self, doc, decision: dict, retrieved: dict = None):
        from . import retrieval
        system = self._core_prompt(doc)
        user = self._draft_user_prompt(decision, retrieved)
        # LLM 自主工具检索（function calling），失败回退普通生成
        draft = self.llm.chat_with_tools(system, user, retrieval.WRITING_TOOLS, retrieval.execute_tool)
        if draft:
            return draft
        return self.llm.chat(system, user, temperature=0.7)

    def _rule_draft(self, doc) -> str:
        b = self.brief
        return "\n\n".join([
            f"【规则模式初稿 · {doc['name_cn']}】",
            f"写作模式：{Registry.by_id('modes', self.mode)['name']}",
            f"核心目的：{b.purpose or '（未填写）'}",
            f"第一读者：{b.primary_audience or '（未填写）'}",
            f"深层含义：{b.deep_meaning or '（未填写）'}",
            f"核心素材：{b.key_materials or '（未填写）'}",
            "",
            f"【结构模板】{doc['structure_mode']}",
            f"【开篇】{doc['opening_template']}",
            f"【正文】{doc['body_template']}",
            f"【结尾】{doc['closing_template']}",
            "",
            "（规则模式仅生成结构骨架；配置 LLM 后由主笔生成完整正文）",
        ])

    # ── 审查 ──
    def review(self):
        self.state = EngineState.REVIEWING
        mode = "llm" if self.llm_available else "rule"
        self._emit("review_start", "reviewing", {"mode": mode})
        result = review.review(self.project.draft, self.mode, round_name="审查")
        if mode == "llm":
            llm_findings = self._llm_review(self.project.draft)
            if llm_findings:
                result.findings.extend(llm_findings)
                result.score = review.score(result.findings)
                result.passed = review.is_passed([result])
        self.project.review_results = [result]
        payload = {
            "round_name": result.round_name,
            "score": result.score,
            "passed": result.passed,
            "findings": [f.model_dump() for f in result.findings],
            "mode": mode,
        }
        self._emit("review_done", "reviewing", payload)
        return payload

    def _reviewer_prompt(self) -> str:
        mode_profile = Registry.by_id("modes", self.mode)
        dims = mode_profile["review_dimensions"]
        dim_text = "\n".join(f"- {d['name']}（权重{d['weight']:.0%}）" for d in dims)
        return (
            "你是公文审查员。按给定维度逐段检查稿件，标注问题位置、严重程度和修改建议。\n"
            f"审查维度：\n{dim_text}\n\n"
            "严重程度取 critical/major/minor/suggestion。\n"
            "请用JSON输出：{\"findings\": [{\"issue\":\"...\",\"severity\":\"...\",\"suggestion\":\"...\"}]}\n"
            "没有问题则输出 {\"findings\": []}"
        )

    def _llm_review(self, draft: str):
        """LLM 深度审查：返回 ReviewFinding 列表（解析失败返回空）。"""
        from ..domain.schemas import ReviewFinding, ReviewSeverity
        data = self.llm.chat_json(self._reviewer_prompt(), f"请审查以下稿件：\n\n{draft[:4000]}", temperature=0.3)
        if not data:
            return []
        findings = []
        for f in data.get("findings", []):
            sev = f.get("severity", "minor")
            if sev not in ("critical", "major", "minor", "suggestion"):
                sev = "minor"
            findings.append(ReviewFinding(
                round_name="AI深度审查",
                severity=ReviewSeverity(sev),
                issue=f.get("issue", ""),
                suggestion=f.get("suggestion", ""),
                error_key="",
                source="llm",
            ))
        return findings

    # ── 交付 ──
    def finalize(self):
        self.state = EngineState.COMPLETED
        self.project.status = ProjectStatus.COMPLETED
        self.project.final_draft = self.project.draft
        payload = {
            "final_draft": self.project.final_draft,
            "versions": [v.model_dump() for v in self.project.versions],
            "review": self.project.review_results[0].model_dump() if self.project.review_results else {},
        }
        self._emit("finalize", "finalize", payload)
        return payload

    def get_state(self) -> dict:
        return {"state": self.state.value, "seq": self._seq}

    # ── 回退 ──
    def rollback_to(self, step: str) -> dict:
        """回退到指定步骤，清空后续状态，返回新状态。

        step ∈ routing / questioning / planning / writing / reviewing
        """
        self.project.final_draft = ""
        if step == "routing":
            self.brief = Brief(); self.plan = Plan()
            self._routing_node = "root"; self._questions = []; self._q_index = 0
            self.project.brief = None; self.project.plan = None
            self.project.draft = ""; self.project.versions = []; self.project.review_results = []
            self.state = EngineState.ROUTING
        elif step == "questioning":
            self.plan = Plan()
            self._questions = []; self._q_index = 0
            self.project.plan = None
            self.project.draft = ""; self.project.versions = []; self.project.review_results = []
            self.state = EngineState.QUESTIONING
        elif step == "planning":
            self.project.draft = ""; self.project.versions = []; self.project.review_results = []
            self.state = EngineState.WAITING_APPROVAL
        elif step == "writing":
            self.project.draft = ""; self.project.versions = []; self.project.review_results = []
            self.state = EngineState.WAITING_APPROVAL
        elif step == "reviewing":
            self.project.review_results = []
            self.state = EngineState.REVIEWING
        self._emit("rollback", step, {"to": step})
        return {"state": self.state.value, "step": step}
