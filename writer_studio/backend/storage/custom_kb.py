"""单位专有知识库与自定义公文模板持久化存储。

支持：
1. 单位政策讲话、特色范文片段上传与管理 (custom_knowledge.json)
2. 自定义公文格式排版模板管理 (templates.json)
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path

from ..domain.schemas import CustomKnowledgeItem, TemplateConfig

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_LOCK = threading.RLock()


def _get_kb_path() -> Path:
    return DATA_DIR / "custom_knowledge.json"


def _get_tpl_path() -> Path:
    return DATA_DIR / "templates.json"


# 默认内置国家标准模板
DEFAULT_TEMPLATES = [
    TemplateConfig(
        id="default_gbt9704",
        name="GB/T 9704-2012 国家公文标准",
        top_margin_mm=37.0,
        bottom_margin_mm=35.0,
        left_margin_mm=28.0,
        right_margin_mm=26.0,
        title_font="方正小标宋_GB2312",
        title_size_pt=22.0,
        body_font="仿宋_GB2312",
        body_size_pt=16.0,
        line_spacing_pt=28.0,
        header_text="",
    ),
    TemplateConfig(
        id="official_redhead",
        name="机关正式红头文件模板",
        top_margin_mm=40.0,
        bottom_margin_mm=35.0,
        left_margin_mm=28.0,
        right_margin_mm=26.0,
        title_font="方正小标宋_GB2312",
        title_size_pt=22.0,
        body_font="仿宋_GB2312",
        body_size_pt=16.0,
        line_spacing_pt=28.0,
        header_text="中共XX机关党组文件",
        doc_code="〔2025〕1号",
    ),
    TemplateConfig(
        id="compact_brief",
        name="紧凑型工作简报/会议纪要模板",
        top_margin_mm=30.0,
        bottom_margin_mm=25.0,
        left_margin_mm=25.0,
        right_margin_mm=25.0,
        title_font="黑体",
        title_size_pt=18.0,
        body_font="仿宋_GB2312",
        body_size_pt=14.0,
        line_spacing_pt=22.0,
        header_text="工作简报（第 1 期）",
    ),
]


class CustomKnowledgeStore:
    @staticmethod
    def load_all() -> list[CustomKnowledgeItem]:
        with _LOCK:
            p = _get_kb_path()
            if not p.exists():
                return []
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                return [CustomKnowledgeItem(**item) for item in raw]
            except Exception:
                return []

    @staticmethod
    def save_all(items: list[CustomKnowledgeItem]):
        with _LOCK:
            p = _get_kb_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            payload = [item.model_dump() for item in items]
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, p)

    @classmethod
    def add_item(cls, title: str, content: str, category: str = "policy", tags: list[str] = None, source: str = "") -> CustomKnowledgeItem:
        items = cls.load_all()
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        item = CustomKnowledgeItem(
            id=f"ckb_{uuid.uuid4().hex[:8]}",
            title=title,
            content=content,
            category=category,
            tags=tags or [],
            source=source,
            created_at=now,
        )
        items.insert(0, item)
        cls.save_all(items)
        return item

    @classmethod
    def delete_item(cls, item_id: str) -> bool:
        items = cls.load_all()
        filtered = [it for it in items if it.id != item_id]
        if len(filtered) != len(items):
            cls.save_all(filtered)
            return True
        return False


class TemplateStore:
    @staticmethod
    def load_all() -> list[TemplateConfig]:
        with _LOCK:
            p = _get_tpl_path()
            if not p.exists():
                TemplateStore.save_all(DEFAULT_TEMPLATES)
                return DEFAULT_TEMPLATES
            try:
                raw = json.loads(p.read_text(encoding="utf-8"))
                return [TemplateConfig(**t) for t in raw]
            except Exception:
                return DEFAULT_TEMPLATES

    @staticmethod
    def save_all(templates: list[TemplateConfig]):
        with _LOCK:
            p = _get_tpl_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            tmp = p.with_suffix(".tmp")
            payload = [t.model_dump() for t in templates]
            tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            os.replace(tmp, p)

    @classmethod
    def add_template(cls, config: TemplateConfig) -> TemplateConfig:
        templates = cls.load_all()
        if not config.id or config.id == "default_gbt9704":
            config.id = f"tpl_{uuid.uuid4().hex[:8]}"
        templates = [t for t in templates if t.id != config.id]
        templates.append(config)
        cls.save_all(templates)
        return config

    @classmethod
    def get_by_id(cls, tpl_id: str) -> TemplateConfig | None:
        templates = cls.load_all()
        return next((t for t in templates if t.id == tpl_id), None)
