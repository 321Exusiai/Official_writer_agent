"""领域模型基础测试（unittest，零第三方依赖）。"""
import unittest

from writer_studio.backend.domain.schemas import (
    AgentResponse,
    Brief,
    ReviewResult,
    ReviewSeverity,
)


class TestSchemas(unittest.TestCase):
    def test_brief_defaults(self):
        b = Brief()
        self.assertEqual(b.writing_mode, "")
        self.assertEqual(b.secondary_audiences, [])
        self.assertEqual(b.style_intensity, 1.0)

    def test_review_result_defaults_and_values(self):
        r = ReviewResult(round_name="第1轮", passed=False, score=50)
        self.assertEqual(r.round_name, "第1轮")
        self.assertIs(r.passed, False)
        self.assertEqual(r.score, 50)
        self.assertEqual(r.findings, [])

    def test_agent_response_mode_rule(self):
        a = AgentResponse(role="reviewer", mode="rule")
        self.assertEqual(a.role, "reviewer")
        self.assertEqual(a.mode, "rule")

    def test_review_severity_values(self):
        self.assertEqual(ReviewSeverity.CRITICAL.value, "critical")
        self.assertEqual(ReviewSeverity.SUGGESTION.value, "suggestion")


if __name__ == "__main__":
    unittest.main()
