"""审查流水线测试。"""
import unittest

from writer_studio.backend.core.review import (
    check_admin_format,
    check_subject_ratio,
    diagnose,
    is_passed,
    review,
    score,
)
from writer_studio.backend.domain.schemas import ReviewFinding, ReviewResult, ReviewSeverity


class TestScore(unittest.TestCase):
    def test_two_critical_equals_50(self):
        fs = [
            ReviewFinding(severity=ReviewSeverity.CRITICAL),
            ReviewFinding(severity=ReviewSeverity.CRITICAL),
        ]
        self.assertEqual(score(fs), 50.0)

    def test_empty_findings_full_score(self):
        self.assertEqual(score([]), 100.0)

    def test_score_clamped_at_zero(self):
        fs = [ReviewFinding(severity=ReviewSeverity.CRITICAL) for _ in range(10)]
        self.assertEqual(score(fs), 0.0)

    def test_passed_threshold(self):
        ok = [ReviewResult(round_name="r", score=80, findings=[])]
        self.assertTrue(is_passed(ok))
        bad = [ReviewResult(round_name="r", score=60, findings=[])]
        self.assertFalse(is_passed(bad))


class TestDiagnose(unittest.TestCase):
    def test_date_with_zero_regex_hits(self):
        """原版缺陷：正则在子串匹配下永不命中，这里用真实 re.search 命中。"""
        text = "会议于2025年07月15日召开。"
        findings = diagnose(text, "administrative")
        keys = [f.error_key for f in findings]
        self.assertIn("date_with_zero", keys)

    def test_empty_platitudes_hit(self):
        findings = diagnose("大家纷纷表示很满意。", "strategic_narrative")
        keys = [f.error_key for f in findings]
        self.assertIn("empty_platitudes", keys)

    def test_mode_filtering(self):
        # 行政专属错误不应在战略叙事模式下触发
        text = "2025年07月"
        self.assertIn("date_with_zero", [f.error_key for f in diagnose(text, "administrative")])
        self.assertNotIn("date_with_zero", [f.error_key for f in diagnose(text, "strategic_narrative")])


class TestChecks(unittest.TestCase):
    def test_subject_ratio_low(self):
        text = "对方介绍了他们的成果，他们表示很满意。" * 3 + "我们"
        findings = check_subject_ratio(text)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].severity, ReviewSeverity.MAJOR)

    def test_admin_format_critical_title(self):
        text = "现将有关事项通知如下，特此通知。"
        findings = check_admin_format(text)
        self.assertIn("title_3elements_missing", [f.error_key for f in findings])

    def test_review_integration(self):
        text = "关于举办论坛的通知\n根据有关精神，现将有关事项通知如下。特此通知。"
        result = review(text, "administrative")
        self.assertIsInstance(result, ReviewResult)
        self.assertGreaterEqual(result.score, 0.0)
        self.assertLessEqual(result.score, 100.0)


if __name__ == "__main__":
    unittest.main()
