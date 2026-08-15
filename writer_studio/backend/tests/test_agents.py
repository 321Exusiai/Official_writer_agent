"""多角色协作测试：诚实降级 + mock LLM 路径。"""
import unittest

from writer_studio.backend.core import agents
from writer_studio.backend.domain.schemas import AgentResponse


class FakeLLM:
    available = True

    def chat(self, system, user, temperature=None, max_tokens=None):
        return "测试正文"

    def chat_json(self, system, user, temperature=None):
        # 返回所有协作方法可能用到的键（consult/decide/debate 各取所需）
        return {
            "concerns": ["测试关注"],
            "suggestions": ["测试建议"],
            "decision": "测试决策",
            "rationale": "测试依据",
            "consensus": "测试共识",
        }


class TestConsult(unittest.TestCase):
    def test_rule_mode_with_empty_context(self):
        context = {"brief": {"purpose": "", "key_materials": ""}, "plan": {"writing_mode": ""}}
        responses = agents.consult(None, "写作方案评审", context)
        self.assertEqual(responses["writer"].mode, "rule")
        self.assertTrue(responses["writer"].concerns)  # 目的/素材缺失 → 有真实 concern

    def test_rule_mode_with_filled_context(self):
        context = {
            "brief": {"purpose": "部署工作", "key_materials": "有素材"},
            "plan": {"writing_mode": "administrative", "doc_type_name": "通知"},
            "style_match": True,
        }
        r = agents.rule_response("writer", context)
        self.assertEqual(r.concerns, [])  # 字段齐全 → 无 concern

    def test_llm_mode(self):
        responses = agents.consult(FakeLLM(), "写作方案评审", {})
        self.assertEqual(responses["writer"].mode, "llm")
        self.assertEqual(responses["writer"].concerns, ["测试关注"])

    def test_style_conflict_concern(self):
        context = {"plan": {}, "style_match": False}
        r = agents.rule_response("style", context)
        self.assertTrue(any("不匹配" in c for c in r.concerns))


class TestDecide(unittest.TestCase):
    def test_rule_mode_aggregates(self):
        responses = {"writer": AgentResponse(role="writer", suggestions=["建议1"], mode="rule")}
        d = agents.decide(None, "议题", responses)
        self.assertEqual(d["mode"], "rule")
        self.assertIn("建议1", d["decision"])

    def test_llm_mode(self):
        d = agents.decide(FakeLLM(), "议题", {})
        self.assertEqual(d["mode"], "llm")


class TestDebate(unittest.TestCase):
    def test_rule_mode_has_consensus(self):
        d = agents.debate(None, "议题", "写方", "审方")
        self.assertEqual(d["mode"], "rule")
        self.assertTrue(d["consensus"])

    def test_llm_mode(self):
        d = agents.debate(FakeLLM(), "议题", "写方", "审方")
        self.assertEqual(d["mode"], "llm")


if __name__ == "__main__":
    unittest.main()
