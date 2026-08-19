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

    def test_dynamic_role_selection(self):
        # 媒体模式 -> 包含 style 和 knowledge
        media_roles = agents.select_roles_for_mode("strategic_narrative", "feature")
        self.assertIn("writer", media_roles)
        self.assertIn("reviewer", media_roles)
        self.assertIn("style", media_roles)
        self.assertIn("knowledge", media_roles)

        # 行政模式 -> 包含 doctype
        admin_roles = agents.select_roles_for_mode("administrative", "notification")
        self.assertIn("doctype", admin_roles)
        self.assertNotIn("style", admin_roles)

        # 有画像记忆时 -> 激活 profile
        mem_roles = agents.select_roles_for_mode("administrative", "notification", has_memory=True)
        self.assertIn("profile", mem_roles)

    def test_build_role_context_specialization(self):
        context = {
            "brief": {"purpose": "测试目的", "key_materials": "核心素材123"},
            "plan": {"doc_type": "notification", "doc_type_name": "通知", "media_style": "people_daily"},
            "user_preferences": ["多用短句"],
            "user_weaknesses": ["空泛套话"],
            "retrieved_policies": ["政策一"],
            "scratchpad": ["备忘要点1"],
        }
        # 验证主笔拿到了素材和备忘录
        writer_ctx = agents.build_role_context("writer", context)
        self.assertEqual(writer_ctx["key_materials"], "核心素材123")
        self.assertIn("备忘要点1", writer_ctx["scratchpad"])

        # 验证知识库角色拿到了检索政策
        kb_ctx = agents.build_role_context("knowledge", context)
        self.assertEqual(kb_ctx["retrieved_policies"], ["政策一"])

        # 验证画像角色拿到了偏好和弱点
        prof_ctx = agents.build_role_context("profile", context)
        self.assertIn("多用短句", prof_ctx["user_preferences"])
        self.assertIn("空泛套话", prof_ctx["user_weaknesses"])

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

    def test_authority_veto_power(self):
        # 当文种专家对行政公文提出明确合规否决项时，必须触发 veto_triggered
        responses = {
            "writer": AgentResponse(role="writer", suggestions=["自由发挥"], mode="rule"),
            "doctype": AgentResponse(role="doctype", concerns=["请示夹带报告，违反一文一事法定规范"], suggestions=["拆分为独立请示与报告"], mode="rule"),
        }
        d = agents.decide(None, "文种合规决策", responses, mode="administrative")
        self.assertTrue(d["veto_triggered"])
        self.assertIn("一票否决", d["decision"])

    def test_build_thought_bubbles(self):
        responses = {
            "writer": AgentResponse(role="writer", suggestions=["精简开篇"], mode="rule"),
            "reviewer": AgentResponse(role="reviewer", concerns=["事实依据不足"], mode="rule"),
        }
        bubbles = agents.build_thought_bubbles(responses)
        self.assertEqual(len(bubbles), 2)
        r_bubble = next(b for b in bubbles if b["role"] == "reviewer")
        self.assertEqual(r_bubble["emoji"], "🧐")
        self.assertIn("事实依据不足", r_bubble["thought"])

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
