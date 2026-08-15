"""文种识别 —— 分轨道统型化打分。

同一天平（关键词/受众/篇幅/素材四维度），但权重矩阵按文种 domain 分轨道配置：
- media（媒体类）重"叙事/新闻价值"关键词；
- official（行政类）重"格式/行文方向"关键词。
"""
from ..domain.registry import Registry
from ..domain.schemas import Brief

WEIGHT_MATRIX = {
    "media": {"keyword": 0.40, "audience": 0.25, "length": 0.25, "material": 0.10},
    "official": {"keyword": 0.45, "audience": 0.30, "length": 0.15, "material": 0.10},
}

# 受众维度：关键词组 → 各文种加分（按 domain 分轨道）
AUDIENCE_RULES = {
    "media": [
        (("领导", "上级", "汇报", "呈报"), {"bulletin": 0.12, "feature": 0.08}),
        (("媒体", "记者", "通稿", "发布"), {"news_brief": 0.12}),
        (("学生", "家长", "团队", "成员"), {"sidelight": 0.10}),
    ],
    "official": [
        (("上级", "领导", "党委", "机关", "政府"), {"request": 0.12, "report": 0.12}),
        (("不相隶属", "兄弟单位", "外单位", "对方单位"), {"letter": 0.15}),
        (("下级", "基层", "各单位", "部门"), {"notification": 0.12}),
        (("人大", "人大常委会", "代表"), {"motion": 0.15}),
    ],
}

# 素材维度：素材类型 → 文种加分
MATERIAL_RULES = {
    "media": [
        (("数据", "同比", "环比", "统计", "%"), {"research_report": 0.08, "news_brief": 0.06}),
        (("他说", "表示", "感言", "谈到"), {"feature": 0.08, "sidelight": 0.06}),
    ],
    "official": [
        (("文件", "附件", "台账", "清单"), {"notification": 0.08, "decision": 0.06}),
        (("数据", "同比", "统计", "%"), {"report": 0.08}),
    ],
}


def _keyword_score(keywords, text):
    """关键词维度：每条 [kw, weight]，命中即加分，封顶 1.0。"""
    if not text:
        return 0.0
    total = 0.0
    for kw, weight in keywords:
        if kw and kw in text:
            total += weight
    return min(1.0, total)


def _audience_score(doc_id, audience, domain):
    total = 0.0
    for kws, boosts in AUDIENCE_RULES.get(domain, []):
        if any(kw in (audience or "") for kw in kws):
            total += boosts.get(doc_id, 0.0)
    return min(1.0, total)


def _length_score(doc, length_hint):
    if not length_hint:
        return 0.0
    lo, hi = doc["typical_length_range"]
    center = (lo + hi) / 2
    half = (hi - lo) / 2
    return max(0.0, 1.0 - abs(length_hint - center) / half)


def _material_score(doc_id, materials, domain):
    if not materials:
        return 0.0
    total = 0.0
    for kws, boosts in MATERIAL_RULES.get(domain, []):
        if any(kw in materials for kw in kws):
            total += boosts.get(doc_id, 0.0)
    return min(1.0, total)


def identify_doc_type(brief: Brief):
    """返回 (doc_type_id, score) 全量排序列表（只含目标 domain 文种）。"""
    target_domain = "official" if brief.writing_mode == "administrative" else "media"
    w = WEIGHT_MATRIX[target_domain]
    doctypes = Registry.filter("doctypes", domain=target_domain)
    scores = []
    for dt in doctypes:
        did = dt["id"]
        s = 0.0
        s += w["keyword"] * _keyword_score(dt.get("keywords", []), brief.purpose)
        s += w["audience"] * _audience_score(did, brief.primary_audience, target_domain)
        s += w["length"] * _length_score(dt, brief.length_hint)
        s += w["material"] * _material_score(did, brief.key_materials, target_domain)
        scores.append((did, round(min(1.0, max(0.0, s)), 4)))
    scores.sort(key=lambda x: -x[1])
    if not scores or scores[0][1] <= 0:
        fallback = "notification" if target_domain == "official" else "feature"
        scores = [(fallback, 0.5)] + [x for x in scores if x[0] != fallback]
    return scores
