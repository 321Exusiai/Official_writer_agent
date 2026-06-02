"""

写作模式系统 — 决策树分类 + 四套写作方法论并列



解决原系统的核心偏差：将"新闻通讯五大原则"从全局硬约束

降级为一个可选写作模式，引入党政机关规范、新闻规范、

高校团学规范等多套方法论。



设计依据：

- 《党政机关公文处理工作条例》(中办发〔2012〕14号)

- 《党政机关公文格式》(GB/T 9704-2012)

- 新闻写作核心规范（5W1H + 倒金字塔 + 客观性原则）

- 985/211高校新闻采编规范：

  · 北京大学新闻网投稿须知（消息≤1500字/通讯≤3000字/第三人称叙事）

  · 南京大学NJUNEWS新闻网投稿须知（消息800-1000字/通讯≤3000字/主题清晰要素齐全）

  · 北京师范大学科研大讨论新闻采编规范（消息为主/5W1H结构/300-800字/格式规范）

  · 武汉大学团委来稿须知（≥800字/第三人称/避免"我院""我专业"）

  · 中山大学英文新闻征稿规范（精简篇幅/国际化叙事逻辑/300-500英文字）

  · 华中科技大学征文活动规范（1500-3000字/内容真实/避免空泛议论）

- 其他高校新闻采编规范（郑轻大/肇庆学院/中南财大/武汉科大团委）— 辅助参考

- 校园活动通讯稿写作指南（安康日报校园小记者指南）— 辅助参考

"""



from dataclasses import dataclass, field

from enum import Enum

from typing import List, Dict, Optional, Tuple, Any





class WritingMode(Enum):

    STRATEGIC_NARRATIVE = "strategic_narrative"

    OBJECTIVE_REPORT = "objective_report"

    ADMINISTRATIVE = "administrative"

    INFORMATIONAL = "informational"





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

        "question": "你要写的这篇文章，最核心的目的是什么？",

        "options": [

            {

                "label": "让外界知道、了解、认可我们",

                "description": "对外传播——新闻通稿、媒体报道、活动宣传、品牌推广",

                "category": DocumentCategory.EXTERNAL_COMM,

                "next": "external_comm",

            },

            {

                "label": "让内部运转——布置工作、请示审批、传达通知",

                "description": "内部行政——通知、请示、批复、函、纪要",

                "category": DocumentCategory.INTERNAL_ADMIN,

                "next": "internal_admin",

            },

            {

                "label": "记录一次活动/事件",

                "description": "活动记录——校园活动、社团活动、班级活动、团日活动",

                "category": DocumentCategory.ACTIVITY_RECORD,

                "next": "activity_record",

            },

            {

                "label": "向上级展示成果、汇报工作",

                "description": "汇报总结——工作总结、调研报告、述职报告、整改报告",

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

                "label": "简短精炼——300-800字，快速告知核心事实",

                "description": "适合新闻快讯、媒体通稿、消息发布",

                "mode": WritingMode.INFORMATIONAL,

                "subtype": "news_brief",

            },

            {

                "label": "深度全面——1500-3000字，展现全景",

                "description": "适合研学报道、重大活动通讯、典型人物报道",

                "mode": WritingMode.STRATEGIC_NARRATIVE,

                "subtype": "feature",

            },

            {

                "label": "场景驱动——800-1500字，聚焦一个动人瞬间",

                "description": "适合侧记、特写、人物专访",

                "mode": WritingMode.INFORMATIONAL,

                "subtype": "sidelight",

            },

        ],

    },



    # ── 分支 2：内部行政 ──

    "internal_admin": {

        "question": "你具体要写哪种行政文书？",

        "options": [

            {

                "label": "通知——发布、传达要求下级执行或周知的事项",

                "description": "会议通知、活动通知、任免通知、印发通知",

                "mode": WritingMode.ADMINISTRATIVE,

                "subtype": "notice",

            },

            {

                "label": "请示/批复——向上级请求指示或答复下级请示",

                "description": "经费请示、项目请示、人事请示、批复",

                "mode": WritingMode.ADMINISTRATIVE,

                "subtype": "request_reply",

            },

            {

                "label": "函——与不相隶属机关商洽工作、询问答复",

                "description": "商洽函、询问函、答复函、邀请函",

                "mode": WritingMode.ADMINISTRATIVE,

                "subtype": "letter",

            },

            {

                "label": "会议纪要——记载会议主要情况和议定事项",

                "description": "办公会纪要、专题会纪要、座谈会纪要",

                "mode": WritingMode.INFORMATIONAL,

                "subtype": "minutes",

            },

            {

                "label": "通报——表彰先进、批评错误、传达重要精神",

                "description": "表彰通报、批评通报、情况通报",

                "mode": WritingMode.OBJECTIVE_REPORT,

                "subtype": "bulletin_formal",

            },

        ],

    },



    # ── 分支 3：活动记录 ──

    "activity_record": {

        "question": "这次活动的性质和层级是？",

        "options": [

            {

                "label": "班级/团支部活动——班会、团日、志愿服务",

                "description": "面向同学、支部成员，语言生动活泼但不过分随意",

                "mode": WritingMode.INFORMATIONAL,

                "subtype": "class_activity",

            },

            {

                "label": "院系/社团活动——讲座、比赛、文化节",

                "description": "面向全院师生或社团成员，兼顾正式性与可读性",

                "mode": WritingMode.INFORMATIONAL,

                "subtype": "campus_activity",

            },

            {

                "label": "研学/考察/社会实践——校外行程、多站参访",

                "description": "需要拔高意义、体现顶层设计",

                "mode": WritingMode.STRATEGIC_NARRATIVE,

                "subtype": "study_tour",

            },

            {

                "label": "校际/重大活动——校庆、开学典礼、大型赛事",

                "description": "需要兼具新闻价值和战略高度",

                "mode": WritingMode.STRATEGIC_NARRATIVE,

                "subtype": "major_event",

            },

        ],

    },



    # ── 分支 4：汇报总结 ──

    "report_summary": {

        "question": "你汇报/总结的核心内容是什么？",

        "options": [

            {

                "label": "阶段性工作总结——做了哪些事、取得了什么成效",

                "description": "学期总结、年度总结、专项工作总结",

                "mode": WritingMode.STRATEGIC_NARRATIVE,

                "subtype": "work_summary",

            },

            {

                "label": "调研/考察报告——发现了什么问题、提出了什么建议",

                "description": "深度调研、田野调查、专项考察",

                "mode": WritingMode.OBJECTIVE_REPORT,

                "subtype": "research_report",

            },

            {

                "label": "事故/问题通报——发生了什么、原因是什么、怎么处理",

                "description": "安全事故通报、违规违纪通报、审计整改报告",

                "mode": WritingMode.OBJECTIVE_REPORT,

                "subtype": "incident_report",

            },

            {

                "label": "述职报告——个人或部门年度履职情况",

                "description": "干部述职、部门述职",

                "mode": WritingMode.ADMINISTRATIVE,

                "subtype": "duty_report",

            },

        ],

    },

}





# ═══════════════════════════════════════════════════════════════

# 四套写作原则 — 并列存在，按模式激活

# ═══════════════════════════════════════════════════════════════



@dataclass

class WritingPrinciples:

    """一套写作原则"""

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

    name="战略叙事原则",

    tagline='从"流程记录"到"战略叙事"——回答“这证明了我们是谁，我们正走向何方”',

    principles=[

        {

            "name": "主体性原则",

            "description": '镜头始终对准"我们"。每句话的主语或叙述重心调整为"我们"。落笔前自问：这句话是在讲对方，还是在讲我们？',

            "check": "如果换成别的单位署名，这段话还能用吗？",

        },

        {

            "name": "赋能性原则",

            "description": '每段行程必须回扣培养理念或战略部署。为每个板块设置"战略锚点"——点明"为什么是这里"。',

            "check": "这段行程如果删掉战略锚点句，还能读得通吗？",

        },

        {

            "name": "借势性原则",

            "description": "以外部权威为组织背书。记录外部权威观点后，主动建立与自身的关联。",

            "check": "是'借外部之锤，敲自家之钟'，还是仅仅记录了外部言行？",

        },

        {

            "name": "成长性原则",

            "description": "用真实感言、具体体悟作为“证据”，让读者自己得出结论。严禁“大家纷纷表示”“深刻感受到”等空泛套话。",

            "check": "如果这段感言去掉后不影响叙事，是否应该删除？",

        },

        {

            "name": "战略性原则",

            "description": "全文服务于组织的长期发展。结尾含蓄但坚定地传递“我们有方向、有资源、有行动力、有成果”。",

            "check": "全文读完后，读者是否会产生'应该继续支持'的印象？",

        },

    ],

    content_rules={

        "must_write": [

            "每站与培养方案/工作部署的对应关系",

            "具体收获、真实感言",

            "大师观点与组织理念的契合",

            "合作方的高规格",

            "前期筹备、带队指导",

        ],

        "must_skip": [

            "对方流程、项目细节",

            "几点几分、乘车入住",

            "具体算法、模型名称",

            '"大家纷纷表示收获很大"等空泛表态',

        ],

    },

    forbidden_patterns=[

        "大家纷纷表示", "深刻感受到", "一致认为", "受益匪浅",

        "收获很大", "深受鼓舞", "感触良多",

        "乘车", "入住", "就餐", "出发", "抵达", "集合", "签到",

        "圆满成功", "顺利结束", "满载而归",

    ],

    language_guidelines=[

        "陈述性、写实性，而非描绘性、虚拟性",

        "多使用客观有力的动词，少用口语化表述",

        "用概括性语言替代过程性描述",

        "适当使用时代感词汇（赋能、淬炼、共振、锚定），但克制不堆砌",

        "段落间逻辑紧密，以过渡句串联，形成递进",

    ],

    benchmark_sources=[
        "人民日报通讯（蜀道新歌、看准了就抓紧干）",
        "新华社深度报道",
        "光明日报调研报告（塔里木沙漠）",
        "北京大学新闻网投稿须知（通讯类≤3000字/第三人称叙事/新闻要素齐全）",
        "南京大学NJUNEWS新闻网投稿须知（通讯类≤3000字/主题清晰/要素齐全）",
        "华中科技大学征文活动规范（1500-3000字/内容真实/避免空泛议论）",
    ],

)



PRINCIPLES_OBJECTIVE_REPORT = WritingPrinciples(

    mode=WritingMode.OBJECTIVE_REPORT,

    name="客观陈述原则",

    tagline="实事求是、准确规范——让事实自己说话，不渲染、不借势、不拔高",

    principles=[

        {

            "name": "事实准确性",

            "description": "所有时间、地点、人名、数据、引用必须经过核实。引用数据需标注来源和统计口径。不确定的信息宁可删除也不猜测。",

            "check": "文中的每一个数字、每一个名字、每一个日期，都有原始出处吗？",

            "source": "《党政机关公文处理工作条例》第五条'实事求是、准确规范'；新闻真实性原则",

        },

        {

            "name": "逻辑一致性",

            "description": "前后数据不矛盾，结论与论据一一对应，因果关系清晰可验证。不允许'因为A所以B'的跳跃式推理。",

            "check": "如果读者逐段核对，有没有发现前后矛盾的地方？",

        },

        {

            "name": "表述客观性",

            "description": "不评价、不拔高、不借势。少用副词和形容词。严禁'第一、首个、重磅、突破性、国际领先'等绝对化表述。",

            "check": "删掉所有形容词和副词后，文章的核心信息是否仍然完整？",

            "source": "郑轻大新闻采编规范：'客观陈述事实，少用副词、形容词'",

        },

        {

            "name": "问题导向性",

            "description": "调研报告以问题开篇，事故通报以事实开篇。不回避矛盾，呈现'不完美的真实'。",

            "check": "文章是否直面了核心问题，而非绕着问题走？",

        },

        {

            "name": "结论可验证性",

            "description": "所有结论必须有数据或案例支撑。对策建议必须可操作、可验证、可追溯。",

            "check": "如果我是一个完全不了解情况的人，看完这篇文章能判断结论是否可信吗？",

        },

    ],

    content_rules={

        "must_write": [

            "核心事实和数据（标注来源和统计口径）",

            "问题的完整呈现（不回避矛盾）",

            "多方信源交叉验证",

            "可操作的对策建议",

            "必要的背景信息（组织背景、行业背景）",

        ],

        "must_skip": [

            "形容词堆砌和主观评价",

            "「大家纷纷表示」「一致认为」等模糊表述",

            "没有数据支撑的结论",

            "与核心问题无关的背景铺垫",

            "对外部权威的借势和攀附",

        ],

    },

    forbidden_patterns=[

        "第一", "首个", "重磅", "突破性", "国际领先", "填补空白",

        "大家纷纷表示", "一致认为", "深刻感受到",

        "高位推动", "高度重视", "精心组织", "周密部署",

        "为了贯彻落实", "在……正确领导下",

    ],

    language_guidelines=[

        "语言客观中立，不使用感情色彩强烈的词汇",

        "数据引用格式：'据XX部门统计''XX报告显示'",

        "使用直接引语时，保持原话完整，不做转述加工",

        "段落简短，一个事实一段",

        "使用'据悉''据了解''数据显示'等中性过渡词",

        "避免'圆满完成''顺利实现'等预判性表述",

    ],

    benchmark_sources=[
        "新华社消息（青海绿电——484字讲清一个复杂事件）",
        "国务院事故调查报告",
        "审计报告标准格式",
        "北京师范大学科研大讨论新闻采编规范（消息为主/5W1H结构/300-800字/格式规范）",
        "郑轻大新闻采编规范",
    ],

)



PRINCIPLES_ADMINISTRATIVE = WritingPrinciples(

    mode=WritingMode.ADMINISTRATIVE,

    name="行政行文原则",

    tagline="格式规范、用词准确、简洁高效——公文是组织运转的'操作系统'",

    principles=[

        {

            "name": "格式规范性",

            "description": "严格遵循《党政机关公文格式》(GB/T 9704-2012)。标题=发文机关+事由+文种。版头、主体、版记要素齐全。",

            "check": "标题三要素齐全吗？发文字号正确吗？主送机关使用全称或规范化简称吗？",

            "source": "《党政机关公文处理工作条例》第三章第九条",

        },

        {

            "name": "用词准确性",

            "description": "使用规范公文用语。'妥否，请批示''经研究决定''现就有关事项通知如下'等格式化用语必须准确。不使用口语、俚语、网络用语。",

            "check": "如果用公文格式化用语字典逐条核对，有没有用错的地方？",

        },

        {

            "name": "合规性",

            "description": "上行文标注签发人。请示一文一事。报告中不夹带请示事项。函的用语体现平等协商而非上下级命令。",

            "check": "行文方向（上行/下行/平行）和文种选择正确吗？",

            "source": "《党政机关公文处理工作条例》第四章行文规则",

        },

        {

            "name": "简洁性",

            "description": "一事一文，不绕弯子。能用一句话说清的不用一段话。删除所有与核心事项无关的修饰和铺垫。",

            "check": "如果把每句话删到只剩主谓宾，核心信息还在吗？",

        },

        {

            "name": "无冗余性",

            "description": "不重复表述。同一信息不在标题、导语、正文中反复出现。不使用'为了贯彻落实……''在……正确领导下'等程式化套话开头。",

            "check": "有没有哪句话去掉后完全不影响理解？如果有，删除。",

            "source": "《党政机关公文处理工作条例》第五条'精简高效'",

        },

    ],

    content_rules={

        "must_write": [

            "发文机关名称（全称或规范化简称）",

            "事由（简明扼要概括核心事项）",

            "文种（通知/请示/批复/函/纪要等）",

            "主送机关（全称或规范化简称）",

            "正文：依据→事项→要求（三段式）",

            "发文机关署名+成文日期+印章",

        ],

        "must_skip": [

            "任何形式的渲染和拔高",

            "形容词和程度副词",

            "背景故事和案例（除非直接相关）",

            "外部权威引用（行政公文不需要借势）",

            "「在……正确领导下」「为了贯彻落实……」等套话",

        ],

    },

    forbidden_patterns=[

        "在……正确领导下", "为了贯彻落实", "深入学习贯彻",

        "高度重视", "亲自", "指示", "重要讲话",

        "隆重", "热烈", "圆满", "顺利",

        "大家纷纷表示", "一致认为",

    ],

    language_guidelines=[

        "使用3号仿宋体字（GB/T 9704-2012标准）",

        "标题：发文机关名称+事由+文种（如'XX学院关于举办2026年毕业典礼的通知'）",

        "正文三段式：依据→事项→要求",

        "通知结尾：'特此通知'",

        "请示结尾：'妥否，请批示'",

        "批复结尾：'此复'",

        "函的结尾：'特此函告''请予支持为盼'",

        "会议纪要：分条列出议定事项，使用'会议指出''会议强调''会议要求'",

    ],

    benchmark_sources=[

        "《党政机关公文处理工作条例》(中办发〔2012〕14号)",

        "《党政机关公文格式》(GB/T 9704-2012)",

        "国务院公文格式范例",

    ],

)



PRINCIPLES_INFORMATIONAL = WritingPrinciples(

    mode=WritingMode.INFORMATIONAL,

    name="信息传达原则",

    tagline="完整、清晰、有重点——让读者在30秒内抓住核心信息",

    principles=[

        {

            "name": "信息完整性",

            "description": "5W1H齐全（何时、何地、何人、何事、何故、如何）。导语一段讲清核心事实，不遗漏关键信息。",

            "check": "读者看完第一段，能回答'谁在什么时间什么地点做了什么'吗？",

            "source": "新闻写作五要素规范",

        },

        {

            "name": "结构清晰性",

            "description": "消息用倒金字塔结构（最重要→次重要→背景）。简报用条目式。活动稿按逻辑顺序（非时间顺序）排列。",

            "check": "如果只保留前两段，文章的核心信息还在吗？",

            "source": "倒金字塔结构（占美国新闻总量80%）",

        },

        {

            "name": "重点突出性",

            "description": "最重要的信息放在最前面。一个段落只讲一件事。标题直接点出最有新闻价值的信息。",

            "check": "标题能让读者3秒内判断这篇文章值不值得读吗？",

            "source": "肇庆学院新闻写作基本规范",

        },

        {

            "name": "不渲染不拔高",

            "description": "事实本身足够有力，不需要加'圆满''顺利''成功'。不用'大家纷纷表示'等模糊表述。语言不含糊、不评价。",

            "check": "去掉所有评价性词语后，文章还剩下什么？",

            "source": "郑轻大新闻采编规范：'语言不含糊、不评价'",

        },

        {

            "name": "受众适配性",

            "description": "对内稿件用'我院/我校'，对外稿件用全称。团学稿件用'支部成员'替代'同学'。人物出场用'职务称谓+姓名'。",

            "check": "这篇文章的目标受众会觉得自己被'看见'了吗？",

            "source": "武汉科大团委投稿规范；肇庆学院新闻写作基本规范",

        },

    ],

    content_rules={

        "must_write": [

            "5W1H核心信息",

            "最重要的1-2个亮点或数据",

            "1-2段直接引语（如有）",

            "必要的背景信息（1-2句即可）",

            "署名（通讯员/作者/摄影）",

        ],

        "must_skip": [

            "形容词堆砌和主观评价",

            "「大家纷纷表示」「一致认为」等模糊表述",

            "几点几分、乘车入住等流水账",

            "与活动主题无关的背景铺垫",

            "对外部权威的借势（信息稿不需要借势）",

        ],

    },

    forbidden_patterns=[

        "大家纷纷表示", "一致认为", "深刻感受到",

        "圆满成功", "顺利结束", "满载而归", "落下帷幕",

        "首先……然后……最后……", "上午……下午……",

        "第一", "首个", "重磅", "突破性",

        "为了贯彻落实", "在……正确领导下",

    ],

    language_guidelines=[

        "消息：倒金字塔结构，导语不超过50字",

        "简报：条目式/分段式，标题规范（发文机关+事由+简报）",

        "校园活动稿：标题控制在15-25字，段落简短",

        "团学稿件：使用'支部成员'替代'同学'，使用'团支书'替代'班长'",

        "人物出场：首次'职务+姓名'，再次仅用姓名",

        "不使用'同志''老师''同学'等口语化称谓",

        "段落间不使用'首先、接着、然后、随后'等连接词",

        "结尾不写'本次活动圆满结束''与会人员合影留念'",

    ],

    benchmark_sources=[
        "新华社消息写作规范",
        "北京大学新闻网投稿须知（消息类≤1500字/第三人称叙事/叙述准确客观）",
        "南京大学NJUNEWS新闻网投稿须知（消息类800-1000字/主题清晰/新闻要素齐全）",
        '武汉大学团委来稿须知（≥800字/第三人称/避免"我院""我专业"）',
        "北京师范大学科研大讨论新闻采编规范（消息为主/5W1H/300-800字）",
        "中山大学英文新闻征稿规范（精简篇幅/国际化叙事逻辑）",
        "肇庆学院新闻写作基本规范",
        "郑轻大新闻采编规范",
        "武汉科大团委先锋在线投稿规范",
        "中南财经政法大学团委投稿须知",
        "校园小记者指南（安康日报）",
    ],

)



ALL_PRINCIPLES: Dict[WritingMode, WritingPrinciples] = {

    WritingMode.STRATEGIC_NARRATIVE: PRINCIPLES_STRATEGIC_NARRATIVE,

    WritingMode.OBJECTIVE_REPORT: PRINCIPLES_OBJECTIVE_REPORT,

    WritingMode.ADMINISTRATIVE: PRINCIPLES_ADMINISTRATIVE,

    WritingMode.INFORMATIONAL: PRINCIPLES_INFORMATIONAL,

}





# ═══════════════════════════════════════════════════════════════

# 各模式的审查维度 — 替代原来的单一五轮审查

# ═══════════════════════════════════════════════════════════════



REVIEW_DIMENSIONS: Dict[WritingMode, List[Dict[str, Any]]] = {

    WritingMode.STRATEGIC_NARRATIVE: [

        {

            "name": "主体性审查",

            "description": "检查每段的核心主语是否为'我们'",

            "weight": 0.20,

            "check_items": [

                "每段的第一句话，主语是谁？",

                "如果换成别的单位署名，这段话还能用吗？",

                "有没有'某单位安排了……'这样的被动叙事？",

            ],

        },

        {

            "name": "赋能性审查",

            "description": "检查每个行程板块是否点明了'为什么是这里'",

            "weight": 0.20,

            "check_items": [

                "每个行程板块是否包含战略锚点句？",

                "行程之间是否有递进逻辑？",

                "是否有段落读起来像独立的游记？",

            ],

        },

        {

            "name": "借势性审查",

            "description": "检查每个外部权威是否与'我们'建立了关联",

            "weight": 0.15,

            "check_items": [

                "外部权威观点后是否有与我方理念的呼应？",

                "重大精神是否呼应了培养目标？",

            ],

        },

        {

            "name": "成长性/瘦身审查",

            "description": "删除空话套话和过程性描述",

            "weight": 0.20,

            "check_items": [

                "有没有'大家纷纷表示'等空话？",

                "有没有过程性流水账？",

                "如果一段感言去掉后不影响叙事，是否应该删除？",

            ],

        },

        {

            "name": "战略性审查",

            "description": "检查全文是否服务于组织的长期发展",

            "weight": 0.15,

            "check_items": [

                "结尾是否传递了'有方向、有资源、有成果'的信号？",

                "标题是否有新闻性和辨识度？",

            ],

        },

        {

            "name": "事实准确性审查",

            "description": "基础事实核查（所有模式通用）",

            "weight": 0.10,

            "check_items": [

                "人名、职务、机构名称是否准确？",

                "日期、数据是否有原始出处？",

                "引语是否真实可溯？",

            ],

        },

    ],



    WritingMode.OBJECTIVE_REPORT: [

        {

            "name": "事实准确性审查",

            "description": "所有事实必须可验证",

            "weight": 0.30,

            "check_items": [

                "每一个数字、名字、日期都有原始出处吗？",

                "数据来源是否标注？统计口径是否一致？",

                "多方信源是否交叉验证？",

            ],

        },

        {

            "name": "逻辑一致性审查",

            "description": "前后数据不矛盾，结论与论据对应",

            "weight": 0.25,

            "check_items": [

                "前后数据是否矛盾？",

                "结论是否有数据和案例支撑？",

                "因果关系是否清晰可验证？",

            ],

        },

        {

            "name": "表述客观性审查",

            "description": "不评价、不拔高、不借势",

            "weight": 0.20,

            "check_items": [

                "有没有'第一''首个''突破性'等绝对化表述？",

                "有没有形容词替代事实的段落？",

                "有没有对外部权威的借势和攀附？",

            ],

        },

        {

            "name": "问题导向性审查",

            "description": "是否直面核心问题",

            "weight": 0.15,

            "check_items": [

                "文章是否以问题开篇？",

                "有没有回避或弱化核心矛盾？",

                "建议是否可操作、可验证？",

            ],

        },

        {

            "name": "格式规范性审查",

            "description": "公文格式是否规范",

            "weight": 0.10,

            "check_items": [

                "标题是否规范？",

                "成文日期、署名、印章是否齐全？",

                "数字用法是否统一（GB/T 15835）？",

            ],

        },

    ],



    WritingMode.ADMINISTRATIVE: [

        {

            "name": "格式规范性审查",

            "description": "严格对照GB/T 9704-2012",

            "weight": 0.30,

            "check_items": [

                "标题三要素（发文机关+事由+文种）齐全？",

                "发文字号正确（机关代字+年份+顺序号）？",

                "主送机关使用全称或规范化简称？",

                "上行文是否标注签发人？",

                "成文日期、署名、印章是否齐全？",

            ],

        },

        {

            "name": "用词准确性审查",

            "description": "格式化用语是否规范",

            "weight": 0.25,

            "check_items": [

                "文种选择是否正确（请示/通知/批复/函/纪要）？",

                "结尾用语是否规范（'妥否，请批示''此复'等）？",

                "是否有口语、俚语、网络用语？",

                "称谓是否规范（职务+姓名）？",

            ],

        },

        {

            "name": "合规性审查",

            "description": "行文规则是否遵守",

            "weight": 0.20,

            "check_items": [

                "请示是否一文一事？",

                "报告中是否夹带请示事项？",

                "函的用语是否体现平等协商？",

                "越级行文是否必要且合规？",

            ],

        },

        {

            "name": "简洁性审查",

            "description": "删除冗余",

            "weight": 0.15,

            "check_items": [

                "是否一事一文，不绕弯子？",

                "有没有可以删除的修饰和铺垫？",

                "有没有'为了贯彻落实……'等套话开头？",

                "有没有重复表述？",

            ],

        },

        {

            "name": "事实准确性审查",

            "description": "基础事实核查",

            "weight": 0.10,

            "check_items": [

                "人名、职务、机构名称、日期是否准确？",

                "引用的政策文件名称和文号是否正确？",

                "数字是否前后一致？",

            ],

        },

    ],



    WritingMode.INFORMATIONAL: [

        {

            "name": "信息完整性审查",

            "description": "5W1H是否齐全",

            "weight": 0.25,

            "check_items": [

                "导语是否包含5W1H？",

                "读者看完第一段能否回答核心事实？",

                "有没有遗漏关键信息？",

            ],

        },

        {

            "name": "结构清晰性审查",

            "description": "是否使用了合适的结构",

            "weight": 0.20,

            "check_items": [

                "消息是否使用倒金字塔结构？",

                "简报是否条目清晰？",

                "如果只保留前两段，核心信息还在吗？",

            ],

        },

        {

            "name": "重点突出性审查",

            "description": "最重要的信息是否在最前面",

            "weight": 0.20,

            "check_items": [

                "标题是否在3秒内让读者知道文章价值？",

                "是否有与核心信息无关的段落？",

                "关键数据是否突出呈现？",

            ],

        },

        {

            "name": "不渲染不拔高审查",

            "description": "删除评价性语言",

            "weight": 0.15,

            "check_items": [

                "有没有'圆满''顺利''成功'等评价词？",

                "有没有'大家纷纷表示'等模糊表述？",

                "有没有借势和攀附？",

                "语言是否客观不含糊？",

            ],

        },

        {

            "name": "受众适配性审查",

            "description": "语言和称谓是否适配目标受众",

            "weight": 0.10,

            "check_items": [

                "对内/对外称谓是否正确？",

                "团学稿件用语是否规范（支部/成员）？",

                "人物出场格式是否正确（职务+姓名）？",

            ],

        },

        {

            "name": "事实准确性审查",

            "description": "基础事实核查",

            "weight": 0.10,

            "check_items": [

                "人名、职务、机构名称、日期是否准确？",

                "引语是否真实可溯？",

                "数字是否前后一致？",

            ],

        },

    ],

}





# ═══════════════════════════════════════════════════════════════

# 各模式的问卷问题集 — 替代原来一刀切的8问

# ═══════════════════════════════════════════════════════════════



MODE_QUESTIONS: Dict[WritingMode, List[Dict[str, str]]] = {

    WritingMode.STRATEGIC_NARRATIVE: [

        {

            "id": "sn_purpose",

            "text": "这篇文章的核心目的是什么？你要让读者读完以后，产生什么想法、做出什么行动？",

            "why_ask": "没有目的的文章就是流水账。目的决定了选材、结构、语气。",

            "hint": "例如：让领导觉得这次投入值了 / 让同行觉得我们专业 / 让团队成员觉得被看见了",

        },

        {

            "id": "sn_audience",

            "text": "这篇文章的第一读者是谁？请具体到人（如'分管学生工作的副校长张某某'），而不是笼统的'领导'。",

            "why_ask": "为具体的人写作，语言才会精准。",

            "hint": "想一想：这篇文章最终会被谁读到？谁会根据这篇文章做决策？",

        },

        {

            "id": "sn_deep_meaning",

            "text": "这件事的'深层含义'是什么？不是'我们做了什么'，而是'这件事证明了什么'？",

            "why_ask": "新闻通讯的本质不是告知'发生了什么'，而是回答'这证明了我们是谁'。",

            "hint": "例如：不是'我们去北大交流了'，而是'我们的培养质量获得了顶尖平台的认可'",

        },

        {

            "id": "sn_strategic_anchor",

            "text": "这次活动与你所在组织的长期战略有什么关联？请具体到某一条。",

            "why_ask": "脱离了组织战略的活动报道没有'根'。",

            "hint": "例如：对应培养方案中'全球视野'模块 / 呼应年度工作要点第X条",

        },

        {

            "id": "sn_opportunity",

            "text": "这篇文章有没有可能成为某个'更大叙事'的一部分？",

            "why_ask": "最好的公文不是孤立的文章，而是更大叙事的注脚。",

            "hint": "例如：教育部正在推的某项计划、媒体正在关注的热点话题",

        },

        {

            "id": "sn_materials",

            "text": "你手上有哪些'不可替代'的素材？（真实感言、独家数据、关键照片、权威评价）",

            "why_ask": "真实感言>空泛表态，具体数据>形容词堆砌。",

            "hint": "有没有哪位同学说了让你印象深刻的话？有没有哪个数据能说明问题？",

        },

        {

            "id": "sn_differentiator",

            "text": "如果另一个单位做了完全相同的活动——你的文章凭什么跟别人不一样？",

            "why_ask": "这个问题逼迫你找到独特的视角。",

            "hint": "不是因为你们做了这件事，而是因为你们做这件事的方式、结果、意义跟别人不同",

        },

    ],



    WritingMode.OBJECTIVE_REPORT: [

        {

            "id": "or_subject",

            "text": "你要报告/通报/调研的核心事项是什么？请用一句话概括。",

            "why_ask": "客观报告的核心是'就事论事'，先明确要说什么事。",

            "hint": "例如：XX实验室安全事故的原因和责任认定 / XX地区乡村振兴的现状与问题",

        },

        {

            "id": "or_data_sources",

            "text": "你的核心数据和事实来自哪些渠道？是否有至少两个独立来源可以交叉验证？",

            "why_ask": "客观报告的生命线是数据可验证。单一来源的信息不可作为结论依据。",

            "hint": "例如：官方统计数据+实地调研访谈 / 财务系统数据+第三方审计",

        },

        {

            "id": "or_audience",

            "text": "这份报告的读者是谁？他们最需要从中获得什么信息？",

            "why_ask": "给领导看的事故报告和给公众看的调查报告，侧重点完全不同。",

            "hint": "例如：上级领导关心责任认定和处理方案 / 公众关心事实真相和安全保障",

        },

        {

            "id": "or_core_findings",

            "text": "你的核心发现或结论是什么？有哪些证据可以支撑？",

            "why_ask": "客观报告不允许'我觉得'——每个结论都必须有证据。",

            "hint": "列出3-5个核心发现，每个后面标注支撑它的证据类型",

        },

        {

            "id": "or_controversy",

            "text": "这件事有没有争议或不同的解读角度？你是否已经了解了各方观点？",

            "why_ask": "只呈现单方面信息不是客观报告。好的报告呈现复杂性，不回避矛盾。",

            "hint": "例如：事故报告中既要写直接原因，也要写管理层面的深层原因",

        },

        {

            "id": "or_recommendations",

            "text": "如果有对策建议，它们是否具体、可操作、可验证？",

            "why_ask": "'加强管理''提高认识'是空话。'每周检查一次消防设备并登记'才是建议。",

            "hint": "用SMART原则检查：Specific / Measurable / Achievable / Relevant / Time-bound",

        },

    ],



    WritingMode.ADMINISTRATIVE: [

        {

            "id": "ad_doc_type",

            "text": "你要写的是哪种行政文书？（通知/请示/批复/函/纪要/通报）",

            "why_ask": "文种错了，后面的格式、用语、行文方向全都会错。",

            "hint": "通知用于'要别人做'，请示用于'请别人批'，函用于'跟平级商量'",

        },

        {

            "id": "ad_direction",

            "text": "行文方向是什么？（上行文/下行文/平行文）",

            "why_ask": "上行文要标注签发人、语气恭敬；下行文可以使用要求性语气；平行文体现协商。",

            "hint": "发给上级=上行文，发给下级=下行文，发给不相隶属单位=平行文（用函）",

        },

        {

            "id": "ad_recipient",

            "text": "主送机关的全称或规范化简称是什么？",

            "why_ask": "主送机关错了，公文就送错了地方。",

            "hint": "例如：'校团委'而非'团委'；'各学院'而非'各院'",

        },

        {

            "id": "ad_core_item",

            "text": "这份公文要处理的核心事项是什么？请用一句话概括。",

            "why_ask": "行政公文的核心是一事一文，先明确要办什么事。",

            "hint": "例如：申请追加活动经费 / 通知各学院提交年度总结 / 商洽联合举办活动",

        },

        {

            "id": "ad_basis",

            "text": "这份公文的依据是什么？（上级文件/会议决定/领导批示/惯例）",

            "why_ask": "行政公文必须有依据，不能凭空发文。",

            "hint": "例如：根据《XX管理办法》第X条 / 经XX会议研究决定 / 应XX单位来函要求",

        },

        {

            "id": "ad_requirements",

            "text": "你要求收文方做什么？有没有明确的时间节点和执行标准？",

            "why_ask": "模糊的要求=无效的公文。'请于X月X日前将材料报送至XX'远比'请尽快完成'有效。",

            "hint": "检查：时间、地点、责任人、完成标准——都写清楚了吗？",

        },

    ],



    WritingMode.INFORMATIONAL: [

        {

            "id": "info_5w1h",

            "text": "请用一句话说清5W1H：什么时间、什么地点、谁、做了什么、为什么、怎么做的？",

            "why_ask": "把5W1H用一句话说清楚，后面写起来就不容易跑偏了。别着急，慢慢组织语言。",

            "hint": "例如：X月X日，XX学院在XX举办了XX活动，旨在XX，共有XX人参加",

        },

        {

            "id": "info_highlight",

            "text": "这件事最大的亮点或最有新闻价值的信息是什么？",

            "why_ask": "读者只关心'这件事跟我有什么关系/有什么特别的'。找不到亮点=没有新闻价值。",

            "hint": "想想：如果你是读者，你会被哪个细节吸引？",

        },

        {

            "id": "info_audience",

            "text": "这篇文章发布在哪里？读者是谁？（校园网/公众号/团委网站/班级群/对外媒体）",

            "why_ask": "发在班级群的活动稿和发在校团委网站的稿子，语言和格式完全不同。",

            "hint": "校园网→正式规范；公众号→生动可读；班级群→亲切自然",

        },

        {

            "id": "info_structure",

            "text": "你打算用什么结构？（倒金字塔/条目式/时间顺序）",

            "why_ask": "消息用倒金字塔，简报用条目式，活动稿用逻辑顺序——结构错了，读者找不到重点。",

            "hint": "如果读者只看前两段就关掉，他能知道最重要的信息吗？",

        },

        {

            "id": "info_quotes",

            "text": "有没有1-2句可以直接引用的原话？（参与者/组织者/嘉宾的真实表述）",

            "why_ask": "直接引语让文章'活'起来。没有引语的信息稿像没有盐的菜。",

            "hint": "去采访1-2个人，问'这次活动让你印象最深的是什么'",

        },

        {

            "id": "info_visuals",

            "text": "有没有配图？图片能独立讲述一个微型故事吗？",

            "why_ask": "好的新闻稿，图片本身就是独立叙事者。",

            "hint": "检查：照片中有交流感吗？有组织标识露出吗？有全景和特写交替吗？",

        },

    ],

}





# ═══════════════════════════════════════════════════════════════

# 决策树导航函数

# ═══════════════════════════════════════════════════════════════



def navigate_tree(path: List[int]) -> Tuple[WritingMode, str, str]:

    """

    根据用户的选择路径，返回对应的写作模式



    Args:

        path: 用户在决策树每层的选择索引列表 [level1_choice, level2_choice]



    Returns:

        (WritingMode, subtype, full_path_description)

    """

    current = DECISION_TREE["root"]

    description_parts = []



    for i, choice_idx in enumerate(path):

        option = current["options"][choice_idx]

        description_parts.append(option["label"])



        if i == len(path) - 1:

            return (

                option["mode"],

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

    """获取指定模式的写作原则"""

    return ALL_PRINCIPLES[mode]





def get_review_dimensions(mode: WritingMode) -> List[Dict[str, Any]]:

    """获取指定模式的审查维度"""

    return REVIEW_DIMENSIONS.get(mode, REVIEW_DIMENSIONS[WritingMode.INFORMATIONAL])





def get_mode_questions(mode: WritingMode) -> List[Dict[str, str]]:

    """获取指定模式的问卷问题"""

    return MODE_QUESTIONS.get(mode, MODE_QUESTIONS[WritingMode.INFORMATIONAL])





def get_mode_description(mode: WritingMode) -> str:

    """获取模式的完整描述"""

    principles = ALL_PRINCIPLES[mode]

    desc = f"【{principles.name}】\n"

    desc += f"{principles.tagline}\n\n"

    desc += "核心原则：\n"

    for i, p in enumerate(principles.principles, 1):

        desc += f"  {i}. {p['name']}：{p['description'][:80]}...\n"

    desc += f"\n对标参考：{'、'.join(principles.benchmark_sources[:3])}"

    return desc





def get_all_modes_summary() -> str:

    """获取所有写作模式的概览"""

    summary = "═══════════════════════════════════════════\n"

    summary += "  四 大 写 作 模 式 概 览\n"

    summary += "═══════════════════════════════════════════\n\n"



    for mode, principles in ALL_PRINCIPLES.items():

        summary += f"【{mode.value}】{principles.name}\n"

        summary += f"  {principles.tagline[:80]}...\n"

        summary += f"  适用场景：\n"

        for p in principles.principles[:3]:

            summary += f"    · {p['name']}\n"

        summary += "\n"



    return summary
