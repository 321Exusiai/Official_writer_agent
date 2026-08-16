"""知识检索（RAG）—— 写作前基于简报自主检索政策/术语/范文/过渡句。

确定性检索：不依赖 LLM 自主决定，引擎在写作前调用，结果注入写作 prompt
并作为 retrieval 事件推送到过程面板。
"""
from ..domain.registry import Registry


def search_terms(text: str, limit: int = 5) -> list:
    """检索命中的术语（简报文本中出现的术语名）。"""
    terms = Registry.load("terminology")
    hits = []
    for term, info in terms.items():
        if term and term in text:
            hits.append({"term": term, **info})
    return hits[:limit]


def search_policy(text: str, limit: int = 5) -> list:
    """检索相关政策/讲话/规范用语（按 topic/category 关键词匹配）。"""
    policies = list(Registry.load("policy").values())
    hits = []
    for p in policies:
        keys = [p.get("topic", ""), p.get("category", "")]
        if any(k and k in text for k in keys):
            hits.append(p)
    return hits[:limit]


def search_exemplars(mode: str, doc_type: str, style: str = "", limit: int = 3) -> list:
    """检索标杆范文（按模式/文种过滤）。"""
    exemplars = list(Registry.load("exemplars").values())
    hits = [e for e in exemplars if e.get("writing_mode") == mode or e.get("doc_type") == doc_type]
    if style:
        styled = [e for e in hits if e.get("style") == style]
        hits = styled or hits
    return hits[:limit]


def retrieve_for_brief(brief, plan, style: str = "") -> dict:
    """确定性 RAG 检索：基于简报文本，返回结构化检索结果。"""
    text = " ".join(filter(None, [
        getattr(brief, "purpose", ""),
        getattr(brief, "key_materials", ""),
        getattr(brief, "deep_meaning", ""),
        getattr(brief, "differentiator", ""),
    ]))
    mode = getattr(brief, "writing_mode", "") or getattr(plan, "writing_mode", "")
    doc_type = getattr(plan, "doc_type", "")
    return {
        "terms": search_terms(text),
        "policies": search_policy(text),
        "exemplars": search_exemplars(mode, doc_type, style),
    }


def format_retrieval_context(retrieved: dict) -> str:
    """将检索结果格式化为可注入写作 prompt 的文本。"""
    lines = []
    if retrieved.get("policies"):
        lines.append("【相关政策与规范表述】")
        for p in retrieved["policies"]:
            lines.append(f"- {p.get('text', '')}（{p.get('source', '')}）")
    if retrieved.get("terms"):
        lines.append("\n【相关术语】")
        for t in retrieved["terms"]:
            lines.append(f"- {t['term']}：{t.get('definition', '')}")
    if retrieved.get("exemplars"):
        lines.append("\n【参考范文结构】")
        for e in retrieved["exemplars"]:
            lines.append(f"- 《{e.get('title', '')}》：{(e.get('structure_skeleton', '') or '')[:60]}")
    return "\n".join(lines)
