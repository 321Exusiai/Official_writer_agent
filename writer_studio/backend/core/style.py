"""风格适配 —— 分轨道统型化 + 强度缩放 + 混合建议。

- 风格含 domain：media（人民日报/新华社/央视/光明）与 official（党政机关行文）；
- 风格-文种匹配约束：official 文种默认只配 official 风格，media 文种默认 media 风格；
- 词汇池统一五类键，强度缩放统一逐类截取。
"""

from ..domain.registry import Registry
from ..domain.schemas import Brief

# 风格选择提示：关键词 → 风格 id（仅用于 media 轨道内排序）
STYLE_HINTS = {
    "people_daily": (("领导", "上级", "汇报", "战略", "大局"), 0.6),
    "xinhua": (("媒体", "记者", "通稿", "发布", "数据"), 0.6),
    "cctv": (("学生", "现场", "场景", "故事", "温度"), 0.6),
    "guangming": (("理论", "思想", "调研", "学术", "文化"), 0.6),
}

INTENSITY_THRESHOLDS = (0.9, 0.7, 0.5, 0.3)  # 完整/标准/适度/轻度/极简


def _style_hint_score(style_id, text):
    entry = STYLE_HINTS.get(style_id)
    if not entry:
        return 0.0
    kws, weight = entry
    return weight if any(kw and kw in (text or "") for kw in kws) else 0.0


def auto_select_style(brief: Brief, doc_type_id: str) -> str:
    """按写作模式 + 文种 domain 选择风格。"""
    dt = Registry.by_id("doctypes", doc_type_id)
    domain = dt["domain"] if dt else "media"
    mode = getattr(brief, "writing_mode", "")
    candidates = [s for s in Registry.load("styles").values() if mode in s.get("modes", [])]
    if not candidates:
        candidates = Registry.filter("styles", domain=domain)
    if not candidates:
        return "government_admin" if domain == "official" else "people_daily"
    if all(s["domain"] == "official" for s in candidates):
        return candidates[0]["id"]  # 官方轨道
    text = f"{brief.primary_audience} {brief.purpose}"
    best = max(candidates, key=lambda s: _style_hint_score(s["id"], text))
    return best["id"]


def suggest_blend(primary_audience: str, purpose: str, secondary_audiences) -> dict:
    """混合风格建议：主风格打分 + 次要受众（非主风格 ×0.6 衰减）。"""
    media_styles = Registry.filter("styles", domain="media")
    text = f"{primary_audience} {purpose}"
    primary_id = max(media_styles, key=lambda s: _style_hint_score(s["id"], text))["id"]

    secondaries = secondary_audiences or []
    if not secondaries:
        return {
            "primary_style": primary_id,
            "primary_weight": 1.0,
            "secondary_style": "",
            "secondary_weight": 0.0,
            "apply_to": "",
            "reasoning": "单一受众，全篇使用主风格",
        }

    secondary_scores = {}
    for aud in secondaries:
        for s in media_styles:
            sid = s["id"]
            if sid == primary_id:
                continue  # 主风格不参与次要打分（修复原版死分支）
            secondary_scores[sid] = secondary_scores.get(sid, 0.0) + _style_hint_score(sid, aud) * 0.6

    best_secondary = max(secondary_scores, key=secondary_scores.get) if secondary_scores else ""
    s_score = secondary_scores.get(best_secondary, 0.0)
    p_score = _style_hint_score(primary_id, text) or 0.7
    if (p_score + s_score) <= 0:
        primary_weight, secondary_weight = 0.7, 0.3
    else:
        primary_weight = p_score / (p_score + s_score)
        secondary_weight = 1.0 - primary_weight

    return {
        "primary_style": primary_id,
        "primary_weight": round(primary_weight, 3),
        "secondary_style": best_secondary,
        "secondary_weight": round(secondary_weight, 3),
        "apply_to": "",
        "reasoning": f"主受众 {primary_audience} 与次要受众 {', '.join(secondaries)} 风格需求不同",
    }


def scale_vocabulary(style_id: str, intensity: float) -> dict:
    """按强度统一截取五类词汇（≥0.8 全量、≥0.5 取3、否则取1）。"""
    style = Registry.by_id("styles", style_id)
    if not style:
        return {}
    if intensity >= 0.8:
        n = 999
    elif intensity >= 0.5:
        n = 3
    else:
        n = 1
    return {k: v[:n] for k, v in style["vocabulary_pool"].items()}


def check_style_doc_match(style_id: str, doc_type_id: str) -> bool:
    """风格-文种 domain 匹配检查（不匹配时前端预警）。"""
    style = Registry.by_id("styles", style_id)
    doc = Registry.by_id("doctypes", doc_type_id)
    if not style or not doc:
        return True
    return style["domain"] == doc["domain"]
