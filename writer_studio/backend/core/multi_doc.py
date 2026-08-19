"""一文多体 —— 从主版本提取短版本（规则版）。

P1 规则版：主文种全文 + 从主文种提取"消息/简报"短版本。
P2 接入 LLM 后走长版→提取短版的完整链路。
"""

from ..domain.registry import Registry
from ..domain.schemas import DocVersion


def _make_title(doc_type_id: str, brief) -> str:
    doc = Registry.by_id("doctypes", doc_type_id)
    name = doc["name_cn"] if doc else doc_type_id
    purpose = (brief.purpose or "有关事项")[:20]
    return f"{name}：{purpose}"


def _extract_lead(draft: str, limit: int = 200) -> str:
    """提取导语：取首个非空段落的前 limit 字。"""
    for para in draft.splitlines():
        para = para.strip()
        if para and not para.startswith(("#", "【")):
            return para[:limit]
    return (draft or "")[:limit]


def generate_multi_doc(draft: str, brief, primary_doc_type: str, mode: str):
    """规则版一文多体：主版本 + 简报/消息短版本。"""
    versions = []
    doc = Registry.by_id("doctypes", primary_doc_type)
    name = doc["name_cn"] if doc else primary_doc_type
    versions.append(
        DocVersion(
            doc_type=primary_doc_type,
            doc_type_name=name,
            content=draft,
            word_count=len(draft),
            generation_order=0,
        )
    )

    # 衍生短版本（与主文种不同 domain 的 short 文种）
    if mode in ("strategic_narrative", "objective_report"):
        short_type = "bulletin" if brief.writing_mode != "informational" else "news_brief"
    else:
        short_type = "news_brief" if mode == "informational" else "bulletin"
    if short_type != primary_doc_type:
        short_doc = Registry.by_id("doctypes", short_type)
        lead = _extract_lead(draft)
        short_content = f"{_make_title(short_type, brief)}\n\n{lead}"
        versions.append(
            DocVersion(
                doc_type=short_type,
                doc_type_name=short_doc["name_cn"],
                content=short_content,
                word_count=len(short_content),
                generation_order=1,
                extracted_from=primary_doc_type,
            )
        )
    return versions
