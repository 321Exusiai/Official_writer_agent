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

    def __init__(self, project: Project):
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
        self.llm_available = False  # P2 接入后置 True

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
        self._emit("write_start", "writing", {"mode": "rule"})
        doc = Registry.by_id("doctypes", self.plan.doc_type)
        draft = self._rule_draft(doc)
        self.project.draft = draft
        self._emit("draft_ready", "writing", {"word_count": len(draft), "mode": "rule"})
        versions = multi_doc.generate_multi_doc(draft, self.brief, self.plan.doc_type, self.mode)
        self.project.versions = versions
        self._emit("multi_doc", "writing", {"versions": [v.model_dump() for v in versions], "mode": "rule"})
        self.state = EngineState.REVIEWING
        return draft

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
        self._emit("review_start", "reviewing", {"mode": "rule"})
        result = review.review(self.project.draft, self.mode, round_name="规则审查")
        self.project.review_results = [result]
        payload = {
            "round_name": result.round_name,
            "score": result.score,
            "passed": result.passed,
            "findings": [f.model_dump() for f in result.findings],
            "mode": "rule",
        }
        self._emit("review_done", "reviewing", payload)
        return payload

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
