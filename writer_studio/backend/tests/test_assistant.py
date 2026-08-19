"""辅助智能体测试：规则降级 + 工具执行器。"""

import os
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

    def test_quick_command_profile(self):
        r = self.agent.chat("/画像")
        self.assertIn("画像分析", r["reply"])

    def test_quick_command_projects(self):
        r = self.agent.chat("/项目")
        self.assertIsInstance(r["reply"], str)

    def test_quick_command_help(self):
        r = self.agent.chat("/帮助")
        self.assertIn("快捷命令", r["reply"])

    def test_api_rule_chat(self):
        r = client.post("/api/assistant/chat", json={"message": "你好", "history": []})
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("reply", d)
        self.assertIn(d["mode"], ("rule", "llm"))

    def test_api_tools(self):
        r = client.get("/api/assistant/tools")
        self.assertEqual(r.status_code, 200)
        tools = r.json()["tools"]
        self.assertGreater(len(tools), 5)
        names = [t["name"] for t in tools]
        self.assertIn("search_web", names)  # P2② 联网搜索工具已注册

    def test_exec_pin_to_scratchpad(self):
        store = self.agent._get_store()
        p = store.create_project("备忘测试项目")
        try:
            res = self.agent._exec_pin_to_scratchpad({"project_id": p.id, "note": "重点落实科技自立自强"})
            self.assertIn("成功", res)
            updated = store.get_project(p.id)
            self.assertIn("重点落实科技自立自强", updated.scratchpad)
        finally:
            store.delete_project(p.id)

    def test_web_search_no_key_returns_guidance(self):
        # 未配置搜索 key → 返回引导文案（不报错、不编造）
        out = self.agent._exec_search_web({"query": "2025年政府工作报告"})
        self.assertIn("搜索", out)

    def test_remember_preferences_writes_profile(self):
        import tempfile
        from pathlib import Path

        from writer_studio.backend.api import profile as prof

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        orig = prof._PROFILE_PATH
        prof._PROFILE_PATH = Path(path)
        try:
            self.agent._remember_preferences("我喜欢短句，语气活泼一些。")
            p = prof.load_profile()
            self.assertTrue(any("短句" in x for x in p.preferences))
        finally:
            prof._PROFILE_PATH = orig
            if Path(path).exists():
                os.unlink(path)

    def test_remember_preferences_respects_switch(self):
        import tempfile
        from pathlib import Path

        from writer_studio.backend.api import profile as prof

        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        orig = prof._PROFILE_PATH
        prof._PROFILE_PATH = Path(path)
        try:
            p = prof.load_profile()
            p.memory_enabled = False
            prof.save_profile(p)
            self.agent._remember_preferences("我偏好正式严肃的文风")
            p2 = prof.load_profile()
            self.assertEqual(p2.preferences, [])
        finally:
            prof._PROFILE_PATH = orig
            if Path(path).exists():
                os.unlink(path)

    def test_get_contextual_actions(self):
        actions_empty = self.agent.get_contextual_actions("")
        self.assertGreaterEqual(len(actions_empty), 2)
        # 测试在有未过审项目时推荐一键自愈
        store = self.agent._get_store()
        p = store.create_project("自愈测试项目")
        from writer_studio.backend.domain.schemas import ReviewFinding, ReviewResult, ReviewSeverity

        p.review_results = [
            ReviewResult(
                score=60.0,
                passed=False,
                findings=[ReviewFinding(issue="套话", severity=ReviewSeverity.MAJOR, suggestion="修改")],
            )
        ]
        store.update_project(p.id, p)
        try:
            actions_proj = self.agent.get_contextual_actions(p.id)
            labels = [a["label"] for a in actions_proj]
            self.assertTrue(any("自愈" in l for l in labels))
        finally:
            store.delete_project(p.id)

    def test_coach_mode_in_prompt(self):
        prompt = self.agent._build_system_prompt()
        self.assertIn("公文私教", prompt)


if __name__ == "__main__":
    unittest.main()
