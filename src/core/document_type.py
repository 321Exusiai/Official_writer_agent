"""
文种识别与模板模块

根据用户输入和写作简报，自动判断最优文种（消息/通讯/侧记/调研报告/简报），
并为每种文种提供对应的结构模板。

核心逻辑：
1. 根据事件性质、篇幅需求、受众类型自动判断文种
2. 每种文种有独立的模板、篇幅规范、对标媒体
3. 用户也可以手动选择文种
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple


class DocumentType(Enum):
    NEWS_BRIEF = "news_brief"
    FEATURE = "feature"
    SIDELIGHT = "sidelight"
    RESEARCH_REPORT = "research_report"
    BULLETIN = "bulletin"
    CIRCULAR = "circular"
    REQUEST = "request"
    NOTIFICATION = "notification"
    REPLY = "reply"
    LETTER = "letter"
    MEETING_MINUTES = "meeting_minutes"
    ANNOUNCEMENT = "announcement"
    DECISION = "decision"
    REPORT = "report"
    OPINION = "opinion"
    MOTION = "motion"


@dataclass
class DocTypeProfile:
    doc_type: DocumentType
    name_cn: str
    description: str
    typical_length_range: Tuple[int, int]
    structure_mode: str
    benchmark_media: str
    applicable_scenarios: List[str]
    key_features: List[str]
    opening_template: str
    body_template: str
    closing_template: str
    audience_focus: Dict[str, str]


DOC_TYPE_PROFILES: Dict[DocumentType, DocTypeProfile] = {
    DocumentType.NEWS_BRIEF: DocTypeProfile(
        doc_type=DocumentType.NEWS_BRIEF,
        name_cn="消息",
        description="短小精悍，一事一报，适合快速传播和媒体通稿",
        typical_length_range=(300, 800),
        structure_mode="倒金字塔：最重要→次重要→背景",
        benchmark_media="新华社",
        applicable_scenarios=[
            "活动简讯/快讯",
            "成果发布/签约仪式",
            "人事任免/通知公告",
            "需要媒体转载的通稿",
        ],
        key_features=[
            "导语五要素齐全（何时、何地、何人、何事、何故）",
            "最重要的事实放在最前面",
            "一段一事，段落简短",
            "不展开议论，以事实说话",
            "字数严格控制在800字以内",
        ],
        opening_template=(
            "【导语段】一句话概括核心事实，五要素齐全\n"
            "格式：时间+地点+主体+事件+意义/结果"
        ),
        body_template=(
            "【核心事实展开】对导语中最重要的事实进行补充说明\n"
            "  - 关键数据、引语、细节\n"
            "【次要事实】按重要性递减排列\n"
            "【背景信息】必要的组织/行业背景（1-2句即可）"
        ),
        closing_template=(
            "【意义点题】一句话点明意义（可选）\n"
            "【后续展望】如有明确后续计划，简要提及（可选）"
        ),
        audience_focus={
            "internal": "成果展示，简明扼要",
            "upward": "事件性质+核心数据",
            "external": "新闻价值+传播要点",
            "peer": "专业亮点+可对标数据",
        },
    ),

    DocumentType.FEATURE: DocTypeProfile(
        doc_type=DocumentType.FEATURE,
        name_cn="通讯",
        description="深度叙事，结构完整，适合研学/调研/考察活动的全面报道",
        typical_length_range=(1500, 3000),
        structure_mode="总—分—总递进式：开篇定位→分站展开→总结升华",
        benchmark_media="人民日报",
        applicable_scenarios=[
            "研学/调研/考察活动深度报道",
            "重要会议的全面纪实",
            "典型人物/团队的深度报道",
            "需要同时满足对内、向上、对外多维度需求的稿件",
        ],
        key_features=[
            "总—分—总递进式布局",
            "行程之间遵循递进逻辑（知→学→志）",
            "三条隐形线索：认知线、情感线、战略线",
            "每段行程必须回扣培养理念（战略锚点）",
            "善用真实感言替代空泛表态",
        ],
        opening_template=(
            "【宏观起笔/场景切入】时代背景或引人入胜的场景\n"
            "【组织定位】一句话交代'我们是谁，为何出发'\n"
            "【导语收束】以一句话点出本次活动的核心意义\n"
            "【行程概述】简要交代活动的时间、地点、主要行程"
        ),
        body_template=(
            "【第一站】战略对接/全球视野（知）\n"
            "  - 战略锚点句：为什么是这里\n"
            "  - 核心场景描述 + 关键收获\n"
            "  - 外部权威观点 + 与我方理念的呼应\n"
            "  - 过渡句：从第一站自然过渡到第二站\n"
            "【第二站】同频共振/学术成长（学）\n"
            "  - 对标锚点句：与谁对标，为何重要\n"
            "  - 交流场景 + 真实感言（1-2段精选）\n"
            "  - 成长证据：具体收获是什么\n"
            "  - 过渡句：从学术成长过渡到使命担当\n"
            "【第三站】家国情怀/使命担当（志）\n"
            "  - 精神锚点句：承载什么精神/使命\n"
            "  - 震撼场景 + 感悟体认\n"
            "  - 与培养目标中'家国情怀'的呼应"
        ),
        closing_template=(
            "【回顾总结】以一句话回顾行程，点明'这段旅程意味着什么'\n"
            "【证据收束】以1-2段真实感言作为'成长证据'\n"
            "【升华展望】结合时代背景与组织愿景，含蓄传递'有方向、有资源、有成果'\n"
            "注意：切忌过度膨胀，点到即止，余韵自生"
        ),
        audience_focus={
            "internal": "团队成员的成长与收获",
            "upward": "组织投入正在产生回报",
            "external": "人才培养格局与国家战略对接",
            "peer": "培养质量不逊于第一梯队",
        },
    ),

    DocumentType.SIDELIGHT: DocTypeProfile(
        doc_type=DocumentType.SIDELIGHT,
        name_cn="侧记/特写",
        description="场景驱动，以小见大，适合活动现场感强的报道",
        typical_length_range=(800, 1500),
        structure_mode="场景切入→细节展开→主题收束",
        benchmark_media="央视新闻",
        applicable_scenarios=[
            "论坛/讲座/沙龙活动的现场报道",
            "人物专访/对话",
            "以某个动人瞬间为切入点的活动报道",
            "需要突出'现场感'和'温度'的稿件",
        ],
        key_features=[
            "从一个具体场景或人物切入",
            "主题事件化、事件人物化、人物命运化",
            "细节叙事，用画面感代替概述",
            "情感浓度高，但不过度煽情",
            "字数精炼，聚焦一个核心场景",
        ],
        opening_template=(
            "【场景切入】以一个具象的场景、人物或细节开篇\n"
            "  - 让读者'看到'现场\n"
            "  - 可以是对话、动作、表情\n"
            "【悬念/转折】从具体场景引出文章主题"
        ),
        body_template=(
            "【场景展开】对核心场景进行深度描绘\n"
            "  - 人物动作、语言、表情\n"
            "  - 环境细节\n"
            "  - 冲突或转折\n"
            "【背景穿插】在叙事中自然穿插必要的背景信息\n"
            "  - 不打断叙事节奏\n"
            "  - 一两句话点到即可"
        ),
        closing_template=(
            "【场景呼应】回到开头的场景或人物，形成首尾呼应\n"
            "【主题升华】从具体到抽象，自然过渡\n"
            "【留白收尾】以画面或一句话结束，不强行总结"
        ),
        audience_focus={
            "internal": "情感共鸣，团队归属感",
            "upward": "工作温度，人文关怀",
            "external": "故事感染力，传播性",
            "peer": "专业品质，人文素养",
        },
    ),

    DocumentType.RESEARCH_REPORT: DocTypeProfile(
        doc_type=DocumentType.RESEARCH_REPORT,
        name_cn="调研报告",
        description="问题导向，学理深度，适合深度调研类报道",
        typical_length_range=(3000, 8000),
        structure_mode="问题—调研—发现—建议",
        benchmark_media="光明日报",
        applicable_scenarios=[
            "深度调研/田野调查",
            "需要系统性分析的长篇报道",
            "涉及多维度问题的综合报告",
            "需要提出对策建议的调研成果",
        ],
        key_features=[
            "问题导向，以一个问题或矛盾开篇",
            "调研过程本身就是核心内容",
            "注重学理深度和思想性",
            "不回避矛盾，呈现'不完美的真实'",
            "善用数据和案例支撑观点",
        ],
        opening_template=(
            "【问题提出】以一个引人深思的问题或矛盾现象开篇\n"
            "【调研背景】为什么选择这个选题，调研了什么\n"
            "【核心发现预告】用一两句话暗示文章的核心发现"
        ),
        body_template=(
            "【第一部分】现象描述：看到了什么\n"
            "  - 选取典型场景和案例\n"
            "  - 呈现矛盾性和复杂性\n"
            "  - 不急于下结论\n"
            "【第二部分】深度分析：为什么会这样\n"
            "  - 引入历史维度和理论框架\n"
            "  - 多角度分析原因\n"
            "  - 数据支撑和案例佐证\n"
            "【第三部分】对策建议：应该怎么办\n"
            "  - 基于调研发现提出建议\n"
            "  - 可操作、可验证\n"
            "  - 区分短期和长期"
        ),
        closing_template=(
            "【思想提炼】将个案经验上升到规律性认识\n"
            "【展望建议】不强行给出答案，但指明方向\n"
            "【余韵】留给读者思考空间"
        ),
        audience_focus={
            "internal": "工作方法和思路启发",
            "upward": "决策参考价值",
            "external": "专业深度和社会价值",
            "peer": "研究方法和发现的可借鉴性",
        },
    ),

    DocumentType.BULLETIN: DocTypeProfile(
        doc_type=DocumentType.BULLETIN,
        name_cn="简报",
        description="条目清晰，要点明确，适合内部汇报和信息传达",
        typical_length_range=(500, 1000),
        structure_mode="条目式/分段式：标题→导语→分条→结语",
        benchmark_media="党政机关公文",
        applicable_scenarios=[
            "内部工作汇报",
            "向上级的信息简报",
            "需要快速传阅的活动总结",
            "OA系统/内部平台发布",
        ],
        key_features=[
            "标题规范：发文机关+事由+文种",
            "条目清晰，一事一条",
            "语言简洁，不展开描写",
            "注重信息密度而非文学性",
            "适合快速阅读和存档",
        ],
        opening_template=(
            "【标题】发文机关名称+事由+简报\n"
            "【导语】时间+地点+活动名称+参与人员+总体情况（2-3句）"
        ),
        body_template=(
            "【分条叙述】按逻辑顺序分条\n"
            "  - 一、主要行程/议程\n"
            "  - 二、核心成果/收获\n"
            "  - 三、下一步计划/建议\n"
            "每条2-4句话，点到即止"
        ),
        closing_template=(
            "【报送范围】抄送：XX部门（如有需要）\n"
            "【成文日期】XXXX年XX月XX日"
        ),
        audience_focus={
            "internal": "工作进展和下一步计划",
            "upward": "核心成果和资源需求",
            "external": "不适用（内部文档）",
            "peer": "工作方法和经验",
        },
    ),
}


class DocumentTypeIdentifier:
    """文种识别器 — 根据写作简报自动推荐文种（V2.3：素材维度 + 篇幅驱动）"""

    MATERIAL_ANALYSIS_KEYWORDS = {
        "data": ["数据", "统计", "数字", "比例", "百分比", "同比", "环比", "增长率", "指标", "测算"],
        "quotes": ["感言", "感受", "说", "表示", "谈到", "感慨", "认为", "印象", "体会", "心得"],
        "scenes": ["场景", "画面", "现场", "瞬间", "镜头", "走进", "看到", "听到", "站在"],
        "documents": ["文件", "通知", "指示", "批示", "精神", "政策", "条例", "办法", "规定"],
    }

    def __init__(self):
        self.profiles = DOC_TYPE_PROFILES

    def analyze_materials(self, key_materials: str) -> Dict[str, float]:
        """
        分析 key_materials 的内容类型比例
        Returns: {"data": 0.3, "quotes": 0.4, "scenes": 0.2, "documents": 0.1}
        """
        if not key_materials:
            return {"data": 0.0, "quotes": 0.0, "scenes": 0.0, "documents": 0.0}

        text = key_materials.lower()
        total_matches = 0
        scores = {}

        for mtype, keywords in self.MATERIAL_ANALYSIS_KEYWORDS.items():
            count = sum(1 for kw in keywords if kw in text)
            scores[mtype] = count
            total_matches += count

        if total_matches == 0:
            return {"data": 0.25, "quotes": 0.25, "scenes": 0.25, "documents": 0.25}

        for mtype in scores:
            scores[mtype] = scores[mtype] / total_matches

        return scores

    def identify(self, brief: "WritingBrief") -> List[Tuple[DocTypeProfile, float]]:
        """
        V2.3：根据写作简报计算每种文种的匹配度
        新增：
        - length_hint：用户指定篇幅驱动推荐
        - materials_analysis：素材内容类型驱动推荐
        - 消解关键词重叠
        """
        scores: Dict[DocumentType, float] = {dt: 0.0 for dt in DocumentType}
        purpose = (brief.purpose or "").lower()
        audience = (brief.primary_audience or "").lower()
        deep = (brief.deep_meaning or "").lower()
        materials = (brief.key_materials or "")

        keyword_rules = [
            (DocumentType.RESEARCH_REPORT, ["深度", "调研", "分析", "报告", "系统性"], 0.20),
            (DocumentType.NEWS_BRIEF, ["快讯", "通稿", "发布", "消息", "简讯"], 0.20),
            (DocumentType.FEATURE, ["记录", "展现", "报道", "纪实", "全面", "研学", "考察", "交流"], 0.15),
            (DocumentType.SIDELIGHT, ["现场", "瞬间", "感人", "特写", "故事", "感动", "侧记"], 0.20),
            (DocumentType.BULLETIN, ["汇报", "简报", "内部", "上报", "传达"], 0.20),
        ]

        for doc_type, keywords, weight in keyword_rules:
            matches = sum(1 for kw in keywords if kw in purpose)
            if matches > 0:
                scores[doc_type] += weight * min(1.0, matches / 2)

        if any(kw in audience for kw in ["领导", "上级", "汇报"]):
            scores[DocumentType.BULLETIN] += 0.12
            scores[DocumentType.FEATURE] += 0.08
        if any(kw in audience for kw in ["媒体", "记者", "报社", "通讯社"]):
            scores[DocumentType.NEWS_BRIEF] += 0.12
        if any(kw in audience for kw in ["学生", "家长", "团队", "成员"]):
            scores[DocumentType.SIDELIGHT] += 0.10
        if any(kw in deep for kw in ["精神", "传承", "思想", "理论", "文化"]):
            scores[DocumentType.RESEARCH_REPORT] += 0.08
            scores[DocumentType.FEATURE] += 0.08

        if brief.length_hint:
            length = brief.length_hint
            length_boosts = [
                (DocumentType.NEWS_BRIEF, 300, 800),
                (DocumentType.BULLETIN, 500, 1000),
                (DocumentType.SIDELIGHT, 800, 1500),
                (DocumentType.FEATURE, 1500, 3000),
                (DocumentType.RESEARCH_REPORT, 3000, 8000),
            ]
            for dt, low, high in length_boosts:
                if low <= length <= high:
                    center = (low + high) / 2
                    range_size = (high - low) / 2
                    distance = abs(length - center) / range_size
                    scores[dt] += 0.35 * (1.0 - distance)

        mat_scores = self.analyze_materials(materials)
        if mat_scores["data"] > 0.35:
            scores[DocumentType.RESEARCH_REPORT] += 0.15
            scores[DocumentType.NEWS_BRIEF] += 0.10
        if mat_scores["quotes"] > 0.35:
            scores[DocumentType.FEATURE] += 0.12
            scores[DocumentType.SIDELIGHT] += 0.10
        if mat_scores["scenes"] > 0.35:
            scores[DocumentType.SIDELIGHT] += 0.15
            scores[DocumentType.FEATURE] += 0.08
        if mat_scores["documents"] > 0.35:
            scores[DocumentType.BULLETIN] += 0.12

        if max(scores.values()) == 0:
            scores[DocumentType.FEATURE] = 0.5

        ranked = sorted(
            [(self.profiles[dt], score) for dt, score in scores.items()],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked

    def get_profile(self, doc_type: DocumentType) -> DocTypeProfile:
        return self.profiles[doc_type]

    def get_all_profiles(self) -> List[DocTypeProfile]:
        return list(self.profiles.values())

    def generate_template_prompt(self, profile: DocTypeProfile, audience: str = "external") -> str:
        """生成注入写作Agent的模板提示"""
        audience_notes = profile.audience_focus.get(audience, profile.audience_focus.get("external", ""))
        return f"""
【当前文种】{profile.name_cn}

【文种要求】
- 篇幅：{profile.typical_length_range[0]}-{profile.typical_length_range[1]}字
- 结构：{profile.structure_mode}
- 对标媒体：{profile.benchmark_media}

【核心特征】
{'；'.join(profile.key_features)}

【结构模板】
>>> 开篇
{profile.opening_template}

>>> 正文
{profile.body_template}

>>> 结尾
{profile.closing_template}

【受众侧重】{audience_notes}
"""
