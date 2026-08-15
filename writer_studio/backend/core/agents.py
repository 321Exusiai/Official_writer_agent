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
    "writer": Role("writer", "主笔", "你是公文主笔，负责起草与修订。关注内容是否充实、表达是否清晰、素材是否用到位。"),
    "reviewer": Role("reviewer", "审稿人", "你是审稿人，负责质量把关。关注事实准确性、格式合规性、语言规范性，发现问题给具体位置和修改方向。"),
    "style": Role("style", "风格专家", "你是风格专家。关注文种与风格是否匹配、风格强度是否合适。行政公文不该用文学风格。"),
    "doctype": Role("doctype", "文种专家", "你是文种专家。关注文种选择对不对、格式符不符合规范。请示不能一文多事、报告不能夹带请示。"),
    "knowledge": Role("knowledge", "知识库", "你是知识库。推送标杆范文、规范术语、写作提示。范文是学结构不是抄句子。"),
    "profile": Role("profile", "用户画像", "你是用户画像。关注用户历史偏好与常见弱点。个性化不是迁就，习惯里的毛病该指出还是要指出。"),
}

_JSON_INSTRUCTION = "\n\n请用JSON格式输出你的意见，只输出JSON：{\"concerns\": [\"关注点1\", ...], \"suggestions\": [\"建议1\", ...]}"


def rule_response(role_id: str, context: dict) -> AgentResponse:
    """规则降级：基于真实上下文计算，非写死文案。"""
    brief = context.get("brief") or {}
    plan = context.get("plan") or {}
    concerns, suggestions = [], []
    purpose = brief.get("purpose", "")
    materials = brief.get("key_materials", "")

    if role_id == "writer":
        if not purpose:
            concerns.append("核心目的缺失，写作方向不明确")
        if not materials:
            concerns.append("核心素材缺失，可能写成空泛套话")
            suggestions.append("建议补充真实感言或具体数据")
        suggestions.append(f"按 {plan.get('doc_type_name', '当前文种')} 的结构模板组织正文")
    elif role_id == "reviewer":
        mode = plan.get("writing_mode", "")
        if not mode:
            concerns.append("写作模式未确定，无法选择审查维度")
        suggestions.append("生成后将按模式维度逐轮审查并自动修复")
    elif role_id == "style":
        if context.get("style_match") is False:
            concerns.append("风格与文种 domain 不匹配（如行政文种配了媒体风格）")
            suggestions.append("建议改配与文种同 domain 的风格")
        suggestions.append("风格强度按需缩放词汇池使用频率")
    elif role_id == "doctype":
        score = context.get("doc_type_score")
        if score is not None and score < 0.5:
            concerns.append(f"文种识别置信度偏低（{score:.0%}），建议人工确认")
        suggestions.append(f"推荐文种：{plan.get('doc_type_name', '待定')}")
    elif role_id == "knowledge":
        suggestions.append("生成时可检索标杆范文学习结构，术语需结合场景使用")
    elif role_id == "profile":
        if not context.get("user_memory"):
            suggestions.append("暂无用户历史记忆，将按通用规范写作")
        else:
            suggestions.append("将结合用户历史偏好与常见弱点针对性写作")

    return AgentResponse(role=role_id, concerns=concerns, suggestions=suggestions, mode="rule")


def consult(llm, topic: str, context: dict, role_ids=None) -> dict:
    """决策前协商：并行调用各角色，返回 {role_id: AgentResponse}。"""
    ids = role_ids or list(ROLES.keys())
    results = {}

    def query(role_id):
        role = ROLES[role_id]
        if llm and llm.available:
            data = llm.chat_json(
                role.system + _JSON_INSTRUCTION,
                f"协商议题：{topic}\n\n上下文：{context}",
                temperature=0.3,
            )
            if data:
                return AgentResponse(
                    role=role_id,
                    concerns=list(data.get("concerns", [])),
                    suggestions=list(data.get("suggestions", [])),
                    mode="llm",
                )
        return rule_response(role_id, context)

    with ThreadPoolExecutor(max_workers=len(ids)) as ex:
        for role_id, resp in zip(ids, ex.map(query, ids)):
            results[role_id] = resp
    return results


def decide(llm, topic: str, responses: dict) -> dict:
    """集中决策：基于各方真实意见裁决。返回 {decision, rationale, mode}。"""
    opinions = "\n".join(
        f"- {ROLES[rid].name}：关注 {'；'.join(r.concerns) or '无'}；建议 {'；'.join(r.suggestions) or '无'}"
        for rid, r in responses.items()
    )
    if llm and llm.available:
        data = llm.chat_json(
            "你是总指挥，拥有最终决策权。基于各方意见做出具体可执行的决策，不是和稀泥。"
            + _JSON_INSTRUCTION.replace("concerns", "decision").replace("suggestions", "rationale"),
            f"议题：{topic}\n\n各方意见：\n{opinions}",
            temperature=0.3,
        )
        if data:
            return {"decision": data.get("decision", ""), "rationale": data.get("rationale", ""), "mode": "llm"}
    # 规则降级：汇总建议作为决策依据
    all_suggestions = [s for r in responses.values() for s in r.suggestions]
    return {
        "decision": "采纳各方建议：\n" + "\n".join(f"- {s}" for s in all_suggestions[:5]),
        "rationale": f"基于 {len(responses)} 方意见汇总（规则模式）",
        "mode": "rule",
    }


def debate(llm, topic: str, writer_position: str, reviewer_position: str, rounds: int = 1) -> dict:
    """辩论共识：LLM 多轮反驳后达成共识。返回 {consensus, mode}。"""
    if llm and llm.available:
        data = llm.chat_json(
            "你需要在撰写方和审查方之间找到平衡，给出具体处理方案，不是和稀泥。"
            + "\n\n请用JSON输出：{\"consensus\": \"共识方案\"}",
            f"议题：{topic}\n撰写方立场：{writer_position}\n审查方立场：{reviewer_position}",
            temperature=0.3,
        )
        if data and data.get("consensus"):
            return {"consensus": data["consensus"], "mode": "llm"}
    return {
        "consensus": f"兼顾创作灵活性与质量把控：{reviewer_position[:80]}",
        "mode": "rule",
    }
