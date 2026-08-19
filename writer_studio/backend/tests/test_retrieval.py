"""RAG 检索测试。"""

import unittest

from writer_studio.backend.core.retrieval import (
    WRITING_TOOLS,
    execute_tool,
    format_retrieval_context,
    retrieve_for_brief,
    search_policy,
    search_terms,
)
from writer_studio.backend.domain.schemas import Brief, Plan


class TestRetrieval(unittest.TestCase):
    def test_search_terms_hits(self):
        text = "推动高质量发展和新质生产力"
        terms = search_terms(text)
        names = [t["term"] for t in terms]
        self.assertIn("高质量发展", names)
        self.assertIn("新质生产力", names)

    def test_search_policy_hits(self):
        text = "推动高质量发展 抓落实"
        policies = search_policy(text)
        topics = [p["topic"] for p in policies]
        self.assertIn("高质量发展", topics)

    def test_retrieve_for_brief(self):
        brief = Brief(
            writing_mode="strategic_narrative", purpose="推动高质量发展，培育新质生产力", key_materials="落实"
        )
        plan = Plan(doc_type="feature", writing_mode="strategic_narrative")
        r = retrieve_for_brief(brief, plan)
        self.assertIsInstance(r, dict)
        self.assertIn("terms", r)
        self.assertIn("policies", r)
        self.assertIn("exemplars", r)

    def test_format_context_nonempty(self):
        brief = Brief(purpose="推动高质量发展")
        plan = Plan(doc_type="feature")
        r = retrieve_for_brief(brief, plan)
        ctx = format_retrieval_context(r)
        self.assertIn("高质量发展", ctx)

    def test_execute_tool_search_policy(self):
        result = execute_tool("search_policy", {"keyword": "高质量发展"})
        self.assertIn("高质量发展", result)

    def test_execute_tool_lookup_term(self):
        result = execute_tool("lookup_term", {"term": "新质生产力"})
        self.assertIn("新质生产力", result)

    def test_truncate_and_summarize(self):
        from writer_studio.backend.core.retrieval import truncate_and_summarize

        short_text = "简短信息"
        self.assertEqual(truncate_and_summarize(short_text, max_chars=50), "简短信息")
        long_text = "长" * 300
        truncated = truncate_and_summarize(long_text, max_chars=50)
        self.assertEqual(len(truncated), 50 + len("…（已精简）"))
        self.assertTrue(truncated.endswith("…（已精简）"))

    def test_bm25_searcher(self):
        from writer_studio.backend.core.retrieval import BM25

        corpus = [
            {"text": "发展新质生产力与科技创新引领现代化产业体系建设"},
            {"text": "落实乡村振兴战略推进农业农村优先发展"},
            {"text": "加强党风廉政建设与反腐败斗争"},
        ]
        bm = BM25(corpus)
        scores = bm.score("科技创新 现代化产业")
        self.assertGreater(scores[0][1], 0)
        self.assertEqual(scores[0][0]["text"], corpus[0]["text"])


if __name__ == "__main__":
    unittest.main()
