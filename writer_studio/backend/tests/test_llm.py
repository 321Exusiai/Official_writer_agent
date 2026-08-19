"""LLM 客户端测试。"""

import unittest

from writer_studio.backend.core.llm import LLMClient, _parse_json
from writer_studio.backend.domain.schemas import LLMConfig


class TestParseJSON(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(_parse_json('{"a": 1}'), {"a": 1})

    def test_fenced(self):
        self.assertEqual(_parse_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_bare_fence(self):
        self.assertEqual(_parse_json('```\n{"a": 1}\n```'), {"a": 1})

    def test_not_json(self):
        self.assertIsNone(_parse_json("这不是JSON"))

    def test_inline_json_block(self):
        self.assertEqual(_parse_json('结果如下：{"a": 1}，完毕'), {"a": 1})


class TestAvailability(unittest.TestCase):
    def test_unavailable_without_key(self):
        self.assertFalse(LLMClient(LLMConfig()).available)

    def test_adaptive_temperature(self):
        from writer_studio.backend.core.llm import adaptive_temperature

        # 审查诊断极低温
        self.assertLessEqual(adaptive_temperature("administrative", stage="review"), 0.1)
        # 行政公文低温严谨
        self.assertLessEqual(adaptive_temperature("administrative", stage="draft"), 0.2)
        # 年轻态/特写较高创意温控
        self.assertGreaterEqual(adaptive_temperature("youth_engagement", stage="draft"), 0.6)
        self.assertGreaterEqual(adaptive_temperature("strategic_narrative", stage="draft"), 0.6)


if __name__ == "__main__":
    unittest.main()
