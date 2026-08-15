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

    def test_available_with_key(self):
        cfg = LLMConfig(api_base="http://x/v1", api_key="k", model="m", enabled=True)
        self.assertTrue(LLMClient(cfg).available)

    def test_chat_returns_none_when_unavailable(self):
        self.assertIsNone(LLMClient(LLMConfig()).chat("s", "u"))


if __name__ == "__main__":
    unittest.main()
