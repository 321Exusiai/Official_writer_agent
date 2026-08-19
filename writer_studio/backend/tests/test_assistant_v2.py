import unittest
from pathlib import Path
import tempfile
import shutil

from backend.core.assistant import AssistantAgent, TOOLS
from backend.storage import custom_kb
from backend.storage.store import Store
from backend.domain.schemas import Project, ReviewResult, ReviewFinding, ReviewSeverity


class TestAssistantV2(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())
        self.orig_data_dir = custom_kb.DATA_DIR
        custom_kb.DATA_DIR = self.tmpdir

        self.store = Store(self.tmpdir)
        self.agent = AssistantAgent(llm=None)
        self.agent._store = self.store

    def tearDown(self):
        custom_kb.DATA_DIR = self.orig_data_dir
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_tools_registered(self):
        """测试 5 个新工具是否已在 TOOLS 中正确注册。"""
        tool_names = [t["function"]["name"] for t in TOOLS]
        for expected in [
            "search_project_history",
            "search_custom_knowledge",
            "add_custom_knowledge",
            "get_red_team_report",
            "inspect_document_standard",
        ]:
            self.assertIn(expected, tool_names)

    def test_search_project_history(self):
        """测试辅助智能体调用历史项目 BM25 检索工具。"""
        p1 = self.store.create_project("2025年全市制造业新型工业化实施方案")
        p1.draft = "加快推进数实融合，推动规上工业企业全面实现数字化转型改造。"
        self.store.update_project(p1.id, p1)

        res = self.agent._executor("search_project_history", {"query": "制造业 数字化"})
        self.assertIn("制造业", res)
        self.assertIn("数字化转型", res)

    def test_custom_knowledge_crud_tools(self):
        """测试辅助智能体录入与检索单位专有知识库。"""
        add_res = self.agent._executor(
            "add_custom_knowledge",
            {
                "title": "局长办公会关于招商引资四项机制的指示",
                "content": "实行周例会调度、半月通报、月度拉练、季度评比四项闭环管理机制。",
                "category": "speech",
                "source": "2026年第3次局长办公会",
            },
        )
        self.assertIn("已成功将", add_res)

        search_res = self.agent._executor("search_custom_knowledge", {"query": "招商引资 四项机制"})
        self.assertIn("局长办公会", search_res)
        self.assertIn("闭环管理机制", search_res)

    def test_red_team_report_tool(self):
        """测试辅助智能体查询红蓝军审签报告。"""
        p = self.store.create_project("测试红蓝军报告项目")
        p.red_team_result = {
            "verdict": "需关注",
            "overall_score": 78,
            "superior_critique": "未明确牵头部门与资金保障来源，责任模糊。",
            "pr_risk_points": ["提及'全面取消限制'可能引发市场不实炒作"],
            "actionable_fixes": ["增加市财政局、市发改委职责分工"],
        }
        self.store.update_project(p.id, p)

        res = self.agent._executor("get_red_team_report", {"project_id": p.id})
        self.assertIn("需关注", res)
        self.assertIn("责任模糊", res)
        self.assertIn("市场不实炒作", res)

    def test_inspect_document_standard_tool(self):
        """测试国家公文格式标准查询工具。"""
        res1 = self.agent._executor("inspect_document_standard", {"topic": "发文字号六角括号"})
        self.assertIn("六角括号", res1)

        res2 = self.agent._executor("inspect_document_standard", {"topic": "正文字体字号与版心边距"})
        self.assertIn("GB/T 9704-2012", res2)
        self.assertIn("仿宋", res2)

    def test_system_prompt_enrichment(self):
        """测试当前活动项目全景上下文注入 System Prompt。"""
        p = self.store.create_project("关于全省科技攻关的通知")
        p.draft = "各市人民政府：现将全省关键核心技术攻坚方案印发给你们。"
        p.scratchpad = ["务必强调专精特新中小企业支持力度"]
        p.review_results = [
            ReviewResult(
                score=82,
                passed=False,
                findings=[ReviewFinding(dimension="normative", issue="发文字号括号缺失", severity=ReviewSeverity.CRITICAL)],
            )
        ]
        self.store.update_project(p.id, p)

        prompt = self.agent._build_system_prompt(project_id=p.id)
        self.assertIn("关于全省科技攻关的通知", prompt)
        self.assertIn("各市人民政府", prompt)
        self.assertIn("专精特新中小企业", prompt)
        self.assertIn("发文字号括号缺失", prompt)


if __name__ == "__main__":
    unittest.main()
