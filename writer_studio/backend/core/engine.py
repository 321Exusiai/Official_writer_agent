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


class EngineState(str, Enum):  # noqa: UP042 — 需与 JSON 字符串直接比较/序列化
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

    def __init__(self, project: Project, llm=None, assistant_llm=None):
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
        self.llm = llm  # 主 LLMClient（写作/审查）
        self.assistant_llm = assistant_llm  # 辅助 LLMClient（轻任务：协商/决策）

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
        """启动（或重新启动）一次写作流程：重置流程状态，保留项目个性化数据。"""
        self.brief = Brief()
        self.plan = Plan()
        self._routing_node = "root"
        self._questions = []
        self._q_index = 0
        self.events = []
        self._seq = 0
        # 项目：保留个性化数据（references/requirements/summary/review_history/favorites），清空本次流程产物
        self.project.brief = None
        self.project.plan = None
        self.project.draft = ""
        self.project.final_draft = ""
        self.project.versions = []
        if self.project.review_results:
            self.project.review_history.extend(self.project.review_results)
            self.project.review_results = []
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
        payload["structure_detail"] = f"{doc['opening_template']}\n{doc['body_template']}\n{doc['closing_template']}"
        self.state = EngineState.WAITING_APPROVAL
        self._emit("plan", "planning", payload)
        return payload

    def update_plan(self, doc_type: str, media_style: str) -> dict:
        """用户手动覆盖文种/风格，重新生成方案。"""
        if self.state not in (EngineState.WAITING_APPROVAL,):
            raise RuntimeError("当前不在方案确认阶段")
        doc = Registry.by_id("doctypes", doc_type)
        if not doc:
            raise ValueError(f"文种不存在：{doc_type}")
        st = Registry.by_id("styles", media_style)
        if not st:
            raise ValueError(f"风格不存在：{media_style}")
        self.plan.doc_type = doc_type
        self.plan.media_style = media_style
        self.plan.estimated_length = f"{doc['typical_length_range'][0]}-{doc['typical_length_range'][1]}字"
        self.plan.structure_outline = doc["structure_mode"]
        style_match = style.check_style_doc_match(media_style, doc_type)
        self.project.plan = self.plan
        payload = self.plan.model_dump()
        payload["doc_type_name"] = doc["name_cn"]
        payload["style_name"] = st["name"]
        payload["style_match"] = style_match
        payload["structure_detail"] = f"{doc['opening_template']}\n{doc['body_template']}\n{doc['closing_template']}"
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
        self._emit(
            "retrieval",
            "writing",
            {
                "terms": [t["term"] for t in retrieved["terms"]],
                "policies": [p["text"] for p in retrieved["policies"]],
                "exemplars": [e["title"] for e in retrieved["exemplars"]],
            },
        )
        # 联网搜索（可选）：配置了搜索 key 时实时检索最新政策/讲话
        web_results = self._web_search()
        if mode == "llm":
            decision = self._consult(retrieved)
            draft = self._llm_draft(doc, decision, retrieved, web_results) or self._rule_draft(doc)
        else:
            draft = self._rule_draft(doc)
        self.project.draft = draft
        self._emit("draft_ready", "writing", {"word_count": len(draft), "mode": mode})
        versions = multi_doc.generate_multi_doc(draft, self.brief, self.plan.doc_type, self.mode)
        self.project.versions = versions
        self._emit("multi_doc", "writing", {"versions": [v.model_dump() for v in versions], "mode": mode})
        self.state = EngineState.REVIEWING
        return draft

    def _web_search(self) -> list:
        """联网搜索（可选）：配置了搜索 key 时实时检索最新政策/讲话。"""
        if not self.llm:
            return []
        key = getattr(self.llm.config, "search_api_key", "")
        if not key:
            return []
        from . import web_search

        query = f"{self.brief.purpose} {self.brief.key_materials}"[:60]
        provider = getattr(self.llm.config, "search_provider", "tavily")
        results = web_search.search_web(query, provider, key)
        self._emit("web_search", "writing", {"query": query, "count": len(results)})
        return results

    def _consult(self, retrieved: dict = None) -> dict:
        """多角色特化协商 + 集中决策，返回 decision。

        写作核心流程一律用主模型；小模型作为独立「辅助智能体」处理写作之外的事务。
        """
        from . import agents, llm

        # 读取用户画像长期记忆（偏好与弱点）
        user_prefs, user_weaknesses, bias_warnings, user_mem_str = [], [], [], ""
        try:
            from ..api.profile import load_profile

            prof = load_profile()
            user_prefs = getattr(prof, "preferences", [])
            user_weaknesses = getattr(prof, "weaknesses", [])
            bias_warnings = getattr(prof, "bias_warnings", [])
            mem_parts = []
            if user_prefs:
                mem_parts.append("写作偏好：" + "；".join(user_prefs[:5]))
            if user_weaknesses:
                mem_parts.append("历史弱点预警：" + "；".join(user_weaknesses[:3]))
            user_mem_str = "\n".join(mem_parts)
        except Exception:
            pass

        st = Registry.by_id("styles", self.plan.media_style) or {}
        doc = Registry.by_id("doctypes", self.plan.doc_type) or {}
        mode_profile = Registry.by_id("modes", self.mode) or {}
        vocab_sample = style.scale_vocabulary(self.plan.media_style, self.brief.style_intensity)

        from . import retrieval
        few_shots = retrieval.get_dynamic_few_shots(self.mode, self.plan.doc_type, limit=2)
        try:
            from ..storage.custom_kb import CustomKnowledgeStore
            custom_items = [f"【{c.title}】{c.content[:120]}" for c in CustomKnowledgeStore.load_all()[:3]]
        except Exception:
            custom_items = []

        context = {
            "brief": self.brief.model_dump(),
            "plan": self.plan.model_dump(),
            "style_match": style.check_style_doc_match(self.plan.media_style, self.plan.doc_type),
            "user_memory": user_mem_str,
            "user_preferences": user_prefs,
            "user_weaknesses": user_weaknesses,
            "bias_warnings": bias_warnings,
            "scratchpad": getattr(self.project, "scratchpad", []),
            "retrieved_policies": [p["text"] for p in (retrieved or {}).get("policies", [])],
            "retrieved_terms": [t["term"] for t in (retrieved or {}).get("terms", [])],
            "retrieved_exemplars": [e["title"] for e in (retrieved or {}).get("exemplars", [])],
            "dynamic_few_shots": few_shots,
            "custom_knowledge_items": custom_items,
            "emotional_tone": st.get("emotional_tone", ""),
            "vocabulary_sample": vocab_sample,
            "forbidden_patterns": st.get("forbidden_patterns", []),
            "structure_detail": f"{doc.get('opening_template', '')}\n{doc.get('body_template', '')}\n{doc.get('closing_template', '')}",
            "typical_length_range": f"{doc.get('typical_length_range', [0, 0])[0]}-{doc.get('typical_length_range', [0, 0])[1]}字",
            "review_dimensions": mode_profile.get("review_dimensions", []),
        }
        responses = agents.consult(self.llm, "写作方案评审", context)
        thought_bubbles = agents.build_thought_bubbles(responses)
        for r in responses.values():
            self._emit("consult", "writing", {**r.model_dump(), "thought_bubbles": thought_bubbles})
        decision = agents.decide(self.llm, "写作方案最终决策", responses, mode=self.mode)
        self._emit("decision", "writing", decision)
        return decision

    def _core_prompt(self, doc) -> str:
        from . import retrieval

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
        ]

        # 动态少样本注入（Dynamic Few-Shot In-Context Learning）
        shots = retrieval.get_dynamic_few_shots(self.mode, self.plan.doc_type, limit=1)
        if shots:
            lines.append(f"\n【标杆范文结构示范】\n参考示范（{shots[0]['title']}）：\n{shots[0]['sample']}")

        lines.append("\n高级行文策略：用事实、结构和细节说话，避免解释自身写作逻辑，避免AI套话。")
        return "\n".join(lines)

    def _draft_user_prompt(self, decision: dict, retrieved: dict = None, web_results: list = None) -> str:
        b = self.brief
        lines = [
            "请根据上述要求生成一篇完整公文。",
            f"核心目的：{b.purpose or '（未填）'}",
            f"第一读者：{b.primary_audience or '（未填）'}",
            f"深层含义：{b.deep_meaning or '（未填）'}",
            f"核心素材：{b.key_materials or '（未填）'}",
            f"差异化视角：{b.differentiator or '（未填）'}",
        ]
        # 融入助手协同沉淀的备忘录与用户指令
        if getattr(self.project, "scratchpad", None):
            lines.append("\n【作者备忘录与重点要求（请重点落实）】\n" + "\n".join(f"- {note}" for note in self.project.scratchpad))
        if getattr(self.project, "work_requirements", ""):
            lines.append(f"\n【工作要求】\n{self.project.work_requirements}")
        # 融入用户画像偏好记忆
        try:
            from ..api.profile import load_profile

            prof = load_profile()
            if getattr(prof, "preferences", None):
                lines.append("\n【作者写作偏好习惯（请自然契合）】\n" + "\n".join(f"- {p}" for p in prof.preferences[:5]))
        except Exception:
            pass

        if retrieved:
            from . import retrieval

            ctx = retrieval.format_retrieval_context(retrieved)
            if ctx:
                lines.append(f"\n【知识库检索到的参考（请自然融入，不要照抄）】\n{ctx}")
        if web_results:
            from . import web_search

            ctx = web_search.format_web_results(web_results)
            if ctx:
                lines.append(f"\n{ctx}")
        if decision and decision.get("decision"):
            lines.append(f"\n【协商决策摘要】\n{decision['decision']}")
        lines.append("\n请直接输出正文，不要输出任何说明或元信息。")
        return "\n".join(lines)

    def _llm_draft(self, doc, decision: dict, retrieved: dict = None, web_results: list = None):
        from . import llm, retrieval

        system = self._core_prompt(doc)
        user = self._draft_user_prompt(decision, retrieved, web_results)
        temp = llm.adaptive_temperature(self.mode, self.plan.doc_type, stage="draft")

        # 1. 尝试流式生成（Token-by-Token SSE 推送打字效果）
        stream_chunks = []
        if hasattr(self.llm, "chat_stream"):
            for chunk in self.llm.chat_stream(system, user, temperature=temp):
                stream_chunks.append(chunk)
                if len(stream_chunks) % 5 == 0:
                    self._emit("draft_chunk", "writing", {"chunk": chunk, "total_len": sum(len(c) for c in stream_chunks)})
            if stream_chunks:
                return "".join(stream_chunks).strip()

        # 2. LLM 自主工具检索（function calling），失败回退普通生成
        draft = self.llm.chat_with_tools(system, user, retrieval.WRITING_TOOLS, retrieval.execute_tool)
        if draft:
            return draft
        return self.llm.chat(system, user, temperature=temp)

    def _rule_draft(self, doc) -> str:
        b = self.brief
        return "\n\n".join(
            [
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
            ]
        )

    # ── 审查 ──
    def review(self):
        self.state = EngineState.REVIEWING
        mode = "llm" if self.llm_available else "rule"
        self._emit("review_start", "reviewing", {"mode": mode})
        result = review.review(self.project.draft, self.mode, round_name="审查")
        debate_consensus = ""
        thought_bubbles = []
        if mode == "llm":
            llm_findings = self._llm_review(self.project.draft)
            if llm_findings:
                result.findings.extend(llm_findings)
                result.score = review.score(result.findings)
                result.passed = review.is_passed([result])
                result.dimension_scores = review.compute_dimension_scores(result.findings)

            # 审查冲突自动辩论（Debate-on-Conflict）：出现 Critical 问题或未通过时，触发主笔与审稿人辩论
            has_critical = any(f.severity.value == "critical" for f in result.findings)
            if (not result.passed or has_critical) and result.findings:
                from . import agents

                crit_f = next((f for f in result.findings if f.severity.value == "critical"), result.findings[0])
                writer_pos = f"起草立足于传达目的「{self.brief.purpose[:50]}」，结合素材「{self.brief.key_materials[:50]}」行文"
                reviewer_pos = f"审查指出严重问题：{crit_f.issue}，修改建议：{crit_f.suggestion}"
                debate_res = agents.debate(self.llm, "文稿审查分歧与共识", writer_pos, reviewer_pos)
                debate_consensus = debate_res.get("consensus", "")
                self._emit("debate", "reviewing", {"consensus": debate_consensus, "mode": debate_res.get("mode", "llm")})
                thought_bubbles.append({"role": "debate", "role_name": "仲裁共识", "emoji": "⚖️", "thought": debate_consensus})

        result.thought_bubbles = thought_bubbles
        self.project.review_results = [result]
        payload = {
            "round_name": result.round_name,
            "score": result.score,
            "passed": result.passed,
            "findings": [f.model_dump() for f in result.findings],
            "dimension_scores": result.dimension_scores,
            "debate_consensus": debate_consensus,
            "thought_bubbles": thought_bubbles,
            "mode": mode,
        }
        self._emit("review_done", "reviewing", payload)
        return payload

    # ── 自主收敛自愈闭环（Reflexion Auto-Repair Loop）──
    def auto_heal(self, target_score: float = 85.0, max_rounds: int = 3) -> dict:
        """多轮自动自愈闭环：按 Critical -> Major 优先级修复并自动复审，带回滚降级保护。"""
        self._emit("healing_start", "reviewing", {"target_score": target_score, "max_rounds": max_rounds})
        history = []
        for r in range(1, max_rounds + 1):
            if not self.project.review_results:
                self.review()
            cur_res = self.project.review_results[0]
            if cur_res.score >= target_score and not any(f.severity.value == "critical" for f in cur_res.findings):
                break
            if not cur_res.findings:
                break

            # 优先级排序：critical (4) > major (3) > minor (2) > suggestion (1)
            sev_order = {"critical": 4, "major": 3, "minor": 2, "suggestion": 1}
            sorted_indices = sorted(range(len(cur_res.findings)), key=lambda i: -sev_order.get(cur_res.findings[i].severity.value, 1))
            target_idx = sorted_indices[0]
            target_finding = cur_res.findings[target_idx]

            # 1. 保存修改前版本快照（Rollback Snapshot）
            draft_snapshot = self.project.draft
            prev_score = cur_res.score

            # 2. 尝试修复该项
            try:
                self.fix_finding(target_idx)
            except Exception as e:
                history.append({"round": r, "issue": target_finding.issue, "error": str(e), "rolled_back": False})
                break

            new_score = self.project.review_results[0].score
            rolled_back = False

            # 3. 降级保护：若修复后得分变差（越改越坏），自动回滚快照！
            if new_score < prev_score:
                self.project.draft = draft_snapshot
                self.review()
                rolled_back = True
                self._emit("healing_rollback", "reviewing", {"round": r, "issue": target_finding.issue, "prev_score": prev_score, "new_score": new_score})

            step_record = {
                "round": r,
                "issue": target_finding.issue,
                "severity": target_finding.severity.value,
                "prev_score": prev_score,
                "new_score": self.project.review_results[0].score,
                "rolled_back": rolled_back,
            }
            history.append(step_record)
            self.project.healing_history.append(step_record)
            self._emit("healing_step", "reviewing", step_record)
            if rolled_back:
                # 出现退化，暂停自动循环，交由人工介入
                break

        final_res = self.project.review_results[0] if self.project.review_results else None
        final_score = final_res.score if final_res else 0.0
        final_passed = final_res.passed if final_res else False
        res_payload = {
            "history": history,
            "final_score": final_score,
            "passed": final_passed,
            "rounds_run": len(history),
        }
        self._emit("healing_done", "reviewing", res_payload)
        return res_payload

    def _reviewer_prompt(self) -> str:
        mode_profile = Registry.by_id("modes", self.mode)
        dims = mode_profile["review_dimensions"]
        dim_text = "\n".join(f"- {d['name']}（权重{d['weight']:.0%}）" for d in dims)
        return (
            "你是公文审查员。按给定维度逐段检查稿件，标注问题位置、严重程度和修改建议。\n"
            f"审查维度：\n{dim_text}\n\n"
            "严重程度取 critical/major/minor/suggestion。\n"
            '请用JSON输出：{"findings": [{"issue":"...","severity":"...","suggestion":"..."}]}\n'
            '没有问题则输出 {"findings": []}'
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
            findings.append(
                ReviewFinding(
                    round_name="AI深度审查",
                    severity=ReviewSeverity(sev),
                    issue=f.get("issue", ""),
                    suggestion=f.get("suggestion", ""),
                    error_key="",
                    source="llm",
                )
            )
        return findings

    # ── HITL-3：逐条自动修复 ──
    def fix_finding(self, index: int) -> dict:
        """修复单条审查发现（规则优先，LLM 兜底），修复后立即重新审查。

        返回与 review() 一致的 payload，并附带 fixed/fixed_method/fixed_index。
        """
        if not self.project.review_results:
            raise RuntimeError("尚无审查结果")
        result = self.project.review_results[0]
        if index < 0 or index >= len(result.findings):
            raise ValueError("审查发现序号越界")
        finding = result.findings[index]
        new_text, applied = review.apply_fix(self.project.draft, finding.error_key or "")
        method = "rule"
        if not applied and self.llm_available:
            new_text = self._llm_fix(finding, self.project.draft)
            applied = bool(new_text) and new_text != self.project.draft
            method = "llm"
        if not applied:
            raise RuntimeError("该问题无法自动修复，请手动编辑草稿")
        self.project.draft = new_text
        self._emit(
            "draft_ready",
            "reviewing",
            {
                "word_count": len(new_text),
                "method": method,
                "fixed_index": index,
            },
        )
        payload = self.review()
        payload["fixed"] = True
        payload["fixed_method"] = method
        payload["fixed_index"] = index
        return payload

    def _llm_fix(self, finding, draft: str) -> str:
        """LLM 修复单条发现：只改该问题，其余逐字保留，直接输出完整文稿。"""
        system = (
            "你是公文修改助手。只修复用户指出的这一个问题，其余内容逐字保留，"
            "直接输出修改后的完整文稿，不要输出任何说明或元信息。"
        )
        user = f"需修复的问题：{finding.issue}\n修改建议：{finding.suggestion}\n\n当前文稿：\n{draft}"
        return self.llm.chat(system, user, temperature=0.3) or ""

    # ── 交付 ──
    def finalize(self):
        self.state = EngineState.COMPLETED
        self.project.status = ProjectStatus.COMPLETED
        self.project.final_draft = self.project.draft
        # 审查历史归档（累计多次写作）
        if self.project.review_results:
            self.project.review_history.extend(self.project.review_results)
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
            self.brief = Brief()
            self.plan = Plan()
            self._routing_node = "root"
            self._questions = []
            self._q_index = 0
            self.project.brief = None
            self.project.plan = None
            self.project.draft = ""
            self.project.versions = []
            self.project.review_results = []
            self.state = EngineState.ROUTING
        elif step == "questioning":
            self.plan = Plan()
            self._questions = []
            self._q_index = 0
            self.project.plan = None
            self.project.draft = ""
            self.project.versions = []
            self.project.review_results = []
            self.state = EngineState.QUESTIONING
        elif step == "planning":
            self.project.draft = ""
            self.project.versions = []
            self.project.review_results = []
            self.state = EngineState.WAITING_APPROVAL
        elif step == "writing":
            self.project.draft = ""
            self.project.versions = []
            self.project.review_results = []
            self.state = EngineState.WAITING_APPROVAL
        elif step == "reviewing":
            self.project.review_results = []
            self.state = EngineState.REVIEWING
        self._emit("rollback", step, {"to": step})
        return {"state": self.state.value, "step": step}

    # ── 大纲驱动的分段递进起草（Chunked Generator） ──
    def chunked_draft(self) -> str:
        """分段递进起草器：大纲规划 ➔ 逐段按上下文递进生成 ➔ 全局衔接缝合。"""
        self.state = EngineState.WRITING
        doc = Registry.by_id("doctypes", self.plan.doc_type) or {
            "name_cn": self.plan.doc_type or "公文",
            "opening_template": "",
            "body_template": "",
            "closing_template": "",
        }
        from . import agents, llm, retrieval

        retrieved = retrieval.retrieve_for_brief(self.brief, self.plan, self.plan.media_style)
        self._emit("chunk_start", "writing", {"doc_type": self.plan.doc_type})

        # 1. 生成分段大纲树
        outline_prompt = (
            f"请为文种【{doc['name_cn']}】制定三段式分段起草大纲（开篇、主体、结尾）。\n"
            f"核心目的：{self.brief.purpose}\n核心素材：{self.brief.key_materials}\n\n"
            '请用JSON输出数组：{"sections": [{"title": "标题", "goal": "本段目标", "materials": "本段素材"}]}'
        )
        outline_data = None
        if self.llm and self.llm.available:
            outline_data = self.llm.chat_json(self._core_prompt(doc), outline_prompt, temperature=0.2)

        sections = (outline_data or {}).get("sections", [
            {"title": "开篇立意", "goal": "开篇点题与背景", "materials": self.brief.purpose},
            {"title": "主体展开", "goal": "核心举措与事实展开", "materials": self.brief.key_materials},
            {"title": "总结升华", "goal": "成效与后续要求", "materials": self.brief.deep_meaning or "抓好落实"},
        ])

        chunks = []
        prev_context = ""
        for idx, sec in enumerate(sections, 1):
            self._emit("chunk_step", "writing", {"section_idx": idx, "total": len(sections), "title": sec.get("title", "")})
            if self.llm and self.llm.available:
                sec_user = (
                    f"当前起草第 {idx}/{len(sections)} 节【{sec.get('title')}】\n"
                    f"本节写作目标：{sec.get('goal')}\n本节核心素材：{sec.get('materials')}\n"
                    f"上一节结尾衔接锚点：\n{prev_context[-200:] if prev_context else '（首段开始）'}\n\n"
                    "请直接输出本节正文："
                )
                sec_text = self.llm.chat(self._core_prompt(doc), sec_user, temperature=0.2) or ""
                chunks.append(sec_text.strip())
                prev_context += "\n" + sec_text.strip()
            else:
                chunks.append(f"【{sec.get('title')}】\n{sec.get('materials')}")

        full_draft = "\n\n".join(chunks)
        self.project.draft = full_draft
        self._emit("draft_ready", "writing", {"word_count": len(full_draft), "mode": "chunked"})
        versions = multi_doc.generate_multi_doc(full_draft, self.brief, self.plan.doc_type, self.mode)
        self.project.versions = versions
        self.state = EngineState.REVIEWING
        return full_draft

    # ── 模拟分管领导审签与舆情红蓝军压力测试 ──
    def red_team_review(self) -> dict:
        """执行模拟分管领导审签与舆情红蓝军压力测试。"""
        from . import agents

        draft = self.project.draft or ""
        result = agents.red_team_evaluate(draft, self.mode, self.plan.doc_type, llm=self.llm)
        self.project.red_team_result = result
        self._emit("red_team", "reviewing", result)
        return result

    # ── 划词局部 AI 伴写 ──
    def inline_transform(self, selection: str, action: str, context: str = "") -> dict:
        """局部选中文本 AI 伴写转换（升华金句/精简套话/政策校对/换风格）。"""
        if not selection.strip():
            return {"result": selection, "mode": "rule"}

        actions_map = {
            "polish": "升华公文金句：使句式对仗严谨，融入权威政策用语，提升立意与思想深度，直接输出改写后的文本，不要任何说明。",
            "concise": "精简去套话：剔除冗余字词、空泛表态和口语化用词，使表述干净利落，直接输出精简后的文本，不要任何说明。",
            "verify": "政策与权威表述校对：核实选中文本中的政治术语与法规表述，纠正不规范提法，直接输出校对后的准确文本，不要任何说明。",
            "style_youth": "转换为中青报/融媒体年轻态文风：去官腔去爹味，用生动具象、有网感、有青春共鸣的语言表达，直接输出改写后的文本，不要任何说明。",
            "style_renmin": "转换为人民日报政论体文风：提升思想立意，运用对仗排比与高瞻远瞩的论述语态，直接输出改写后的文本，不要任何说明。",
        }
        instruction = actions_map.get(action, actions_map["polish"])

        if self.llm and self.llm.available:
            system = f"你是公文与媒体写作精修专家。\n指令：{instruction}"
            user = f"当前上下文环境：{context[:300] if context else '公文起草'}\n\n待处理选中文本：\n{selection}"
            out = self.llm.chat(system, user, temperature=0.3)
            if out:
                return {"result": out.strip().strip('"').strip("'"), "mode": "llm"}

        # 规则兜底
        if action == "concise":
            clean = selection
            for plat in ("大家纷纷表示", "一致认为", "深刻感受到", "取得了丰硕成果", "毫无疑问", "众所周知"):
                clean = clean.replace(plat, "")
            return {"result": clean, "mode": "rule"}

        return {"result": selection, "mode": "rule"}

