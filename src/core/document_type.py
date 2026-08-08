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

    # ═══════════════════════════════════════════════════════════
    # 法定行政公文（依据《党政机关公文处理工作条例》中办发〔2012〕14号、
    # 《党政机关公文格式》GB/T 9704-2012）
    # ═══════════════════════════════════════════════════════════

    DocumentType.NOTIFICATION: DocTypeProfile(
        doc_type=DocumentType.NOTIFICATION,
        name_cn="通知",
        description="发布、传达要求下级机关执行和有关单位周知或执行的事项，批转、转发公文。适用范围最广",
        typical_length_range=(500, 1500),
        structure_mode="标题→主送机关→缘由→事项→执行要求→落款（缘由简明、事项具体、要求可执行）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "发布性通知：发布规章制度、工作部署",
            "指示性通知：对下级布置工作、提出要求",
            "批转/转发性通知：批转下级机关或转发上级机关公文",
            "知照性通知：需要有关单位和人员周知的事项",
        ],
        key_features=[
            "标题三要素齐全：发文机关+事由+文种",
            "主送机关应准确写明，一文一主送",
            "正文用'特此通知'作结语",
            "语言准确简洁，指令清晰，不拖泥带水",
            "杜绝与请示、报告、通报等文种混用",
        ],
        opening_template=(
            "【标题】发文机关名称+关于事由的通知\n"
            "【主送机关】各有关单位名称\n"
            "【缘由】发文依据和目的（1-2句），常用'根据……''为……'，"
            "后用'现将有关事项通知如下'过渡"
        ),
        body_template=(
            "【事项】分条列明通知的具体内容\n"
            "  - 一、工作内容与目标\n"
            "  - 二、具体安排与分工\n"
            "  - 三、时间节点与要求\n"
            "每条一项，表述准确，避免歧义"
        ),
        closing_template=(
            "【结语】'特此通知'\n"
            "【落款】发文机关署名+成文日期（阿拉伯数字，如2026年8月4日）"
        ),
        audience_focus={
            "internal": "执行主体与责任分工要明确",
            "upward": "请示性通知需说明依据与目的",
            "external": "知照事项要完整、可周知",
            "peer": "平行通知注意商洽语气",
        },
    ),

    DocumentType.REQUEST: DocTypeProfile(
        doc_type=DocumentType.REQUEST,
        name_cn="请示",
        description="向上级机关请求指示、批准。一文一事，逐级行文，不得越级",
        typical_length_range=(800, 2000),
        structure_mode="标题→主送机关→请示缘由→请示事项→结语→落款（一文一事、理由充分、事项单一）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "请求上级机关审批事项（人、财、物、机构等）",
            "对政策界限不清的事项请求指示",
            "工作中遇到新情况新问题需上级定夺",
            "对原规定作出调整的请示",
        ],
        key_features=[
            "一文一事，一份请示只请求一件事",
            "只写一个主送机关，不得多头请示",
            "理由充分、依据明确，事项具体可行",
            "不得抄送下级机关",
            "结语规范：'妥否，请批示''以上请示，请予审批'",
            "与'报告'严格区分：请示需答复，报告不需",
        ],
        opening_template=(
            "【标题】发文机关名称+关于事的请示\n"
            "【主送机关】唯一上级机关名称\n"
            "【缘由】请示的理由和依据（政策依据+现实需要），实事求是、充分有力"
        ),
        body_template=(
            "【事项】具体请示内容\n"
            "  - 拟开展事项的背景与必要性\n"
            "  - 拟采取的做法、规模、经费等具体方案\n"
            "  - 需要上级批准/指示的具体问题，逐条列明\n"
            "事项单一，方案明确，便于上级决策"
        ),
        closing_template=(
            "【结语】'妥否，请批示'或'以上请示，请予审批'\n"
            "【落款】发文机关署名+成文日期+（联系人及电话，视需要）"
        ),
        audience_focus={
            "internal": "只报送归口上级机关",
            "upward": "理由充分、事项明确、便于快速批复",
            "external": "不适用（请示不对外行文）",
            "peer": "不适用（请示不发送平行机关）",
        },
    ),

    DocumentType.REPLY: DocTypeProfile(
        doc_type=DocumentType.REPLY,
        name_cn="批复",
        description="答复下级机关请示事项。具有明确的针对性和指示性",
        typical_length_range=(300, 800),
        structure_mode="标题→主送机关→引述来文→批复意见→结语→落款（先引后批、态度明确）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "答复下级机关的请示事项",
            "批准或不同意下级的请求",
            "对请示事项作政策性答复",
        ],
        key_features=[
            "针对请示事项逐一答复，有请示必有批复",
            "态度明确：同意、不同意或部分同意，不含糊",
            "标题可含原请示标题，如'关于××的批复'",
            "引述来文：'你单位《关于……的请示》（文号）收悉'",
            "不同意的批复要说明理由和依据",
            "语言简洁庄重，不解释过多",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+请示事由+的批复\n"
            "【主送机关】来文请示机关名称\n"
            "【引述】'你单位《关于××的请示》（×〔2026〕×号）收悉'"
        ),
        body_template=(
            "【批复意见】明确表态\n"
            "  - 同意：'同意你单位……'并简述执行要求\n"
            "  - 不同意：'不同意……'并说明依据和理由\n"
            "  - 部分同意：分别说明同意与不同意的事项\n"
            "  - 如有附带要求，分条说明"
        ),
        closing_template=(
            "【结语】'此复'或'特此批复'\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "执行要求具体明确",
            "upward": "不适用（批复面向下级）",
            "external": "不适用",
            "peer": "不适用（批复不发送平行机关）",
        },
    ),

    DocumentType.LETTER: DocTypeProfile(
        doc_type=DocumentType.LETTER,
        name_cn="函",
        description="不相隶属机关之间商洽工作、询问和答复问题、请求批准和答复审批事项",
        typical_length_range=(300, 1000),
        structure_mode="标题→主送机关→缘由→事项→结语→落款（平等商洽、简洁得体）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "商洽工作：不相隶属机关之间的工作协作",
            "询问与答复问题",
            "请求批准事项（函代请示）",
            "答复审批事项",
        ],
        key_features=[
            "用于不相隶属机关之间，无论级别高低一律平等",
            "语言得体、态度诚恳，多用商洽语气",
            "请求批准事项的函可用'请予审批'，但不等同于请示",
            "结语规范：'特此函达''特此函复''盼予函复'",
            "回复性函要针对来函内容作答",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的函\n"
            "【主送机关】不相隶属机关名称\n"
            "【缘由】发函的原因和目的，'为……，特函商请贵单位……'"
        ),
        body_template=(
            "【事项】商洽/询问/告知的具体内容\n"
            "  - 说明来意和请求事项\n"
            "  - 提出具体合作方式或问题\n"
            "  - 回复性函先引述来函，再逐一答复\n"
            "简明扼要，一事一函"
        ),
        closing_template=(
            "【结语】'特此函达，盼予函复'或'专此函复'\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "协调事项责任清晰",
            "upward": "不适用（函用于平行/不相隶属）",
            "external": "平等沟通，态度诚恳",
            "peer": "协作事项表述具体",
        },
    ),

    DocumentType.MEETING_MINUTES: DocTypeProfile(
        doc_type=DocumentType.MEETING_MINUTES,
        name_cn="会议纪要",
        description="记载会议主要情况和议定事项，用于统一认识、指导工作",
        typical_length_range=(1000, 3000),
        structure_mode="标题→时间地点→与会人员→会议内容→议定事项→结语（纪实性+纪要性）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "党委（党组）会议、行政办公会议纪要",
            "专题工作会议纪要",
            "联席会议、协调会议纪要",
            "座谈会、研讨会情况整理",
        ],
        key_features=[
            "纪实性：真实记录会议主要情况",
            "纪要性：只记结论和议定事项，不记讨论过程",
            "常用'会议认为''会议指出''会议强调''会议决定'表述",
            "议定事项责任到人、时限明确",
            "经与会领导审签后印发",
        ],
        opening_template=(
            "【标题】会议名称+会议纪要，如'××工作部署会议纪要'\n"
            "【会议概况】时间、地点、主持人、出席人员、列席人员（1段）"
        ),
        body_template=(
            "【会议内容】按议题分节\n"
            "  - 一、关于××工作的汇报与讨论\n"
            "  - 二、会议认为……（统一认识）\n"
            "  - 三、会议决定……（议定事项）\n"
            "  - 四、会议要求……（任务分工、时限）\n"
            "每项议定事项明确责任单位和完成时限"
        ),
        closing_template=(
            "【印发说明】'以上纪要请各相关单位认真贯彻执行'（视需要）\n"
            "【落款】会议组织单位+日期（纪要可不署名，由办公室印发）"
        ),
        audience_focus={
            "internal": "议定事项与责任分工是核心",
            "upward": "请示性议题需记录上级意见",
            "external": "对外联合会议纪要需双方确认",
            "peer": "协调事项记录完整",
        },
    ),

    DocumentType.CIRCULAR: DocTypeProfile(
        doc_type=DocumentType.CIRCULAR,
        name_cn="通报",
        description="表彰先进、批评错误、传达重要精神和告知重要情况",
        typical_length_range=(500, 1500),
        structure_mode="标题→主送机关→通报事实→分析评价→决定/要求→落款（事实为基、褒贬分明）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "表彰性通报：表彰先进单位和先进个人",
            "批评性通报：批评错误、通报事故查处情况",
            "情况性通报：传达重要精神、告知重要情况",
        ],
        key_features=[
            "事实准确、典型，具有普遍教育意义",
            "表彰性通报评价恰当、号召有力",
            "批评性通报分析深刻、引以为戒",
            "情况性通报信息完整、要点突出",
            "与'通知'区分：通报重在告知情况、教育引导",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的通报\n"
            "【主送机关】有关单位和人员\n"
            "【缘由】通报的背景和依据，引出通报对象"
        ),
        body_template=(
            "【事实】通报的主要事实（时间、地点、对象、经过、结果）\n"
            "【评价】对事实的分析评价\n"
            "  - 表彰性：先进事迹的意义与精神\n"
            "  - 批评性：错误的性质、原因与教训\n"
            "  - 情况性：重要情况的要点归纳\n"
            "【决定】给予的表彰/处分决定"
        ),
        closing_template=(
            "【要求】向有关单位和人员提出的希望或要求\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "教育意义与工作要求",
            "upward": "事实准确、定性恰当",
            "external": "典型宣传价值",
            "peer": "经验教训可借鉴",
        },
    ),

    DocumentType.ANNOUNCEMENT: DocTypeProfile(
        doc_type=DocumentType.ANNOUNCEMENT,
        name_cn="公告",
        description="向国内外宣布重要事项或法定事项，发布范围最广、庄重性最强",
        typical_length_range=(200, 800),
        structure_mode="标题→正文（依据+事项+结语）→落款（庄重简明、周知性强）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "宣布重要事项（机构设立、重大决策等）",
            "公布法定事项（选举结果、任职公告等）",
            "需向国内外公开周知的重要信息",
        ],
        key_features=[
            "发文机关一般为级别较高的机关或其授权机关",
            "面向国内外，范围最广",
            "语言庄重、简明、准确，不加渲染",
            "结语常用'特此公告''现予公告'",
            "与'通告'区分：公告面向国内外，通告面向一定范围",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的公告\n"
            "【依据】公告的法律依据或决策依据，'根据……，现就××事项公告如下'"
        ),
        body_template=(
            "【事项】公告的具体内容\n"
            "  - 重要事项：事项内容、适用范围、生效时间\n"
            "  - 法定事项：法定依据、事项详情、相关程序\n"
            "  - 需要周知的信息完整、无歧义\n"
            "分条列明，每条独立完整"
        ),
        closing_template=(
            "【结语】'特此公告'\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "不适用（公告对外发布）",
            "upward": "重大事项需经审批后发布",
            "external": "信息完整、便于公众周知",
            "peer": "不适用",
        },
    ),

    DocumentType.DECISION: DocTypeProfile(
        doc_type=DocumentType.DECISION,
        name_cn="决定",
        description="对重要事项作出决策和部署、奖惩有关单位和人员、变更或撤销下级机关不适当的决定事项",
        typical_length_range=(500, 2000),
        structure_mode="标题→正文（缘由+事项+要求）→落款（决策明确、部署周密）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "重大决策部署",
            "表彰奖励或纪律处分的决定",
            "机构设置、人事任免等决定事项",
            "变更或撤销下级机关不适当决定",
        ],
        key_features=[
            "决策性：结论性意见，权威性、强制性",
            "标题为'××的决定'，可省略发文机关",
            "部署类决定事项明确、责任清晰、可考核",
            "奖惩类决定事实清楚、依据充分、处分恰当",
            "与'通知'区分：决定更权威，适用于重要事项",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的决定\n"
            "【缘由】作出决定的依据和目的（1-2段），'为……，特作如下决定'"
        ),
        body_template=(
            "【事项】决定的具体内容\n"
            "  - 决策类：总体目标、重点任务、保障措施\n"
            "  - 部署类：工作安排、责任分工、时限要求\n"
            "  - 奖惩类：事由、依据、具体奖惩决定\n"
            "  - 变更类：被变更事项、新决定内容\n"
            "分条列明，语言斩钉截铁、明确无歧义"
        ),
        closing_template=(
            "【要求】贯彻执行的具体要求（视需要）\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "执行责任与考核要求",
            "upward": "决策依据与上级精神",
            "external": "重大决策的公开宣示",
            "peer": "决策先例与经验",
        },
    ),

    DocumentType.REPORT: DocTypeProfile(
        doc_type=DocumentType.REPORT,
        name_cn="报告",
        description="向上级机关汇报工作、反映情况、回复上级机关的询问。呈报性文书，不需上级答复",
        typical_length_range=(500, 3000),
        structure_mode="标题→主送机关→工作概况→做法成效→存在问题→下一步打算→结语（陈述为主、事实说话）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "向上级汇报阶段性工作",
            "反映工作中出现的情况和问题",
            "回复上级机关的询问和交办事项",
            "报送工作总结、工作要点等材料",
        ],
        key_features=[
            "呈报性：只汇报不请示，不得夹带请示事项",
            "陈述性：以事实和数据说话，不抒情不议论",
            "结构清晰：情况—做法—成效—问题—打算",
            "问题要如实反映，不回避、不粉饰",
            "结语'特此报告'（不需上级批复）",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的报告\n"
            "【主送机关】上级机关名称\n"
            "【概况】报告事项的总括（时间、背景、总体情况）"
        ),
        body_template=(
            "【做法与成效】主要工作措施与取得成效\n"
            "  - 分条汇报，数据支撑\n"
            "【存在问题】如实反映存在的困难和问题\n"
            "【下一步打算】下阶段工作安排和计划\n"
            "回复性报告直接针对询问事项作答"
        ),
        closing_template=(
            "【结语】'特此报告'（工作报告）；回复性报告用'专此报告'\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "全面客观反映工作",
            "upward": "重点突出、数据准确、便于决策参考",
            "external": "不适用（报告向上行文）",
            "peer": "不适用",
        },
    ),

    DocumentType.OPINION: DocTypeProfile(
        doc_type=DocumentType.OPINION,
        name_cn="意见",
        description="对重要问题提出见解和处理办法。兼具指导性与建议性",
        typical_length_range=(500, 2500),
        structure_mode="标题→主送机关→缘由→意见内容→实施要求→落款（问题导向、办法可行）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "对重要工作提出指导性意见",
            "对需要解决的重要问题提出处理办法",
            "指导下级机关开展某项工作",
            "向上级提出建议性意见",
        ],
        key_features=[
            "问题导向：先讲清问题，再提意见",
            "意见具有针对性和可操作性",
            "上行意见供上级参考，下行意见具有指导约束力",
            "结构通常按'总体要求—重点任务—保障措施'展开",
            "标题为'关于××的意见'",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的意见\n"
            "【主送机关】受文单位或上级机关\n"
            "【缘由】提出意见的背景、依据和目的"
        ),
        body_template=(
            "【总体要求】指导思想、基本原则、工作目标\n"
            "【重点任务】分条列明主要任务与具体措施\n"
            "  - 每条明确责任主体和完成时限\n"
            "【保障措施】组织保障、考核督查等"
        ),
        closing_template=(
            "【实施要求】对贯彻落实提出的要求\n"
            "【落款】发文机关署名+成文日期"
        ),
        audience_focus={
            "internal": "任务分解与执行责任",
            "upward": "建议依据充分、方案可行",
            "external": "指导意见公开宣示",
            "peer": "经验做法的交流参考",
        },
    ),

    DocumentType.MOTION: DocTypeProfile(
        doc_type=DocumentType.MOTION,
        name_cn="议案",
        description="各级人民政府按照法律程序向同级人民代表大会或其常务委员会提请审议事项",
        typical_length_range=(200, 1500),
        structure_mode="标题→主送机关→案由→事项→结语→落款（依法定程序、案由明确）",
        benchmark_media="党政机关公文（GB/T 9704-2012）",
        applicable_scenarios=[
            "提请人大审议法律、法规、规章草案",
            "提请人大审议重大事项安排",
            "提请人大审查批准预算决算等事项",
            "提请人大常委会决定人事任免等事项",
        ],
        key_features=[
            "法定性：必须按法律程序提出，由政府机关提出",
            "主送机关为同级人大或其常务委员会",
            "案由清楚、依据充分、事项完整",
            "结语规范：'请予审议''现提请审议'",
            "与'请示'区分：议案面向权力机关，有法定程序",
        ],
        opening_template=(
            "【标题】发文机关名称+关于+事由+的议案\n"
            "【主送机关】同级人民代表大会/人民代表大会常务委员会\n"
            "【案由】提请审议的事项和理由（法律依据+现实需要）"
        ),
        body_template=(
            "【事项】提请审议的具体内容\n"
            "  - 法规草案：说明起草背景、依据和主要内容\n"
            "  - 重大事项：事项详情、必要性、可行性\n"
            "  - 人事任免：人选情况、任职依据\n"
            "附：相关草案文本或说明材料"
        ),
        closing_template=(
            "【结语】'现提请审议''请予审议'\n"
            "【落款】政府机关署名（政府首长署名）+成文日期"
        ),
        audience_focus={
            "internal": "程序完备、材料齐全",
            "upward": "不适用（议案面向权力机关）",
            "external": "审议公开信息",
            "peer": "不适用",
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

        # 行政模式专用识别：只对法定行政公文文种打分，避免推荐媒体文种
        from ..core.writing_mode import WritingMode
        if getattr(brief, "writing_mode", "") == WritingMode.ADMINISTRATIVE.value:
            return self._identify_administrative(brief, purpose, audience, deep, materials)

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
            [(self.profiles[dt], score) for dt, score in scores.items() if dt in self.profiles],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked

    def _identify_administrative(
        self, brief: "WritingBrief", purpose: str, audience: str, deep: str, materials: str
    ) -> List[Tuple[DocTypeProfile, float]]:
        """行政模式专用识别：仅对 11 种法定行政公文文种打分，不推荐媒体文种"""
        scores: Dict[DocumentType, float] = {dt: 0.0 for dt in DocumentType}

        admin_keyword_rules = [
            (DocumentType.NOTIFICATION, ["通知", "布置", "部署", "安排工作", "传达", "转发", "知照"], 0.20),
            (DocumentType.REQUEST, ["请示", "请求批准", "请求指示", "恳请", "报请", "审批"], 0.25),
            (DocumentType.REPLY, ["批复", "答复请示", "批准请示"], 0.25),
            (DocumentType.LETTER, ["商洽", "函询", "商请", "询问问题", "不相隶属"], 0.20),
            (DocumentType.MEETING_MINUTES, ["会议纪要", "纪要", "议定事项", "会议决定"], 0.25),
            (DocumentType.CIRCULAR, ["通报", "表彰", "批评", "表扬", "传达重要情况"], 0.20),
            (DocumentType.ANNOUNCEMENT, ["公告", "宣布", "法定事项", "面向社会"], 0.20),
            (DocumentType.DECISION, ["决定", "决策部署", "奖惩", "任免"], 0.20),
            (DocumentType.REPORT, ["汇报", "报告工作", "反映情况", "工作情况", "总结"], 0.20),
            (DocumentType.OPINION, ["意见", "处理办法", "提出建议", "指导"], 0.20),
            (DocumentType.MOTION, ["议案", "提请审议", "人大", "人大常委会"], 0.25),
        ]
        for doc_type, keywords, weight in admin_keyword_rules:
            matches = sum(1 for kw in keywords if kw in purpose)
            if matches > 0:
                scores[doc_type] += weight * min(1.0, matches / 2)

        # 受众驱动：上行文/平行文/下行文
        if any(kw in audience for kw in ["上级", "领导", "党委", "机关"]):
            scores[DocumentType.REQUEST] += 0.12
            scores[DocumentType.REPORT] += 0.12
        if any(kw in audience for kw in ["不相隶属", "兄弟单位", "外单位", "对方单位"]):
            scores[DocumentType.LETTER] += 0.15
        if any(kw in audience for kw in ["下级", "基层", "各单位", "部门"]):
            scores[DocumentType.NOTIFICATION] += 0.12
        if any(kw in audience for kw in ["人大", "人大常委会", "代表"]):
            scores[DocumentType.MOTION] += 0.15

        # 篇幅驱动
        if brief.length_hint:
            length = brief.length_hint
            length_boosts = [
                (DocumentType.REPLY, 300, 800),
                (DocumentType.LETTER, 300, 1000),
                (DocumentType.ANNOUNCEMENT, 200, 800),
                (DocumentType.NOTIFICATION, 500, 1500),
                (DocumentType.REQUEST, 800, 2000),
                (DocumentType.MOTION, 200, 1500),
                (DocumentType.CIRCULAR, 500, 1500),
                (DocumentType.DECISION, 500, 2000),
                (DocumentType.MEETING_MINUTES, 1000, 3000),
                (DocumentType.OPINION, 500, 2500),
                (DocumentType.REPORT, 500, 3000),
            ]
            for dt, low, high in length_boosts:
                if low <= length <= high:
                    center = (high + low) / 2
                    range_size = (high - low) / 2
                    distance = abs(length - center) / range_size
                    scores[dt] += 0.35 * (1.0 - distance)

        # 素材类型驱动
        mat_scores = self.analyze_materials(materials)
        if mat_scores["documents"] > 0.35:
            scores[DocumentType.NOTIFICATION] += 0.12
            scores[DocumentType.DECISION] += 0.10
        if mat_scores["data"] > 0.35:
            scores[DocumentType.REPORT] += 0.12

        if max(scores.values()) == 0:
            scores[DocumentType.NOTIFICATION] = 0.5  # 行政模式默认推荐通知

        ranked = sorted(
            [(self.profiles[dt], score) for dt, score in scores.items() if dt in self.profiles],
            key=lambda x: x[1],
            reverse=True,
        )
        return ranked

    def get_profile(self, doc_type: DocumentType) -> DocTypeProfile:
        if doc_type in self.profiles:
            return self.profiles[doc_type]
        
        # 动态为未在 profiles 中显式配置的行政公文类型生成默认 Profile，防止 KeyError
        name_cn_map = {
            DocumentType.NOTIFICATION: "通知",
            DocumentType.REQUEST: "请示",
            DocumentType.REPLY: "批复",
            DocumentType.LETTER: "函",
            DocumentType.MEETING_MINUTES: "会议纪要",
            DocumentType.CIRCULAR: "通报",
            DocumentType.ANNOUNCEMENT: "公告",
            DocumentType.DECISION: "决定",
            DocumentType.REPORT: "报告",
            DocumentType.OPINION: "意见",
            DocumentType.MOTION: "议案",
        }
        name_cn = name_cn_map.get(doc_type, doc_type.value)
        
        return DocTypeProfile(
            doc_type=doc_type,
            name_cn=name_cn,
            description=f"关于{name_cn}的行政行文规范",
            typical_length_range=(500, 1500),
            structure_mode="依据→事项→要求（三段式标准结构）",
            benchmark_media="党政机关行文规范",
            applicable_scenarios=[f"发布、传达{name_cn}要求或办理相关事项"],
            key_features=[
                "严格遵循党政机关公文格式规范与国家标准",
                "表达清晰准确，语言严谨平实",
                "包含完整的标题、主送机关、正文与落款",
            ],
            opening_template="【标题】发文机关名称+事由+文种\n【引言】交代行文依据、目的及宗旨",
            body_template="【正文部分】按条列出具体的事项、办法、程序和要求",
            closing_template="【结语与落款】规范结语（如'特此通知'、'妥否，请批示'），并署名成文日期",
            audience_focus={"internal": "明确事项细节", "upward": "呈报待批示"},
        )

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
