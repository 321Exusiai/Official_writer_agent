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


# ── LLM 自主工具调用（function calling） ──

WRITING_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_policy",
            "description": "检索相关政策表述、领导讲话金句、公文规范用语（如'高质量发展''乡村振兴'）",
            "parameters": {
                "type": "object",
                "properties": {"keyword": {"type": "string", "description": "主题关键词"}},
                "required": ["keyword"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "lookup_term",
            "description": "查询术语的准确定义、使用语境、常见误用（如'新质生产力'）",
            "parameters": {
                "type": "object",
                "properties": {"term": {"type": "string", "description": "要查询的术语"}},
                "required": ["term"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_exemplars",
            "description": "检索标杆范文的结构骨架（按文种）",
            "parameters": {
                "type": "object",
                "properties": {"doc_type": {"type": "string", "description": "文种，如'通讯''通知'"}},
                "required": ["doc_type"],
            },
        },
    },
]


def execute_tool(name: str, args: dict) -> str:
    """执行检索工具，返回结果文本（供 chat_with_tools 回传）。"""
    if name == "search_policy":
        hits = search_policy(args.get("keyword", ""))
        if not hits:
            return "未检索到相关政策表述"
        return "\n".join(f"- {p['text']}（{p.get('source', '')}）" for p in hits)
    if name == "lookup_term":
        term = args.get("term", "")
        terms = Registry.load("terminology")
        info = terms.get(term)
        if not info:
            return f"未找到术语：{term}"
        return f"{term}：{info.get('definition', '')}（误用提示：{info.get('common_misuse', '')}）"
    if name == "search_exemplars":
        hits = search_exemplars("", args.get("doc_type", ""), "")
        if not hits:
            return "未检索到相关范文"
        return "\n".join(f"- 《{e.get('title', '')}》：{(e.get('structure_skeleton', '') or '')[:80]}" for e in hits)
    return ""
