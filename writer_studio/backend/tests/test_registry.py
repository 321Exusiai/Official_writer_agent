"""统一注册表测试：加载、完整性校验、过滤。"""

import unittest

from writer_studio.backend.domain.registry import Registry


class TestRegistry(unittest.TestCase):
    def test_load_styles_has_five_domains(self):
        styles = Registry.load("styles")
        self.assertEqual(len(styles), 10)
        media = Registry.filter("styles", domain="media")
        official = Registry.filter("styles", domain="official")
        self.assertEqual(len(media), 9)
        self.assertEqual(len(official), 1)
        # 每个模式（除行政外）应 ≥3 种可选风格
        from collections import Counter

        cnt = Counter()
        for s in styles.values():
            for m in s.get("modes", []):
                cnt[m] += 1
        for mode, n in cnt.items():
            if mode != "administrative":
                self.assertGreaterEqual(n, 3, f"{mode} 可选风格不足3种")

    def test_vocab_pool_never_missing(self):
        styles = Registry.load("styles")
        for sid, s in styles.items():
            pool = s["vocabulary_pool"]
            for key in ("verbs", "nouns", "adjectives", "phrases", "transitions"):
                self.assertGreaterEqual(len(pool[key]), 5, f"{sid}.{key} 不足5条")

    def test_load_doctypes_16_with_domains(self):
        doctypes = Registry.load("doctypes")
        self.assertEqual(len(doctypes), 17)
        media = Registry.filter("doctypes", domain="media")
        official = Registry.filter("doctypes", domain="official")
        self.assertEqual(len(media), 6)
        self.assertEqual(len(official), 11)
        # 新媒体推文文种仅适用 youth_engagement
        sp = doctypes["social_post"]
        self.assertEqual(sp["modes"], ["youth_engagement"])

    def test_load_modes_5(self):
        modes = Registry.load("modes")
        self.assertEqual(len(modes), 5)
        for _mid, m in modes.items():
            self.assertIn("review_dimensions", m)
            self.assertIn("questions", m)

    def test_by_id(self):
        style = Registry.by_id("styles", "government_admin")
        self.assertEqual(style["domain"], "official")

    def test_load_exemplars(self):
        self.assertGreaterEqual(len(Registry.load("exemplars")), 20)

    def test_load_terminology(self):
        self.assertGreaterEqual(len(Registry.load("terminology")), 25)

    def test_load_transitions(self):
        self.assertGreaterEqual(len(Registry.load("transitions")), 5)

    def test_load_formulaic(self):
        self.assertGreaterEqual(len(Registry.load("formulaic")), 5)


if __name__ == "__main__":
    unittest.main()
