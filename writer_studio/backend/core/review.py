"""审查流水线 —— 单一评分公式 + 真实规则诊断。

全系统唯一评分公式：
    score = clamp(100 − Σ severity_weight, 0, 100)
    critical=25, major=15, minor=5, suggestion=2
    passed = (无 critical) 且 (score ≥ 70)

规则诊断用真实正则引擎（re.search），修复原版"子串匹配导致正则永不命中"的问题。
"""
import re

from ..domain.registry import Registry
from ..domain.schemas import ReviewFinding, ReviewResult, ReviewSeverity

SEVERITY_WEIGHT = {
    "critical": 25,
    "major": 15,
    "minor": 5,
    "suggestion": 2,
}

PASS_THRESHOLD = 70.0

# 行政公文结尾用语（缺失即报错）
ADMIN_CLOSINGS = ("妥否", "请批示", "请批复", "特此通知", "此复", "特此报告", "特此函告")
# 行政公文标题三要素中的文种词
ADMIN_TITLE_TYPES = ("通知", "请示", "批复", "函", "纪要", "报告", "决定", "意见", "通报", "公告", "议案")


def score(findings) -> float:
    """统一评分公式。"""
    total = sum(SEVERITY_WEIGHT.get(f.severity.value, 0) for f in findings)
    return max(0.0, min(100.0, 100.0 - total))


def is_passed(results) -> bool:
    """全部轮次：无 critical 且分数 ≥ 阈值。"""
    return all(
        (not any(f.severity == ReviewSeverity.CRITICAL for f in r.findings))
        and r.score >= PASS_THRESHOLD
        for r in results
    )


def diagnose(text: str, mode: str) -> list:
    """规则诊断：真实正则命中错误模式，返回 ReviewFinding 列表。"""
    findings = []
    if not text:
        return findings
    for eid, err in Registry.load("errors").items():
        if err["mode"] != "all" and err["mode"] != mode:
            continue
        if re.search(err["pattern"], text):
            findings.append(ReviewFinding(
                round_name="规则诊断",
                severity=ReviewSeverity(err["severity"]),
                issue=err["name"],
                suggestion=err["prescription"],
                error_key=eid,
                source="rule",
                dimension=err.get("dimension", ""),
            ))
    return findings


def compute_dimension_scores(findings: list) -> list:
    """按维度聚合扣分：每维度基础 100，该维度发现按严重度扣分。"""
    dims = {}
    for f in findings:
        d = f.dimension or "其他"
        dims[d] = dims.get(d, 0) + SEVERITY_WEIGHT.get(f.severity.value, 0)
    if not dims:
        return [{"name": "整体", "score": 100.0, "deducted": 0}]
    return [
        {"name": name, "score": round(max(0.0, 100.0 - deducted), 1), "deducted": deducted}
        for name, deducted in sorted(dims.items(), key=lambda x: -x[1])
    ]


def check_subject_ratio(text: str) -> list:
    """主语比例检查（战略叙事）：'我们'主体性词频 vs '对方'词频。"""
    we_words = ("我们", "同学们", "师生", "团队", "学院", "我方", "学校")
    they_words = ("对方", "他们", "教授", "专家", "据称", "据了解")
    we = sum(text.count(w) for w in we_words)
    they = sum(text.count(w) for w in they_words)
    if (we + they) == 0:
        return []
    ratio = we / (we + they)
    if ratio < 0.6:
        return [ReviewFinding(
            round_name="规则诊断",
            severity=ReviewSeverity.MAJOR,
            issue="主体性不足",
            suggestion=f"镜头应始终对准'我们'（当前主体词频占比 {ratio:.0%}，偏低），减少对'对方'的着墨",
            error_key="subject_ratio_low",
            source="rule",
        )]
    return []


def check_admin_format(text: str) -> list:
    """行政公文格式检查：标题三要素 + 结尾用语。"""
    findings = []
    if not text:
        return findings
    first_line = next((ln.strip() for ln in text.splitlines() if ln.strip()), "")
    # 标题须同时含"关于"（事由标志）与文种词；正文过渡句（"现将…通知如下"）不算标题
    has_title = first_line and ("关于" in first_line) and any(dt in first_line for dt in ADMIN_TITLE_TYPES)
    if not has_title:
        findings.append(ReviewFinding(
            round_name="规则诊断",
            severity=ReviewSeverity.CRITICAL,
            issue="标题三要素缺失",
            suggestion="标题应为：发文机关+事由+文种（如'XX学院关于XX的通知'）",
            error_key="title_3elements_missing",
            source="rule",
        ))
    if not any(c in text for c in ADMIN_CLOSINGS):
        findings.append(ReviewFinding(
            round_name="规则诊断",
            severity=ReviewSeverity.MAJOR,
            issue="结尾用语缺失",
            suggestion="应使用规范公文结尾用语（如'特此通知''妥否，请批示''此复'）",
            error_key="closing_missing",
            source="rule",
        ))
    return findings


def review(text: str, mode: str, round_name: str = "审查") -> ReviewResult:
    """规则版审查：模式错误诊断 + 模式专属检查，产出单一 ReviewResult（含逐维度得分）。"""
    findings = diagnose(text, mode)
    if mode == "strategic_narrative":
        findings.extend(check_subject_ratio(text))
    elif mode == "administrative":
        findings.extend(check_admin_format(text))
    return ReviewResult(
        round_name=round_name,
        findings=findings,
        score=score(findings),
        dimension_scores=compute_dimension_scores(findings),
        passed=score(findings) >= PASS_THRESHOLD
        and not any(f.severity == ReviewSeverity.CRITICAL for f in findings),
    )
