"""多角色协作 —— 真实 LLM 协商/辩论/决策 + 诚实降级。

有 LLM（client.available）时角色真实调用 LLM 输出结构化 JSON；
无 LLM 时走 rule_backend，基于真实上下文（brief/plan/匹配度）计算，
绝不 `if "风格" in topic` 式写死文案。返回的 AgentResponse.mode 标注 llm/rule。
"""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

from ..domain.schemas import AgentResponse


@dataclass
class Role:
    id: str
    name: str
    system: str


ROLES: dict = {
    "writer": Role(
        "writer",
        "主笔",
        "你是公文与宣传主笔，负责起草与修订。牢记马克思主义新闻观与机关严谨公文规范，坚持实事求是、言之有物，用鲜活事实和精准数据说话，杜绝假大空套话。",
    ),
    "reviewer": Role(
        "reviewer",
        "审稿人",
        "你是高级审稿人，执行公文审核与三审质控。严格把关政治方向、政策口径、事实准确性、时度效与文风规范，发现问题明确指出具体位置与修改方向。",
    ),
    "style": Role(
        "style",
        "风格专家",
        "你是文风与宣传叙事专家。精通党媒党刊（人民日报、新华社、求是、中青报）与机关法定公文调性，确保镜头主体性，力戒官腔与AI套话。",
    ),
    "doctype": Role(
        "doctype",
        "文种专家",
        "你是公文体例与法定文种专家。严格遵循《党政机关公文处理工作条例》与 GB/T 9704-2012 标准，严格执行'一文一事'、'法定文种唯一'、'标题三要素合规'等行文铁律。",
    ),
    "knowledge": Role(
        "knowledge",
        "知识库",
        "你是知识检索与政策专家。负责准确召回党中央最新政策提法（如二十届三中全会《决定》）、权威术语与标杆范文骨架，确保引经据典准确无误。",
    ),
    "profile": Role(
        "profile",
        "画像教练",
        "你是公文私教与画像教练。立足宣传'四力'（脚力、眼力、脑力、笔力）提升，关注作者习惯偏好与常见弱点，帮助作者规避典型错情、提升写作思维。",
    ),
}

_JSON_INSTRUCTION = (
    '\n\n请用JSON格式输出你的意见，只输出JSON：{"concerns": ["关注点1", ...], "suggestions": ["建议1", ...]}'
)


def select_roles_for_mode(mode: str, doc_type: str = "", has_memory: bool = False) -> list[str]:
    """动态专家路由（Dynamic MoA）：按模式与文种特征精选 3–4 个专业角色，避免全量并发 6 个角色造成频控与算力浪费。"""
    roles = ["writer", "reviewer"]
    # 媒体与年轻态模式重点关注风格与知识库标杆
    if mode in ("strategic_narrative", "informational", "youth_engagement"):
        roles.append("style")
        roles.append("knowledge")
    # 行政与客观报告模式重点把关法定公文格式与文种规则
    elif mode in ("administrative", "objective_report"):
        roles.append("doctype")
        if mode == "objective_report":
            roles.append("knowledge")
    # 有画像记忆时，激活画像专家
    if has_memory and "profile" not in roles:
        roles.append("profile")
    # 兜底：若角色过少，补充文种专家
    if len(roles) < 3:
        roles.append("doctype")
    # 去重并保持顺序
    seen = set()
    return [r for r in roles if not (r in seen or seen.add(r))]


def build_role_context(role_id: str, context: dict) -> dict:
    """角色上下文特化注水：为不同专家注入与其职责紧密相关的专属知识片段，告别'千人一面'。"""
    brief = context.get("brief") or {}
    plan = context.get("plan") or {}
    base = {
        "purpose": brief.get("purpose", ""),
        "doc_type": plan.get("doc_type", ""),
        "doc_type_name": plan.get("doc_type_name", ""),
        "writing_mode": plan.get("writing_mode", "") or brief.get("writing_mode", ""),
    }

    if role_id == "writer":
        base.update({
            "key_materials": brief.get("key_materials", ""),
            "deep_meaning": brief.get("deep_meaning", ""),
            "differentiator": brief.get("differentiator", ""),
            "structure_outline": plan.get("structure_outline", ""),
            "scratchpad": context.get("scratchpad", []),
            "dynamic_few_shots": context.get("dynamic_few_shots", []),
            "custom_knowledge_items": context.get("custom_knowledge_items", []),
        })
    elif role_id == "reviewer":
        base.update({
            "primary_audience": brief.get("primary_audience", ""),
            "estimated_length": plan.get("estimated_length", ""),
            "review_dimensions": context.get("review_dimensions", []),
            "forbidden_patterns": context.get("forbidden_patterns", []),
        })
    elif role_id == "style":
        base.update({
            "style_name": plan.get("style_name", ""),
            "style_match": context.get("style_match", True),
            "emotional_tone": context.get("emotional_tone", ""),
            "vocabulary_sample": context.get("vocabulary_sample", {}),
            "forbidden_patterns": context.get("forbidden_patterns", []),
        })
    elif role_id == "doctype":
        base.update({
            "structure_detail": context.get("structure_detail", ""),
            "primary_audience": brief.get("primary_audience", ""),
            "typical_length_range": context.get("typical_length_range", ""),
            "gbt9704_standard": "A4版心/上37下35左28右26mm/小标宋标题/三号仿宋正文/固定28磅行距/首行缩进2字符/六角括号年份〔〕/法定文种唯一",
        })
    elif role_id == "knowledge":
        base.update({
            "retrieved_policies": context.get("retrieved_policies", []),
            "retrieved_terms": context.get("retrieved_terms", []),
            "retrieved_exemplars": context.get("retrieved_exemplars", []),
            "custom_knowledge_items": context.get("custom_knowledge_items", []),
        })
    elif role_id == "profile":
        base.update({
            "user_preferences": context.get("user_preferences", []),
            "user_weaknesses": context.get("user_weaknesses", []),
            "bias_warnings": context.get("bias_warnings", []),
            "user_memory": context.get("user_memory", ""),
        })

    return base


def rule_response(role_id: str, context: dict) -> AgentResponse:
    """规则降级：基于角色特化上下文真实计算，非写死文案。"""
    brief = context.get("brief") or {}
    plan = context.get("plan") or {}
    concerns, suggestions = [], []
    purpose = context.get("purpose") or brief.get("purpose", "")
    materials = context.get("key_materials") or brief.get("key_materials", "")
    doc_name = context.get("doc_type_name") or plan.get("doc_type_name", "当前文种")
    writing_mode = context.get("writing_mode") or plan.get("writing_mode", "") or brief.get("writing_mode", "")
    style_match = context.get("style_match") if "style_match" in context else True

    if role_id == "writer":
        if not purpose:
            concerns.append("核心目的缺失，写作方向不明确")
        if not materials:
            concerns.append("核心素材缺失，可能写成空泛套话")
            suggestions.append("建议补充真实感言或具体数据")
        suggestions.append(f"按 {doc_name} 的结构模板组织正文")
    elif role_id == "reviewer":
        if not writing_mode:
            concerns.append("写作模式未确定，无法选择审查维度")
        suggestions.append("生成后将按模式维度逐轮审查并自动修复")
    elif role_id == "style":
        if style_match is False:
            concerns.append("风格与文种 domain 不匹配（如行政文种配了媒体风格）")
            suggestions.append("建议改配与文种同 domain 的风格")
        suggestions.append(f"风格「{context.get('style_name', '选定风格')}」：按需缩放词汇池使用频率")
    elif role_id == "doctype":
        suggestions.append(f"严格遵守 {doc_name} 的行文规范与格式结构")
    elif role_id == "knowledge":
        pols = context.get("retrieved_policies", [])
        if pols:
            suggestions.append(f"已检索到 {len(pols)} 条相关政策/表述，建议自然融入")
        else:
            suggestions.append("生成时可检索标杆范文学习结构，术语需结合场景使用")
    elif role_id == "profile":
        weaknesses = context.get("user_weaknesses", [])
        prefs = context.get("user_preferences", [])
        if weaknesses:
            concerns.append(f"历史易发问题预警：{weaknesses[0]}")
        if prefs:
            suggestions.append(f"结合个人偏好：{prefs[0]}")
        elif not weaknesses and not context.get("user_memory"):
            suggestions.append("将结合通用公文规范与上下文针对性起草")
        else:
            suggestions.append("将结合用户历史偏好与常见弱点针对性写作")

    return AgentResponse(role=role_id, concerns=concerns, suggestions=suggestions, mode="rule")


def consult(llm, topic: str, context: dict, role_ids=None) -> dict:
    """决策前协商：按需并行调用特化角色（注入定制上下文），返回 {role_id: AgentResponse}。"""
    mode = context.get("plan", {}).get("writing_mode", "") or context.get("brief", {}).get("writing_mode", "")
    doc_type = context.get("plan", {}).get("doc_type", "")
    has_mem = bool(context.get("user_memory") or context.get("user_preferences"))
    ids = role_ids or select_roles_for_mode(mode, doc_type, has_mem)
    results = {}

    def query(role_id):
        role = ROLES[role_id]
        role_ctx = build_role_context(role_id, context)
        if llm and llm.available:
            data = llm.chat_json(
                role.system + _JSON_INSTRUCTION,
                f"协商议题：{topic}\n\n专属特化上下文：{role_ctx}",
                temperature=0.3,
            )
            if data:
                return AgentResponse(
                    role=role_id,
                    concerns=list(data.get("concerns", [])),
                    suggestions=list(data.get("suggestions", [])),
                    mode="llm",
                )
        return rule_response(role_id, role_ctx)

    with ThreadPoolExecutor(max_workers=min(len(ids), 4)) as ex:
        for role_id, resp in zip(ids, ex.map(query, ids), strict=False):
            results[role_id] = resp
    return results


ROLE_EMOJIS = {
    "writer": ("✍️", "主笔"),
    "reviewer": ("🧐", "审稿人"),
    "style": ("🎨", "风格专家"),
    "doctype": ("🏛️", "文种专家"),
    "knowledge": ("📚", "知识库"),
    "profile": ("👤", "画像教练"),
}


def build_thought_bubbles(responses: dict) -> list[dict]:
    """生成结构化专家思维气泡（Thought Bubbles），用于前端直观展示各角色内心交锋。"""
    bubbles = []
    for rid, resp in responses.items():
        emoji, name = ROLE_EMOJIS.get(rid, ("💡", rid))
        thought = ""
        if resp.concerns:
            thought = f"指出隐患：{'；'.join(resp.concerns)}"
        elif resp.suggestions:
            thought = f"指导建议：{'；'.join(resp.suggestions[:2])}"
        else:
            thought = "方案符合规范，准予推进"

        bubbles.append(
            {
                "role": rid,
                "role_name": name,
                "emoji": emoji,
                "thought": thought,
                "mode": resp.mode,
            }
        )
    return bubbles


def decide(llm, topic: str, responses: dict, mode: str = "administrative", custom_weights: dict = None) -> dict:
    """集中决策：引入领域权威权重矩阵与一票否决权（Veto Power），支持用户自定义权重调节。"""
    authority_weights = {
        "doctype": 2.0 if mode == "administrative" else 1.0,
        "style": 2.0 if mode in ("strategic_narrative", "youth_engagement") else 0.8,
        "reviewer": 1.5,
        "profile": 1.2,
        "writer": 1.0,
        "knowledge": 1.0,
    }
    if custom_weights:
        authority_weights.update(custom_weights)

    # 检查文种与合规一票否决项（Veto check）
    veto_notes = []
    doctype_resp = responses.get("doctype")
    if doctype_resp and mode == "administrative" and doctype_resp.concerns:
        for c in doctype_resp.concerns:
            veto_notes.append(f"【文种一票否决/强制约束】{c}")

    style_resp = responses.get("style")
    if style_resp and mode in ("strategic_narrative", "youth_engagement"):
        for c in style_resp.concerns:
            if "不匹配" in c:
                veto_notes.append(f"【风格一票否决/强制约束】{c}")

    opinions = []
    for rid, r in responses.items():
        weight = authority_weights.get(rid, 1.0)
        weight_tag = f"（权威权重：{weight:.1f}）" if weight != 1.0 else ""
        concerns_text = "；".join(r.concerns) or "无"
        sugg_text = "；".join(r.suggestions) or "无"
        opinions.append(f"- {ROLES[rid].name}{weight_tag}：关注 {concerns_text}；建议 {sugg_text}")

    opinions_str = "\n".join(opinions)
    if veto_notes:
        opinions_str += "\n\n⚠️ 触发强制约束指令：\n" + "\n".join(veto_notes)

    if llm and llm.available:
        data = llm.chat_json(
            "你是总指挥，拥有最终决策权。基于各方意见与权威权重做出具体可执行的决策。特别注意：若有【强制约束/一票否决】，必须严格作为第一执行原则，不可和稀泥。"
            + _JSON_INSTRUCTION.replace("concerns", "decision").replace("suggestions", "rationale"),
            f"议题：{topic}\n\n各方意见与权威权重：\n{opinions_str}",
            temperature=0.2,
        )
        if data:
            return {
                "decision": data.get("decision", ""),
                "rationale": data.get("rationale", ""),
                "veto_triggered": bool(veto_notes),
                "mode": "llm",
            }

    # 规则降级：按权重排序并优先落实否决项
    all_suggestions = []
    if veto_notes:
        all_suggestions.extend(veto_notes)
    for rid in sorted(responses.keys(), key=lambda k: -authority_weights.get(k, 1.0)):
        all_suggestions.extend(responses[rid].suggestions)

    return {
        "decision": "采纳核心决策方案：\n" + "\n".join(f"- {s}" for s in all_suggestions[:5]),
        "rationale": f"基于 {len(responses)} 方意见及权威权重仲裁（规则模式）",
        "veto_triggered": bool(veto_notes),
        "mode": "rule",
    }


def debate(llm, topic: str, writer_position: str, reviewer_position: str, rounds: int = 1) -> dict:
    """辩论共识：LLM 对抗辩论达成平衡共识。返回 {consensus, mode}。"""
    if llm and llm.available:
        data = llm.chat_json(
            "你需要在撰写方和审查方之间找到平衡，给出具体处理方案，不是和稀泥。"
            + '\n\n请用JSON输出：{"consensus": "共识方案"}',
            f"议题：{topic}\n撰写方立场：{writer_position}\n审查方立场：{reviewer_position}",
            temperature=0.2,
        )
        if data and data.get("consensus"):
            return {"consensus": data["consensus"], "mode": "llm"}
    return {
        "consensus": f"兼顾创作灵活性与质量把控：{reviewer_position[:80]}",
        "mode": "rule",
    }


def red_team_evaluate(draft: str, mode: str, doc_type: str, llm=None) -> dict:
    """模拟分管领导审签与舆情红蓝军压力测试（Red-Team Adversarial Stress Test）。"""
    if llm and llm.available:
        sys_prompt = (
            "你是由【挑剔分管领导】与【资深舆情风险排查员】组成的红蓝军审签压力测试组。\n"
            "请以最严格的机关审签标准和舆情风险视角对文稿进行压力测试，指出致命漏洞：\n"
            "1. 政治方向与政策口径：有无表述不严谨、定性不当或与中央精神不符？\n"
            "2. 分管领导审签挑刺：主体责任是否清晰？措施是真招实招还是推诿空话？数据是否禁得起推敲？\n"
            "3. 公众舆情风险：涉民生/高校/经费等内容，是否存在被断章取义或引发次生舆情的风险点？\n\n"
            '请严格输出JSON：{"verdict": "通过|需关注|严厉整改", "superior_critique": "领导审签挑刺意见", "pr_risk_points": ["风险点1", ...], "actionable_fixes": ["修改建议1", ...], "overall_score": 85}'
        )
        data = llm.chat_json(sys_prompt, f"文种：{doc_type}（模式：{mode}）\n\n待审签草稿：\n{draft[:3500]}", temperature=0.1)
        if data:
            return {**data, "mode": "llm"}

    # 规则模式兜底
    risks = []
    critiques = []
    if "大家纷纷表示" in draft:
        critiques.append("套话堆砌，未见真抓实干的具体抓手")
    if "全国首个" in draft or "全球唯一" in draft:
        risks.append("绝对化表述缺乏权威第三方审计背书，易引发质疑")
    if not critiques:
        critiques.append("文稿整体脉络清晰，符合基本报送要求")

    return {
        "verdict": "需关注" if (risks or len(critiques) > 1) else "通过",
        "superior_critique": "；".join(critiques),
        "pr_risk_points": risks or ["暂未发现高危舆情断章取义风险点"],
        "actionable_fixes": ["强化责任单位落地时限与具体指标", "核实数据出处"],
        "overall_score": 88 if not risks else 76,
        "mode": "rule",
    }

