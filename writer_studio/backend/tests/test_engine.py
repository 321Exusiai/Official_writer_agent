"""工作流引擎测试：无 Key 规则版全链路。"""
import unittest

from writer_studio.backend.core.engine import EngineState, WorkflowEngine
from writer_studio.backend.domain.schemas import Project


def run_full_flow(mode_answers):
    """跑完整链路，返回 (engine, project)。"""
    p = Project(id="p1", name="测试项目")
    eng = WorkflowEngine(p)

    q = eng.start()
    assert eng.state == EngineState.ROUTING
    # 路由：根节点选"内部行政"(index 1)
    q = eng.answer("1")
    # 内部行政分支选"下行文"(index 1)
    q = eng.answer("1")
    assert eng.state == EngineState.QUESTIONING
    # 逐题作答
    for ans in mode_answers:
        q = eng.answer(ans)
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


if __name__ == "__main__":
    unittest.main()
