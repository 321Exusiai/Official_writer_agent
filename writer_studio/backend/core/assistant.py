"""辅助智能体（Assistant Agent）—— 内置的"随叫随到小帮手"

- 驱动模型：辅助轨道（GLM-4-Flash，免费），未启用时诚实降级为规则助手。
- 定位：问答 + 工具调用，处理**写作流程之外**的事务（资料/画像/收藏/搜索/知识/导出）。
- 行为边界：不参与写作核心流程；只基于工具结果回答，防幻觉；不越权修改。
- 实现：OpenAI 兼容 function calling 工具循环（复用 LLMClient.chat_with_tools）。
"""
from typing import Callable, Dict, List

from ..domain.registry import Registry
from . import profile as profile_core
from . import retrieval

SYSTEM_PROMPT = """你是「公文写作工作室」的内置辅助智能体（Assistant Agent）。

【你的职责】
回答用户关于本系统与公文写作的问答，并通过工具帮用户处理写作流程之外的事务：
资料整理与解读、用户画像分析、收藏夹管理、全局搜索、知识库查询、项目概览、导出等。

【能力边界 · 必须遵守】
1. 你【不参与】文章写作、多角色协商、审查等核心写作流程——这些由主写作引擎完成。
   用户要"写一篇完整公文"时，引导其使用工作流，而不是代写全文（可提供思路、要点、片段）。
2. 你只能基于工具返回的结果回答；工具未返回的信息，明确说"我没有这方面的数据"，绝不编造。
3. 涉及删除/修改用户数据的操作，先向用户说明将要做什么，确认后再执行。

【防幻觉规则】
1. 引用数据必须来自工具结果，并注明来源（如"知识库检索到…""画像分析显示…"）。
2. 不确定时明确说明"我不确定"，不猜测、不编造。
3. 不虚构项目、数据、审查结果、收藏内容。
4. 工具执行失败时如实报告失败原因。

【回答风格】
简洁、专业、直接。需要工具就调用工具，把工具结果整理成清晰的中文回答。

【可用工具】由系统在每次请求时注入。"""


def _tool(name: str, description: str, props: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOLS: List[dict] = [
    _tool("search_knowledge", "检索内置知识库（范文/术语/政策讲话/过渡句/格式化用语）", {
        "keyword": {"type": "string", "description": "检索关键词，如'新质生产力'、'研学通讯'"},
        "kind": {"type": "string", "description": "term|policy|exemplar|transition|formulaic，缺省全查"},
    }, ["keyword"]),
    _tool("explain_term", "解释一个公文/政策术语的定义、用法与常见误用", {
        "term": {"type": "string"},
    }, ["term"]),
    _tool("search_global", "全局搜索：跨项目匹配名称/草稿/参考文本/收藏，以及综合收藏夹", {
        "query": {"type": "string"},
    }, ["query"]),
    _tool("analyze_profile", "分析用户画像：写作弱点与潜在 bias 预警", {}, []),
    _tool("list_favorites", "查看综合收藏夹的词汇与句子", {}, []),
    _tool("add_favorite", "把词汇或句子收藏到综合收藏夹或指定项目", {
        "kind": {"type": "string", "description": "term|phrase"},
        "value": {"type": "string"},
        "project_id": {"type": "string", "description": "留空=综合收藏夹"},
    }, ["kind", "value"]),
    _tool("analyze_reference", "解读一段参考文本：提取值得借鉴的句子、高频词汇、句式特征", {
        "text": {"type": "string"},
    }, ["text"]),
    _tool("list_projects", "列出所有项目及基本状态", {}, []),
    _tool("get_project_summary", "查看指定项目的问卷总结/风格要求/工作要求/参考文本数量", {
        "project_id": {"type": "string"},
    }, ["project_id"]),
    _tool("export_project_md", "把指定项目的终稿整理为 Markdown（含版本列表与审查摘要）", {
        "project_id": {"type": "string"},
    }, ["project_id"]),
]


class AssistantAgent:
    """辅助智能体：GLM-4-Flash 驱动，function calling 工具循环。"""

    def __init__(self, llm):
        self.llm = llm
        self._store = None

    @property
    def available(self) -> bool:
        return bool(self.llm and self.llm.available)

    def _get_store(self):
        if self._store is None:
            from ..storage.store import Store
            self._store = Store()
        return self._store

    # ── 工具执行器 ──
    def _executor(self, name: str, args: dict) -> str:
        try:
            handler = getattr(self, f"_exec_{name}", None)
            if not handler:
                return f"工具 {name} 不存在"
            return handler(args)
        except Exception as e:
            return f"工具执行失败：{e}"

    def _exec_search_knowledge(self, args) -> str:
        kw = args.get("keyword", "")
        kind = args.get("kind", "")
        out = []
        if kind in ("", "term") or kind == "term":
            terms = Registry.load("terminology")
            hits = {t: v for t, v in terms.items() if kw in t}
            if hits:
                t = list(hits)[0]
                out.append(f"术语「{t}」：{hits[t].get('definition', '')}（误用：{hits[t].get('common_misuse', '')}）")
        if kind in ("", "policy") or kind == "policy":
            pols = [p for p in Registry.load("policy").values() if kw in p.get("text", "") or kw in p.get("topic", "")]
            for p in pols[:3]:
                out.append(f"政策/讲话：{p['text']}（{p.get('source', '')}）")
        if kind in ("", "exemplar") or kind == "exemplar":
            exs = [e for e in Registry.load("exemplars").values() if kw in e.get("title", "")]
            for e in exs[:3]:
                out.append(f"范文《{e['title']}》：{(e.get('structure_skeleton', '') or '')[:60]}")
        if kind in ("", "transition"):
            for style, phrases in Registry.load("transitions").items():
                if any(kw in p for p in phrases):
                    out.append(f"{style}过渡句：{'/'.join(phrases[:3])}")
        return "\n".join(out) if out else f"知识库中未找到与「{kw}」相关的内容"

    def _exec_explain_term(self, args) -> str:
        term = args.get("term", "")
        terms = Registry.load("terminology")
        info = terms.get(term)
        if not info:
            return f"术语库中未收录「{term}」（现有 {len(terms)} 条，可先检索）"
        return (f"【{term}】\n定义：{info.get('definition', '')}\n"
                f"出处：{info.get('context', '')}\n用法：{info.get('usage_note', '')}\n"
                f"常见误用：{info.get('common_misuse', '')}")

    def _exec_search_global(self, args) -> str:
        kw = args.get("query", "")
        store = self._get_store()
        out = []
        for p in store.list_projects():
            hit = kw in (p.name or "") or kw in (p.draft or "") or kw in (p.description or "")
            refs = [r for r in p.references if kw in r.title or kw in r.content]
            favs = [t for t in list(p.favorite_terms) + list(p.favorite_phrases) if kw in t]
            if hit or refs or favs:
                out.append(f"项目「{p.name}」：参考{len(refs)}条、收藏{len(favs)}条")
        try:
            from ..api.profile import load_profile
            prof = load_profile()
            favs = [t for t in list(prof.favorite_terms) + list(prof.favorite_phrases) if kw in t]
            if favs:
                out.append(f"综合收藏：{'、'.join(favs)}")
        except Exception:
            pass
        return "\n".join(out) if out else f"未找到与「{kw}」相关的内容"

    def _exec_analyze_profile(self, args) -> str:
        projects = self._get_store().list_projects()
        a = profile_core.analyze_profile(projects)
        lines = [f"画像分析：{a['summary']}"]
        for w in a["weaknesses"]:
            lines.append(f"⚠️ {w}")
        for b in a["bias_warnings"]:
            lines.append(f"🧭 {b}")
        return "\n".join(lines)

    def _exec_list_favorites(self, args) -> str:
        from ..api.profile import load_profile
        p = load_profile()
        return (f"综合收藏夹：\n词汇：{'、'.join(p.favorite_terms) or '（空）'}\n"
                f"句子：{'、'.join(p.favorite_phrases) or '（空）'}")

    def _exec_add_favorite(self, args) -> str:
        from ..api.profile import load_profile, save_profile
        from ..storage.store import Store
        kind = args.get("kind", "term")
        value = args.get("value", "")
        pid = args.get("project_id", "")
        if not value:
            return "缺少要收藏的内容"
        if pid:
            store = Store()
            p = store.get_project(pid)
            if not p:
                return f"项目 {pid} 不存在"
            lst = p.favorite_terms if kind == "term" else p.favorite_phrases
            if value not in lst:
                lst.append(value)
            store.update_project(pid, p)
            return f"已收藏「{value}」到项目「{p.name}」"
        prof = load_profile()
        lst = prof.favorite_terms if kind == "term" else prof.favorite_phrases
        if value not in lst:
            lst.append(value)
        save_profile(prof)
        return f"已收藏「{value}」到综合收藏夹"

    def _exec_analyze_reference(self, args) -> str:
        return profile_core.analyze_reference(args.get("text", ""))

    def _exec_list_projects(self, args) -> str:
        projects = self._get_store().list_projects()
        if not projects:
            return "还没有项目"
        return "\n".join(
            f"- {p.name}（{p.status.value}，参考{len(p.references)}篇，审查{len(p.review_history) + len(p.review_results)}次）"
            for p in projects
        )

    def _exec_get_project_summary(self, args) -> str:
        p = self._get_store().get_project(args.get("project_id", ""))
        if not p:
            return "项目不存在"
        return (f"项目「{p.name}」\n状态：{p.status.value}\n"
                f"风格要求：{p.style_requirements or '（未设）'}\n工作要求：{p.work_requirements or '（未设）'}\n"
                f"问卷总结：{p.questionnaire_summary or '（未完成问卷）'}\n"
                f"参考文本：{len(p.references)}篇\n收藏：词汇{len(p.favorite_terms)}/句子{len(p.favorite_phrases)}")

    def _exec_export_project_md(self, args) -> str:
        p = self._get_store().get_project(args.get("project_id", ""))
        if not p:
            return "项目不存在"
        lines = [f"# {p.name}", "", "## 终稿", "", p.final_draft or p.draft or "（无终稿）", ""]
        if p.versions:
            lines.append("## 多版本")
            for v in p.versions:
                lines.append(f"- {v.doc_type_name}（{v.word_count}字）")
            lines.append("")
        if p.review_history or p.review_results:
            rs = list(p.review_history) + list(p.review_results)
            lines.append(f"## 审查摘要（{len(rs)}次）")
            lines.append(f"最近评分：{rs[-1].score}，通过：{'是' if rs[-1].passed else '否'}")
            lines.append("")
        if p.style_requirements or p.work_requirements:
            lines.append("## 项目要求")
            if p.style_requirements:
                lines.append(f"- 风格：{p.style_requirements}")
            if p.work_requirements:
                lines.append(f"- 工作：{p.work_requirements}")
        return "\n".join(lines)

    # ── 对话 ──
    def chat(self, message: str, history: list = None) -> dict:
        """处理一条用户消息，返回 {"reply", "mode", "tool_calls"}。

        mode: llm（GLM 驱动）| rule（无 GLM 时规则降级）
        """
        history = history or []
        if not self.available:
            return {"reply": self._rule_reply(message), "mode": "rule", "tool_calls": []}
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for h in history[-8:]:
            messages.append(h)
        messages.append({"role": "user", "content": message})
        tool_calls = []
        # 直接构造带工具的消息调用
        raw = self._run_tools(messages, tool_calls)
        if raw is None:
            return {"reply": self._rule_reply(message), "mode": "rule", "tool_calls": tool_calls}
        return {"reply": raw, "mode": "llm", "tool_calls": tool_calls}

    def _run_tools(self, messages: list, tool_calls: list):
        """工具循环：GLM 自主决定调用工具，直到输出最终回答。"""
        url = self.llm.config.api_base.rstrip("/") + "/chat/completions"
        import json
        import httpx
        for _ in range(4):
            payload = {
                "model": self.llm.config.model,
                "messages": messages,
                "temperature": self.llm.config.temperature,
                "max_tokens": self.llm.config.max_tokens,
                "tools": TOOLS,
                "tool_choice": "auto",
            }
            try:
                resp = httpx.post(
                    url, json=payload, timeout=60,
                    headers={"Authorization": f"Bearer {self.llm.config.api_key}"},
                )
                if resp.status_code != 200:
                    return None
                msg = (resp.json().get("choices") or [{}])[0].get("message", {})
            except httpx.HTTPError:
                return None
            calls = msg.get("tool_calls")
            if not calls:
                return msg.get("content")
            messages.append(msg)
            for tc in calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                result = self._executor(name, args)
                tool_calls.append({"name": name, "args": args, "result": result[:120]})
                messages.append({"role": "tool", "tool_call_id": tc.get("id", ""), "content": result})
        return None

    def _rule_reply(self, message: str) -> str:
        """无 GLM 时的规则降级：识别常见意图，给出确定性回答。"""
        if "搜索" in message or "查找" in message or "检索" in message:
            return "（规则模式）我没有启用模型，无法智能检索。请到「设置」启用辅助轨道（免费 GLM-4-Flash），或在知识库/全局搜索里手动查找。"
        if "画像" in message or "弱点" in message or "bias" in message.lower():
            a = profile_core.analyze_profile(self._get_store().list_projects())
            return f"（规则模式·画像分析）{a['summary']}\n" + "\n".join(f"⚠️ {w}" for w in a["weaknesses"]) + "\n" + "\n".join(f"🧭 {b}" for b in a["bias_warnings"])
        if "项目" in message and ("哪些" in message or "列表" in message or "概览" in message):
            return self._exec_list_projects({})
        if "收藏" in message:
            return self._exec_list_favorites({})
        return ("（规则模式）当前未启用辅助轨道模型。启用后我可以：检索知识库与政策讲话、全局搜索、分析用户画像、整理收藏与资料、导出文章等。"
                "请到「设置 → 辅助轨道」填写免费 GLM-4-Flash 的 API Key。")


def get_tools_info() -> list:
    """返回工具清单（供前端展示助手能力）。"""
    return [{"name": t["function"]["name"], "description": t["function"]["description"]} for t in TOOLS]
