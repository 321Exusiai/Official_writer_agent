"""V2 升级特性全面单元测试集。

覆盖：
1. 存储层：单项目拆分存储、BM25 历史项目检索、时光机版本快照记录与回滚。
2. 专有库与模板：单位专有知识库 CRUD、公文排版模板库 CRUD。
3. 导出引擎：GB/T 9704-2012 Word (.docx) 规范导出。
4. 检索层：单位知识库与动态少样本（Few-Shot）提取。
5. 智能体与引擎：决策权威权重定制、红蓝军压力测试、划词 AI 伴写、分段递进起草。
"""

import io
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.core import agents, engine, exporter, retrieval
from backend.domain.schemas import Brief, Plan, Project, TemplateConfig
from backend.storage.custom_kb import CustomKnowledgeStore, TemplateStore
from backend.storage.store import Store


class TestV2Features(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.store_dir = Path(self.temp_dir) / "store"
        self.store_dir.mkdir(parents=True, exist_ok=True)
        self.store = Store(data_dir=self.store_dir)

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_store_split_and_history_search(self):
        """测试单项目拆分存储与 BM25 全文检索。"""
        p1 = self.store.create_project("2026全省新质生产力大会通报", "关于加快推进新型工业化的工作通报")
        p1.draft = "为深入贯彻全省新质生产力大会精神，加快传统制造业高端化、智能化、绿色化转型升级，特通报如下。"
        self.store.update_project(p1.id, p1)

        p2 = self.store.create_project("关于开展青年干部调研的通知", "机关青年党建与作风调研")
        p2.draft = "决定在全厅开展青年干部下基层调研活动，提升政治站位与调查研究能力。"
        self.store.update_project(p2.id, p2)

        # 验证项目文件是否独立拆分
        p1_file = self.store_dir / "projects" / f"{p1.id}.json"
        self.assertTrue(p1_file.exists())

        # 验证 BM25 检索历史项目
        hits = self.store.search_projects("新质生产力 制造业转型")
        self.assertTrue(len(hits) >= 1)
        self.assertEqual(hits[0]["id"], p1.id)

        hits2 = self.store.search_projects("青年干部 基层调研")
        self.assertTrue(len(hits2) >= 1)
        self.assertEqual(hits2[0]["id"], p2.id)

    def test_revisions_snapshot_and_restore(self):
        """测试草稿变更时自动记录时光机快照，并支持一键恢复历史版本。"""
        p = self.store.create_project("测试版本回滚项目")
        p.draft = "初稿版本第一段内容。"
        self.store.update_project(p.id, p)
        self.assertEqual(len(p.revisions), 1)

        # 修改草稿
        p.draft = "第二版修改后的草稿内容。"
        self.store.update_project(p.id, p)
        self.assertEqual(len(p.revisions), 2)
        old_rev_id = p.revisions[1].id

        # 恢复到第一版
        restored = self.store.restore_revision(p.id, old_rev_id)
        self.assertIsNotNone(restored)
        self.assertEqual(restored.draft, "初稿版本第一段内容。")

    def test_custom_kb_and_templates(self):
        """测试单位专有知识库与排版模板 CRUD。"""
        custom_file = Path(self.temp_dir) / "custom.json"
        tpl_file = Path(self.temp_dir) / "templates.json"
        CustomKnowledgeStore.FILE_PATH = custom_file
        TemplateStore.FILE_PATH = tpl_file

        item = CustomKnowledgeStore.add_item(
            title="本厅数字化转型考核办法",
            content="各处室应于每季度末提交数字化创新应用案例，赋分纳入年终考核。",
            category="rule",
            source="厅办发〔2026〕5号",
        )
        self.assertTrue(len(CustomKnowledgeStore.load_all()) >= 1)

        # 模板测试
        tpl = TemplateStore.add_template(
            TemplateConfig(
                id="custom_red",
                name="省科技厅红头模板",
                header_text="某某省科学技术厅文件",
                doc_code="某科发〔2026〕10号",
            )
        )
        self.assertEqual(TemplateStore.get_by_id("custom_red").name, "省科技厅红头模板")

    def test_docx_export(self):
        """测试导出 GB/T 9704-2012 国家标准 Word 文档。"""
        p = Project(
            id="p_docx_test",
            name="关于加快构建全省现代化产业体系的实施意见",
            draft="关于加快构建全省现代化产业体系的实施意见\n\n各市人民政府，省政府各部门：\n\n一、总体要求\n加快推进产业高端化发展。\n\n（一）强化科技创新引领\n加大关键核心技术攻关力度。\n\n2026年3月15日",
        )
        buf = exporter.export_project_to_docx(p)
        self.assertIsInstance(buf, io.BytesIO)
        self.assertTrue(buf.getbuffer().nbytes > 1000)

    def test_dynamic_few_shots_and_retrieval(self):
        """测试标杆范文少样本（Few-Shot）抽取与 RAG 政策检索。"""
        shots = retrieval.get_dynamic_few_shots("administrative", "notice", limit=2)
        self.assertTrue(isinstance(shots, list))

        policies = retrieval.search_policy("新质生产力 改革")
        self.assertTrue(len(policies) > 0)

    def test_agents_custom_weights_and_red_team(self):
        """测试专家决策权重调节与红蓝军压力测试。"""
        responses = agents.consult(None, "议题", {"writing_mode": "administrative"})
        custom_weights = {"doctype": 3.0, "style": 0.5}
        dec = agents.decide(None, "议题", responses, mode="administrative", custom_weights=custom_weights)
        self.assertTrue("decision" in dec)

        red_result = agents.red_team_evaluate(
            "关于深入推进基层治理现代化的决定\n大家纷纷表示要做好落实。",
            mode="administrative",
            doc_type="decision",
            llm=None,
        )
        self.assertIn("verdict", red_result)
        self.assertIn("superior_critique", red_result)
        self.assertIn("pr_risk_points", red_result)

    def test_engine_inline_and_chunked_draft(self):
        """测试 WorkflowEngine 划词 AI 伴写、分段起草与红蓝军测试。"""
        p = Project(id="p_engine_test", name="测试工程项目")
        eng = engine.WorkflowEngine(p, llm=None)
        eng.brief = Brief(purpose="汇报年度科技攻坚成果", key_materials="立项50项，突破核心技术12项")
        eng.plan = Plan(doc_type="work_report", writing_mode="administrative")

        # 划词伴写（精简去套话）
        res = eng.inline_transform("大家纷纷表示深感振奋", "concise")
        self.assertEqual(res["result"], "深感振奋")

        # 分段起草
        draft = eng.chunked_draft()
        self.assertTrue(len(draft) > 20)

        # 红蓝军测试
        rt = eng.red_team_review()
        self.assertIn("verdict", rt)
        self.assertEqual(p.red_team_result, rt)


if __name__ == "__main__":
    unittest.main()

