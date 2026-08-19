"""辅助智能体（Assistant Agent）—— 内置的"随叫随到小帮手"

- 驱动模型：辅助轨道（GLM-4-Flash，免费），未启用时诚实降级为规则助手。
- 定位：问答 + 工具调用，处理**写作流程之外**的事务（资料/画像/收藏/搜索/知识/导出）。
- 行为边界：不参与写作核心流程；只基于工具结果回答，防幻觉；不越权修改。
- 实现：OpenAI 兼容 function calling 工具循环（复用 LLMClient.chat_with_tools）。
"""

from ..domain.registry import Registry
from . import profile as profile_core

SYSTEM_PROMPT = """你是「公文写作工作室」的内置辅助智能体（Assistant Agent），针对公文写作场景特化。

【你的职责】
回答用户关于本系统与公文写作的问答，并通过工具帮用户处理写作流程之外的事务：
资料整理与解读、用户画像分析、收藏夹管理、全局搜索、知识库查询、项目概览、导出等。

【工作方式：ReAct 多轮循环】
严格按"思考 → 行动 → 观察"循环工作：
1. 思考（Think）：先想清楚用户要什么、需要哪些信息、第一步调用哪个工具。
2. 行动（Act）：调用工具获取信息或执行操作。一次回答里可以【连续调用多个工具】，
   让工具结果互相衔接（例如：先 search_knowledge 找到范文 → 再 analyze_reference 解读 → 再 add_favorite 收藏）。
3. 观察（Observe）：根据工具返回的结果继续思考；信息不足就再调工具，直到能给出完整、准确的回答。
4. 最后综合所有工具结果，给出清晰的中文回答。

【多工具协作原则】
- 复杂任务拆成多步，按依赖顺序调用工具，不要一次问用户要所有信息。
- 工具结果要综合：多个工具的结果拼成完整答案（如"画像+项目+收藏"三合一）。
- 一个工具的结果可以作为下一个工具的参数依据。

【上下文注意机制】
- 充分利用会话历史：用户之前提过的偏好、项目名、结论，后续保持一致。
- 若提供了"当前项目"上下文，回答时优先结合它。
- 只依据工具结果和会话历史作答；工具没返回的内容，明确说"没有这方面的数据"。

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
简洁、专业、直接。需要工具就调用工具，把多个工具结果整理成清晰的中文回答；
结构化的信息（列表、项目、得分）用要点呈现。

【可用工具】由系统在每次请求时注入。每个工具都注明了用途与适用场景。"""


def _tool(name: str, description: str, props: dict, required: list) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": props, "required": required},
        },
    }


TOOLS: list[dict] = [
    _tool(
        "search_knowledge",
        "检索内置知识库（范文/术语/政策讲话/过渡句/格式化用语）。适用：用户想了解某个主题的规范表述、找范文参考、查政策用语。可配合 analyze_reference 解读检索到的内容。",
        {
            "keyword": {"type": "string", "description": "检索关键词，如'新质生产力'、'研学通讯'"},
            "kind": {"type": "string", "description": "term|policy|exemplar|transition|formulaic，缺省全查"},
        },
        ["keyword"],
    ),
    _tool(
        "explain_term",
        "解释一个公文/政策术语的定义、出处、用法与常见误用。适用：用户问'XX是什么意思/怎么用'。比 search_knowledge 更聚焦单术语。",
        {
            "term": {"type": "string"},
        },
        ["term"],
    ),
    _tool(
        "search_global",
        "全局搜索：跨项目匹配名称/草稿/参考文本/收藏，以及综合收藏夹。适用：用户问'哪里提到过 XX''我有收藏过 XX 吗'。可配合 get_project_summary 深入某个命中项目。",
        {
            "query": {"type": "string"},
        },
        ["query"],
    ),
    _tool(
        "analyze_profile",
        "分析用户画像：写作弱点与潜在 bias 预警。适用：用户问'我有什么问题''我的写作风格如何'。可与 list_projects 一起给出全景。",
        {},
        [],
    ),
    _tool("list_favorites", "查看综合收藏夹的词汇与句子。适用：用户问'我收藏了什么'。", {}, []),
    _tool(
        "add_favorite",
        "把词汇或句子收藏到综合收藏夹或指定项目。适用：用户在对话中提到想收藏的好词好句，或要求'把这句话收藏起来'。可配合 analyze_reference 提取的词汇。",
        {
            "kind": {"type": "string", "description": "term|phrase"},
            "value": {"type": "string"},
            "project_id": {"type": "string", "description": "留空=综合收藏夹"},
        },
        ["kind", "value"],
    ),
    _tool(
        "analyze_reference",
        "解读一段参考文本：提取值得借鉴的句子、高频词汇、句式特征。适用：用户粘贴文章/段落，希望学习其写法。可配合 add_favorite 把提炼的好词好句收藏。",
        {
            "text": {"type": "string"},
        },
        ["text"],
    ),
    _tool(
        "list_projects",
        "列出所有项目及基本状态（参考数/审查次数）。适用：用户问'有哪些项目''我的进度'。可配合 get_project_summary 查看单个项目。",
        {},
        [],
    ),
    _tool(
        "get_project_summary",
        "查看指定项目的问卷总结/风格要求/工作要求/参考文本数量。适用：用户问'某个项目怎么样''那个项目的要求是什么'。",
        {
            "project_id": {"type": "string"},
        },
        ["project_id"],
    ),
    _tool(
        "export_project_md",
        "把指定项目的终稿整理为 Markdown（含版本列表与审查摘要）",
        {
            "project_id": {"type": "string"},
        },
        ["project_id"],
    ),
    _tool(
        "pin_to_scratchpad",
        "把写作灵感、核心要点、修改建议或指示直接沉淀/置顶到指定项目的写作备忘录（Scratchpad）。"
        "适用：用户在对话中提炼出关键思路、提出写作要求、或希望把某个好点子直接用于公文正文起草。",
        {
            "project_id": {"type": "string", "description": "项目 ID"},
            "note": {"type": "string", "description": "要置顶沉淀的要点/灵感/指令内容"},
        },
        ["project_id", "note"],
    ),
    _tool(
        "search_web",
        "实时联网搜索最新政策、新闻、讲话、行业动态（需在「设置→主轨道」配置搜索 API Key）。"
        "适用：知识库没有的新政策、最新会议精神、时事素材。比 search_knowledge 更新、更实时，但只返回网络公开信息。",
        {
            "query": {"type": "string", "description": "搜索关键词，如'2025年政府工作报告 教育'"},
        },
        ["query"],
    ),
    _tool(
        "search_project_history",
        "跨所有历史项目草稿、素材与备忘录进行 BM25 全文检索。适用：用户问'我之前写过关于XX的材料吗''查查过往文章里怎么写XX的'。",
        {
            "query": {"type": "string", "description": "检索关键词，如'新型工业化 数字化改造'"},
        },
        ["query"],
    ),
    _tool(
        "search_custom_knowledge",
        "检索单位专有知识库（单位内部政策、领导讲话、考核办法、专有业务术语）。适用：用户询问本单位特有要求或领导近期讲话指示。",
        {
            "query": {"type": "string", "description": "检索关键词"},
            "category": {"type": "string", "description": "policy|speech|rule，留空查全部"},
        },
        ["query"],
    ),
    _tool(
        "add_custom_knowledge",
        "将单位政策、领导讲话金句或工作规范录入沉淀至单位专有知识库。适用：用户要求'把这句话记到单位知识库'或'把局长讲话要求记录下来'。",
        {
            "title": {"type": "string", "description": "条目标题"},
            "content": {"type": "string", "description": "具体内容"},
            "category": {"type": "string", "description": "policy(政策)|speech(讲话)|rule(规范)"},
            "source": {"type": "string", "description": "出处/文件号/讲话场合"},
        },
        ["title", "content"],
    ),
    _tool(
        "get_red_team_report",
        "查看当前项目的分管领导审签挑刺意见与舆情红蓝军压力测试排查结果。适用：用户询问文稿审签意见、潜在舆情风险点或整改建议。",
        {
            "project_id": {"type": "string", "description": "项目 ID"},
        },
        ["project_id"],
    ),
    _tool(
        "inspect_document_standard",
        "查询《党政机关公文处理工作条例》（中办发〔2012〕14号）与 GB/T 9704-2012 国家公文格式标准规范。适用：用户询问公文字体字号、版心边距、行距缩进、发文字号六角括号、联合行文印章、法定文种15种等规范铁律。",
        {
            "topic": {"type": "string", "description": "查询主题，如'发文字号'、'联合盖章'、'通报与通告区别'、'正文字体行距'"},
        },
        ["topic"],
    ),
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
            try:
                from ..api.projects import store

                self._store = store
            except Exception:
                from ..storage.store import Store

                self._store = Store()
        return self._store

    # ── 工具执行器 ──
    def _executor(self, name: str, args: dict) -> str:
        try:
            handler = getattr(self, f"_exec_{name}", None)
            if not handler:
                return f"工具 {name} 不存在"
            res = handler(args)
            from .retrieval import truncate_and_summarize

            return truncate_and_summarize(str(res), max_chars=300)
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
        return (
            f"【{term}】\n定义：{info.get('definition', '')}\n"
            f"出处：{info.get('context', '')}\n用法：{info.get('usage_note', '')}\n"
            f"常见误用：{info.get('common_misuse', '')}"
        )

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
        profile_core.enhance_profile_summary(a, self.llm if self.available else None)
        lines = [f"画像分析：{a['summary']}"]
        for w in a["weaknesses"]:
            lines.append(f"⚠️ {w}")
        for b in a["bias_warnings"]:
            lines.append(f"🧭 {b}")
        return "\n".join(lines)

    def _exec_list_favorites(self, args) -> str:
        from ..api.profile import load_profile

        p = load_profile()
        return (
            f"综合收藏夹：\n词汇：{'、'.join(p.favorite_terms) or '（空）'}\n"
            f"句子：{'、'.join(p.favorite_phrases) or '（空）'}"
        )

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
        return (
            f"项目「{p.name}」\n状态：{p.status.value}\n"
            f"风格要求：{p.style_requirements or '（未设）'}\n工作要求：{p.work_requirements or '（未设）'}\n"
            f"问卷总结：{p.questionnaire_summary or '（未完成问卷）'}\n"
            f"参考文本：{len(p.references)}篇\n收藏：词汇{len(p.favorite_terms)}/句子{len(p.favorite_phrases)}"
        )

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

    def _exec_pin_to_scratchpad(self, args) -> str:
        pid = args.get("project_id", "")
        note = args.get("note", "").strip()
        if not pid or not note:
            return "缺少项目 ID 或备忘内容"
        store = self._get_store()
        p = store.get_project(pid)
        if not p:
            return f"项目 {pid} 不存在"
        if note not in p.scratchpad:
            p.scratchpad.append(note)
            store.update_project(pid, p)
            return f"已成功将要点「{note}」同步沉淀至项目「{p.name}」的写作备忘录，主写作引擎起草时将自动融入此要点。"
        return f"要点已存在于项目「{p.name}」的写作备忘录中"

    def _exec_search_web(self, args) -> str:
        """实时联网搜索：复用主轨道的搜索 key（Tavily/博查）。"""
        from . import web_search

        query = args.get("query", "")
        if not query:
            return "缺少搜索关键词"
        try:
            from ..api.config import get_client

            main = get_client()
            key = getattr(main.config, "search_api_key", "")
            provider = getattr(main.config, "search_provider", "tavily")
        except Exception:
            key, provider = "", "tavily"
        if not key:
            return "未配置联网搜索：请到「设置 → 主轨道」填写搜索 API Key（Tavily）后，我才能实时检索最新政策与讲话。"
        results = web_search.search_web(query, provider, key, limit=4)
        if not results:
            return f"联网未检索到与「{query}」相关的内容"
        lines = [f"【联网检索 · {query}】"]
        for r in results:
            lines.append(f"- {r['title']}：{r['content']}（{r['url']}）")
        return "\n".join(lines)

    def _exec_search_project_history(self, args) -> str:
        query = args.get("query", "")
        if not query:
            return "缺少搜索关键词"
        store = self._get_store()
        hits = store.search_projects(query, limit=5)
        if not hits:
            return f"历史项目草稿中未检索到与「{query}」相关的内容"
        lines = [f"【历史项目全文检索 · {query}】"]
        for h in hits:
            lines.append(f"- 项目「{h['name']}」（{h.get('writing_mode', '公文')}）：\n  草稿片段：{h.get('draft_snippet', '')}")
        return "\n\n".join(lines)

    def _exec_search_custom_knowledge(self, args) -> str:
        from ..storage.custom_kb import CustomKnowledgeStore

        query = args.get("query", "").lower()
        cat = args.get("category", "")
        items = CustomKnowledgeStore.load_all()
        if cat:
            items = [i for i in items if i.category == cat]
        if query:
            words = [w for w in query.split() if w]
            items = [
                i for i in items
                if any(w in (i.title + " " + i.content + " " + i.source).lower() for w in words)
            ]
        if not items:
            return f"单位专有知识库中未找到与「{query}」相关的内容"
        lines = [f"【单位专有知识库检索结果（共 {len(items)} 条）】"]
        for i in items[:4]:
            lines.append(f"- 【{i.title}】（{i.category} · {i.source or '单位专有'}）：\n  {i.content}")
        return "\n\n".join(lines)

    def _exec_add_custom_knowledge(self, args) -> str:
        from ..storage.custom_kb import CustomKnowledgeStore

        title = args.get("title", "").strip()
        content = args.get("content", "").strip()
        cat = args.get("category", "policy")
        src = args.get("source", "")
        if not title or not content:
            return "缺少条目标题或内容"
        CustomKnowledgeStore.add_item(title=title, content=content, category=cat, source=src)
        return f"已成功将「{title}」录入单位专有知识库（分类：{cat}），后续起草将自动支持检索与参考！"

    def _exec_get_red_team_report(self, args) -> str:
        pid = args.get("project_id", "")
        if not pid:
            return "缺少项目 ID"
        p = self._get_store().get_project(pid)
        if not p:
            return f"项目 {pid} 不存在"
        if not p.red_team_result:
            return f"项目「{p.name}」尚未执行分管领导审签与舆情红蓝军测试，可点击「👔 模拟领导审签/红蓝军测试」进行评估。"
        rt = p.red_team_result
        lines = [
            f"【项目「{p.name}」红蓝军审签压力测试报告】",
            f"判定结果：{rt.get('verdict', '通过')}（综合评分：{rt.get('overall_score', 85)}分）",
            f"领导审签意见：{rt.get('superior_critique', '无特殊意见')}",
            "舆情风险排查点：",
        ]
        for risk in rt.get("pr_risk_points", []):
            lines.append(f"  - ⚠️ {risk}")
        if rt.get("actionable_fixes"):
            lines.append(f"整改建议：{'；'.join(rt.get('actionable_fixes', []))}")
        return "\n".join(lines)

    def _exec_inspect_document_standard(self, args) -> str:
        topic = args.get("topic", "")
        t = topic.lower()
        if any(k in t for k in ("发文字号", "括号", "年份")):
            return "【发文字号规范】年份必须使用六角括号「〔 〕」（GB/T 9704-2012），严禁使用中括号 [ ]、方括号或圆括号。序号不编虚位（即不写成第01号，写第1号）。如：国发〔2026〕1号。"
        if any(k in t for k in ("盖章", "印章", "联合行文", "签名")):
            return "【印章与签署规范】联合行文时，发文机关署名按照党政军群顺序排列，主办机关居前；各机关印章必须自左至右、自上而下对齐排列，印章不得压住正文，但必须压住成文日期（'上不压正文，下压成文日期'）。"
        if any(k in t for k in ("字体", "字号", "版心", "边距", "行距", "排版")):
            return "【GB/T 9704-2012 版面规范】\n- 版心：A4纸，上边距37mm，下边距35mm，左边距28mm，右边距26mm。\n- 标题：二号方正小标宋体，居中。\n- 主送机关：三号仿宋体，顶格，标全称或规范简称。\n- 正文：三号仿宋体，首行缩进2字符，固定行距28磅。\n- 一级标题：三号黑体（一、...）；二级标题：三号楷体（（一）...）；三级标题：三号仿宋加粗（1. ...）。"
        if any(k in t for k in ("请示", "报告", "通报", "通告", "文种")):
            return "【法定文种铁律】《党政机关公文处理工作条例》法定文种15种：决议、决定、命令、公报、公告、通告、意见、通知、通报、报告、请示、批复、条例、函、纪要。行文铁律：\n1. 请示必须'一文一事'，严禁在报告中夹带请示事项（'请示报告'属于严重违规混用）；\n2. 通报用于表彰先进、批评错误、传达重要精神，不作请批要求；\n3. 向上级行文原则上主送一个上级机关，不抄送下级机关。"
        return (
            "【党政机关公文核心规范】\n"
            "1. 法定文种唯一性：依据《党政机关公文处理工作条例》（中办发〔2012〕14号），15种法定文种严格按行文方向选用。\n"
            "2. 排版标准：GB/T 9704-2012，二号小标宋标题、三号仿宋正文、一级黑体、二级楷体、28磅行距、首行缩进2字。\n"
            "3. 发文字号：机关代字+六角括号年份〔2026〕+顺序号。\n"
            "4. 行文铁律：一文一事、不越级请示、报告不夹带请示。"
        )

    # ── 对话 ──
    def chat(self, message: str, history: list = None, project_id: str = "") -> dict:
        """处理一条用户消息，返回 {"reply", "mode", "tool_calls"}。

        mode: llm（GLM 驱动）| rule（无 GLM 时规则降级）| error（网络/鉴权异常）
        project_id: 当前活动项目（注入上下文，供助手结合项目作答）
        """
        history = history or []
        # 长期记忆：从对话自动提炼写作偏好写入画像（受开关控制，静默失败）
        self._remember_preferences(message)
        # 快捷命令（确定性，不经 LLM）
        quick = self._handle_quick_command(message)
        if quick is not None:
            return {"reply": quick, "mode": "rule", "tool_calls": []}
        if not self.available:
            return {"reply": self._rule_reply(message), "mode": "rule", "tool_calls": []}
        messages = [{"role": "system", "content": self._build_system_prompt(project_id)}]
        for h in history[-10:]:
            messages.append(h)
        messages.append({"role": "user", "content": message})
        tool_calls = []
        raw = self._run_tools(messages, tool_calls)
        if raw is None:
            err = getattr(self.llm, "last_error", "") or "模型网络通信失败，未返回有效回答"
            return {"reply": f"【辅助智能体响应失败】{err}。请检查模型设置与网络连接。", "mode": "error", "tool_calls": tool_calls}
        return {"reply": raw, "mode": "llm", "tool_calls": tool_calls}

    def _remember_preferences(self, message: str):
        """长期记忆：从用户消息提炼写作偏好，去重写入画像（可开关，静默失败）。"""
        if not message or message.strip().startswith("/"):
            return
        try:
            from ..api.profile import load_profile, save_profile

            prof = load_profile()
            if not getattr(prof, "memory_enabled", True):
                return
            prefs = profile_core.extract_preferences_from_dialog(message)
            if not prefs:
                return
            changed = False
            for p in prefs:
                if p and p not in prof.preferences:
                    prof.preferences.append(p)
                    changed = True
            if changed:
                prof.preferences = prof.preferences[:30]
                save_profile(prof)
        except Exception:
            pass

    def _build_system_prompt(self, project_id: str = "") -> str:
        """系统提示词 + 用户画像偏好（长期记忆） + 当前项目全景上下文 + 公文私教教学模式。"""
        prompt = SYSTEM_PROMPT
        # 长期记忆与私教教学模式
        try:
            from ..api.profile import load_profile

            prof = load_profile()
            if prof.preferences:
                prompt += "\n\n【用户写作偏好（长期记忆）】\n" + "\n".join(f"- {p}" for p in prof.preferences)
            if prof.weaknesses:
                prompt += "\n\n【用户常见写作薄弱点（画像提醒）】\n" + "\n".join(f"- {w}" for w in prof.weaknesses[:3])
            if getattr(prof, "coach_mode", True):
                prompt += (
                    "\n\n【公文私教教学模式已启用】"
                    "\n在解答用户关于公文体例、修改建议、文种选型或段落润色时，请自然附带「💡 公文私教·写作精要」，"
                    "通俗透彻地解释'为什么这样写才地道/为什么这样修改'背后的公文逻辑与体例规范，帮助写作者举一反三。"
                )
        except Exception:
            pass

        if project_id:
            p = self._get_store().get_project(project_id)
            if p:
                proj_lines = [
                    f"【当前活动项目全景看板】",
                    f"项目名称：{p.name}（状态：{p.status.value}）",
                    f"文种/模式：{p.doc_type or '未选定'} / {p.writing_mode or 'administrative'}",
                    f"当前草稿字数：{len(p.draft)} 字",
                ]
                if p.draft:
                    proj_lines.append(f"草稿开篇片段：{p.draft[:150]}…")
                    if len(p.draft) > 200:
                        proj_lines.append(f"草稿最新进展：…{p.draft[-150:]}")
                if p.scratchpad:
                    proj_lines.append(f"作者备忘录（{len(p.scratchpad)}条）：" + "；".join(p.scratchpad[:3]))
                if p.review_results:
                    findings = [f.issue for f in p.review_results[0].findings]
                    if findings:
                        proj_lines.append(f"待整改审查缺陷（{len(findings)}处）：" + "；".join(findings[:3]))
                if p.red_team_result:
                    proj_lines.append(f"红蓝军审签判定：{p.red_team_result.get('verdict', '通过')}")

                prompt += "\n\n" + "\n".join(proj_lines) + "\n（回答与该项目相关的问题时请优先深度融合以上信息。）"
        return prompt

    def get_contextual_actions(self, project_id: str = "") -> list[dict]:
        """根据当前工作流阶段与项目状态，动态生成情境动作胶囊（Contextual Action Pills）。"""
        actions = []
        if not project_id:
            return [
                {"label": "🔍 检索政策与金句", "cmd": "/搜索 新质生产力", "icon": "🔍"},
                {"label": "👤 查看我的写作画像", "cmd": "/画像", "icon": "👤"},
                {"label": "📚 浏览项目列表", "cmd": "/项目", "icon": "📚"},
            ]
        p = self._get_store().get_project(project_id)
        if not p:
            return []

        # 1. 审查阶段且有未通过或低分
        if p.review_results:
            last_res = p.review_results[0]
            if not last_res.passed or last_res.score < 85:
                actions.append({"label": "⚡ 一键自愈 (85分+)", "action": "auto_heal", "icon": "⚡", "hint": "按重要级自动循环辩论与定向修复"})
            if last_res.thought_bubbles:
                actions.append({"label": "⚖️ 查看审查辩论共识", "action": "view_debate", "icon": "⚖️", "hint": "查看主笔与审稿人分歧调解"})
        # 2. 方案阶段
        if p.plan and not p.draft:
            actions.append({"label": "📌 提炼指示进备忘录", "cmd": f"请帮我把这条核心要求写入项目「{p.name}」的写作备忘录：", "icon": "📌"})
            actions.append({"label": "🏛️ 解释文种与风格依据", "cmd": f"结合项目「{p.name}」的目标，请深入分析为什么推荐该文种和风格？", "icon": "🏛️"})
        # 3. 参考文本分析
        if p.references:
            actions.append({"label": "💡 提炼参考文章金句", "cmd": f"请帮我从项目「{p.name}」的参考文章中提炼可用金句与句式", "icon": "💡"})

        actions.append({"label": f"🔍 检索「{p.name[:10]}」相关政策", "cmd": f"/搜索 {p.name[:15]}", "icon": "🔍"})
        return actions

    def _handle_quick_command(self, message: str):
        """快捷命令（斜杠规则）：/画像 /项目 /收藏 /搜索 <q> /资料 <q> /术语 <t> /导出 <pid>。"""
        m = message.strip()
        if m.startswith("/"):
            cmd, _, rest = m[1:].partition(" ")
            rest = rest.strip()
            if cmd in ("画像", "分析", "profile"):
                return self._exec_analyze_profile({})
            if cmd in ("项目", "projects", "列表"):
                return self._exec_list_projects({})
            if cmd in ("收藏", "favorites"):
                return self._exec_list_favorites({})
            if cmd in ("搜索", "search") and rest:
                return self._exec_search_global({"query": rest})
            if cmd in ("资料", "知识", "kb") and rest:
                return self._exec_search_knowledge({"keyword": rest})
            if cmd in ("术语", "term") and rest:
                return self._exec_explain_term({"term": rest})
            if cmd in ("导出", "export") and rest:
                return self._exec_export_project_md({"project_id": rest})
            if cmd in ("帮助", "help", "?"):
                return (
                    "快捷命令：\n/画像 查看画像分析\n/项目 项目列表\n/收藏 综合收藏夹\n"
                    "/搜索 <关键词> 全局搜索\n/资料 <关键词> 知识库检索\n/术语 <词> 术语解释\n/导出 <项目id> 导出 Markdown"
                )
        return None

    def _run_tools(self, messages: list, tool_calls: list):
        """ReAct 工具循环：GLM 自主决定调用工具（支持多工具并发与死循环熔断），上限 6 轮。"""
        import json
        from concurrent.futures import ThreadPoolExecutor

        import httpx

        url = self.llm.config.api_base.rstrip("/") + "/chat/completions"
        call_history_signatures = []

        for round_idx in range(6):
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
                    url,
                    json=payload,
                    timeout=60,
                    headers={"Authorization": f"Bearer {self.llm.config.api_key}"},
                )
                if resp.status_code != 200:
                    self.llm.last_error = f"API 状态码异常 (HTTP {resp.status_code})：{resp.text[:120]}"
                    return None
                msg = (resp.json().get("choices") or [{}])[0].get("message", {})
            except httpx.TimeoutException:
                self.llm.last_error = "请求超时 (60s)"
                return None
            except httpx.HTTPError as e:
                self.llm.last_error = f"网络请求失败：{e}"
                return None

            calls = msg.get("tool_calls")
            if not calls:
                return msg.get("content")

            messages.append(msg)

            # 准备待执行的工具任务
            tasks = []
            for tc in calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                tasks.append((tc.get("id", ""), name, args))

            # 死循环熔断防护（Loop Trap Guard）：检查是否连续在跑同一批无变化的空转调用
            current_signature = [(name, json.dumps(args, sort_keys=True)) for _, name, args in tasks]
            if call_history_signatures.count(current_signature) >= 2:
                # 连续两次相同调用，熔断并注入提示促使 LLM 总结现有信息
                messages.append({
                    "role": "system",
                    "content": "【系统提示】检测到重复检索且无新信息，请根据当前已有信息直接综合回答，不要重复调用相同参数的工具。",
                })
                continue
            call_history_signatures.append(current_signature)

            # 多工具并发执行（优化多工具调用延迟）
            def _invoke_single_tool(item):
                tc_id, name, args = item
                res = self._executor(name, args)
                return tc_id, name, args, res

            if len(tasks) > 1:
                with ThreadPoolExecutor(max_workers=min(len(tasks), 4)) as executor:
                    results = list(executor.map(_invoke_single_tool, tasks))
            else:
                results = [_invoke_single_tool(tasks[0])]

            for tc_id, name, args, res in results:
                tool_calls.append({"name": name, "args": args, "result": res[:120]})
                messages.append({"role": "tool", "tool_call_id": tc_id, "content": res})

        return None

    def _rule_reply(self, message: str) -> str:
        """无 GLM 时的规则降级：识别常见意图，给出确定性回答。"""
        if "搜索" in message or "查找" in message or "检索" in message:
            return "（规则模式）我没有启用模型，无法智能检索。请到「设置」启用辅助轨道（免费 GLM-4-Flash），或在知识库/全局搜索里手动查找。"
        if "画像" in message or "弱点" in message or "bias" in message.lower():
            a = profile_core.analyze_profile(self._get_store().list_projects())
            return (
                f"（规则模式·画像分析）{a['summary']}\n"
                + "\n".join(f"⚠️ {w}" for w in a["weaknesses"])
                + "\n"
                + "\n".join(f"🧭 {b}" for b in a["bias_warnings"])
            )
        if "项目" in message and ("哪些" in message or "列表" in message or "概览" in message):
            return self._exec_list_projects({})
        if "收藏" in message:
            return self._exec_list_favorites({})
        return (
            "（规则模式）当前未启用辅助轨道模型。启用后我可以：检索知识库与政策讲话、全局搜索、分析用户画像、整理收藏与资料、导出文章等。"
            "请到「设置 → 辅助轨道」填写免费 GLM-4-Flash 的 API Key。"
        )


def get_tools_info() -> list:
    """返回工具清单（供前端展示助手能力）。"""
    return [{"name": t["function"]["name"], "description": t["function"]["description"]} for t in TOOLS]
