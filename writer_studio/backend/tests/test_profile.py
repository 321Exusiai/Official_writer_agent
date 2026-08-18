"""用户专属数据库测试：参考文本解读 + 画像分析 + API。"""
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from writer_studio.backend.api import profile as prof
from writer_studio.backend.core.profile import analyze_profile, analyze_reference, summarize_questionnaire
from writer_studio.backend.domain.schemas import Brief, Project, ReviewFinding, ReviewResult, ReviewSeverity
from writer_studio.backend.main import app

client = TestClient(app)


class TestProfileCore(unittest.TestCase):
    def test_analyze_reference_extracts(self):
        text = "他说：“这次交流让我看到了差距。”数据显示，参与度同比提升30%。同学们说：“太燃了！”"
        out = analyze_reference(text)
        self.assertIn("值得借鉴的句子", out)
        self.assertIn("高频词汇", out)

    def test_summarize_questionnaire(self):
        b = Brief(purpose="记录研学活动", primary_audience="学院师生", key_materials="同学感言")
        s = summarize_questionnaire(b)
        self.assertIn("研学", s)
        self.assertIn("师生", s)

    def test_analyze_profile_weakness(self):
        finding = ReviewFinding(error_key="empty_platitudes", severity=ReviewSeverity.MAJOR, issue="空泛套话")
        r = ReviewResult(round_name="r", findings=[finding])
        p = Project(id="p1", name="x", brief=Brief(writing_mode="strategic_narrative"), review_results=[r])
        a = analyze_profile([p])
        self.assertTrue(any("空泛套话" in w for w in a["weaknesses"]))


class TestProfileAPI(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.tmp = Path(path)
        self._orig = prof._PROFILE_PATH
        prof._PROFILE_PATH = self.tmp

    def tearDown(self):
        prof._PROFILE_PATH = self._orig
        if self.tmp.exists():
            os.unlink(self.tmp)

    def test_add_text_ref_and_analyze(self):
        r = client.post("/api/profile/references/text", json={
            "title": "参考", "content": "他说：“这次交流让我看到了差距。”同学们说：“太燃了！”",
        })
        self.assertEqual(r.status_code, 200)
        ref = r.json()
        self.assertIn("值得借鉴的句子", ref["analysis"])
        rid = ref["id"]
        r2 = client.post(f"/api/profile/references/{rid}/analyze")
        self.assertEqual(r2.status_code, 200)

    def test_favorites(self):
        client.post("/api/profile/favorites", json={"kind": "term", "value": "新质生产力"})
        p = client.get("/api/profile").json()
        self.assertIn("新质生产力", p["favorite_terms"])
        client.delete("/api/profile/favorites?kind=term&value=新质生产力")
        p2 = client.get("/api/profile").json()
        self.assertNotIn("新质生产力", p2["favorite_terms"])

    def test_overview(self):
        r = client.get("/api/profile/overview")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("profile", d)
        self.assertIn("analysis", d)


if __name__ == "__main__":
    unittest.main()
