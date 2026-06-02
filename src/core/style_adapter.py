"""
风格适配模块 — 五大媒体风格的完整定义与切换

5种风格各有其独特的语言特征、结构模式和适用场景。
智能体根据用户选择或自动判断，为写作Agent注入对应的风格参数。

V2.2 新增：
- StyleBlend：风格混合建议（如"正文70%人民日报 + 导语30%新华社"）
- secondary_audiences 分析：多受众场景的混合风格推荐
- 风格强度参数 (0.0-1.0)：控制风格特征的注入强度
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any


class MediaStyle(Enum):
    PEOPLE_DAILY = "people_daily"
    XINHUA = "xinhua"
    CCTV = "cctv"
    GUANGMING = "guangming"
    GOVERNMENT_ADMIN = "government_admin"


@dataclass
class StyleProfile:
    style: MediaStyle
    name: str
    description: str
    typical_length_range: tuple
    narrative_perspective: str
    emotional_tone: str
    data_density: str
    literary_level: str
    policy_linkage: str
    opening_template: str
    body_template: str
    closing_template: str
    language_features: List[str]
    forbidden_patterns: List[str]
    transition_words: List[str]
    vocabulary_pool: Dict[str, List[str]]
    example_opening: str
    example_closing: str


STYLE_PROFILES: Dict[MediaStyle, StyleProfile] = {
    MediaStyle.PEOPLE_DAILY: StyleProfile(
        style=MediaStyle.PEOPLE_DAILY,
        name="人民日报风格",
        description="庄重大气，政策站位高。善用宏观叙事，将地方经验上升到国家叙事。",
        typical_length_range=(1500, 3000),
        narrative_perspective="宏观起笔→政策呼应→案例落地→升华收束",
        emotional_tone="中（庄重而不失温度）",
        data_density="中",
        literary_level="中高",
        policy_linkage="高",
        opening_template=(
            "【宏观起笔】点明时代背景或国家战略语境\n"
            "【组织定位】一句话交代'我们是谁，为何出发'\n"
            "【导语收束】以一句话点出本次活动的核心意义"
        ),
        body_template=(
            "【第一站】战略对接：此行如何回应国家/行业重大关切\n"
            "  - 战略锚点句（为什么是这里）\n"
            "  - 核心场景 + 关键数据\n"
            "  - 外部权威观点 + 我方收获\n"
            "【第二站】学术成长：此行如何检验培养质量\n"
            "  - 对标锚点句（与谁对标，为何重要）\n"
            "  - 交流细节 + 真实感言\n"
            "  - 成长证据\n"
            "【第三站】使命担当：此行如何体现家国情怀\n"
            "  - 精神锚点句（承载什么精神/使命）\n"
            "  - 震撼场景 + 感悟\n"
            "  - 与培养目标的呼应"
        ),
        closing_template=(
            "【回顾总结】以一句话概括行程，点明'这次旅程意味着什么'\n"
            "【证据收束】以1-2段真实感言作为'成长证据'\n"
            "【升华展望】结合时代背景与组织愿景，含蓄传递'我们有方向、有资源、有成果'"
        ),
        language_features=[
            "善用对仗标题和化用典故",
            "段落首句往往是论断性语句",
            "善用'历史性机遇''时代新人'等宏观叙事词汇",
            "数据与场景交替呈现，形成节奏感",
            "结尾善用排比或对仗收束",
        ],
        forbidden_patterns=[
            "避免过于口语化的表达",
            "避免纯技术细节罗列",
            "避免'大家纷纷表示'等空泛套话",
            "避免没有政策高度的就事论事",
        ],
        transition_words=[
            "由此观之", "放眼全局", "回望来路", "展望前路",
            "这不仅是一次……更是一次……", "如果说……那么……",
        ],
        vocabulary_pool={
            "verbs": [
                "锚定", "擘画", "淬炼", "共振", "赋能", "贯通", "夯实",
                "统筹", "谋划", "推进", "深化", "引领", "驱动",
                "培育", "塑造", "激发", "凝聚", "厚植", "赓续",
                "攻坚", "破局", "蝶变", "跃升", "辐射", "溢出",
            ],
            "nouns": [
                "格局", "高地", "引擎", "标杆", "新增长极", "历史性机遇",
                "战略支点", "核心动能", "关键变量", "最大增量",
                "底层逻辑", "顶层设计", "系统重塑", "生态体系",
                "时代答卷", "奋进坐标", "精神谱系", "实践伟力",
            ],
            "adjectives": [
                "战略性的", "系统性的", "开创性的", "里程碑式的",
                "全局性的", "前瞻性的", "根本性的", "决定性的",
            ],
            "four_char": [
                "统筹谋划", "精准施策", "纵深推进", "落地见效",
                "提质增效", "善作善成", "迎难而上", "砥砺奋进",
                "真抓实干", "锐意进取", "凝心聚力", "求真务实",
                "踔厉奋发", "勇毅前行", "守正创新", "笃行不怠",
            ],
            "transitions": [
                "由此观之", "放眼全局", "回望来路", "展望前路",
                "如果说……那么……", "这不仅是一次……更是一次……",
                "从……到……", "以……为……",
            ],
        },
        example_opening=(
            "在加快建设教育强国的时代背景下，高素质人才培养已成为衡量一所大学办学水准的"
            "核心标尺。近日，XX学院组织师生赴京开展研学实践，以'行走的课堂'回应'培养什么人、"
            "怎样培养人、为谁培养人'这一根本问题。"
        ),
        example_closing=(
            "从实验室到生产线，从学术殿堂到国之重器，这条研学之路串联起的，不仅是一次"
            "求知之旅，更是一幅拔尖创新人才培养的生动画卷。路虽远，行则将至——而这，"
            "正是XX学院交给时代的一份答卷。"
        ),
    ),

    MediaStyle.XINHUA: StyleProfile(
        style=MediaStyle.XINHUA,
        name="新华社风格",
        description="严谨凝练，信息密度大。善于用事实解释事实，很少空发议论。",
        typical_length_range=(500, 2000),
        narrative_perspective="客观第三人称→核心事实→背景支撑→意义点题",
        emotional_tone="低（克制、客观）",
        data_density="高",
        literary_level="低",
        policy_linkage="中",
        opening_template=(
            "【导语】五要素齐全（何时、何地、何人、何事、何故），一句话交代核心事实\n"
            "【要点预告】如有必要，用一句话预告文章将展开的核心内容"
        ),
        body_template=(
            "【核心事实展开】最重要的事实优先，逐层展开\n"
            "  - 一个事实一段，段落简短\n"
            "  - 关键数据直接引用，不加修饰\n"
            "【背景支撑】提供必要的背景信息，帮助读者理解事实的意义\n"
            "  - 组织背景（该单位在此领域的积累）\n"
            "  - 行业背景（该活动在行业中的位置）\n"
            "【权威引述】如有外部权威评价，直接引用原话\n"
            "  - 保持原话完整，不做转述加工"
        ),
        closing_template=(
            "【意义点题】用1-2句话点明该事件的意义，不展开议论\n"
            "【展望/后续】如有明确的后续计划，简要提及"
        ),
        language_features=[
            "消息一般不超过800字，通讯不超过2000字",
            "善于用事实解释事实，不空发议论",
            "层次清晰，尽量一个事实一段",
            "语言简洁，避免'高位推动''高度重视'等套话",
            "起篇较高，有宏观性概述",
            "善用四字格和简洁对仗",
        ],
        forbidden_patterns=[
            "严禁'大家纷纷表示''一致认为'等模糊表述",
            "严禁形容词堆砌替代事实陈述",
            "严禁'高位推动''精心组织''周密部署'三连套话",
            "严禁过程性流水账（几点几分、乘车入住）",
        ],
        transition_words=[
            "据悉", "据了解", "数据显示", "值得注意的是",
            "与此同时", "在此基础上",
        ],
        vocabulary_pool={
            "verbs": [
                "推进", "实现", "完成", "达成", "签署", "发布", "落地",
                "开展", "实施", "推进", "覆盖", "惠及", "带动",
                "突破", "优化", "提升", "规范", "强化", "完善",
            ],
            "nouns": [
                "突破", "进展", "成果", "数据", "指标", "体系",
                "成效", "态势", "规模", "比重", "增幅", "占比",
                "市场主体", "营商环境", "产业链", "供应链",
            ],
            "adjectives": [
                "实质性的", "阶段性的", "标志性的",
                "历史性的", "结构性的", "趋势性的",
            ],
            "four_char": [
                "稳中有进", "持续向好", "成效显著", "亮点纷呈",
                "有序推进", "扎实推进", "稳步提升", "明显增强",
                "基本形成", "初步构建", "相得益彰", "多点开花",
            ],
            "data_phrases": [
                "同比增长", "环比增长", "累计完成", "突破",
                "达到", "占", "提升至", "压缩至",
            ],
            "transitions": [
                "据悉", "据了解", "数据显示", "值得注意的是",
                "与此同时", "在此基础上", "统计表明",
            ],
        },
        example_opening=(
            "新华社北京X月X日电  XX学院师生代表团近日赴京完成为期X天的研学实践活动，"
            "先后走访北京大学、中国科学院等单位，在学术交流与科技前沿感知中检验培养成效。"
        ),
        example_closing=(
            "据悉，该学院已将研学实践纳入常态化培养体系，下一步将拓展与更多顶尖科研院所的"
            "合作渠道，持续完善拔尖创新人才培养模式。"
        ),
    ),

    MediaStyle.CCTV: StyleProfile(
        style=MediaStyle.CCTV,
        name="央视新闻风格",
        description="叙事生动，兼具深度与可读性。善用具象细节引出宏大主题，场景驱动叙事。",
        typical_length_range=(800, 2000),
        narrative_perspective="悬念切入→场景展开→人物带出→细节支撑→主题升华",
        emotional_tone="高（共鸣、温度）",
        data_density="低",
        literary_level="中",
        policy_linkage="中低",
        opening_template=(
            "【场景切入】以一个具象的场景、细节或悬念开头，勾起读者的好奇心\n"
            "【主题引出】从具体场景自然过渡到文章主题\n"
            "【预告展开】暗示文章将呈现的精彩内容"
        ),
        body_template=(
            "【场景一】以现场感和人物为核心\n"
            "  - 选取最具画面感的场景\n"
            "  - 以人物的动作、语言、表情为线索\n"
            "  - '主题事件化、事件人物化、人物命运化'\n"
            "【场景二】递进或对比\n"
            "  - 与前一个场景形成递进或对比关系\n"
            "  - 每个场景独立讲述一个微型故事\n"
            "【场景三】高潮或转折\n"
            "  - 情感最浓烈或认知最深刻的部分\n"
            "  - 自然引出主题升华"
        ),
        closing_template=(
            "【情感收束】回到开头的人物或场景，形成首尾呼应\n"
            "【主题升华】从具象到抽象，自然过渡，不突兀\n"
            "【留白收尾】以一个画面或一句话结束，余韵自生"
        ),
        language_features=[
            "'主题事件化、事件人物化、人物命运化'",
            "设置悬念开头，勾起好奇心",
            "场景驱动，将宏大议题具象化为可感知的生活场景",
            "细节叙事，增强情感共鸣",
            "语言口语化但不失深度",
            "善用直接引语和对话",
        ],
        forbidden_patterns=[
            "避免'主题先行'式开头（先喊口号再讲故事）",
            "避免过度使用政策术语",
            "避免人物沦为背景板（要给人物特写）",
        ],
        transition_words=[
            "就在此时", "谁也想不到", "更令人触动的是",
            "如果说……那么……", "镜头转向",
        ],
        vocabulary_pool={
            "verbs": [
                "走进", "见证", "触摸", "聆听", "感受", "发现",
                "叩问", "凝视", "追寻", "定格", "记录", "传递",
                "扎根", "破土", "绽放", "温暖", "照亮", "回响",
            ],
            "nouns": [
                "现场", "瞬间", "故事", "面孔", "温度", "回响",
                "画面", "细节", "场景", "镜头", "特写", "底色",
                "烟火气", "人情味", "生命力", "时代感",
            ],
            "adjectives": [
                "鲜活的", "滚烫的", "真实的", "动人的",
                "质朴的", "温润的", "厚重的", "隽永的",
            ],
            "four_char": [
                "润物无声", "娓娓道来", "扣人心弦", "催人泪下",
                "历历在目", "跃然纸上", "声情并茂", "栩栩如生",
                "以小见大", "见微知著", "春风化雨", "润物无声",
            ],
            "scene_words": [
                "推开", "走进", "站在", "回头", "转身", "远望",
                "耳边", "眼前", "脚下", "心中",
            ],
            "transitions": [
                "就在此时", "谁也想不到", "更令人触动的是",
                "如果说……那么……", "镜头转向", "谁曾想",
            ],
        },
        example_opening=(
            "站在北京大学图灵班的实验室里，大三学生李明的手微微颤抖——不是因为紧张，"
            "而是因为兴奋。屏幕上，他刚刚调试完成的一段代码，正在驱动一台机器人完成"
            "复杂的人机交互动作。'这跟我在课本上学到的完全不一样。'他说。"
        ),
        example_closing=(
            "返程的高铁上，车窗外的风景飞速后退，而同学们关于未来的讨论才刚刚开始。"
            "或许，真正的研学从来不只是'走出去'，而是把远方变成脚下的路。"
        ),
    ),

    MediaStyle.GUANGMING: StyleProfile(
        style=MediaStyle.GUANGMING,
        name="光明日报风格",
        description="理论性强，注重思想引领。善用经典论述与育人叙事结合，提倡'文气、清雅气、书卷气'。",
        typical_length_range=(2000, 5000),
        narrative_perspective="思想锚点→矛盾张力→人物传承→学理升华→文学收束",
        emotional_tone="中（深沉而不煽情）",
        data_density="中高",
        literary_level="高",
        policy_linkage="高（学理化）",
        opening_template=(
            "【思想锚点】以一个引人深思的问题或经典论述开篇\n"
            "【背景铺垫】交代'为什么此刻讨论这个问题是有意义的'\n"
            "【预告路径】暗示文章将从哪些维度展开思考"
        ),
        body_template=(
            "【第一部分】问题展开：从具体案例到普遍问题\n"
            "  - 选取矛盾性事件塑造叙事张力\n"
            "  - 不回避'不完美的英雄'\n"
            "【第二部分】纵深分析：历史维度与学理深度\n"
            "  - 引入历史脉络和理论框架\n"
            "  - 注重人物的成长性与传承性\n"
            "【第三部分】思想提炼：从个案到规律\n"
            "  - 提炼可推广的经验和启示\n"
            "  - 与更大时代命题建立关联"
        ),
        closing_template=(
            "【学理升华】将个案经验上升到理论高度\n"
            "【文学收束】以富有文学性的语言完成收尾\n"
            "【余韵】点到即止，留给读者思考空间"
        ),
        language_features=[
            "提倡'文气、清雅气、书卷气'",
            "反对'俗气、八股气、粗鄙气'",
            "评论应具备'四性'：新闻性、思想性、学理性、文学性",
            "从'小角度讲大道理'",
            "'妙故事化硬题目'",
            "注重人物的成长性与传承性",
        ],
        forbidden_patterns=[
            "反对空洞说教和道德绑架式叙事",
            "反对'完美英雄'式的人物塑造",
            "反对学术术语堆砌而不加解释",
            "反对没有思想深度的就事论事",
        ],
        transition_words=[
            "追本溯源", "换言之", "更深一层看",
            "这不禁令人思考", "从某种意义上说",
        ],
        vocabulary_pool={
            "verbs": [
                "叩问", "观照", "烛照", "赓续", "涵育", "砥砺", "薪传",
                "追问", "探求", "思辨", "审视", "洞察", "启迪",
                "沉淀", "升华", "传承", "守望", "扎根", "滋养",
            ],
            "nouns": [
                "精神家园", "思想火炬", "文化根脉", "时代命题", "育人沃土",
                "价值坐标", "精神谱系", "思想底色", "文化底蕴", "学术脉络",
                "历史纵深", "时代回响", "精神丰碑", "思想之光",
            ],
            "adjectives": [
                "深沉的", "隽永的", "厚重的", "清澈的",
                "深邃的", "温润的", "苍劲的", "悠远的",
            ],
            "four_char": [
                "文以载道", "以文化人", "润物无声", "春风化雨",
                "薪火相传", "弦歌不辍", "继往开来", "革故鼎新",
                "守正创新", "培根铸魂", "启智润心", "明德弘道",
            ],
            "philosophical": [
                "从某种意义上说", "更深一层看", "追本溯源",
                "这不禁令人思考", "何尝不是一种", "与其说……不如说……",
            ],
            "transitions": [
                "追本溯源", "换言之", "更深一层看",
                "这不禁令人思考", "从某种意义上说", "毋庸讳言",
            ],
        },
        example_opening=(
            "'培养什么人、怎样培养人、为谁培养人'——这是教育的根本问题，也是一代代"
            "教育工作者用实践作答的时代命题。当XX学院的师生走进中国科学院航天城，他们"
            "寻找的，或许不只是前沿科技，更是一种精神坐标。"
        ),
        example_closing=(
            "费孝通先生曾说：'各美其美，美人之美，美美与共，天下大同。'研学之路，"
            "何尝不是一条'美美与共'之路——在交流中看见他者，在碰撞中认识自己，"
            "在行走中锚定方向。这条路，值得一直走下去。"
        ),
    ),

    MediaStyle.GOVERNMENT_ADMIN: StyleProfile(
        style=MediaStyle.GOVERNMENT_ADMIN,
        name="党政机关行文规范风格",
        description="格式规范、用词准确、简洁高效。严格遵循《党政机关公文处理工作条例》和GB/T 9704-2012格式标准。",
        typical_length_range=(200, 2000),
        narrative_perspective="依据→事项→要求（三段式标准结构）",
        emotional_tone="低（客观、公事公办、无个人色彩）",
        data_density="高",
        literary_level="极低（禁止修辞）",
        policy_linkage="低（仅引用政策依据，不做阐发）",
        opening_template=(
            "【标题】发文机关全称+事由+文种（如：XX学院关于举办XXXX的通知）\n"
            "【主送机关】使用全称或规范化简称，顶格\n"
            "【引言段】交代行文依据（常用'根据……''为……'开头）\n"
            "【过渡句】'现将有关事项通知如下：''现就……请示如下：'等格式化用语"
        ),
        body_template=(
            "【通知类】分条列出事项，使用'一、''二、'结构\n"
            "  - 第一条：总体要求或目的\n"
            "  - 后续条：具体安排（时间、地点、人员、任务）\n"
            "  - 最后一条：执行要求或联系方式\n"
            "【请示类】一事一文，三段式\n"
            "  - 第一段：请示缘由（为什么需要）\n"
            "  - 第二段：请示事项（具体请求什么）\n"
            "  - 第三段：结语（'妥否，请批示'）\n"
            "【批复类】引用来文+答复意见\n"
            "  - 引述对方来文标题和文号\n"
            "  - 逐一答复请示事项\n"
            "  - 结语：'此复'\n"
            "【函类】商洽/询问/答复\n"
            "  - 开头交代发函缘由\n"
            "  - 主体说明具体事项\n"
            "  - 结语：'特此函告''请予支持为盼'"
        ),
        closing_template=(
            "【规范结语】必须使用法定格式化用语\n"
            "【署名】发文机关全称（加盖印章）\n"
            "【成文日期】XXXX年XX月XX日（阿拉伯数字，不编虚位）"
        ),
        language_features=[
            "3号仿宋体字，每面22行，每行28字（GB/T 9704-2012）",
            "使用'经研究决定''现就有关事项通知如下'等格式化用语",
            "一文一事，不绕弯子，直接陈述",
            "不渲染、不拔高、不借势",
            "不使用任何形容词、副词修饰",
            "不使用口语、俚语、网络用语",
            "称谓规范：职务在前、姓名在后",
            "引用公文先引标题后引文号",
        ],
        forbidden_patterns=[
            "严禁任何形式的渲染和拔高",
            "严禁形容词和程度副词修饰",
            "严禁'在……正确领导下''为了贯彻落实……'等程式化套话",
            "严禁'高度重视''亲自''指示''重要讲话'等主观色彩词汇",
            "严禁'隆重''热烈''圆满''顺利'等评价性词汇",
            "严禁外部权威引用（行政公文不需要借势）",
            "严禁个人观点和议论",
            "严禁口语化表达",
        ],
        transition_words=[
            "根据", "依据", "按照", "参照", "经研究",
            "现就", "为此", "鉴于", "接……来文",
        ],
        vocabulary_pool={
            "verbs": [
                "研究", "决定", "通知", "请示", "批复", "转发", "印发",
                "部署", "落实", "推进", "开展", "加强", "完善",
                "督促", "检查", "整改", "规范", "优化", "提升",
            ],
            "nouns": [
                "事项", "事宜", "意见", "建议", "函", "纪要",
                "台账", "清单", "机制", "举措", "预案", "方案",
                "主体责任", "第一责任人", "分管领导", "牵头部门",
            ],
            "formulaic": [
                "妥否，请批示", "此复", "特此通知", "特此函告",
                "请予支持为盼", "经研究决定", "现就有关事项通知如下",
                "以上请示，请予审批", "请认真贯彻执行",
                "为深入贯彻落实……", "经研究，现将……",
                "请结合实际，认真贯彻落实",
            ],
            "four_char": [
                "统筹兼顾", "各司其职", "密切配合", "协同推进",
                "立行立改", "举一反三", "标本兼治", "长效管控",
                "依法依规", "从严从紧", "从细从实", "落细落实",
            ],
            "action_phrases": [
                "建立台账", "明确时限", "落实责任", "闭环管理",
                "跟踪督办", "定期通报", "考核评估", "问责追责",
            ],
            "transitions": [
                "根据", "依据", "按照", "参照", "经研究",
                "现就", "为此", "鉴于", "接……来文",
            ],
        },
        example_opening=(
            "XX学院关于举办2026年学生学术论坛的通知\n\n"
            "各系（所）、各年级：\n\n"
            "根据学校《关于进一步加强本科生科研训练的实施意见》（XX校发〔2025〕12号）精神，"
            "经学院党政联席会议研究，决定举办2026年学生学术论坛。现将有关事项通知如下："
        ),
        example_closing=(
            "XX学院\n"
            "2026年X月X日"
        ),
    ),
}


@dataclass
class StyleBlend:
    """风格混合建议 — 支持多段落/多受众的场景"""
    primary_style: MediaStyle
    primary_weight: float
    secondary_style: Optional[MediaStyle] = None
    secondary_weight: float = 0.0
    secondary_apply_to: str = ""
    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary": self.primary_style.value,
            "primary_weight": self.primary_weight,
            "secondary": self.secondary_style.value if self.secondary_style else None,
            "secondary_weight": self.secondary_weight,
            "secondary_apply_to": self.secondary_apply_to,
            "reasoning": self.reasoning,
        }

    def display(self) -> str:
        if self.secondary_style and self.secondary_weight > 0:
            return (
                f"{STYLE_PROFILES[self.primary_style].name} "
                f"({self.primary_weight:.0%}) + "
                f"{STYLE_PROFILES[self.secondary_style].name} "
                f"({self.secondary_weight:.0%}，应用于{self.secondary_apply_to})"
            )
        return f"{STYLE_PROFILES[self.primary_style].name} ({self.primary_weight:.0%})"


class StyleAdapter:
    """风格适配器 — 为写作Agent注入风格参数（V2.2：混合风格 + 多受众 + 强度控制）"""

    SECONDARY_AUDIENCE_MAP: Dict[str, Tuple[MediaStyle, str]] = {
        "领导": (MediaStyle.PEOPLE_DAILY, "开篇和结尾"),
        "上级": (MediaStyle.PEOPLE_DAILY, "开篇和结尾"),
        "汇报": (MediaStyle.PEOPLE_DAILY, "开篇和结尾"),
        "媒体": (MediaStyle.XINHUA, "导语和事实段落"),
        "记者": (MediaStyle.XINHUA, "导语和事实段落"),
        "通稿": (MediaStyle.XINHUA, "导语和事实段落"),
        "学生": (MediaStyle.CCTV, "人物故事和感言段落"),
        "家长": (MediaStyle.CCTV, "人物故事和感言段落"),
        "团队": (MediaStyle.CCTV, "人物故事和感言段落"),
        "同行": (MediaStyle.GUANGMING, "分析和升华段落"),
        "对标": (MediaStyle.GUANGMING, "分析和升华段落"),
    }

    def __init__(self):
        self.profiles = STYLE_PROFILES
        self.current_style: Optional[MediaStyle] = None
        self.intensity: float = 1.0

    def list_styles(self) -> List[Dict[str, str]]:
        return [
            {
                "id": style.value,
                "name": profile.name,
                "description": profile.description,
                "length": f"{profile.typical_length_range[0]}-{profile.typical_length_range[1]}字",
            }
            for style, profile in self.profiles.items()
        ]

    def select_style(self, style: MediaStyle, intensity: float = 1.0) -> StyleProfile:
        self.current_style = style
        self.intensity = max(0.0, min(1.0, intensity))
        return self.profiles[style]

    def _score_style(self, style: MediaStyle, text: str) -> float:
        """计算某个风格对给定文本的匹配分数（0.0-1.0）"""
        keywords_map = {
            MediaStyle.PEOPLE_DAILY: [
                ("领导", 3), ("汇报", 3), ("上级", 3), ("政策", 2), ("战略", 2),
                ("格局", 2), ("展示", 2), ("成果", 2), ("方向", 2), ("高度", 1),
                ("顶层", 2), ("部署", 1), ("全局", 1),
            ],
            MediaStyle.XINHUA: [
                ("媒体", 3), ("发布", 3), ("通稿", 3), ("快讯", 2), ("新闻", 2),
                ("消息", 2), ("简讯", 2), ("通报", 2), ("事实", 2), ("数据", 1),
                ("客观", 1), ("核实", 1),
            ],
            MediaStyle.CCTV: [
                ("对内", 3), ("团队", 2), ("成员", 2), ("学生", 2), ("家长", 2),
                ("故事", 3), ("感动", 2), ("成长", 2), ("体验", 2), ("现场", 2),
                ("场景", 1), ("情感", 1),
            ],
            MediaStyle.GUANGMING: [
                ("理论", 3), ("思想", 3), ("深度", 2), ("调研", 2), ("学术", 2),
                ("教育", 2), ("育人", 2), ("精神", 2), ("文化", 2), ("传承", 2),
                ("思考", 1), ("反思", 1),
            ],
            MediaStyle.GOVERNMENT_ADMIN: [
                ("通知", 3), ("请示", 3), ("批复", 3), ("函", 3), ("纪要", 3),
                ("公文", 3), ("行政", 3), ("机关", 2), ("组织", 2), ("正式", 2),
                ("发文", 2), ("印发", 2),
            ],
        }
        text_lower = text.lower()
        max_possible = sum(w for _, w in keywords_map[style])
        if max_possible == 0:
            return 0.0
        score = sum(w for kw, w in keywords_map[style] if kw in text_lower)
        return min(1.0, score / max(1, max_possible * 0.4))

    def auto_select_style(self, audience_description: str, purpose: str) -> MediaStyle:
        """
        根据受众和目的自动推荐风格
        - 向上汇报/政策性强 → 人民日报
        - 新闻发布/快讯/媒体通稿 → 新华社
        - 对内宣传/团队建设/情感共鸣 → 央视新闻
        - 深度思考/理论探讨/育人叙事 → 光明日报
        - 行政公文/通知/请示/批复/函 → 党政机关行文规范
        """
        combined = (audience_description + purpose).lower()
        scores = {}
        for style in MediaStyle:
            scores[style] = self._score_style(style, combined)
        if max(scores.values()) == 0:
            return MediaStyle.XINHUA
        return max(scores, key=scores.get)

    def suggest_blend(
        self,
        primary_audience: str,
        purpose: str = "",
        secondary_audiences: Optional[List[str]] = None,
    ) -> StyleBlend:
        """
        V2.2：基于多受众分析生成风格混合建议

        Args:
            primary_audience: 主要受众描述
            purpose: 写作目的
            secondary_audiences: 次要受众列表（如 ["领导", "媒体", "学生"]）

        Returns:
            StyleBlend 对象，含主风格、次风格、权重和应用位置建议
        """
        combined = (primary_audience + " " + purpose).lower()

        style_scores: Dict[MediaStyle, float] = {}
        for style in MediaStyle:
            style_scores[style] = self._score_style(style, combined)

        sorted_styles = sorted(style_scores.items(), key=lambda x: x[1], reverse=True)
        primary_style = sorted_styles[0][0]
        primary_score = sorted_styles[0][1]

        if not secondary_audiences:
            return StyleBlend(
                primary_style=primary_style,
                primary_weight=1.0,
                reasoning=f"单一受众场景，全篇使用{STYLE_PROFILES[primary_style].name}",
            )

        secondary_scores: Dict[MediaStyle, float] = {}
        for audience in secondary_audiences:
            aud_lower = audience.lower()
            for style in MediaStyle:
                s = self._score_style(style, aud_lower)
                if s > 0:
                    secondary_scores[style] = secondary_scores.get(style, 0) + s

        for style in secondary_scores:
            if style == primary_style:
                continue
            secondary_scores[style] *= 0.6

        if not secondary_scores:
            return StyleBlend(
                primary_style=primary_style,
                primary_weight=1.0,
                reasoning=f"次要受众与主风格重合，全篇使用{STYLE_PROFILES[primary_style].name}",
            )

        best_secondary = max(secondary_scores, key=secondary_scores.get)
        secondary_score = secondary_scores[best_secondary]

        if best_secondary == primary_style:
            return StyleBlend(
                primary_style=primary_style,
                primary_weight=1.0,
                reasoning=f"次要受众风格与主风格一致，全篇使用{STYLE_PROFILES[primary_style].name}",
            )

        total = primary_score + secondary_score
        primary_weight = primary_score / total if total > 0 else 0.7
        secondary_weight = secondary_score / total if total > 0 else 0.3

        apply_to = self.SECONDARY_AUDIENCE_MAP.get(
            secondary_audiences[0].lower() if secondary_audiences else "",
            ("", "特定段落"),
        )[1]

        reasons = []
        reasons.append(f"主要受众({primary_audience})→{STYLE_PROFILES[primary_style].name}")
        reasons.append(f"次要受众({', '.join(secondary_audiences)})→{STYLE_PROFILES[best_secondary].name}")

        return StyleBlend(
            primary_style=primary_style,
            primary_weight=primary_weight,
            secondary_style=best_secondary,
            secondary_weight=secondary_weight,
            secondary_apply_to=apply_to,
            reasoning="；".join(reasons),
        )

    def get_system_prompt_injection(
        self,
        profile: StyleProfile,
        blend: Optional[StyleBlend] = None,
    ) -> str:
        """
        生成注入写作Agent的System Prompt片段（V2.2：支持混合风格和强度控制）

        Args:
            profile: 主风格配置
            blend: 可选的风格混合建议
        """
        if blend and blend.secondary_style and blend.secondary_weight > 0.15:
            return self._build_blend_prompt(profile, blend)
        return self._build_single_prompt(profile)

    def _build_single_prompt(self, profile: StyleProfile) -> str:
        """构建单一风格的 System Prompt"""
        intensity_note = self._intensity_note()
        return f"""
【当前写作风格】{profile.name}{intensity_note}

【风格要求】
- 篇幅范围：{profile.typical_length_range[0]}-{profile.typical_length_range[1]}字
- 叙事视角：{profile.narrative_perspective}
- 情感基调：{profile.emotional_tone}
- 语言特征：{'；'.join(self._scale_language_features(profile))}

【开篇模式】
{profile.opening_template}

【正文模式】
{profile.body_template}

【结尾模式】
{profile.closing_template}

【推荐词汇】
- 动词：{'、'.join(profile.vocabulary_pool.get('verbs', [])[:5])}
- 名词：{'、'.join(profile.vocabulary_pool.get('nouns', [])[:5])}

【严禁】
{'；'.join(self._scale_forbidden(profile))}

【参考开头示例】
{profile.example_opening}

【参考结尾示例】
{profile.example_closing}
"""

    def _build_blend_prompt(
        self,
        primary_profile: StyleProfile,
        blend: StyleBlend,
    ) -> str:
        """构建混合风格的 System Prompt"""
        if not blend.secondary_style:
            return self._build_single_prompt(primary_profile)

        secondary_profile = self.profiles[blend.secondary_style]
        return f"""
【写作风格】混合风格：{blend.display()}

【主导风格 — {primary_profile.name}（{blend.primary_weight:.0%}）】
- 叙事视角：{primary_profile.narrative_perspective}
- 情感基调：{primary_profile.emotional_tone}
- 语言特征：{'；'.join(primary_profile.language_features[:3])}
- 参考开头：{primary_profile.example_opening[:100]}...
- 参考结尾：{primary_profile.example_closing[:100]}...

【辅助风格 — {secondary_profile.name}（{blend.secondary_weight:.0%}，应用于{blend.secondary_apply_to}）】
- 语言特征：{'；'.join(secondary_profile.language_features[:2])}
- 参考写法：{secondary_profile.example_opening[:100]}...

【混合规则】
- {blend.secondary_apply_to}采用{secondary_profile.name}的特征（{secondary_profile.emotional_tone}情感、{secondary_profile.narrative_perspective}视角）
- 其余部分保持{primary_profile.name}的叙事节奏和语言风格
- 两种风格的过渡要自然，避免风格突变

【正文模式】
{primary_profile.body_template}

【严禁】
{'；'.join(primary_profile.forbidden_patterns[:3])}
"""

    def _intensity_note(self) -> str:
        """根据强度参数生成提示"""
        if self.intensity >= 0.9:
            return "（完整强度）"
        elif self.intensity >= 0.7:
            return "（标准强度）"
        elif self.intensity >= 0.5:
            return "（适度风格）"
        elif self.intensity >= 0.3:
            return "（轻度风格）"
        else:
            return "（极简风格，以信息传达为优先）"

    def _scale_language_features(self, profile: StyleProfile) -> List[str]:
        """根据强度参数缩放语言特征数量"""
        features = profile.language_features
        if self.intensity >= 0.8:
            return features[:5]
        elif self.intensity >= 0.5:
            return features[:3]
        else:
            return features[:1]

    def _scale_forbidden(self, profile: StyleProfile) -> List[str]:
        """根据强度参数缩放禁用模式数量"""
        forbidden = profile.forbidden_patterns
        if self.intensity >= 0.7:
            return forbidden[:5]
        elif self.intensity >= 0.4:
            return forbidden[:3]
        else:
            return forbidden[:1]

    def get_system_prompt_injection_with_intensity(
        self,
        profile: StyleProfile,
        intensity: float,
    ) -> str:
        """便捷方法：指定强度参数注入风格（V2.2）"""
        self.intensity = max(0.0, min(1.0, intensity))
        return self.get_system_prompt_injection(profile)
