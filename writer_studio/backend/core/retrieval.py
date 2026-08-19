"""知识检索（RAG）—— BM25 混合检索 + 写作前自主检索政策/术语/范文。

采用 BM25（Okapi BM25 词频-逆文档频率）+ 中文分词/N-gram 混合算法，
支持语义意图与同义表述召回，不单依赖简单子串匹配。
"""

import math
import re
from collections import Counter

from ..domain.registry import Registry


def _tokenize(text: str) -> list[str]:
    """中文分词与 2-gram 提取（纯 Python 高性能分词）。"""
    if not text:
        return []
    clean = re.sub(r"[^\w\u4e00-\u9fff]", " ", text.lower())
    words = re.findall(r"[\u4e00-\u9fff]{2,4}|[a-zA-Z0-9]+", clean)
    # 补充 2-gram 字符特征（增强短词与错别字/同义词重叠度召回）
    c_text = re.sub(r"[^\u4e00-\u9fff]", "", text)
    bigrams = [c_text[i : i + 2] for i in range(len(c_text) - 1)]
    return words + bigrams


class BM25:
    """Okapi BM25 检索算法实现。"""

    def __init__(self, corpus: list[dict], text_field: str = "text", k1: float = 1.5, b: float = 0.75):
        self.corpus = corpus
        self.k1 = k1
        self.b = b
        self.doc_len = []
        self.doc_freqs = []
        self.nd = len(corpus)
        self.avgdl = 0.0
        self.idf = {}

        total_len = 0
        df = Counter()
        for doc in corpus:
            raw_text = doc.get(text_field, "")
            if isinstance(raw_text, dict):
                raw_text = " ".join(str(v) for v in raw_text.values())
            tokens = _tokenize(str(raw_text))
            self.doc_len.append(len(tokens))
            total_len += len(tokens)
            freq = Counter(tokens)
            self.doc_freqs.append(freq)
            for token in set(tokens):
                df[token] += 1

        self.avgdl = (total_len / self.nd) if self.nd > 0 else 1.0
        for token, count in df.items():
            self.idf[token] = math.log((self.nd - count + 0.5) / (count + 0.5) + 1.0)

    def score(self, query: str) -> list[tuple[dict, float]]:
        q_tokens = _tokenize(query)
        if not q_tokens or not self.corpus:
            return []
        scores = []
        for idx, doc in enumerate(self.corpus):
            s = 0.0
            freq = self.doc_freqs[idx]
            d_len = self.doc_len[idx]
            for token in q_tokens:
                if token not in freq:
                    continue
                tf = freq[token]
                idf = self.idf.get(token, 0.1)
                num = tf * (self.k1 + 1.0)
                den = tf + self.k1 * (1.0 - self.b + self.b * (d_len / self.avgdl))
                s += idf * (num / den)
            # 精确包含加权（Hybrid boost）
            raw_text = str(doc.get("text", "") or doc.get("term", "") or doc.get("title", ""))
            if query and query in raw_text:
                s += 2.0
            scores.append((doc, s))

        scores.sort(key=lambda x: -x[1])
        return scores


def search_terms(text: str, limit: int = 5) -> list:
    """检索命中的术语（BM25 混合检索 + 精确子串提权）。"""
    terms_dict = Registry.load("terminology")
    corpus = [{"term": term, **info, "text": f"{term} {info.get('definition', '')} {info.get('context', '')}"} for term, info in terms_dict.items()]
    bm = BM25(corpus, text_field="text")
    scored = bm.score(text)
    # 取相关性大于 0 的命中项
    hits = [doc for doc, s in scored if s > 0.3]
    return hits[:limit]


def search_policy(text: str, limit: int = 5) -> list:
    """检索相关政策/讲话/规范用语（包含官方内置库 + 单位专有知识库）。"""
    policies = list(Registry.load("policy").values())
    # 动态并入单位专有知识库
    try:
        from ..storage.custom_kb import CustomKnowledgeStore

        custom_items = CustomKnowledgeStore.load_all()
        for ci in custom_items:
            policies.append({
                "text": ci.content,
                "topic": ci.title,
                "category": ci.category,
                "source": f"单位知识库({ci.source or '本地'})",
                "usage": "单位专有要求/领导讲话",
            })
    except Exception:
        pass

    corpus = [{"text": f"{p.get('text', '')} {p.get('topic', '')} {p.get('category', '')}", **p} for p in policies]
    bm = BM25(corpus, text_field="text")
    scored = bm.score(text)
    hits = [doc for doc, s in scored if s > 0.3]
    return hits[:limit]


def search_exemplars(mode: str, doc_type: str, style: str = "", limit: int = 3, query_text: str = "") -> list:
    """检索标杆范文（文种/模式过滤 + BM25 骨架语义排序）。"""
    exemplars = list(Registry.load("exemplars").values())
    filtered = [e for e in exemplars if e.get("writing_mode") == mode or e.get("doc_type") == doc_type]
    if style:
        styled = [e for e in filtered if e.get("style") == style]
        filtered = styled or filtered
    if not filtered:
        filtered = exemplars

    if query_text:
        corpus = [{"text": f"{e.get('title', '')} {e.get('structure_skeleton', '')} {e.get('opening_sample', '')}", **e} for e in filtered]
        bm = BM25(corpus, text_field="text")
        scored = bm.score(query_text)
        hits = [doc for doc, _ in scored]
        return hits[:limit]

    return filtered[:limit]


def get_dynamic_few_shots(mode: str, doc_type: str, limit: int = 2) -> list[dict]:
    """提取代表性少样本示例（Few-Shot In-Context Learning），供主笔起草精准模仿体例。"""
    exemplars = search_exemplars(mode, doc_type, limit=limit)
    shots = []
    for e in exemplars:
        sample = e.get("opening_sample") or e.get("structure_skeleton") or ""
        if sample:
            shots.append({
                "title": e.get("title", "标杆示范"),
                "doc_type": e.get("doc_type", doc_type),
                "sample": sample[:240],
            })
    return shots


def truncate_and_summarize(text: str, max_chars: int = 260) -> str:
    """工具返回内容精炼截断，防止 ReAct 多轮调用时上下文无序暴涨。"""
    if not text or len(text) <= max_chars:
        return text or ""
    return text[:max_chars].rstrip() + "…（已精简）"


def retrieve_for_brief(brief, plan, style: str = "") -> dict:
    """确定性 RAG 混合检索：基于简报文本与目标文种，返回结构化检索结果。"""
    text = " ".join(
        filter(
            None,
            [
                getattr(brief, "purpose", ""),
                getattr(brief, "key_materials", ""),
                getattr(brief, "deep_meaning", ""),
                getattr(brief, "differentiator", ""),
            ],
        )
    )
    mode = getattr(brief, "writing_mode", "") or getattr(plan, "writing_mode", "")
    doc_type = getattr(plan, "doc_type", "")
    return {
        "terms": search_terms(text),
        "policies": search_policy(text),
        "exemplars": search_exemplars(mode, doc_type, style, query_text=text),
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
