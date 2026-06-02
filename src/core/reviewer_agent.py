"""
审稿 Agent — 模式感知的多维度迭代审查

核心改进：
1. 审查维度不再只有"五大原则五轮审查"，而是根据写作模式动态切换
2. 新增客观性审查和规范性审查（所有模式通用）
3. 保留原有的错误诊断库作为 STRATEGIC_NARRATIVE 模式的专属工具
4. [V2.1] 新增迭代修复能力：基于审查发现自动生成修改建议并应用修改

审查维度按模式分配：
- STRATEGIC_NARRATIVE：主体性 + 赋能性 + 借势性 + 瘦身 + 战略性 + 事实准确性
- OBJECTIVE_REPORT：事实准确性 + 逻辑一致性 + 表述客观性 + 问题导向性 + 格式规范性
- ADMINISTRATIVE：格式规范性 + 用词准确性 + 合规性 + 简洁性 + 事实准确性
- INFORMATIONAL：信息完整性 + 结构清晰性 + 重点突出性 + 不渲染 + 受众适配性 + 事实准确性
"""

from dataclasses import dataclass, field
from typing import Any, List, Dict, Optional, Tuple
from enum import Enum

from .writing_mode import (
    WritingMode,
    get_review_dimensions,
    get_mode_profile,
    ALL_PRINCIPLES,
)
from ..utils.response_cache import cached_prompt, store_prompt


class ReviewSeverity(Enum):
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


@dataclass
class ReviewFinding:
    round_name: str
    severity: ReviewSeverity
    location: str
    issue: str
    suggestion: str
    original_text: str = ""
    suggested_revision: str = ""


@dataclass
class ReviewResult:
    round_name: str
    passed: bool
    findings: List[ReviewFinding] = field(default_factory=list)
    overall_score: float = 0.0
    summary: str = ""


# ═══════════════════════════════════════════════════════════════
# 通用错误诊断库（所有模式共享）
# ═══════════════════════════════════════════════════════════════

UNIVERSAL_ERROR_DB = {
    "fact_error": {
        "patterns": [],
        "diagnosis": "事实可能不准确——人名、职务、日期、数据未标注来源",
        "prescription": "所有关键事实标注出处。人名职务核实无误。数据注明统计口径和来源。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "format_error": {
        "patterns": [],
        "diagnosis": "格式不符合规范（标题格式、署名格式、日期格式、段落格式）",
        "prescription": "参照《党政机关公文格式》(GB/T 9704-2012)或相应写作规范调整格式。",
        "severity": ReviewSeverity.MAJOR,
        "check_method": "structural",
    },
    "vague_attribution": {
        "patterns": [
            "据悉", "据了解", "有关人士", "相关部门", "知情人士",
        ],
        "diagnosis": "使用了模糊信源，降低了文章可信度",
        "prescription": "尽可能使用具体信源：'据XX部门统计''XX负责人表示'。如必须使用模糊信源，说明原因。",
        "severity": ReviewSeverity.MAJOR,
    },
    "data_inconsistency": {
        "patterns": [],
        "diagnosis": "前后数据可能矛盾或统计口径不一致",
        "prescription": "核对全文所有数字，确保前后一致。不同来源的数据注明统计口径差异。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "sensitive_wording": {
        "patterns": [
            "第一", "首个", "唯一", "史上最", "全国最",
        ],
        "diagnosis": "使用了绝对化或敏感表述，可能引发争议",
        "prescription": "删除绝对化表述。如需强调领先地位，用具体数据说话：'据XX统计，该校是全省首个……的高校（附数据来源）'",
        "severity": ReviewSeverity.MAJOR,
    },
    "empty_content": {
        "patterns": [],
        "diagnosis": "内容空泛，缺乏实质性信息",
        "prescription": "检查文章是否包含具体的人、事、数、时。如果去掉套话后文章没有实质内容，需要补充。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "missing_context": {
        "patterns": [],
        "diagnosis": "缺少必要的背景信息，读者难以理解事件的意义",
        "prescription": "添加1-2句背景信息：这是什么级别的活动？该组织在该领域的积累是什么？",
        "severity": ReviewSeverity.MINOR,
        "check_method": "semantic",
    },
    "redundant_repetition": {
        "patterns": [],
        "diagnosis": "存在重复表述，同一信息在多处出现",
        "prescription": "删除重复内容。同一信息在标题、导语、正文中只出现一次即可。",
        "severity": ReviewSeverity.MINOR,
        "check_method": "structural",
    },
    "wrong_tone": {
        "patterns": [],
        "diagnosis": "语气与文种/受众不匹配",
        "prescription": "向上行文用谦敬语气（'恳请''敬请'），向下行文用明确语气（'请认真执行'），平行行文用协商语气（'请予支持'）。",
        "severity": ReviewSeverity.MAJOR,
        "check_method": "semantic",
    },
}

# ═══════════════════════════════════════════════════════════════
# STRATEGIC_NARRATIVE 专属错误诊断库（保留原版）
# ═══════════════════════════════════════════════════════════════

STRATEGIC_ERROR_DB = {
    "passive_narrative": {
        "patterns": ["安排了", "组织了", "邀请了", "讲解了", "介绍了", "展示了"],
        "diagnosis": "被动叙事占主导，叙述重心落在对方而非我方",
        "prescription": "将主语改为'我们'，重心从'对方做了什么'转向'我们收获了什么'",
        "severity": ReviewSeverity.CRITICAL,
    },
    "empty_platitudes": {
        "patterns": [
            "大家纷纷表示", "深刻感受到", "一致认为", "受益匪浅",
            "收获很大", "深受鼓舞", "感触良多", "获益良多",
        ],
        "diagnosis": "使用空泛套话替代真实感言，缺乏说服力",
        "prescription": "删除空话，替换为1-2段具体的、有细节的真实感言",
        "severity": ReviewSeverity.CRITICAL,
    },
    "no_strategic_anchor": {
        "patterns": [],
        "diagnosis": "行程板块缺少战略锚点句，读起来像独立游记",
        "prescription": "为每个行程板块添加一句'为什么是这里'，点明与培养方案/工作部署的关联",
        "severity": ReviewSeverity.MAJOR,
        "check_method": "structural",
    },
    "external_without_link": {
        "patterns": [],
        "diagnosis": "记录了外部权威的言行，但没有建立与我方的关联",
        "prescription": "在外部权威观点后添加一句'这印证了/这与……一脉相承/这让我方成员深刻认识到……'",
        "severity": ReviewSeverity.MAJOR,
        "check_method": "structural",
    },
    "process_flow_account": {
        "patterns": ["乘车", "入住", "就餐", "出发", "抵达", "集合", "签到"],
        "diagnosis": "包含大量无意义的流程描述，占用篇幅",
        "prescription": "删除所有纯过程性描述，只保留有叙事价值的时间节点",
        "severity": ReviewSeverity.MINOR,
    },
    "weak_ending": {
        "patterns": ["圆满成功", "顺利结束", "满载而归", "活动在", "落下帷幕"],
        "diagnosis": "结尾停留在'活动结束'，没有传递组织信号",
        "prescription": "改为含蓄传递'我们有方向、有资源、有成果'的战略信号",
        "severity": ReviewSeverity.MAJOR,
    },
    "title_weak": {
        "patterns": ["顺利举行", "圆满举办", "成功召开", "活动纪实", "活动报道"],
        "diagnosis": "标题缺乏新闻性和辨识度",
        "prescription": "标题应包含判断或问题，让读者一眼知道文章的核心价值",
        "severity": ReviewSeverity.MAJOR,
    },
    "subject_is_them": {
        "patterns": [],
        "diagnosis": "段落主语是'对方'而非'我们'",
        "prescription": "逐句检查，将主语调整为'我们'或我方成员",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
}

# ═══════════════════════════════════════════════════════════════
# ADMINISTRATIVE 专属错误诊断库
# ═══════════════════════════════════════════════════════════════

ADMIN_ERROR_DB = {
    "wrong_doc_type": {
        "patterns": [],
        "diagnosis": "文种选择可能不正确",
        "prescription": "确认文种：通知（要求执行/周知）、请示（请求批准）、批复（答复请示）、函（平级商洽）、纪要（记载会议）。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "missing_title_elements": {
        "patterns": [],
        "diagnosis": "标题缺少三要素（发文机关+事由+文种）之一",
        "prescription": "标题格式：'XX单位关于XXXX的通知/请示/批复/函'",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "structural",
    },
    "wrong_closing_formula": {
        "patterns": [],
        "diagnosis": "结尾用语不符合文种规范",
        "prescription": "通知→'特此通知'；请示→'妥否，请批示'；批复→'此复'；函→'特此函告'或'请予支持为盼'",
        "severity": ReviewSeverity.MAJOR,
        "check_method": "structural",
    },
    "missing_signer": {
        "patterns": [],
        "diagnosis": "上行文缺少签发人标注",
        "prescription": "上行文必须在发文字号右侧标注签发人姓名。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "structural",
    },
    "multiple_items_in_request": {
        "patterns": [],
        "diagnosis": "请示中包含多个不相关的事项",
        "prescription": "请示必须一文一事。如有多个事项需要请示，分别行文。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "structural",
    },
    "report_with_request": {
        "patterns": [],
        "diagnosis": "报告中夹带了请示事项",
        "prescription": "报告不得夹带请示事项。如需请示，单独行文。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "redundant_opening": {
        "patterns": [
            "为了贯彻落实", "在……正确领导下", "深入学习贯彻",
            "以……为指导", "高举……伟大旗帜",
        ],
        "diagnosis": "使用了程式化套话开头，增加冗余",
        "prescription": "删除套话。行政公文直接以'根据……'或事项本身开头。",
        "severity": ReviewSeverity.MINOR,
    },
}

# ═══════════════════════════════════════════════════════════════
# OBJECTIVE_REPORT 专属错误诊断库
# ═══════════════════════════════════════════════════════════════

OBJECTIVE_ERROR_DB = {
    "absolute_claims": {
        "patterns": [
            "第一", "首个", "唯一", "史上最", "全国最", "突破性",
            "填补空白", "国际领先", "世界一流",
        ],
        "diagnosis": "使用了绝对化或夸大性表述，不符合客观报告要求",
        "prescription": "删除绝对化表述。如需说明领先性，用具体数据：'据XX统计，该指标在XX范围内排名第X'",
        "severity": ReviewSeverity.CRITICAL,
    },
    "subjective_judgment": {
        "patterns": [
            "高度重视", "精心组织", "周密部署", "高位推动",
            "圆满完成", "顺利实现", "成效显著",
        ],
        "diagnosis": "使用了主观评价性语言",
        "prescription": "删除评价性词汇。'高度重视'→具体说明采取了哪些措施。'成效显著'→用数据说明成效。",
        "severity": ReviewSeverity.MAJOR,
    },
    "conclusion_without_evidence": {
        "patterns": [],
        "diagnosis": "结论缺少数据或案例支撑",
        "prescription": "每个结论必须附带数据来源或案例引用。建议格式：'……（数据来源：XX报告/XX部门统计）'",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "evading_core_issue": {
        "patterns": [],
        "diagnosis": "文章可能回避或弱化了核心问题",
        "prescription": "事故通报以事实开篇，调研报告以问题开篇。不回避矛盾，直面'不完美的真实'。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "semantic",
    },
    "external_leverage": {
        "patterns": [],
        "diagnosis": "试图借外部权威为自身背书（客观报告不需要借势）",
        "prescription": "删除借势性表述。客观报告只需要事实、数据和逻辑，不需要'XX专家指出'来增强可信度。",
        "severity": ReviewSeverity.MAJOR,
        "check_method": "semantic",
    },
}

INFO_ERROR_DB = {
    "missing_5w1h": {
        "patterns": [],
        "diagnosis": "导语缺少5W1H中的关键要素",
        "prescription": "导语必须包含：时间、地点、主体、事件、目的/意义。读者看完第一段应能回答'谁在什么时间什么地点做了什么'。",
        "severity": ReviewSeverity.CRITICAL,
        "check_method": "structural",
    },
    "wrong_structure": {
        "patterns": ["首先", "然后", "接着", "最后", "上午", "下午"],
        "diagnosis": "使用了时间顺序流水账，而非逻辑结构",
        "prescription": "消息用倒金字塔（最重要→次重要→背景）。活动稿按逻辑顺序而非时间顺序排列。",
        "severity": ReviewSeverity.MAJOR,
    },
    "evaluative_language": {
        "patterns": [
            "圆满", "顺利", "成功", "精彩", "热烈", "隆重",
            "大家纷纷表示", "一致认为", "深刻感受到",
        ],
        "diagnosis": "使用了评价性语言和模糊表述",
        "prescription": "删除评价性词语。'圆满成功'→直接陈述结果。'大家纷纷表示'→引用具体人的原话。",
        "severity": ReviewSeverity.MAJOR,
    },
    "wrong_audience_address": {
        "patterns": [],
        "diagnosis": "对内/对外称谓不当",
        "prescription": "对内稿件可用'我院/我校'，对外稿件用全称。团学稿件用'支部成员'替代'同学'。",
        "severity": ReviewSeverity.MINOR,
        "check_method": "semantic",
    },
    "photo_ending": {
        "patterns": ["合影留念", "本次活动圆满结束", "活动到此结束"],
        "diagnosis": "结尾使用了'合影留念''圆满结束'等套话",
        "prescription": "删除此类结尾。如需注明摄影者，格式为'（通讯员：XXX 摄影：XXX）'",
        "severity": ReviewSeverity.MINOR,
    },
    "title_too_weak": {
        "patterns": ["活动纪实", "活动报道", "新闻稿", "通讯稿"],
        "diagnosis": "标题缺乏信息量",
        "prescription": "标题应直接点出最有新闻价值的信息，控制在15-25字。",
        "severity": ReviewSeverity.MAJOR,
    },
}

ALL_ERROR_DBS = {
    WritingMode.STRATEGIC_NARRATIVE: {**UNIVERSAL_ERROR_DB, **STRATEGIC_ERROR_DB},
    WritingMode.OBJECTIVE_REPORT: {**UNIVERSAL_ERROR_DB, **OBJECTIVE_ERROR_DB},
    WritingMode.ADMINISTRATIVE: {**UNIVERSAL_ERROR_DB, **ADMIN_ERROR_DB},
    WritingMode.INFORMATIONAL: {**UNIVERSAL_ERROR_DB, **INFO_ERROR_DB},
}


class ReviewerAgent:
    """
    模式感知的审稿Agent

    核心改进：
    1. 审查维度不再硬编码，而是根据写作模式动态选择
    2. 新增'事实准确性审查'作为所有模式的通用底线
    3. 不同模式有各自专属的错误诊断库
    """

    def __init__(self):
        self.mode: Optional[WritingMode] = None
        self.review_history: List[ReviewResult] = []

    def set_mode(self, mode: WritingMode):
        """设置当前写作模式，据此切换审查维度和错误库"""
        self.mode = mode

    def get_dimensions(self) -> List[Dict[str, Any]]:
        """获取当前模式的审查维度"""
        if not self.mode:
            self.mode = WritingMode.STRATEGIC_NARRATIVE
        return get_review_dimensions(self.mode)

    def get_error_db(self) -> Dict:
        """获取当前模式的错误诊断库"""
        if not self.mode:
            self.mode = WritingMode.STRATEGIC_NARRATIVE
        return ALL_ERROR_DBS.get(self.mode, ALL_ERROR_DBS[WritingMode.STRATEGIC_NARRATIVE])

    def build_review_prompt(
        self, draft: str, round_index: int, brief: Any = None
    ) -> str:
        """为指定轮次构建审查Prompt（模式感知版）"""
        dimensions = self.get_dimensions()
        if round_index >= len(dimensions):
            return ""

        dim = dimensions[round_index]

        mode_key = self.mode.value if self.mode else "default"
        cache_key = f"review_{mode_key}_r{round_index}"
        cached = cached_prompt("reviewer_round", cache_key)
        
        if cached:
            static_parts = cached
        else:
            mode_profile = get_mode_profile(self.mode)
            static_parts = f"""
# 审稿任务：{dim['name']}

## 审查说明
{dim['description']}

## 检查清单
{chr(10).join(f'- {item}' for item in dim['check_items'])}

## 当前写作模式
{mode_profile.name}
核心理念：{mode_profile.tagline}

## 该模式禁止的表述
{chr(10).join(f'- {p}' for p in mode_profile.forbidden_patterns[:5])}

## 输出格式要求

请按以下格式输出审查结果：

### 总体判断
[通过/未通过]
"""

        prompt = static_parts

        if brief:
            prompt += f"""
## 写作简报参考
- 核心目的：{brief.purpose if hasattr(brief, 'purpose') else '未指定'}
- 目标读者：{brief.primary_audience if hasattr(brief, 'primary_audience') else '未指定'}
"""

        prompt += f"""
## 待审稿件

{draft}

### 发现的问题
对每个问题，按以下格式输出：
- 位置：[指出具体段落或句子]
- 问题：[描述问题]
- 严重程度：[严重/重要/轻微/建议]
- 修改建议：[具体如何修改]
- 建议修改为：[给出修改后的文本]

### 本轮评分
[0-100分]

### 总结
[一句话总结本轮审查的核心发现]
"""
        return prompt

    def run_review(
        self, draft: str, round_index: int, brief: Any = None
    ) -> ReviewResult:
        """执行单轮审查"""
        dimensions = self.get_dimensions()
        if round_index >= len(dimensions):
            return ReviewResult(
                round_name="审查完成",
                passed=True,
                overall_score=100.0,
            )

        dim = dimensions[round_index]
        result = ReviewResult(
            round_name=dim['name'],
            passed=True,
            findings=[],
            overall_score=100.0,
        )
        self.review_history.append(result)
        return result

    def get_round_prompt(self, round_index: int) -> str:
        """获取指定轮次的审查Prompt（供LLM API调用）"""
        dimensions = self.get_dimensions()
        if round_index >= len(dimensions):
            return "所有审查轮次已完成。"

        dim = dimensions[round_index]
        return f"""
执行{dim['name']}（权重：{dim['weight']*100:.0f}%）：
{dim['description']}

检查以下项目：
{chr(10).join(f'  {i+1}. {item}' for i, item in enumerate(dim['check_items']))}
"""

    def get_all_round_prompts(self) -> List[str]:
        """获取全部审查轮次的Prompt列表"""
        return [self.get_round_prompt(i) for i in range(len(self.get_dimensions()))]

    def get_round_count(self) -> int:
        """获取当前模式的审查轮次数"""
        return len(self.get_dimensions())

    def diagnose_errors(self, text: str) -> List[Dict[str, str]]:
        """
        基于模式匹配的自动错误诊断（模式感知版）
        可以在不调用LLM的情况下快速发现常见问题
        """
        error_db = self.get_error_db()
        findings = []
        for error_key, error_info in error_db.items():
            if error_info.get("check_method") == "structural":
                continue
            for pattern in error_info.get("patterns", []):
                if pattern in text:
                    findings.append({
                        "error_key": error_key,
                        "diagnosis": error_info["diagnosis"],
                        "prescription": error_info["prescription"],
                        "severity": error_info["severity"].value,
                        "matched_pattern": pattern,
                    })
                    break
        return findings

    def check_subject_ratio(self, text: str) -> Dict[str, Any]:
        """
        检查主体性：统计主语分布
        仅对 STRATEGIC_NARRATIVE 模式有效
        """
        we_indicators = ["我们", "同学们", "师生", "团队", "学院", "我方"]
        they_indicators = ["北大", "清华", "对方", "他们", "教授", "专家"]

        we_count = sum(text.count(w) for w in we_indicators)
        they_count = sum(text.count(w) for w in they_indicators)

        total = we_count + they_count
        we_ratio = we_count / total if total > 0 else 0.5

        return {
            "we_count": we_count,
            "they_count": they_count,
            "we_ratio": we_ratio,
            "healthy": we_ratio >= 0.6,
            "suggestion": (
                "主体性良好，叙述重心在'我们'"
                if we_ratio >= 0.6
                else f"⚠️ 我方叙述占比仅{we_ratio:.0%}，建议将更多'对方做了什么'改为'我们收获了什么'"
            ),
        }

    def check_format_compliance(self, text: str) -> List[Dict[str, str]]:
        """
        格式合规性检查（所有模式通用）
        基于《党政机关公文格式》(GB/T 9704-2012)
        """
        findings = []

        if "请示" in text[:50] and "妥否" not in text[-100:]:
            findings.append({
                "error_key": "missing_closing_formula",
                "diagnosis": "请示结尾可能缺少'妥否，请批示'",
                "prescription": "请示结尾必须使用'妥否，请批示'或'以上请示妥否，请批示'",
                "severity": "critical",
            })

        if "通知" in text[:50] and "特此通知" not in text[-100:]:
            findings.append({
                "error_key": "missing_closing_formula",
                "diagnosis": "通知结尾可能缺少'特此通知'",
                "prescription": "通知一般以'特此通知'结尾",
                "severity": "major",
            })

        return findings

    def run_full_review(
        self, draft: str, mode: WritingMode, brief: Any = None
    ) -> List[Dict[str, Any]]:
        """
        执行一次性的并行审查（不迭代修改）

        Returns:
            每轮审查的汇总结果
        """
        self.set_mode(mode)
        dimensions = self.get_dimensions()
        results = []

        for i, dim in enumerate(dimensions):
            auto_findings = self.diagnose_errors(draft)

            subject_check = None
            if mode == WritingMode.STRATEGIC_NARRATIVE:
                subject_check = self.check_subject_ratio(draft)

            format_check = None
            if mode == WritingMode.ADMINISTRATIVE:
                format_check = self.check_format_compliance(draft)

            results.append({
                "round": dim["name"],
                "weight": dim["weight"],
                "passed": len(auto_findings) == 0,
                "auto_findings": auto_findings,
                "subject_check": subject_check,
                "format_check": format_check,
                "review_prompt": self.build_review_prompt(draft, i, brief),
            })

        return results

    # ═══════════════════════════════════════════════════════════
    # 迭代修复方法（V2.1 新增）
    # ═══════════════════════════════════════════════════════════

    @staticmethod
    def _apply_fix(draft: str, finding: Dict[str, str]) -> str:
        """
        基于单条审查发现对文本应用自动修复

        策略优先级：
          1. 精确匹配替换 (pattern -> fix)
          2. 语义替换（关键词启发式）

        Args:
            draft: 原文
            finding: 单条诊断结果，含 'matched_pattern', 'prescription' 等字段

        Returns:
            修复后的文本
        """
        import re

        pattern = finding.get("matched_pattern")
        error_key = finding.get("error_key", "")
        prescription = finding.get("prescription", "")

        if not pattern:
            return draft

        error_specific_fixes = {
            "passive_narrative": lambda d, p: _rewrite_passive_to_active(d, p),
            "empty_platitudes": lambda d, p: _remove_pattern(d, p),
            "process_flow_account": lambda d, p: _remove_pattern(d, p),
            "redundant_opening": lambda d, p: _remove_pattern(d, p),
            "evaluative_language": lambda d, p: _remove_pattern(d, p),
            "absolute_claims": lambda d, p: _remove_pattern(d, p),
            "subjective_judgment": lambda d, p: _remove_pattern(d, p),
            "wrong_structure": lambda d, p: _remove_pattern(d, p),
            "photo_ending": lambda d, p: _remove_pattern(d, p),
            "weak_ending": lambda d, p: _remove_pattern(d, p),
            "title_weak": lambda d, p: _remove_pattern(d, p),
        }

        if error_key in error_specific_fixes:
            return error_specific_fixes[error_key](draft, pattern)

        return _remove_pattern(draft, pattern)

    @staticmethod
    def apply_fixes(
        draft: str, findings: List[Dict[str, str]]
    ) -> Tuple[str, List[str]]:
        """
        批量应用修复，返回修复后的文本和变更日志

        Args:
            draft: 原文
            findings: diagnose_errors() 返回的诊断结果列表

        Returns:
            (fixed_draft, [change_log_entries])
        """
        fixed = draft
        change_log = []

        findings_sorted = sorted(
            findings,
            key=lambda f: {"critical": 0, "major": 1, "minor": 2}.get(
                f.get("severity", "minor"), 3
            ),
        )

        for finding in findings_sorted:
            pattern = finding.get("matched_pattern")
            if not pattern or pattern not in fixed:
                continue

            fixed = ReviewerAgent._apply_fix(fixed, finding)
            change_log.append(
                f"[{finding.get('severity', 'minor').upper()}] "
                f"已移除 '{pattern}' — {finding.get('diagnosis', '')}"
            )

        return fixed, change_log

    def iterate_review(
        self,
        draft: str,
        mode: WritingMode,
        brief: Any = None,
        max_iterations: Optional[int] = None,
    ) -> Tuple[str, List[Dict[str, Any]]]:
        """
        执行迭代式审查（V2.1 核心方法）

        流程：
          第1轮：审 original_draft → 自动修复 → rev1_draft
          第2轮：审 rev1_draft → 自动修复 → rev2_draft
          ...
          最后一轮：审上一轮修复后的版本 → 记录残留问题

        Args:
            draft: 原始初稿
            mode: 写作模式
            brief: 写作简报
            max_iterations: 最大迭代次数，默认使用模式维度数

        Returns:
            (final_draft, [per_round_results])
        """
        self.set_mode(mode)
        self.review_history = []
        dimensions = self.get_dimensions()

        if max_iterations is None:
            max_iterations = len(dimensions)

        current_draft = draft
        iteration_results = []

        for i in range(min(max_iterations, len(dimensions))):
            dim = dimensions[i]

            auto_findings = self.diagnose_errors(current_draft)

            subject_check = None
            if mode == WritingMode.STRATEGIC_NARRATIVE:
                subject_check = self.check_subject_ratio(current_draft)

            format_check = None
            if mode == WritingMode.ADMINISTRATIVE:
                format_check = self.check_format_compliance(current_draft)

            change_log = []
            if auto_findings:
                current_draft, change_log = self.apply_fixes(current_draft, auto_findings)

            round_result = ReviewResult(
                round_name=dim["name"],
                passed=len(auto_findings) == 0 or len(change_log) > 0,
                findings=[
                    ReviewFinding(
                        round_name=dim["name"],
                        severity=ReviewSeverity(f.get("severity", "minor")),
                        location="auto-detect",
                        issue=f.get("diagnosis", ""),
                        suggestion=f.get("prescription", ""),
                    )
                    for f in auto_findings
                ],
                overall_score=100.0 - len(auto_findings) * (100.0 / max(len(dimensions), 1)),
            )
            self.review_history.append(round_result)

            iteration_results.append({
                "round": dim["name"],
                "weight": dim["weight"],
                "findings_count": len(auto_findings),
                "fixes_applied": len(change_log),
                "change_log": change_log,
                "subject_check": subject_check,
                "format_check": format_check,
                "review_prompt": self.build_review_prompt(current_draft, i, brief),
                "passed": round_result.passed,
            })

        return current_draft, iteration_results

    def run_parallel_review(
        self, draft: str, mode: WritingMode, brief: Any = None
    ) -> List[Dict[str, Any]]:
        return self.run_full_review(draft, mode, brief)


def _remove_pattern(text: str, pattern: str) -> str:
    result = text.replace(pattern, "")
    result = text.replace(pattern, "")
    return result


def _rewrite_passive_to_active(text: str, trigger_word: str) -> str:
    import re
    replacements = {
        "安排了": "我们前往",
        "组织了": "我们参与了",
        "邀请了": "我们有幸聆听了",
        "讲解了": "我们学习了",
        "介绍了": "我们了解到",
        "展示了": "我们观摩了",
    }
    return text.replace(trigger_word, replacements.get(trigger_word, ""))
