"""用户专属数据库 —— 画像分析 / 参考文本智能解读 / 智能总结。

规则版先落地（离线可用、无 key 也能跑）；LLM 版后续增强。
"""
import re
from collections import Counter

from ..domain.schemas import Brief

# 弱点映射：高频审查错误 → 弱点描述
WEAKNESS_MAP = {
    "empty_platitudes": "习惯使用空泛套话，缺少真实细节",
    "absolute_claims": "倾向绝对化表述，论证不够严谨",
    "ai_flavor": "带有AI套话痕迹，表达不够自然",
    "date_with_zero": "公文格式规范不熟（如日期编虚位）",
    "evaluative_language": "行政文书中误用评价性词汇",
    "literary_metaphor": "公文中使用文学化修辞",
    "passive_narrative": "叙事偏被动，主体性不足",
    "subject_ratio_low": "镜头常对准对方而非'我们'，主体性偏弱",
    "title_3elements_missing": "公文标题三要素不完整",
    "closing_missing": "公文结尾用语不规范",
    "official_ai_mix": "新媒体文案中混入官腔套话",
    "subjective_judgment": "客观报告中夹带主观评价",
    "inverted_pyramid_break": "消息导语未能突出核心事实",
}


def analyze_reference(text: str, title: str = "") -> str:
    """智能解读参考文本：提取高频词汇、引语句、句式与表达特点。"""
    if not text:
        return "（无内容可解读）"
    parts = []
    # 引语句
    quotes = re.findall(r'["“]([^"”]{8,60})["”]', text)
    if quotes:
        parts.append("【值得借鉴的句子】")
        for q in quotes[:3]:
            parts.append(f"- “{q}”")
    # 高频 2-4 字词（候选词汇）
    words = re.findall(r"[\u4e00-\u9fff]{2,4}", text)
    freq = [w for w, _ in Counter(words).most_common(12) if len(set(w)) > 1][:8]
    if freq:
        parts.append("\n【高频词汇】" + "、".join(freq))
    # 句式特征
    sents = [s for s in re.split(r"[。！？!?]", text) if s.strip()]
    if sents:
        avg_len = sum(len(s) for s in sents) / len(sents)
        if avg_len < 20:
            parts.append("句长：短句为主，节奏明快，适合新媒体")
        elif avg_len > 45:
            parts.append("句长：长句为主，信息密度大，偏正式")
        else:
            parts.append("句长：长短句结合，张弛有度")
        dash = text.count("——")
        colon = text.count("：")
        if dash >= 3:
            parts.append("善用破折号制造停顿与强调")
        if colon >= 3:
            parts.append("常用冒号引出说明或引语")
    # 表达方式
    if any(k in text for k in ("他说", "她表示", "同学说", "老师")):
        parts.append("表达方式：重视直接引语与人物声音")
    if any(k in text for k in ("数据显示", "同比", "统计")):
        parts.append("表达方式：数据支撑，注重事实")
    return "\n".join(parts)


def summarize_questionnaire(brief: Brief) -> str:
    """生成问卷要点总结（供项目页展示）。"""
    if not brief or not brief.purpose:
        return "（尚未完成问卷）"
    lines = [f"目的：{brief.purpose[:60]}"]
    if brief.primary_audience:
        lines.append(f"读者：{brief.primary_audience[:40]}")
    if brief.deep_meaning:
        lines.append(f"深意：{brief.deep_meaning[:60]}")
    if brief.key_materials:
        lines.append(f"素材：{brief.key_materials[:60]}")
    if brief.strategic_anchor:
        lines.append(f"关联：{brief.strategic_anchor[:60]}")
    if brief.differentiator:
        lines.append(f"差异点：{brief.differentiator[:60]}")
    return "\n".join(lines)


def analyze_profile(projects: list) -> dict:
    """基于项目与审查历史分析弱点与 bias，返回 {"weaknesses", "bias_warnings", "summary"}。"""
    error_keys = Counter()
    modes = Counter()
    for p in projects:
        modes[p.brief.writing_mode if p.brief else "?"] += 1
        for r in p.review_results:
            for f in r.findings:
                if f.error_key:
                    error_keys[f.error_key] += 1
    weaknesses = []
    for key, count in error_keys.most_common(3):
        if count >= 1 and key in WEAKNESS_MAP:
            weaknesses.append(WEAKNESS_MAP[key])
    if not weaknesses and error_keys:
        weaknesses = ["存在少量格式/表达问题，建议结合审查反馈针对性改进"]
    # bias：模式单一化预警
    bias_warnings = []
    if len(modes) >= 2 and max(modes.values()) / max(1, sum(modes.values())) >= 0.7:
        top = modes.most_common(1)[0][0]
        bias_warnings.append(f"写作类型较集中于「{top}」，可尝试其他文风拓宽表达")
    if len(modes) == 1 and sum(modes.values()) >= 2:
        top = modes.most_common(1)[0][0]
        bias_warnings.append(f"目前只写过「{top}」类型，建议尝试更多场景")
    if not bias_warnings:
        bias_warnings.append("暂无明显写作 bias，类型覆盖良好")
    summary = f"累计完成 {len(projects)} 个项目，类型覆盖 {'、'.join(modes.keys()) if modes else '无'}；常见弱点 {len(weaknesses)} 项。"
    return {"weaknesses": weaknesses, "bias_warnings": bias_warnings, "summary": summary}
