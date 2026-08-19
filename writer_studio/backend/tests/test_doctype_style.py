"""文种识别与风格适配测试。"""

import unittest

from writer_studio.backend.core.doctype import identify_doc_type
from writer_studio.backend.core.style import (
    auto_select_style,
    check_style_doc_match,
    scale_vocabulary,
    suggest_blend,
)
from writer_studio.backend.domain.schemas import Brief


class TestDocType(unittest.TestCase):
    def test_admin_mode_returns_official_doctypes(self):
        brief = Brief(
            writing_mode="administrative", purpose="请示关于举办学术论坛的事项", primary_audience="上级领导机关"
        )
        ranked = identify_doc_type(brief)
        self.assertGreater(len(ranked), 0)
        self.assertEqual(ranked[0][0], "request")  # 请示关键词 + 上级受众

    def test_media_mode_returns_media_doctypes(self):
        brief = Brief(writing_mode="strategic_narrative", purpose="记录研学考察活动", primary_audience="学院师生")
        ranked = identify_doc_type(brief)
        ids = [x[0] for x in ranked]
        self.assertIn("feature", ids)
        self.assertNotIn("request", ids)  # 不推荐行政文种

    def test_fallback_when_no_signal(self):
        brief = Brief(writing_mode="strategic_narrative", purpose="", primary_audience="")
        ranked = identify_doc_type(brief)
        self.assertEqual(ranked[0][0], "feature")

    def test_scores_sorted_desc(self):
        brief = Brief(writing_mode="administrative", purpose="部署工作 通知", primary_audience="下级单位")
        ranked = identify_doc_type(brief)
        scores = [s for _, s in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))


class TestStyle(unittest.TestCase):
    def test_official_doc_gets_official_style(self):
        brief = Brief(writing_mode="administrative", purpose="通知", primary_audience="下级")
        self.assertEqual(auto_select_style(brief, "notification"), "government_admin")

    def test_media_doc_gets_media_style(self):
        brief = Brief(primary_audience="媒体记者", purpose="发布通稿")
        self.assertEqual(auto_select_style(brief, "news_brief"), "xinhua")

    def test_blend_single_audience(self):
        blend = suggest_blend("学院领导", "汇报成果", [])
        self.assertEqual(blend["primary_weight"], 1.0)
        self.assertEqual(blend["secondary_weight"], 0.0)

    def test_blend_weights_sum_to_one(self):
        blend = suggest_blend("学院领导", "汇报成果", ["学生群体"])
        self.assertAlmostEqual(blend["primary_weight"] + blend["secondary_weight"], 1.0, places=3)
        self.assertNotEqual(blend["secondary_style"], "")

    def test_scale_vocabulary(self):
        style = scale_vocabulary("people_daily", 0.9)
        self.assertGreaterEqual(len(style["verbs"]), 5)
        weak = scale_vocabulary("people_daily", 0.1)
        self.assertEqual(len(weak["verbs"]), 1)

    def test_style_doc_match(self):
        self.assertTrue(check_style_doc_match("government_admin", "notification"))
        self.assertFalse(check_style_doc_match("people_daily", "notification"))
        self.assertTrue(check_style_doc_match("people_daily", "feature"))


if __name__ == "__main__":
    unittest.main()
