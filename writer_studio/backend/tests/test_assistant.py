"""辅助智能体测试：规则降级 + 工具执行器。"""
import unittest

from fastapi.testclient import TestClient

from writer_studio.backend.core.assistant import AssistantAgent
from writer_studio.backend.main import app

client = TestClient(app)


class TestAssistant(unittest.TestCase):
    def setUp(self):
        self.agent = AssistantAgent(llm=None)  # 无 LLM → 规则降级

    def test_rule_reply_profile(self):
        reply = self.agent._rule_reply("分析我的画像和弱点")
        self.assertIn("规则模式", reply)

    def test_rule_reply_general(self):
        reply = self.agent._rule_reply("你好")
        self.assertIn("辅助轨道", reply)

    def test_exec_explain_term(self):
        out = self.agent._exec_explain_term({"term": "新质生产力"})
        self.assertIn("新质生产力", out)
        self.assertIn("定义", out)

    def test_exec_search_knowledge(self):
        out = self.agent._exec_search_knowledge({"keyword": "高质量发展"})
        self.assertTrue(out)

    def test_exec_list_projects_empty(self):
        out = self.agent._exec_list_projects({})
        self.assertIsInstance(out, str)

    def test_chat_rule_mode(self):
        r = self.agent.chat("有哪些项目？")
        self.assertEqual(r["mode"], "rule")

    def test_api_rule_chat(self):
        r = client.post("/api/assistant/chat", json={"message": "你好", "history": []})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("reply", d)
        self.assertEqual(d["mode"], "rule")

    def test_api_tools(self):
        r = client.get("/api/assistant/tools")
        self.assertEqual(r.status_code, 200)
        self.assertGreater(len(r.json()["tools"]), 5)


if __name__ == "__main__":
    unittest.main()
