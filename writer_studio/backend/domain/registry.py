"""统一注册表 —— 所有可枚举静态知识的单一加载入口。

每个容器 JSON 统一顶层结构 ``{"id": {...}}``，加载时执行完整性校验，
缺失或违反约束直接抛错（杜绝"空转"）。
"""

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parent.parent / "knowledge" / "data"

# 词汇池统一五类键，每类必须有内容
VOCAB_KEYS = ("verbs", "nouns", "adjectives", "phrases", "transitions")
MIN_VOCAB = 5


class RegistryError(Exception):
    """知识数据完整性校验失败。"""


class Registry:
    _cache: dict = {}

    @classmethod
    def load(cls, name: str) -> dict:
        if name in cls._cache:
            return cls._cache[name]
        path = _DATA_DIR / f"{name}.json"
        if not path.exists():
            raise RegistryError(f"知识容器缺失: {name}.json")
        data = json.loads(path.read_text(encoding="utf-8"))
        cls._validate(name, data)
        cls._cache[name] = data
        return data

    @classmethod
    def by_id(cls, name: str, id_: str):
        return cls.load(name).get(id_)

    @classmethod
    def filter(cls, name: str, domain: str = None) -> list:
        items = cls.load(name).values()
        return [i for i in items if domain is None or i.get("domain") == domain]

    @classmethod
    def _validate(cls, name: str, data: dict):
        if not isinstance(data, dict):
            raise RegistryError(f"{name}.json 顶层必须为对象")
        if name == "styles":
            cls._validate_styles(data)
        elif name == "doctypes":
            cls._validate_doctypes(data)
        elif name == "modes":
            cls._validate_modes(data)
        elif name == "exemplars":
            if len(data) < 20:
                raise RegistryError(f"exemplars 应 ≥20 篇范文，实为 {len(data)}")
        elif name == "terminology":
            if len(data) < 25:
                raise RegistryError(f"terminology 应 ≥25 条术语，实为 {len(data)}")
        elif name == "policy":
            if len(data) < 30:
                raise RegistryError(f"policy 应 ≥30 条政策/讲话/规范表述，实为 {len(data)}")

    @classmethod
    def _validate_styles(cls, data):
        for sid, s in data.items():
            assert "domain" in s, f"styles.{sid} 缺 domain"
            pool = s.get("vocabulary_pool", {})
            for key in VOCAB_KEYS:
                vals = pool.get(key)
                if not isinstance(vals, list) or len(vals) < MIN_VOCAB:
                    raise RegistryError(f"styles.{sid}.vocabulary_pool.{key} 必须为 ≥{MIN_VOCAB} 条的列表")

    @classmethod
    def _validate_doctypes(cls, data):
        if len(data) != 17:
            raise RegistryError(f"doctypes 应为 17 个文种，实为 {len(data)}")
        for did, d in data.items():
            assert "domain" in d, f"doctypes.{did} 缺 domain"
            assert d["domain"] in ("media", "official"), f"doctypes.{did}.domain 非法"
            assert "modes" in d and d["modes"], f"doctypes.{did} 缺 modes 适用映射"

    @classmethod
    def _validate_modes(cls, data):
        if len(data) != 5:
            raise RegistryError(f"modes 应为 5 个模式，实为 {len(data)}")
        for mid, m in data.items():
            assert "review_dimensions" in m, f"modes.{mid} 缺 review_dimensions"
            assert "questions" in m, f"modes.{mid} 缺 questions"
