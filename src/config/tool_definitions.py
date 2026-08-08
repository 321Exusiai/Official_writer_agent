"""
工具定义模块

向 LLM 声明可用工具的名称、功能和参数格式。
对应 IMPROVEMENT_PLAN.md 中 TD-1：在 prompt 中声明工具。

短期方案：LLM 在输出中用 [TOOL_CALL: ...] 标记建议调用工具，
         由代码解析执行后将结果返回给 LLM。
中期方案：迁移到 function calling API，工具定义可直接注册为 functions。

工具按使用阶段分三组：
  - pre_writing（写作前）：文种识别、风格选择、范文检索、素材分析、用户记忆
  - during_writing（写作中）：术语查询、过渡词、格式化用语
  - post_writing（写作后）：错误诊断、格式诊断、弱点分析
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional


@dataclass
class ToolParam:
    """工具参数定义"""
    name: str
    type: str           # string / int / float / bool
    required: bool
    description: str
    default: str = ""


@dataclass
class ToolDefinition:
    """单个工具的完整定义"""
    name: str
    description: str
    category: str       # 知识库 / 文种识别 / 风格适配 / 个性化 / 导入
    phase: str          # pre_writing / during_writing / post_writing
    parameters: List[ToolParam] = field(default_factory=list)
    returns: str = ""
    example: str = ""   # 调用示例


# ═══════════════════════════════════════════════════════════════
# 工具定义清单
# ==================================================================

TOOL_DEFINITIONS: List[ToolDefinition] = [

    # ── 知识库工具 ──

    ToolDefinition(
        name="diagnose_text",
        description="检查文本中的常见写作错误：被动叙事、空泛表态、流水账、标题缺乏辨识度等",
        category="知识库",
        phase="post_writing",
        parameters=[
            ToolParam("text", "string", True, "待诊断的文本内容"),
        ],
        returns="错误列表，每条含：错误名称、诊断说明、修改建议、严重程度",
        example="[TOOL_CALL: diagnose_text(text=刚才写的初稿内容)]",
    ),
    ToolDefinition(
        name="diagnose_format",
        description="检查公文格式错误：标题三要素缺失、日期格式、引文格式、结尾用语、行文规则等",
        category="知识库",
        phase="post_writing",
        parameters=[
            ToolParam("text", "string", True, "待检查格式的公文文本"),
        ],
        returns="格式错误列表，每条含：错误名称、问题描述、修改建议、严重程度",
        example="[TOOL_CALL: diagnose_format(text=刚才写的通知正文)]",
    ),
    ToolDefinition(
        name="lookup_term",
        description="查询术语的准确定义、使用语境、常见误用和例句。覆盖经济/科技/教育/文化/党建/生态等领域",
        category="知识库",
        phase="during_writing",
        parameters=[
            ToolParam("term", "string", True, "要查询的术语，如'新质生产力'、'产教融合'"),
        ],
        returns="术语信息：定义、出处、使用注意、实践示例、常见误用",
        example="[TOOL_CALL: lookup_term(term=新质生产力)]",
    ),
    ToolDefinition(
        name="search_exemplars",
        description="按写作模式/文种/风格检索标杆范文（中国新闻奖、中央机关公文大赛获奖作品）",
        category="知识库",
        phase="pre_writing",
        parameters=[
            ToolParam("writing_mode", "string", False, "写作模式：strategic_narrative / objective_report / administrative / informational / youth_engagement"),
            ToolParam("doc_type", "string", False, "文种：消息 / 通讯 / 侧记 / 调研报告 / 简报 / 通知 / 请示 / 批复 / 函 / 纪要"),
            ToolParam("style", "string", False, "媒体风格：人民日报 / 新华社 / 央视新闻 / 光明日报 / 党政机关行文规范"),
        ],
        returns="范文列表，每篇含：标题、来源、结构骨架、关键句式、语言特征、可复用模式",
        example="[TOOL_CALL: search_exemplars(writing_mode=administrative, doc_type=通知)]",
    ),
    ToolDefinition(
        name="get_writing_tips",
        description="获取指定文种和风格的写作提示（导语怎么写、结构怎么排、语言注意什么）",
        category="知识库",
        phase="pre_writing",
        parameters=[
            ToolParam("doc_type", "string", True, "文种：消息 / 通讯 / 侧记 / 调研报告 / 通知 / 请示 等"),
            ToolParam("style", "string", True, "媒体风格：人民日报 / 新华社 / 央视新闻 / 光明日报 / 党政机关行文规范"),
        ],
        returns="写作提示列表，如'导语五要素齐全''一段一事段落简短'等",
        example="[TOOL_CALL: get_writing_tips(doc_type=消息, style=新华社)]",
    ),
    ToolDefinition(
        name="get_formulaic",
        description="获取指定文种的格式化用语规范（开头/过渡/结尾的标准表述）",
        category="知识库",
        phase="during_writing",
        parameters=[
            ToolParam("doc_type", "string", True, "文种：批复 / 请示 / 函 / 通知 / 报告 / 纪要"),
        ],
        returns="格式化用语表，按用途分类（如'引据''过渡''结语'）",
        example="[TOOL_CALL: get_formulaic(doc_type=请示)]",
    ),
    ToolDefinition(
        name="get_transitions",
        description="获取指定媒体风格的过渡词和衔接句",
        category="知识库",
        phase="during_writing",
        parameters=[
            ToolParam("style", "string", True, "媒体风格：人民日报 / 新华社 / 央视新闻 / 光明日报 / 党政机关行文规范"),
            ToolParam("count", "int", False, "返回数量，默认3", "3"),
        ],
        returns="过渡词列表",
        example="[TOOL_CALL: get_transitions(style=人民日报, count=3)]",
    ),

    # ── 文种识别工具 ──

    ToolDefinition(
        name="identify_doc_type",
        description="根据写作简报（目的、受众、篇幅、素材）推荐最合适的文种，返回带置信度的排序结果",
        category="文种识别",
        phase="pre_writing",
        parameters=[
            ToolParam("purpose", "string", True, "写作目的"),
            ToolParam("audience", "string", True, "主要受众"),
            ToolParam("length", "int", False, "预期篇幅（字数）"),
            ToolParam("key_materials", "string", False, "核心素材概述"),
        ],
        returns="文种推荐列表，每条含：文种名称、匹配度、结构模式、典型篇幅范围、对标媒体",
        example="[TOOL_CALL: identify_doc_type(purpose=记录研学活动, audience=学院师生, length=2000)]",
    ),
    ToolDefinition(
        name="analyze_materials",
        description="分析素材的内容类型构成（数据型/引语型/场景型/文件型），辅助判断适合的文种和写法",
        category="文种识别",
        phase="pre_writing",
        parameters=[
            ToolParam("key_materials", "string", True, "用户提供的核心素材文本"),
        ],
        returns="素材构成比例，如 {data: 0.3, quotes: 0.4, scenes: 0.2, documents: 0.1}",
        example="[TOOL_CALL: analyze_materials(key_materials=用户填写的素材内容)]",
    ),

    # ── 风格适配工具 ──

    ToolDefinition(
        name="list_styles",
        description="列出所有可选的媒体风格及其特征（情感基调/数据密度/文学性/政策关联度）",
        category="风格适配",
        phase="pre_writing",
        parameters=[],
        returns="风格列表，每个含：名称、特征描述、适用场景",
        example="[TOOL_CALL: list_styles()]",
    ),
    ToolDefinition(
        name="auto_select_style",
        description="根据受众和写作目的自动推荐最合适的媒体风格",
        category="风格适配",
        phase="pre_writing",
        parameters=[
            ToolParam("audience", "string", True, "主要受众，如'学院领导'、'社会公众'、'学生群体'"),
            ToolParam("purpose", "string", True, "写作目的，如'汇报成果'、'宣传推广'、'传达精神'"),
        ],
        returns="推荐风格名称及理由",
        example="[TOOL_CALL: auto_select_style(audience=学院领导, purpose=汇报成果)]",
    ),
    ToolDefinition(
        name="suggest_style_blend",
        description="当单一受众/场景难以匹配风格时，基于受众与写作目的建议混合风格方案（如70%人民日报+30%新华社）",
        category="风格适配",
        phase="pre_writing",
        parameters=[
            ToolParam("primary_audience", "string", True, "主要受众，如'学院领导'、'社会公众'、'学生群体'"),
            ToolParam("purpose", "string", True, "写作目的，如'汇报成果'、'宣传推广'、'传达精神'"),
            ToolParam("secondary_audiences", "string", False, "次要受众，多个用'|'分隔"),
        ],
        returns="混合风格方案：主副风格比例、混合后特征、适用场景",
        example="[TOOL_CALL: suggest_style_blend(primary_audience=学院领导, purpose=汇报成果, secondary_audiences=学生群体)]",
    ),

    # ── 个性化工具 ──

    ToolDefinition(
        name="get_memory_summary",
        description="获取当前用户的历史偏好、常见错误和项目记忆，辅助个性化写作",
        category="个性化",
        phase="pre_writing",
        parameters=[
            ToolParam("project_id", "string", False, "项目ID，传入时同时返回项目级记忆"),
        ],
        returns="记忆摘要：常用模式/文种/风格、常见优势、历史错误、禁用词、记忆笔记",
        example="[TOOL_CALL: get_memory_summary(project_id=proj_abc123)]",
    ),
    ToolDefinition(
        name="get_style_recommendation",
        description="基于用户历史偏好和当前项目信息，推荐风格并提供 bias 预警和创新建议",
        category="个性化",
        phase="pre_writing",
        parameters=[
            ToolParam("project_id", "string", True, "当前项目ID"),
        ],
        returns="推荐结果：建议风格、推荐词汇、bias 预警、创新角度",
        example="[TOOL_CALL: get_style_recommendation(project_id=proj_abc123)]",
    ),
    ToolDefinition(
        name="analyze_weaknesses",
        description="分析初稿的弱点：篇幅、结构、空泛表述、禁用词、缺少战略锚点等",
        category="个性化",
        phase="post_writing",
        parameters=[
            ToolParam("project_id", "string", True, "当前项目ID"),
            ToolParam("draft", "string", True, "初稿文本"),
        ],
        returns="弱点列表，如'篇幅偏短''使用了空泛表态''缺少战略锚点句'等",
        example="[TOOL_CALL: analyze_weaknesses(project_id=proj_abc123, draft=初稿内容)]",
    ),

    # ── 导入工具 ──

    ToolDefinition(
        name="import_from_url",
        description="从网页URL导入参考文档，自动提取标题/正文/作者/日期/关键词/风格特征",
        category="导入",
        phase="pre_writing",
        parameters=[
            ToolParam("url", "string", True, "要导入的网页URL"),
        ],
        returns="导入结果：标题、来源、正文、格式类型（新闻/公文/报告）、关键词、风格特征",
        example="[TOOL_CALL: import_from_url(url=https://example.com/article)]",
    ),
    ToolDefinition(
        name="import_from_text",
        description="从用户粘贴的文本导入参考文档，自动识别格式、提取关键词和风格特征，并保存到项目资料库",
        category="导入",
        phase="pre_writing",
        parameters=[
            ToolParam("title", "string", True, "文档标题"),
            ToolParam("content", "string", True, "文档正文"),
            ToolParam("source", "string", False, "来源说明", "手动导入"),
            ToolParam("project_id", "string", False, "项目ID，传入时同步保存到该项目资料库"),
        ],
        returns="导入结果：格式类型、关键词、语言特征",
        example="[TOOL_CALL: import_from_text(title=参考文章, content=文章正文, project_id=proj_abc123)]",
    ),
]


# ═══════════════════════════════════════════════════════════════
# 工具定义注入函数
# ==================================================================

def get_tool_definitions_for_prompt(phases: Optional[List[str]] = None) -> str:
    """
    生成工具声明文本，用于注入到系统提示词中。

    让 LLM 知道有哪些工具可用、每个工具做什么、怎么调用。
    LLM 可在输出中用 [TOOL_CALL: ...] 标记建议调用工具，
    由代码解析执行后将结果返回给 LLM。

    Args:
        phases: 仅注入指定阶段的工具（如 ["pre_writing", "during_writing"]）；
                None 表示全量注入（默认，保持向后兼容）。
    """
    selected = set(phases) if phases else None

    lines = ["# 可用工具", ""]
    lines.append("以下工具可在写作过程中调用。需要调用时，在输出中插入标记：")
    lines.append("  [TOOL_CALL: 工具名(参数1=值1, 参数2=值2)]")
    lines.append("系统会执行该工具，把结果返回给你，你再继续。")
    lines.append("")

    # 按阶段分组
    phases_order = [
        ("pre_writing", "写作前（规划准备阶段）"),
        ("during_writing", "写作中（生成阶段）"),
        ("post_writing", "写作后（审查阶段）"),
    ]

    for phase_key, phase_label in phases_order:
        if selected and phase_key not in selected:
            continue
        phase_tools = get_tools_by_phase(phase_key)
        if not phase_tools:
            continue
        lines.append(f"## {phase_label}")
        lines.append("")
        for tool in phase_tools:
            lines.append(f"### {tool.name}")
            lines.append(f"功能：{tool.description}")
            lines.append(f"来源：{tool.category}")
            if tool.parameters:
                lines.append("参数：")
                for p in tool.parameters:
                    req = "必填" if p.required else "可选"
                    default = f"，默认'{p.default}'" if p.default else ""
                    lines.append(f"  - {p.name}（{p.type}，{req}）：{p.description}{default}")
            else:
                lines.append("参数：无")
            lines.append(f"返回：{tool.returns}")
            lines.append(f"示例：{tool.example}")
            lines.append("")

    return "\n".join(lines)


def get_tool_call_format() -> str:
    """返回工具调用格式说明（简短版，用于系统提示词头部）"""
    return (
        "# 工具调用\n"
        "写作过程中可调用工具辅助决策。调用方式：在输出中插入 [TOOL_CALL: 工具名(参数=值)]，"
        "系统执行后返回结果。具体工具列表见下方'可用工具'部分。"
    )


def parse_tool_call(text: str):
    """
    从 LLM 输出中解析工具调用标记。

    Args:
        text: LLM 的输出文本

    Returns:
        list of (tool_name, params_dict)，如果没有工具调用则返回空列表
    """
    import re
    calls = []
    # 匹配 [TOOL_CALL: tool_name(key=value, key2=value2)]
    # 用非贪婪 .*? 配合 )\s*\] 锚定：避免参数值含半角 ) 时被 [^)]* 提前截断
    pattern = r'\[TOOL_CALL:\s*(\w+)\s*\((.*?)\)\s*\]'
    for match in re.finditer(pattern, text, re.DOTALL):
        tool_name = match.group(1)
        params_str = match.group(2).strip()
        params = {}
        if params_str:
            # 按 ", key=" 模式切分参数：只有逗号后紧跟"标识符="才视为参数分隔符，
            # 避免参数值中的逗号（含英文逗号）被误切导致值截断
            param_pattern = r'(\w+)\s*=\s*(.*?)(?=\s*,\s*\w+\s*=|$)'
            for pm in re.finditer(param_pattern, params_str, re.DOTALL):
                k = pm.group(1).strip()
                v = pm.group(2).strip().strip("'\"")
                params[k] = v
        calls.append((tool_name, params))
    return calls


def get_tool_by_name(name: str) -> ToolDefinition:
    """按名称查找工具定义"""
    for tool in TOOL_DEFINITIONS:
        if tool.name == name:
            return tool
    return None


def get_tools_by_phase(phase: str) -> List[ToolDefinition]:
    """按阶段查找工具"""
    return [t for t in TOOL_DEFINITIONS if t.phase == phase]


def get_tools_by_category(category: str) -> List[ToolDefinition]:
    """按来源分类查找工具"""
    return [t for t in TOOL_DEFINITIONS if t.category == category]
