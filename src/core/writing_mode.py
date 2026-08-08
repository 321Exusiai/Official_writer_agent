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
                "description": "活动记录——团日活动、音乐节、招新游园、学术讲座、策划案、活动总结",
                "category": DocumentCategory.ACTIVITY_RECORD,
                "next": "activity_record",
            },
            {
                "label": "工作成果汇报与问题调研",
                "description": "汇报总结——工作总结、调研报告、述职、事故通报、社会实践报告",
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
        "question": "你要写的是哪种行文方向的公文？（对应《党政机关公文处理工作条例》15种法定公文）",
        "options": [
            {
                "label": "上行文——向上级请求指示或汇报工作",
                "description": "请示（请求批准，一文一事）、报告（汇报工作/反映情况，不夹带请示事项）",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "upward",
            },
            {
                "label": "下行文——对下级布置工作、答复或奖惩",
                "description": "通知、通报（表彰/批评/告知）、批复、决定",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "downward",
            },
            {
                "label": "平行文——不相隶属机关商洽工作",
                "description": "函（商洽/询问/答复/求批）、意见（可上行/下行/平行）、议案（政府向同级人大提请）",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "parallel",
            },
            {
                "label": "公布性公文——向社会公布重要或周知事项",
                "description": "公告（国内外重要事项）、通告（特定范围遵守事项）、公报、命令(令)",
                "mode": WritingMode.ADMINISTRATIVE,
                "subtype": "public",
            },
            {
                "label": "会议文书——记载会议情况和议定事项",
                "description": "纪要、决议（会议讨论通过的重大决策）",
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
                "label": "社团招新/文艺汇演/游园会推文——网感拉满，充满青春活力",
                "description": "面向同龄人，需要情绪价值，适合新媒体推文",
                "mode": WritingMode.YOUTH_ENGAGEMENT,
                "subtype": "club_activity",
            },
            {
                "label": "班会/讲座/典礼报道——要素清晰，客观准确",
                "description": "面向全院师生，兼顾可读性与准确性（含校庆、开学典礼等重大校际活动）",
                "mode": WritingMode.INFORMATIONAL,
                "subtype": "campus_activity",
            },
            {
                "label": "研学考察/社会实践报道——立意高远，体现思政引领",
                "description": "需要拔高意义，将个体实践融入国家宏大叙事",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "study_tour",
            },
            {
                "label": "活动策划案——要素齐全，可操作可落地",
                "description": "活动前文书：背景、主题、时间地点、对象、内容、经费预算、注意事项、安全预案",
                "mode": WritingMode.INFORMATIONAL,
                "subtype": "activity_proposal",
            },
            {
                "label": "活动总结——盘点成效，反思不足，提炼改进",
                "description": "活动后正式总结（非推文）：活动概述、成效、存在的不足、改进措施、努力方向",
                "mode": WritingMode.STRATEGIC_NARRATIVE,
                "subtype": "activity_summary",
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
            {
                "label": "社会实践/志愿服务报告——受教育、长才干、作贡献",
                "description": "三下乡、返家乡、社区实践：有问题意识、有材料支撑、有分析深度的应用实践型成果",
                "mode": WritingMode.OBJECTIVE_REPORT,
                "subtype": "practice_report",
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
            "name": "党性原则与正确导向",
            "description": "马克思主义新闻观的根本原则。党性和人民性相统一而非对立，自觉在思想上政治上行动上同党中央保持一致。新闻报道通过对事实的取舍、详略、编排体现价值判断，必须传达正确立场，落实'高举旗帜、引领导向，围绕中心、服务大局'职责使命。",
            "check": "全文读完后，读者是否会被引向正确的价值判断？是否存在导向偏差或立场模糊？",
        },
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
            "description": "行程或工作部署应与国家战略（中国式现代化、新质生产力、共同富裕等）、高校双一流建设形成内在呼应。点明“为什么做这件事”。事实是新闻的生命，战略锚点必须建立在真实之上。",
            "check": "删掉战略锚点句，文章是否就沦为流水账？锚点是否有真实事实支撑？",
        },
    ],
    content_rules={
        "must_write": ["实践与宏观战略的对应关系", "群众/个体的真实获得感", "克服困难的深度逻辑", "正确的价值导向"],
        "must_skip": ["空洞的口号堆砌", "没有事实支撑的拔高", "枯燥的流程流水账", "立场模糊的中立化表述"],
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
            "name": "实事求是与调查研究",
            "description": "调查研究是党的传家宝、做好各项工作的基本功。从群众中来、到群众中去，不唯书不唯上只唯实。采用座谈、走访、问卷、田野调查等方法获取一手资料，“没有调查就没有发言权”。",
            "check": "文中的事实是亲身调研所得，还是二手转述？调研方法是否科学？",
        },
        {
            "name": "事实交叉验证",
            "description": "所有数据、结论必须有可靠来源。单一信源不可作为核心结论的唯一支撑。",
            "check": "文中的核心判断是否有坚实的数据或访谈支撑？",
        },
        {
            "name": "矛盾分析法",
            "description": "运用唯物辩证法，直面核心问题，抓主要矛盾和矛盾的主要方面，呈现“不完美的真实”。深挖现象背后的深层原因。",
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
    tagline="以文辅政、一文一旨、格式规范、语言四要求——严格执行《党政机关公文处理工作条例》与GB/T 9704-2012。",
    principles=[
        {
            "name": "文种选择与行文方向",
            "description": "依据行文目的、发文机关职权和主送机关的行文关系确定文种。上行文用请示/报告/议案；下行文用决定/通知/通报/批复/命令；平行文用函/意见。15种法定公文各有专属用途，不可生造、滥用、错用。易混淆文种必须辨析：请示vs报告（请示求批准、报告只汇报）、通知vs通报（通知告知事项、通报表彰批评）、函vs请示（函用于不相隶属机关）。",
            "check": "文种与行文方向匹配吗？有没有把请示写成报告、把函用于上下级？",
        },
        {
            "name": "一文一旨与行文规则",
            "description": "一篇公文只表达一个主旨、解决一个问题。请示必须一文一事，不得在报告等非请示性公文中夹带请示事项。上行文原则上主送一个上级机关，不抄送下级。不得越级行文（特殊情况需抄送被越过机关）。除上级机关负责人直接交办外，不得以机关名义向上级机关负责人报送公文。",
            "check": "是否一文多事？请示中是否夹带了汇报？是否越级行文？",
        },
        {
            "name": "GB/T 9704-2012格式规范",
            "description": "公文格式18要素分版头、主体、版记三部分。版头：份号/密级/紧急程度/发文机关标志/发文字号/签发人（上行文必标）；主体：标题/主送机关/正文/附件说明/发文机关署名/成文日期/印章/附注；版记：抄送机关/印发机关和印发日期。标题三要素齐全：发文机关+事由+文种（如'XX大学关于XX的通知'）。成文日期用阿拉伯数字（2025年7月27日，不写07月）。引文先引标题后括号注文号（如'根据《XX办法》（XX发〔2025〕5号）'）。数字用法全文统一（GB/T 15835）。",
            "check": "标题三要素齐全吗？日期格式正确吗？引文格式规范吗？数字用法统一吗？",
        },
        {
            "name": "公文语言四要求",
            "description": "准确：一词一句只能有一种解释，不产生歧义，概念清晰、判断精确、推理严谨。简明：开门见山、言简意赅，一针见血指出问题，摒弃大话空话套话。朴实：平易朴实、通俗易懂，忌用华丽辞藻，不宜抒情，平铺直叙讲问题。得体：上行文突出请示性（'妥否，请批示'），下行文强调指令性（'请遵照执行'），平行文注重协商性（'请予函复'）。",
            "check": "每个词是否只有一种解释？有没有歧义？语气与行文关系匹配吗？",
        },
        {
            "name": "表达方式约束",
            "description": "法定公文主要用叙述和说明，少量议论。基本不用描写和抒情。用'直笔'不用'曲笔'——不用比喻、借代、比拟、夸张等修辞手法。公文是工具不是艺术品，'犹如''仿佛''宛如'等文学性比喻词禁止使用。段落层次结构严格遵守（一、（一）、1、（1））。",
            "check": "有没有用比喻拟人？有没有抒情描写？有没有文学性词汇？",
        },
        {
            "name": "指令清晰性",
            "description": "对于通知等下行文，时间、地点、责任人、标准必须没有任何歧义。事项、要求、依据一目了然，不绕弯子。",
            "check": "下级看完后还会产生疑问吗？执行标准是否明确？",
        },
    ],
    content_rules={
        "must_write": ["明确的发文依据/引语", "核心诉求或指令", "具体的时间节点与责任方", "规范的标题三要素", "标准公文结尾用语"],
        "must_skip": ["任何私人感情色彩", "模棱两可的用词", "与主旨无关的背景铺垫", "比喻拟人夸张等修辞", "抒情描写"],
    },
    forbidden_patterns=["大概", "也许", "尽量", "亲自", "网络热梗", "犹如", "仿佛", "宛如", "好似", "犹如一幅", "宛如一首"],
    language_guidelines=[
        "字斟句酌，言简意赅，一词一句只允许一种解释。",
        "使用'特此通知''妥否请批示''请予函复''请遵照执行'等标准公文收尾。",
        "段落层次结构严格遵守（一、（一）、1、（1））。",
        "成文日期用阿拉伯数字，不补零（2025年7月27日，非07月27日）。",
        "引文先引标题全称，后括号注文号。",
        "数字用法全文统一，遵循GB/T 15835。",
    ],
    benchmark_sources=["《党政机关公文处理工作条例》(中办发〔2012〕14号)", "《党政机关公文格式》(GB/T 9704-2012)", "《出版物上数字用法》(GB/T 15835)", "《标点符号用法》(GB/T 15834)"],
)

PRINCIPLES_INFORMATIONAL = WritingPrinciples(
    mode=WritingMode.INFORMATIONAL,
    name="专业新闻通报原则",
    tagline="新闻价值判断、5W1H齐全、倒金字塔结构--还原最纯粹的信息价值。",
    principles=[
        {
            "name": "新闻价值判断",
            "description": "新闻选择的根本标准。用五要素衡量事实的传播价值：时新性（新近发生、内容新鲜）、重要性（影响多数人、利害攸关）、接近性（地理与心理接近）、显著性（人物/地点知名度）、趣味性（人情味与戏剧性）。重要性与时新性是底线，要素越多价值越高。",
            "check": "这件事到底值不值得报？五要素里哪一项最强？如果都不强，是否不该写？",
        },
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
    name="青年共情与社团活力原则 (思想引领与网感并重)",
    tagline="懂年轻人的梗，说人话，抓情绪，但娱乐外壳下必有价值内核--高校新媒体是“大思政”阵地。",
    principles=[
        {
            "name": "思想引领与立德树人",
            "description": "高校共青团新媒体的首要任务是思想政治引领。坚持党性原则，牢牢把握马克思主义新闻观，把党的声音传播到校园。娱乐是外壳，价值是内核，做到“成风化人、凝心聚力”。严格落实“三审三校”机制，守牢政治底线与风险防范。",
            "check": "这篇推文除了好玩，想传递什么价值？思想落点在哪？是否走完了三审三校？",
        },
        {
            "name": "青年话语体系与圈层共情",
            "description": "针对青年“去中心化”“碎片化”“圈层化”特征，用网言网语破圈共情。文字轻盈跳跃，多短句，为现场照片和视频留出视觉空间。用合适的颜文字或内部梗增强表现力，但别用极其抽象的小众烂梗。",
            "check": "这段文字在手机屏幕上阅读会让人窒息吗？是否用了青年听得懂的话语？",
        },
        {
            "name": "政治边界与去爹味",
            "description": "像学长学姐一样平视真诚交流，但严禁强行称兄道弟、过度讨好谄媚（禁称'宝宝们'）。坚守政治边界，不迎合庸俗趣味，不降低格调。",
            "check": "这语气是平视的真诚，还是刻意的装嫩？是否突破了政治底线？",
        },
        {
            "name": "克制情绪，去官腔，去AI味",
            "description": "情绪由具体细节流露，禁止堆砌感叹号。严禁“领导高度重视”、“圆满成功”等官样文章。禁止“总而言之”等AI套话。",
            "check": "有没有爹味、官腔或机器味？",
        },
    ],
    content_rules={
        "must_write": ["现场最鲜活/搞笑/感人的瞬间", "强互动的问句或行动号召", "社团独特的黑话/标识", "价值引领的思想落点"],
        "must_skip": ["领导致辞的冗长总结", "枯燥的流程记录", "无病呻吟的抒情段落", "极其抽象的小众烂梗", "无价值内核的纯娱乐"],
    },
    forbidden_patterns=[
        "领导高度重视", "圆满成功", "取得丰硕成果", "总而言之", "不可否认的是", "充满激情与活力",
        "家人们", "宝宝们", "绝绝子"
    ],
    language_guidelines=[
        "采用对话体，多用'你'和'我们'。",
        "语言自带画面感和BGM感。",
        "用自嘲、幽默或真诚化解严肃。",
        "娱乐外壳下必须有价值内核，破圈但不破底线。"
    ],
    benchmark_sources=["优秀高校社团微信公众号推文", "小红书爆款校园笔记", "B站校园共创内容", "共青团中央新媒体矩阵"],
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
        {"name": "党性原则与导向审查", "weight": 0.25},
        {"name": "事实与微观落点审查", "weight": 0.25},
        {"name": "战略锚点与真实性审查", "weight": 0.20},
        {"name": "语言去AI味审查", "weight": 0.15},
        {"name": "行文逻辑审查", "weight": 0.15},
    ],
    WritingMode.OBJECTIVE_REPORT: [
        {"name": "调查研究方法审查", "weight": 0.15},
        {"name": "交叉验证与事实审查", "weight": 0.30},
        {"name": "矛盾分析与问题导向审查", "weight": 0.25},
        {"name": "对策可行性审查", "weight": 0.20},
        {"name": "客观性表达审查", "weight": 0.10},
    ],
    WritingMode.ADMINISTRATIVE: [
        {"name": "文种选择正确性审查", "weight": 0.15},
        {"name": "GB/T 9704-2012格式规范审查", "weight": 0.20},
        {"name": "一文一旨与行文规则审查", "weight": 0.15},
        {"name": "公文语言四要求审查（准确/简明/朴实/得体）", "weight": 0.20},
        {"name": "表达方式约束审查（直笔不曲/无修辞无抒情）", "weight": 0.15},
        {"name": "指令清晰度审查", "weight": 0.10},
        {"name": "标题三要素与结尾用语审查", "weight": 0.05},
    ],
    WritingMode.INFORMATIONAL: [
        {"name": "新闻价值判断审查", "weight": 0.20},
        {"name": "5W1H要素审查", "weight": 0.30},
        {"name": "倒金字塔结构审查", "weight": 0.25},
        {"name": "客观数据与引语审查", "weight": 0.15},
        {"name": "冗余过滤审查", "weight": 0.10},
    ],
    WritingMode.YOUTH_ENGAGEMENT: [
        {"name": "思想引领与价值落点审查", "weight": 0.25},
        {"name": "边界感与去爹味审查", "weight": 0.25},
        {"name": "网感与情绪价值审查", "weight": 0.25},
        {"name": "视觉留白与排版潜力审查", "weight": 0.15},
        {"name": "互动号召力审查", "weight": 0.10},
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
            "why_ask": "有影响力的通讯，通常能让一件事和更大的背景产生关联。找到这层联系，文章会更有厚度。",
            "hint": "例如：呼应了“数字中国”建设 / 践行了学校“全球视野”的人才培养理念",
        },
        {
            "id": "sn_logic",
            "text": "在推进这项工作的过程中，你们克服了哪些核心矛盾？深层动因是什么？",
            "why_ask": "过程中的波折和转折，往往比结果更值得写。如果有分歧、瓶颈或弯路，反而是文章最有张力的部分。",
            "hint": "如果有过路线分歧、资金缺口或技术瓶颈，把当时怎么破局的写下来。",
        },
        {
            "id": "sn_people",
            "text": "作为亲历者或受众群体，个体感受最深、获得感最强的具体细节是什么？",
            "why_ask": "大背景之外，具体到个人的细节最能打动人。一个瞬间、一句话，往往比宏观概括更真实。",
            "hint": "比如现场某位同学的一句话、某个熬夜奋战的瞬间。",
        },
        {
            "id": "sn_value",
            "text": "在同类实践或兄弟院校/单位的比较中，你们的经验具备哪些独特的可推广价值？",
            "why_ask": "如果能从这次实践中提炼出可复用的做法或机制，文章就不只是记录，而有参考价值。",
            "hint": "如果这次沉淀出了什么可复用的方法或机制，哪怕很小，都值得写。",
        },
        {
            "id": "sn_direction",
            "text": "这篇文章要传达的核心价值判断和舆论导向是什么？读者读完后应被引向什么结论？",
            "why_ask": "新闻报道的取舍详略会自然体现立场。明确这篇文章想让读者带走什么结论，写起来才更有方向。",
            "hint": "例如：引导读者认识到XX政策的必然性 / 增强对XX道路的信心 / 凝聚改革共识",
        },
    ],

    WritingMode.OBJECTIVE_REPORT: [
        {
            "id": "or_problem",
            "text": "本次调研或通报试图揭示的核心现象、症结或事实是什么？",
            "why_ask": "报告的力度来自直面真实问题。试着用尽量客观的语言描述现状。",
            "hint": "例如：XX项目推进迟缓的现状 / XX安全事故的具体经过",
        },
        {
            "id": "or_cause",
            "text": "导致该现象的深层次原因是什么？是否有交叉验证的客观数据或多方走访支撑？",
            "why_ask": "一个结论如果有多个独立来源互相印证，会更有说服力。",
            "hint": "比如：'财务数据显示…'加上'基层反映…'，多个角度互相印证。",
        },
        {
            "id": "or_solution",
            "text": "基于上述事实，有何“政治上可取、政策上可推、操作上可行”的建设性方案？",
            "why_ask": "对策写得越具体，落地越容易。能明确到由谁做、什么时候做、做到什么程度最好。",
            "hint": "比如'由XX部门牵头，每周三联合巡检'，比'加强重视'更具体。",
        },
        {
            "id": "or_method",
            "text": "你用了哪些调查研究方法获取这些事实？样本量、信源类型和调研方式是怎样的？",
            "why_ask": "调研方式直接决定结论的可信度。说明了信息是怎么收集的，结论就更有底气。",
            "hint": "例如：实地走访3个村镇+问卷500份+座谈12场 / 数据来自统计局原始表+审计底稿+当事人访谈",
        },
    ],

    WritingMode.ADMINISTRATIVE: [
        {
            "id": "ad_basis",
            "text": "本次行文的政策依据、上级文件精神或现实迫切需求是什么？",
            "why_ask": "有明确的政策依据或现实需求，公文才站得住。这也是审核的第一步。",
            "hint": "例如：根据《XX条例》第X条规定 / 针对近期校园内频发的XX现象",
        },
        {
            "id": "ad_core",
            "text": "本文的唯一核心诉求（请示）或明确指令（通知）是什么？",
            "why_ask": "一篇公文只解决一件事。试试用一句话把核心诉求讲清楚。",
            "hint": "能写明时间节点、责任部门和资金额度，执行起来会更清晰。",
        },
        {
            "id": "ad_route",
            "text": "主送单位与抄送单位分别是谁？是否涉及跨部门协调？",
            "why_ask": "发给谁、用什么关系行文，决定了措辞的正式程度和语气。确认一下主送和抄送对象。",
            "hint": "主送一般只写一个主管单位；跨级的情况建议先走正常渠道。",
        },
        {
            "id": "ad_doc_type",
            "text": "本文的行文方向是什么？为何选这个文种而非其他（如请示vs报告、通知vs通报）？",
            "why_ask": "文种选对，文章才有效力。请示和报告、通知和通报是最容易混淆的两组，值得先想清楚。",
            "hint": "向上级要钱要批文用“请示”，仅汇报情况用“报告”（不夹带请示事项）；布置工作用“通知”，表彰批评用“通报”。",
        },
    ],

    WritingMode.INFORMATIONAL: [
        {
            "id": "info_5w1h",
            "text": "请简述本次事件的核心要素（时间、地点、人物、起因、经过、结果）？",
            "why_ask": "时间、地点、人物、起因、经过、结果——这六要素是读者判断一条消息是否完整的第一标准。",
            "hint": "注意写清关键人物的职务和事件的确切时间。",
        },
        {
            "id": "info_lead",
            "text": "如果只能用一句话向外界传递该事件的价值（新闻眼），最核心的信息点是什么？",
            "why_ask": "消息的阅读习惯是越重要的越靠前。如果能用一句话点出核心信息，读者会更快被抓住。",
            "hint": "例如不是“我们开了个会”，而是“会上发布了某项颠覆性技术”。",
        },
        {
            "id": "info_quotes",
            "text": "有哪些直接说明问题的客观数据或当事人原话（直接引语）？",
            "why_ask": "当事人的原话往往比作者的转述更有现场感。直接引语也能增加可信度。",
            "hint": "找几个当事人，把他们的原话记下来。",
        },
        {
            "id": "info_value",
            "text": "这件事的新闻价值五要素里，哪一项最强？为什么值得报道？",
            "why_ask": "用新闻价值五要素（时新性/重要性/接近性/显著性/趣味性）衡量一下：这件事最值得被人知道的一点是什么？",
            "hint": "例如：时新性最强（刚发生）+重要性（影响全校） / 显著性（校领导出席）+接近性（本院师生关心）",
        },
        {
            "id": "info_plan",
            "text": "如果是活动策划案：活动背景、主题、时间地点、对象、经费预算、安全预案各是什么？（非策划案可跳过）",
            "why_ask": "策划案审批看的就是要素是否齐全、能否落地。逐项理清后写起来会更顺畅。",
            "hint": "背景点明意义；主题尽量工整；预算细到单项；安全预案里加上应急联络人。",
        },
    ],

    WritingMode.YOUTH_ENGAGEMENT: [
        {
            "id": "ye_vibe",
            "text": "这次活动现场最“燃”、最“治愈”或最欢乐的瞬间是什么？描述一下当时的画面。",
            "why_ask": "读者首先感受到的是氛围。如果能把现场最鲜活的画面还原出来，文章就成功了一半。",
            "hint": "比如：全场合唱破音的瞬间 / 突然天降大雨但大家都在雨中狂舞的画面",
        },
        {
            "id": "ye_identity",
            "text": "你们社团/活动独有的“内部梗”或最能代表你们气质的元素是什么？",
            "why_ask": "一点专属的表达能显出社团的个性。选大家都能get、不用解释太多的那种。",
            "hint": "比如动漫社的特定称呼，或者吉他社常被调侃的某位部长。",
        },
        {
            "id": "ye_interaction",
            "text": "现场同学们参与度最高、反响最热烈的环节是哪个？有没有有趣的突发状况？",
            "why_ask": "现场的突发和小插曲，往往是最真实的记忆点，写出来更有共鸣。",
            "hint": "比如设备突然断电，结果主唱直接清唱引发全场大合唱。",
        },
        {
            "id": "ye_cta",
            "text": "在推文的结尾，你想呼吁大家做什么？",
            "why_ask": "结尾给读者一个明确的行动出口，互动率会明显不一样。",
            "hint": "比如：扫码加群暗号XX / 评论区留下你的感受，抽三个送周边！",
        },
        {
            "id": "ye_value",
            "text": "这篇推文除了好玩，想传递什么价值？如何体现思想落点和育人属性呢？",
            "why_ask": "推文好看之外，如果还能留下一个值得回味的思想落点，内容会更有分量。想想这篇想让人记住什么。",
            "hint": "例如：表面是音乐节，落点是“青春自信与校园文化自信” / 表面是招新，落点是“社团精神传承与成长平台”。",
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
        if choice_idx < 0 or choice_idx >= len(current["options"]):
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

