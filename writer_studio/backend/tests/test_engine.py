"""工作流引擎测试：无 Key 规则版全链路。"""

import unittest

from writer_studio.backend.core.engine import EngineState, WorkflowEngine
from writer_studio.backend.domain.schemas import Project


def run_full_flow(mode_answers):
    """跑完整链路，返回 (engine, project)。"""
    p = Project(id="p1", name="测试项目")
    eng = WorkflowEngine(p)

    eng.start()
    assert eng.state == EngineState.ROUTING
    # 路由：根节点选"内部行政"(index 1)
    eng.answer("1")
    # 内部行政分支选"下行文"(index 1)
    eng.answer("1")
    assert eng.state == EngineState.QUESTIONING
    # 逐题作答
    for ans in mode_answers:
        eng.answer(ans)
    assert eng.state == EngineState.WAITING_APPROVAL
    # 确认方案 → 写作
    eng.confirm_plan()
    assert eng.state == EngineState.REVIEWING
    eng.review()
    eng.finalize()
    assert eng.state == EngineState.COMPLETED
    return eng, p


class TestEngine(unittest.TestCase):
    def test_full_flow_administrative(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        self.assertEqual(eng.mode, "administrative")
        self.assertEqual(p.status.value, "completed")
        self.assertTrue(p.draft)
        self.assertTrue(p.versions)
        self.assertTrue(p.review_results)

    def test_full_flow_strategic(self):
        # 根节点选"对外传播"(index 0)，分支选"深度通讯"(index 1)
        p = Project(id="p2", name="研学")
        eng = WorkflowEngine(p)
        eng.start()
        eng.answer("0")
        eng.answer("1")
        self.assertEqual(eng.mode, "strategic_narrative")
        for ans in ["回应国家战略", "克服资金困难", "同学感言", "可推广经验", "坚定信心"]:
            eng.answer(ans)
        eng.confirm_plan()
        self.assertEqual(p.plan.doc_type, "feature")

    def test_events_cover_all_steps(self):
        eng, _ = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        steps = [e.step for e in eng.events]
        for expected in ("routing", "questioning", "planning", "writing", "reviewing", "finalize"):
            self.assertIn(expected, steps)

    def test_events_have_monotonic_seq(self):
        eng, _ = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        seqs = [e.seq for e in eng.events]
        self.assertEqual(seqs, sorted(seqs))
        self.assertEqual(seqs, list(range(1, len(seqs) + 1)))

    def test_invalid_state_answer_raises(self):
        p = Project(id="p3", name="x")
        eng = WorkflowEngine(p)
        with self.assertRaises(RuntimeError):
            eng.answer("随便")  # IDLE 状态不可作答

    def test_rollback_to_writing(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        r = eng.rollback_to("writing")
        self.assertEqual(r["state"], "waiting_approval")
        self.assertEqual(p.draft, "")
        self.assertEqual(p.versions, [])
        self.assertEqual(p.review_results, [])

    def test_rollback_to_questioning(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        r = eng.rollback_to("questioning")
        self.assertEqual(r["state"], "questioning")
        self.assertIsNone(p.plan)
        self.assertEqual(p.draft, "")

    def test_fix_finding_rule(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        # 注入含"空泛套话"的草稿并重审，找到对应 finding 修复
        p.draft = "大家纷纷表示，本次检查很有意义。\n特此通知。"
        eng.project.draft = p.draft
        eng.review()
        findings = eng.project.review_results[0].findings
        idx = next((i for i, f in enumerate(findings) if f.error_key == "empty_platitudes"), None)
        self.assertIsNotNone(idx, "应能诊断出空泛套话")
        result = eng.fix_finding(idx)
        self.assertTrue(result.get("fixed"))
        self.assertEqual(result.get("fixed_method"), "rule")
        self.assertNotIn("大家纷纷表示", eng.project.draft)
        # 修复后该问题不应再出现
        keys = [f.error_key for f in eng.project.review_results[0].findings]
        self.assertNotIn("empty_platitudes", keys)

    def test_fix_finding_bad_index(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        eng.review()
        with self.assertRaises(ValueError):
            eng.fix_finding(999)

    def test_fix_finding_no_llm_manual_only(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        # 无规则 fix 且无 LLM → 抛错要求人工
        p.draft = "我们被组织参观了展馆。\n特此通知。"
        eng.project.draft = p.draft
        eng.review()
        findings = eng.project.review_results[0].findings
        idx = next((i for i, f in enumerate(findings) if f.error_key == "passive_narrative"), None)
    def test_draft_user_prompt_includes_scratchpad(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        p.scratchpad = ["务必强调实验室安全责任制", "增加周报频次"]
        prompt = eng._draft_user_prompt({"decision": "按结构起草"})
        self.assertIn("实验室安全责任制", prompt)
        self.assertIn("增加周报频次", prompt)

    def test_debate_triggered_on_critical_review_with_llm(self):
        class FakeReviewLLM:
            available = True

            def chat_json(self, system, user, temperature=None):
                if "审查员" in system:
                    return {
                        "findings": [
                            {"issue": "重大事实错误", "severity": "critical", "suggestion": "核对数据"}
                        ]
                    }
                if "辩论" in system or "平衡" in system:
                    return {"consensus": "经辩论采纳修改意见并保留主体事实"}
                return {"decision": "测试决策"}

            def chat(self, system, user, temperature=None):
                return "测试文本"

            def chat_with_tools(self, system, user, tools, executor, max_rounds=3):
                return None

        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        eng.llm = FakeReviewLLM()
        res = eng.review()
        self.assertIn("debate_consensus", res)
        self.assertEqual(res["debate_consensus"], "经辩论采纳修改意见并保留主体事实")
        # 验证发射了 debate 事件
        event_types = [e.type for e in eng.events]
        self.assertIn("debate", event_types)

    def test_auto_heal_loop_convergence(self):
        eng, p = run_full_flow(["根据上级要求", "部署安全检查工作", "各二级单位", "通知"])
        # 使用具备规范要素但包含空泛套话的稿件
        eng.project.draft = (
            "关于开展2025年春季安全检查的通知\n\n"
            "各二级单位：\n"
            "为切实保障校园安全，现定于下周开展安全大检查。\n"
            "大家纷纷表示，一定要抓好责任落实。\n\n"
            "特此通知。\n"
        )
        eng.review()
        initial_score = eng.project.review_results[0].score
        self.assertLess(initial_score, 100.0)
        res = eng.auto_heal(target_score=95.0, max_rounds=2)
        self.assertIn("final_score", res)
        self.assertGreaterEqual(res["final_score"], 90.0)
        self.assertNotIn("大家纷纷表示", eng.project.draft)


if __name__ == "__main__":
    unittest.main()
