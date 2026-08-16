"""RAG 检索测试。"""
import unittest

from writer_studio.backend.core.retrieval import (
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
        brief = Brief(writing_mode="strategic_narrative", purpose="推动高质量发展，培育新质生产力", key_materials="落实")
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


if __name__ == "__main__":
    unittest.main()
