"""
写作模式系统 — 决策树分类 + 五套写作方法论并列

解决原系统的核心偏差：将"新闻通讯五大原则"从全局硬约束
降级为一个可选写作模式，引入党政机关规范、新闻规范、
高校团学规范、新媒体青年共情等多套方法论。

设计依据：
- 《党政机关公文处理工作条例》(中办发〔2012〕14号)
- 《党政机关公文格式》(GB/T 9704-2012)
- 马克思主义新闻观与中国当代政治话语体系（宏大叙事与微观落点）
- 新闻采编核心规范（5W1H + 倒金字塔 + 事实交叉验证）
- 高校共青团与学生会新媒体宣传规律（网感、情绪价值、破除官腔）
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any


class WritingMode(Enum):
    STRATEGIC_NARRATIVE = "strategic_narrative"
    OBJECTIVE_REPORT = "objective_report"
    ADMINISTRATIVE = "administrative"
    INFORMATIONAL = "informational"
    YOUTH_ENGAGEMENT = "youth_engagement"


class DocumentCategory(Enum):
    EXTERNAL_COMM = "external_communication"
    INTERNAL_ADMIN = "internal_administration"
    ACTIVITY_RECORD = "activity_record"
    REPORT_SUMMARY = "report_summary"

# ═══════════════════════════════════════════════════════════════
# 决策树：从用户意图到写作模式的层层分流
# ═══════════════════════════════════════════════════════════════

DECISION_TREE = {
    "root": {
        "question": "这篇文章最核心的使命是什么？请根据受众和目标进行选择。",
        "options": [
            {
                "label": "战略叙事与外宣构建",
                "description": "对外传播——新闻通稿、深度报道、典型人物宣传",
                "category": DocumentCategory.EXTERNAL_COMM,
                "next": "external_comm",
            },
            {
                "label": "规范性公文流转",
                "description": "内部行政——通知、请示、批复、函、纪要",
                "category": DocumentCategory.INTERNAL_ADMIN,
                "next": "internal_admin",
            },
            {
                "label": "校园与社团活动记录",
                "description": "活动记录——团日活动、音乐节、招新游园、学术讲座",
                "category": DocumentCategory.ACTIVITY_RECORD,
                "next": "activity_record",
            },
            {
                "label": "工作成果汇报与问题调研",
                "description": "汇报总结——工作总结、调研报告、述职、事故通报",
                "category": DocumentCategory.REPORT_SUMMARY,
                "next": "report_summary",
            },
        ],
    },

    # ── 分支 1：对外传播 ──
    "external_comm": {
        "question": "你希望文章的深度和篇幅是怎样的？",
        "options": [
            {
                "label": "新闻快讯——简短精炼（300-800字），快速告知核心事实",
                "description": "适合硬核新闻、媒体通稿",
                "mode": WritingMode.INFORMATIONAL,
                "subtype": "news_brief",
            },
            {
                "label": "深度通讯——全景展现（1500-3000字），体现战略高度",
                "description": "适合研学报道、重大活动通讯、典型人物报道",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "feature",
            },
            {
                "label": "特写侧记——场景驱动（800-1500字），聚焦动人瞬间",
                "description": "适合侧记、特写、人物专访",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "sidelight",
            },
        ],
    },

    # ── 分支 2：内部行政 ──
    "internal_admin": {
        "question": "你具体要写哪种行政文书？（严格遵守公文条例）",
        "options": [
            {
                "label": "通知——要求下级机关执行或周知的事项",
                "description": "会议通知、活动通知、任免通知",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "notice",
            },
            {
                "label": "请示/批复——向上级请求指示或答复下级",
                "description": "经费请示、项目请示、人事请示",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "request_reply",
            },
            {
                "label": "函——不相隶属机关商洽工作、询问答复",
                "description": "商洽函、邀请函、答复函",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "letter",
            },
            {
                "label": "会议纪要——记载会议主要情况和议定事项",
                "description": "办公会纪要、专题会纪要",
                "mode": WritingMode.INFORMATIONAL,
                "subtype": "minutes",
            },
        ],
    },

    # ── 分支 3：活动记录 ──
    "activity_record": {
        "question": "这次活动的性质和受众调性是怎样的？",
        "options": [
            {
                "label": "社团招新/文艺汇演/游园会——网感拉满，充满青春活力",
                "description": "面向同龄人，需要情绪价值，适合新媒体推文",
                "mode": WritingMode.YOUTH_ENGAGEMENT,
                "subtype": "club_activity",
            },
            {
                "label": "常规班会/学术讲座——要素清晰，客观准确",
                "description": "面向全院师生，兼顾可读性与准确性",
                "mode": WritingMode.INFORMATIONAL,
                "subtype": "campus_activity",
            },
            {
                "label": "研学考察/社会实践——立意高远，体现思政引领",
                "description": "需要拔高意义，将个体实践融入国家宏大叙事",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "study_tour",
            },
            {
                "label": "校庆/开学典礼等重大校际活动——庄重宏大，品牌塑造",
                "description": "兼具新闻价值与战略高度",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "major_event",
            },
        ],
    },

    # ── 分支 4：汇报总结 ──
    "report_summary": {
        "question": "你汇报或调研的核心内容是什么？",
        "options": [
            {
                "label": "阶段性工作总结——盘点成绩，提炼规律",
                "description": "学期总结、年度总结、专项工作总结",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "work_summary",
            },
            {
                "label": "深度调研报告——发现问题，剖析原因，提出对策",
                "description": "田野调查、专项考察报告",
                "mode": WritingMode.OBJECTIVE_REPORT,
                "subtype": "research_report",
            },
            {
                "label": "事故/问题通报——客观陈述事实，不回避矛盾",
                "description": "安全通报、违规违纪通报、审计整改",
                "mode": WritingMode.OBJECTIVE_REPORT,
                "subtype": "incident_report",
            },
            {
                "label": "个人或部门述职——年度履职情况展示",
                "description": "干部述职、部门述职",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "duty_report",
            },
        ],
    },
}

# ═══════════════════════════════════════════════════════════════
# 五套写作原则 — 理论深度与边界控制
# ═══════════════════════════════════════════════════════════════

@dataclass
class WritingPrinciples:
    mode: WritingMode
    name: str
    tagline: str
    principles: List[Dict[str, str]]
    content_rules: Dict[str, List[str]]
    forbidden_patterns: List[str]
    language_guidelines: List[str]
    benchmark_sources: List[str]

PRINCIPLES_STRATEGIC_NARRATIVE = WritingPrinciples(
    mode=WritingMode.STRATEGIC_NARRATIVE,
    name="战略叙事原则 (马克思主义新闻观视角)",
    tagline='将“信息采集”升华为“意义建构”，用事实说理，将微观实践嵌入宏大叙事。',
    principles=[
        {
            "name": "人民性与微观落点",
            "description": "宏大叙事必须有微观落点。用亲历者的真实感言、具体体悟作为“证据”，让读者自己得出结论。严禁“大家纷纷表示”等空泛套话。",
            "check": "这段感言是否具有唯一性？如果是套话，是否应该删除？",
        },
        {
            "name": "唯物史观与过程逻辑",
            "description": "不只展示光鲜结果，更要展现克服困难的过程和深层动因。记录实践的演进规律。",
            "check": "文章是否揭示了事物发展的内在逻辑？",
        },
        {
            "name": "政治站位与战略锚点",
            "description": "行程或工作部署应与国家战略、高校双一流建设形成内在呼应。点明“为什么做这件事”。",
            "check": "删掉战略锚点句，文章是否就沦为流水账？",
        },
    ],
    content_rules={
        "must_write": ["实践与宏观战略的对应关系", "群众/个体的真实获得感", "克服困难的深度逻辑"],
        "must_skip": ["空洞的口号堆砌", "没有事实支撑的拔高", "枯燥的流程流水账"],
    },
    forbidden_patterns=["大家纷纷表示", "深刻感受到", "一致认为", "圆满成功", "顺利结束"],
    language_guidelines=[
        "陈述性、写实性，而非描绘性、虚拟性。",
        "适当使用时代感词汇（赋能、淬炼、共振、锚定），但克制不堆砌。",
        "融通中外，话语自塑，用事实说话。"
    ],
    benchmark_sources=["人民日报深度通讯", "新华社战略报道", "求是杂志理论文章"],
)

PRINCIPLES_OBJECTIVE_REPORT = WritingPrinciples(
    mode=WritingMode.OBJECTIVE_REPORT,
    name="客观调研与通报原则",
    tagline="问题导向、实事求是、交叉验证——让事实自己说话，绝不渲染拔高。",
    principles=[
        {
            "name": "事实交叉验证",
            "description": "所有数据、结论必须有可靠来源。单一信源不可作为核心结论的唯一支撑。",
            "check": "文中的核心判断是否有坚实的数据或访谈支撑？",
        },
        {
            "name": "系统思维与问题导向",
            "description": "直面核心问题，不回避矛盾，呈现“不完美的真实”。深挖现象背后的深层原因。",
            "check": "文章是否抓住了主要矛盾，而非绕着问题走？",
        },
        {
            "name": "对策可操作性",
            "description": "结论和建议必须“政治上可取、政策上可推、操作上可行”。",
            "check": "如果我是执行者，看完建议知道第一步该干什么吗？",
        },
    ],
    content_rules={
        "must_write": ["核心事实和多方数据", "未过滤的矛盾与问题", "具体的改进对策"],
        "must_skip": ["形容词堆砌和主观评价", "没有数据支撑的推论", "“加强管理”等正确的废话"],
    },
    forbidden_patterns=["第一", "首个", "重磅", "突破性", "大家纷纷表示"],
    language_guidelines=[
        "语言极端客观中立，严禁感情色彩强烈的词汇。",
        "段落简短，一个事实一段。",
        "引用时保持原话完整，不做转述加工。"
    ],
    benchmark_sources=["国务院事故调查报告", "高质量政协/人大调研报告", "审计署整改报告"],
)

PRINCIPLES_ADMINISTRATIVE = WritingPrinciples(
    mode=WritingMode.ADMINISTRATIVE,
    name="党政机关公文原则",
    tagline="格式严谨、权责分明、一文一事——严格执行《党政机关公文处理工作条例》。",
    principles=[
        {
            "name": "合规与行文规则",
            "description": "严格区分上行、下行、平行文。请示必须一文一事，报告中严禁夹带请示事项。函的语态应平等协商。",
            "check": "行文方向与文种匹配吗？是否越级行文？",
        },
        {
            "name": "用语规范性",
            "description": "使用规范的公文格式化用语字典（如“妥否，请批示”、“经研究决定”）。严禁口语、俚语和网络词汇。",
            "check": "结尾用语是否符合国家标准规范？",
        },
        {
            "name": "指令清晰性",
            "description": "对于通知等下行文，时间、地点、责任人、标准必须没有任何歧义。",
            "check": "下级看完后还会产生疑问吗？",
        },
    ],
    content_rules={
        "must_write": ["明确的发文依据/引语", "核心诉求或指令", "具体的时间节点与责任方"],
        "must_skip": ["任何私人感情色彩", "模棱两可的用词", "与主旨无关的背景铺垫"],
    },
    forbidden_patterns=["大概", "也许", "尽量", "亲自", "网络热梗"],
    language_guidelines=[
        "字斟句酌，言简意赅。",
        "使用“特此通知”、“请予批复”等标准公文收尾。",
        "段落层次结构严格遵守（一、（一）、1、（1））。"
    ],
    benchmark_sources=["《党政机关公文处理工作条例》(中办发〔2012〕14号)", "《党政机关公文格式》(GB/T 9704-2012)"],
)

PRINCIPLES_INFORMATIONAL = WritingPrinciples(
    mode=WritingMode.INFORMATIONAL,
    name="专业新闻通报原则",
    tagline="5W1H清晰、倒金字塔结构——还原最纯粹的信息价值。",
    principles=[
        {
            "name": "倒金字塔结构",
            "description": "导语即高潮，最重要的信息（新闻眼）放在第一段第一句。逐层递减重要性。",
            "check": "如果只看第一段，读者能掌握核心事实吗？",
        },
        {
            "name": "剥离主观性",
            "description": "不评价、不干预。用直接引语代替作者的转述，用客观数据代替形容词。",
            "check": "删掉所有形容词，核心信息还在吗？",
        },
        {
            "name": "信息完整性",
            "description": "时间、地点、人物、起因、经过、结果（5W1H）不可或缺。",
            "check": "要素是否有遗漏？",
        },
    ],
    content_rules={
        "must_write": ["包含新闻眼的导语", "5W1H", "真实的直接引语"],
        "must_skip": ["作者的个人感慨", "过长的前情提要", "缺乏来源的断言"],
    },
    forbidden_patterns=["值得一提的是", "毫无疑问", "笔者认为", "让人感叹"],
    language_guidelines=[
        "精炼有力，长短句结合。",
        "不铺垫，开门见山。",
        "大量使用动名词搭配，少用副词。"
    ],
    benchmark_sources=["新华社快讯", "高校新闻网消息规范"],
)

PRINCIPLES_YOUTH_ENGAGEMENT = WritingPrinciples(
    mode=WritingMode.YOUTH_ENGAGEMENT,
    name="青年共情与社团活力原则 (网感与边界控制)",
    tagline="懂年轻人的梗，说人话，抓情绪——为新媒体时代的校园发声，但坚守边界。",
    principles=[
        {
            "name": "网感与视觉留白",
            "description": "文字轻盈跳跃，多短句，为现场照片和视频留出视觉空间。使用合适的颜文字或梗，增强表现力。",
            "check": "这段文字如果在手机屏幕上阅读，会让人感到窒息吗？",
        },
        {
            "name": "不失分寸 (边界控制)",
            "description": "像学长学姐一样真诚交流，但严禁强行称兄道弟、过度讨好谄媚（禁称'宝宝们'）。",
            "check": "这语气是平视的真诚，还是刻意的装嫩？",
        },
        {
            "name": "克制情绪，去官腔，去AI味",
            "description": "情绪由具体细节流露，禁止堆砌感叹号。严禁'领导高度重视'、'圆满成功'等官样文章。禁止'总而言之'等AI套话。",
            "check": "有没有爹味、官腔或机器味？",
        },
    ],
    content_rules={
        "must_write": ["现场最鲜活/搞笑/感人的瞬间", "强互动的问句或行动号召", "社团独特的黑话/标识"],
        "must_skip": ["领导致辞的冗长总结", "枯燥的流程记录", "无病呻吟的抒情段落", "极其抽象的小众烂梗"],
    },
    forbidden_patterns=[
        "领导高度重视", "圆满成功", "取得丰硕成果", "总而言之", "不可否认的是", "充满激情与活力",
        "家人们", "宝宝们", "绝绝子"
    ],
    language_guidelines=[
        "采用对话体，多用'你'和'我们'。",
        "语言自带画面感和BGM感。",
        "用自嘲、幽默或真诚化解严肃。"
    ],
    benchmark_sources=["优秀高校社团微信公众号推文", "小红书爆款校园笔记", "B站校园共创内容"],
)

ALL_PRINCIPLES = {
    WritingMode.STRATEGIC_NARRATIVE: PRINCIPLES_STRATEGIC_NARRATIVE,
    WritingMode.OBJECTIVE_REPORT: PRINCIPLES_OBJECTIVE_REPORT,
    WritingMode.ADMINISTRATIVE: PRINCIPLES_ADMINISTRATIVE,
    WritingMode.INFORMATIONAL: PRINCIPLES_INFORMATIONAL,
    WritingMode.YOUTH_ENGAGEMENT: PRINCIPLES_YOUTH_ENGAGEMENT,
}

# ═══════════════════════════════════════════════════════════════
# 审查维度 (用于ReviewerAgent)
# ═══════════════════════════════════════════════════════════════

REVIEW_DIMENSIONS = {
    WritingMode.STRATEGIC_NARRATIVE: [
        {"name": "政治站位审查", "weight": 0.30},
        {"name": "事实与微观落点审查", "weight": 0.30},
        {"name": "语言去AI味审查", "weight": 0.20},
        {"name": "行文逻辑审查", "weight": 0.20},
    ],
    WritingMode.OBJECTIVE_REPORT: [
        {"name": "交叉验证与事实审查", "weight": 0.40},
        {"name": "问题导向审查", "weight": 0.30},
        {"name": "对策可行性审查", "weight": 0.20},
        {"name": "客观性表达审查", "weight": 0.10},
    ],
    WritingMode.ADMINISTRATIVE: [
        {"name": "公文格式规范审查", "weight": 0.40},
        {"name": "行文关系与权限审查", "weight": 0.30},
        {"name": "用语标准度审查", "weight": 0.20},
        {"name": "指令清晰度审查", "weight": 0.10},
    ],
    WritingMode.INFORMATIONAL: [
        {"name": "5W1H要素审查", "weight": 0.40},
        {"name": "倒金字塔结构审查", "weight": 0.30},
        {"name": "客观数据与引语审查", "weight": 0.20},
        {"name": "冗余过滤审查", "weight": 0.10},
    ],
    WritingMode.YOUTH_ENGAGEMENT: [
        {"name": "边界感与去爹味审查", "weight": 0.35},
        {"name": "网感与情绪价值审查", "weight": 0.30},
        {"name": "视觉留白与排版潜力审查", "weight": 0.20},
        {"name": "互动号召力审查", "weight": 0.15},
    ],
}

# ═══════════════════════════════════════════════════════════════
# 各模式的问卷问题集 — 深度与人性化升级
# ═══════════════════════════════════════════════════════════════

MODE_QUESTIONS: Dict[WritingMode, List[Dict[str, str]]] = {
    WritingMode.STRATEGIC_NARRATIVE: [
        {
            "id": "sn_vision",
            "text": "这项实践/活动是如何回应当前国家战略、行业趋势或高校双一流建设等宏观议题的？",
            "why_ask": "一篇有高度的通讯，必须把基层的实践嵌进时代的宏大叙事中。帮我找到这个“战略锚点”。",
            "hint": "例如：呼应了“数字中国”建设 / 践行了学校“全球视野”的人才培养理念",
        },
        {
            "id": "sn_logic",
            "text": "在推进这项工作的过程中，你们克服了哪些核心矛盾？深层动因是什么？",
            "why_ask": "唯物史观告诉我们，过程比光鲜的结果更有价值。没有波折的故事打动不了人。",
            "hint": "不要只写成功，告诉我你们经历了怎样的路线分歧、资金短缺或技术瓶颈，又是如何解决的。",
        },
        {
            "id": "sn_people",
            "text": "作为亲历者或受众群体，个体感受最深、获得感最强的具体细节是什么？",
            "why_ask": "宏大叙事必须有微观落点。我们需要“人的温度”，而不是冰冷的数据堆砌。",
            "hint": "告诉我现场某位同学红了眼眶的一句话，或者某个熬夜奋战的真实瞬间。",
        },
        {
            "id": "sn_value",
            "text": "在同类实践或兄弟院校/单位的比较中，你们的经验具备哪些独特的可推广价值？",
            "why_ask": "我们需要总结出规律性认识，完成理论升华，证明我们走在前列。",
            "hint": "不仅是“我们做了”，更是“我们探索出了一套XX机制”。",
        },
    ],

    WritingMode.OBJECTIVE_REPORT: [
        {
            "id": "or_problem",
            "text": "本次调研或通报试图揭示的核心现象、症结或事实是什么？",
            "why_ask": "客观报告的生命力在于直面真实问题。请用最不带感情色彩的语言描述现状。",
            "hint": "例如：XX项目推进迟缓的现状 / XX安全事故的具体经过",
        },
        {
            "id": "or_cause",
            "text": "导致该现象的深层次原因是什么？是否有交叉验证的客观数据或多方走访支撑？",
            "why_ask": "单一信源不可作为结论依据。我们需要数据和事实的交叉印证。",
            "hint": "不要写“可能因为”，请告诉我“财务数据显示...”加上“基层反映...”。",
        },
        {
            "id": "or_solution",
            "text": "基于上述事实，有何“政治上可取、政策上可推、操作上可行”的建设性方案？",
            "why_ask": "发现问题是为了解决问题。对策必须具体到能够直接落地执行。",
            "hint": "别写“加强重视”，写“由XX部门牵头，每周三进行联合巡检”。",
        },
    ],

    WritingMode.ADMINISTRATIVE: [
        {
            "id": "ad_basis",
            "text": "本次行文的政策依据、上级文件精神或现实迫切需求是什么？",
            "why_ask": "行政公文“师出有名”是第一准则。没有依据的公文会被退回。",
            "hint": "例如：根据《XX条例》第X条规定 / 针对近期校园内频发的XX现象",
        },
        {
            "id": "ad_core",
            "text": "本文的唯一核心诉求（请示）或明确指令（通知）是什么？",
            "why_ask": "公文必须“一文一事”。请用一句话说清楚你到底想要什么或要求别人做什么。",
            "hint": "明确指出时间节点、责任部门和资金额度。拒绝模棱两可。",
        },
        {
            "id": "ad_route",
            "text": "主送单位与抄送单位分别是谁？是否涉及跨部门协调？",
            "why_ask": "行文关系决定了你的语气。发给上级（请示）、下级（通知）还是平级（函）？",
            "hint": "主送只能有一个主管单位，别越级请示。",
        },
    ],

    WritingMode.INFORMATIONAL: [
        {
            "id": "info_5w1h",
            "text": "请简述本次事件的核心要素（时间、地点、人物、起因、经过、结果）？",
            "why_ask": "这是新闻写作的基石。把地基打牢，文章才站得住脚。",
            "hint": "别漏掉关键人物的头衔和事件的确切时间点。",
        },
        {
            "id": "info_lead",
            "text": "如果只能用一句话向外界传递该事件的价值（新闻眼），最核心的信息点是什么？",
            "why_ask": "新闻遵循倒金字塔结构。读者的耐心只有3秒，把最震撼的内容放前面。",
            "hint": "例如不是“我们开了个会”，而是“会上发布了某项颠覆性技术”。",
        },
        {
            "id": "info_quotes",
            "text": "有哪些直接说明问题的客观数据或当事人原话（直接引语）？",
            "why_ask": "让当事人的嘴替你说话，比你自己堆砌一万个形容词都管用。",
            "hint": "去采访几个人，把他们最原汁原味的评价放上来。",
        },
    ],

    WritingMode.YOUTH_ENGAGEMENT: [
        {
            "id": "ye_vibe",
            "text": "这次活动现场最“燃”、最“治愈”或最欢乐的瞬间是什么？描述一下当时的画面。",
            "why_ask": "写给年轻人看的文章，情绪价值是第一生产力。帮我找回当时的氛围（Vibe）。",
            "hint": "比如：全场合唱破音的瞬间 / 突然天降大雨但大家都在雨中狂舞的画面",
        },
        {
            "id": "ye_identity",
            "text": "你们社团/活动独有的“内部梗”或最能代表你们气质的元素是什么？",
            "why_ask": "我们需要适度的“黑话”来拉近距离，彰显社团的灵魂和个性。但注意别太抽象。",
            "hint": "比如动漫社的特定称呼，或者吉他社常被调侃的某位部长。",
        },
        {
            "id": "ye_interaction",
            "text": "现场同学们参与度最高、反响最热烈的环节是哪个？有没有有趣的突发状况？",
            "why_ask": "完美的流程那是公文，带点瑕疵和意外的真实互动才是青春。",
            "hint": "比如设备突然断电，结果主唱直接清唱引发全场大合唱。",
        },
        {
            "id": "ye_cta",
            "text": "在推文的结尾，你想呼吁大家做什么？",
            "why_ask": "新媒体文章一定有互动目的，别让大家看完就划走了。",
            "hint": "比如：扫码加群暗号XX / 评论区留下你的感受，抽三个送周边！",
        },
    ],
}

# ═══════════════════════════════════════════════════════════════
# 决策树导航与辅助函数
# ═══════════════════════════════════════════════════════════════

def navigate_tree(path: List[int]) -> Tuple[WritingMode, str, str]:
    current = DECISION_TREE["root"]
    description_parts = []
    
    for i, choice_idx in enumerate(path):
        if choice_idx >= len(current["options"]):
            break
        option = current["options"][choice_idx]
        description_parts.append(option["label"].split("——")[0])
        
        if i == len(path) - 1:
            return (
                option.get("mode", WritingMode.INFORMATIONAL),
                option.get("subtype", ""),
                " → ".join(description_parts),
            )
            
        next_key = option.get("next")
        if next_key and next_key in DECISION_TREE:
            current = DECISION_TREE[next_key]
        else:
            break
            
    return WritingMode.INFORMATIONAL, "", " → ".join(description_parts)

def get_mode_profile(mode: WritingMode) -> WritingPrinciples:
    return ALL_PRINCIPLES.get(mode, ALL_PRINCIPLES[WritingMode.INFORMATIONAL])

def get_review_dimensions(mode: WritingMode) -> List[Dict[str, Any]]:
    return REVIEW_DIMENSIONS.get(mode, REVIEW_DIMENSIONS[WritingMode.INFORMATIONAL])

def get_mode_questions(mode: WritingMode) -> List[Dict[str, str]]:
    return MODE_QUESTIONS.get(mode, MODE_QUESTIONS[WritingMode.INFORMATIONAL])

def get_mode_description(mode: WritingMode) -> str:
    principles = ALL_PRINCIPLES.get(mode, ALL_PRINCIPLES[WritingMode.INFORMATIONAL])
    desc = f"【{principles.name}】\n"
    desc += f"{principles.tagline}\n\n"
    desc += "核心原则：\n"
    for i, p in enumerate(principles.principles, 1):
        desc += f"  {i}. {p['name']}：{p['description']}\n"
    desc += f"\n语言边界与底线：\n"
    for line in principles.language_guidelines:
        desc += f"  - {line}\n"
    desc += f"  - 禁用词：{'、'.join(principles.forbidden_patterns[:5])}等\n"
    return desc
