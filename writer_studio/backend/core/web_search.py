"""联网搜索（可选）—— 配置搜索 API key 后，写作前实时检索最新政策/讲话。

支持 Tavily（默认）与博查 Boya；未配置 key 时 search_web 返回 []。
"""

import httpx


def search_web(query: str, provider: str = "tavily", api_key: str = "", limit: int = 3) -> list:
    """联网搜索，返回 [{"title", "content", "url"}]；未配置/失败返回 []。"""
    if not api_key or not query:
        return []
    if provider == "boya":
        return _search_boya(query, api_key, limit)
    return _search_tavily(query, api_key, limit)


def _search_tavily(query: str, api_key: str, limit: int) -> list:
    try:
        resp = httpx.post(
            "https://api.tavily.com/search",
            json={"api_key": api_key, "query": query, "max_results": limit},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("results", [])
        return [
            {"title": r.get("title", ""), "content": (r.get("content", "") or "")[:200], "url": r.get("url", "")}
            for r in results[:limit]
        ]
    except httpx.HTTPError:
        return []


def _search_boya(query: str, api_key: str, limit: int) -> list:
    try:
        resp = httpx.get(
            "https://api.bochaai.com/v1/web-search",
            params={"q": query, "count": limit},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=15,
        )
        if resp.status_code != 200:
            return []
        results = resp.json().get("data", {}).get("webPages", {}).get("value", [])
        return [
            {"title": r.get("name", ""), "content": (r.get("summary", "") or "")[:200], "url": r.get("url", "")}
            for r in results[:limit]
        ]
    except httpx.HTTPError:
        return []


def format_web_results(results: list) -> str:
    """将联网搜索结果格式化为可注入写作 prompt 的文本。"""
    if not results:
        return ""
    lines = ["【联网检索（最新政策/讲话）】"]
    for r in results:
        lines.append(f"- {r['title']}：{r['content']}")
    return "\n".join(lines)
