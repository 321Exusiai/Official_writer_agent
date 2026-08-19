"""问卷与写作简报 —— 决策树路由 + 模式专属问卷。

决策树两级：root（4 选 1）→ 分支（叶子带 mode/subtype）。
问卷题目来自统一注册表 modes（含 why_ask/hint 教学说明）。
"""

from ..domain.registry import Registry

ROUTING_TREE = {
    "root": {
        "question": "这篇文章最核心的使命是什么？请根据受众和目标选择。",
        "options": [
            {"label": "对外传播", "description": "新闻通稿、深度报道、典型人物宣传", "next": "external_comm"},
            {"label": "内部行政", "description": "通知、请示、批复、函、纪要", "next": "internal_admin"},
            {"label": "活动记录", "description": "团日活动、音乐节、讲座、策划案、活动总结", "next": "activity_record"},
            {"label": "汇报总结", "description": "工作总结、调研报告、述职、事故通报", "next": "report_summary"},
        ],
    },
    "external_comm": {
        "question": "你希望文章的深度和篇幅是怎样的？",
        "options": [
            {"label": "新闻快讯（300-800字）", "mode": "informational", "subtype": "news_brief"},
            {"label": "深度通讯（1500-3000字）", "mode": "strategic_narrative", "subtype": "feature"},
            {"label": "特写侧记（800-1500字）", "mode": "strategic_narrative", "subtype": "sidelight"},
        ],
    },
    "internal_admin": {
        "question": "你要写的是哪种行文方向的公文？",
        "options": [
            {"label": "上行文（请示/报告）", "mode": "administrative", "subtype": "upward"},
            {"label": "下行文（通知/通报/批复/决定）", "mode": "administrative", "subtype": "downward"},
            {"label": "平行文（函/意见/议案）", "mode": "administrative", "subtype": "parallel"},
            {"label": "公布性公文（公告/通告）", "mode": "administrative", "subtype": "public"},
            {"label": "会议文书（纪要/决议）", "mode": "informational", "subtype": "minutes"},
        ],
    },
    "activity_record": {
        "question": "这次活动的性质和受众调性是怎样的？",
        "options": [
            {"label": "社团招新/文艺汇演推文", "mode": "youth_engagement", "subtype": "club_activity"},
            {"label": "班会/讲座/典礼报道", "mode": "informational", "subtype": "campus_activity"},
            {"label": "研学考察/社会实践报道", "mode": "strategic_narrative", "subtype": "study_tour"},
            {"label": "活动策划案", "mode": "informational", "subtype": "activity_proposal"},
            {"label": "活动总结", "mode": "strategic_narrative", "subtype": "activity_summary"},
        ],
    },
    "report_summary": {
        "question": "你汇报或调研的核心内容是什么？",
        "options": [
            {"label": "阶段性工作总结", "mode": "strategic_narrative", "subtype": "work_summary"},
            {"label": "深度调研报告", "mode": "objective_report", "subtype": "research_report"},
            {"label": "事故/问题通报", "mode": "objective_report", "subtype": "incident_report"},
            {"label": "个人或部门述职", "mode": "administrative", "subtype": "duty_report"},
            {"label": "社会实践报告", "mode": "objective_report", "subtype": "practice_report"},
        ],
    },
}

# 问题 id → Brief 字段映射（模式问卷答案写回简报）
FIELD_MAP = {
    "sn_vision": "strategic_anchor",
    "sn_logic": "deep_meaning",
    "sn_people": "key_materials",
    "sn_value": "differentiator",
    "sn_direction": "purpose",
    "or_problem": "purpose",
    "or_cause": "key_materials",
    "or_solution": "differentiator",
    "or_method": "deep_meaning",
    "ad_basis": "strategic_anchor",
    "ad_core": "purpose",
    "ad_route": "primary_audience",
    "ad_doc_type": "deep_meaning",
    "info_5w1h": "purpose",
    "info_lead": "deep_meaning",
    "info_quotes": "key_materials",
    "info_value": "differentiator",
    "info_plan": "strategic_anchor",
    "ye_vibe": "deep_meaning",
    "ye_identity": "differentiator",
    "ye_interaction": "key_materials",
    "ye_cta": "purpose",
    "ye_value": "strategic_anchor",
}


def routing_question(node: str = "root"):
    n = ROUTING_TREE[node]
    return {
        "node": node,
        "question": n["question"],
        "options": [
            {"index": i, "label": o["label"], "description": o.get("description", "")}
            for i, o in enumerate(n["options"])
        ],
    }


def submit_routing(node: str, choice_index: int):
    """提交路由选择，返回 (next_node, None) 或 (None, {"mode":..., "subtype":...})。"""
    n = ROUTING_TREE[node]
    if choice_index < 0 or choice_index >= len(n["options"]):
        raise ValueError("选择超出范围")
    opt = n["options"][choice_index]
    if "mode" in opt:
        return None, {"mode": opt["mode"], "subtype": opt["subtype"]}
    return opt["next"], None


def mode_questions(mode: str):
    """返回当前模式专属问卷题目列表（含 why_ask/hint）。"""
    profile = Registry.by_id("modes", mode)
    return profile["questions"] if profile else []


def apply_answer(brief, question_id: str, answer: str):
    """将问题答案写回 Brief 字段。"""
    field = FIELD_MAP.get(question_id)
    if field and hasattr(brief, field):
        setattr(brief, field, answer)
    brief.raw_answers[question_id] = answer
