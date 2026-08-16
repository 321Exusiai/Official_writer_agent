"""外部资料导入 —— URL / 粘贴文本一键导入到项目语料库（RAG 语料来源）。"""
import re
import time
import uuid

import httpx

from ..domain.schemas import ReferenceArticle

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _extract_title(html: str) -> str:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
    return (m.group(1).strip() if m else "未命名")[:80]


def _extract_text(html: str) -> str:
    html = re.sub(r"<(script|style|nav|footer|header|aside)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"&[a-z]+;", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def import_from_url(url: str) -> ReferenceArticle:
    resp = httpx.get(url, timeout=15, follow_redirects=True, headers=_UA)
    resp.raise_for_status()
    return ReferenceArticle(
        id=f"ref_{uuid.uuid4().hex[:8]}",
        title=_extract_title(resp.text),
        content=_extract_text(resp.text)[:5000],
        source=url,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )


def import_from_text(title: str, content: str, source: str = "手动粘贴") -> ReferenceArticle:
    return ReferenceArticle(
        id=f"ref_{uuid.uuid4().hex[:8]}",
        title=(title or "未命名").strip()[:80],
        content=content.strip()[:5000],
        source=source,
        created_at=time.strftime("%Y-%m-%d %H:%M:%S"),
    )
