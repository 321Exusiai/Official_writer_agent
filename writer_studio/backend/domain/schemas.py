"""领域数据模型 —— 全系统唯一数据真相（Pydantic v2）。

前后端共享字段命名；`core/` 领域逻辑与 `api/` 路由均消费本模块。
"""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):  # noqa: UP042 — 需与 JSON 字符串直接比较/序列化
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


class Brief(BaseModel):
    """写作简报：问卷系统的产出、所有下游模块的输入。"""

    writing_mode: str = ""
    subtype: str = ""
    purpose: str = ""
    primary_audience: str = ""
    secondary_audiences: list[str] = Field(default_factory=list)
    deep_meaning: str = ""
    strategic_anchor: str = ""
    opportunity_context: str = ""
    key_materials: str = ""
    differentiator: str = ""
    length_hint: int | None = None
    style_intensity: float = 1.0
    raw_answers: dict[str, str] = Field(default_factory=dict)


class Plan(BaseModel):
    """写作方案：文种/风格/结构大纲。"""

    doc_type: str = ""
    media_style: str = ""
    audience_focus: str = "external"
    estimated_length: str = ""
    structure_outline: str = ""
    writing_mode: str = ""


class EnvState(BaseModel):
    """环境状态：注入 LLM 的工作流上下文。"""

    writing_mode: str = ""
    mode_value: str = ""
    subtype: str = ""
    stage: str = ""
    doc_type: str = ""
    media_style: str = ""
    style_intensity: float = 1.0
    purpose: str = ""
    primary_audience: str = ""
    length_hint: int | None = None
    iteration_count: int = 0
    draft_version: int = 0
    previous_issues: str = ""


class ReviewSeverity(str, Enum):  # noqa: UP042 — 需与 JSON 字符串直接比较/序列化
    CRITICAL = "critical"
    MAJOR = "major"
    MINOR = "minor"
    SUGGESTION = "suggestion"


class ReviewFinding(BaseModel):
    round_name: str = ""
    severity: ReviewSeverity = ReviewSeverity.MINOR
    location: str = ""
    issue: str = ""
    suggestion: str = ""
    error_key: str = ""
    source: str = "rule"  # rule | llm
    dimension: str = ""  # 维度标签（语言/事实/格式/结构/主体性/客观性/表达）


class ReviewResult(BaseModel):
    round_name: str = ""
    passed: bool = True
    score: float = 100.0
    findings: list[ReviewFinding] = Field(default_factory=list)
    dimension_scores: list[dict] = Field(default_factory=list)  # [{name, weight, score, deducted}]
    thought_bubbles: list[dict] = Field(default_factory=list)  # 专家思维透明度气泡 [{role, role_name, emoji, thought}]
    draft_version: int = 0


class DocVersion(BaseModel):
    doc_type: str = ""
    doc_type_name: str = ""
    content: str = ""
    word_count: int = 0
    generation_order: int = 0
    extracted_from: str = ""


class ReferenceArticle(BaseModel):
    id: str = ""
    title: str = ""
    content: str = ""
    source: str = ""
    created_at: str = ""
    analysis: str = ""  # AI 解读：词汇/句式/表达方式/写作风格


class Revision(BaseModel):
    """时光机版本快照。"""

    id: str = ""
    timestamp: str = ""
    summary: str = ""
    draft_snapshot: str = ""
    score: float | None = None
    source: str = "manual"  # manual | auto_heal | ai_rewrite | chunk_draft


class CustomKnowledgeItem(BaseModel):
    """单位专有知识库条目。"""

    id: str = ""
    title: str = ""
    content: str = ""
    category: str = "policy"  # policy | speech | exemplar | rule
    tags: list[str] = Field(default_factory=list)
    source: str = ""
    created_at: str = ""


class TemplateConfig(BaseModel):
    """公文格式模板配置（支持 GB/T 9704-2012 及单位自定义规范）。"""

    id: str = "default_gbt9704"
    name: str = "GB/T 9704-2012 国家公文标准规范"
    top_margin_mm: float = 37.0
    bottom_margin_mm: float = 35.0
    left_margin_mm: float = 28.0
    right_margin_mm: float = 26.0
    title_font: str = "方正小标宋_GB2312"
    title_size_pt: float = 22.0  # 二号
    body_font: str = "仿宋_GB2312"
    body_size_pt: float = 16.0   # 三号
    line_spacing_pt: float = 28.0  # 固定行距 28 磅
    header_text: str = ""  # 红头/发文机关名称（如"XX省人民政府文件"）
    doc_code: str = ""     # 发文字号（如"X府发〔2025〕1号"）


class Project(BaseModel):
    """项目状态 —— 领域层与持久化层的单一结构真相。"""

    id: str
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    mode_value: str = ""  # 历史兼容
    writing_mode: str = ""  # 统一使用 writing_mode
    doc_type: str = ""
    media_style: str = ""
    style_intensity: float = 1.0
    brief: Brief = Field(default_factory=Brief)
    plan: Plan = Field(default_factory=Plan)
    draft: str = ""
    final_draft: str = ""
    versions: list[DocVersion] = Field(default_factory=list)
    revisions: list[Revision] = Field(default_factory=list)  # 时光机版本快照树
    review_results: list[ReviewResult] = Field(default_factory=list)
    review_history: list[ReviewResult] = Field(default_factory=list)  # 多次写作的累计审查历史
    healing_history: list[dict] = Field(default_factory=list)  # 自愈收敛历史记录
    custom_role_weights: dict[str, float] = Field(default_factory=dict)  # 用户微调的专家权威权重
    red_team_result: dict[str, Any] | None = None  # 模拟分管领导与舆情红蓝军审签压力测试报告
    template_config: TemplateConfig | None = None  # 绑定的公文排版模板
    references: list[ReferenceArticle] = Field(default_factory=list)  # 项目参考文本（唯一归属）
    favorite_terms: list[str] = Field(default_factory=list)  # 项目级收藏：词汇
    favorite_phrases: list[str] = Field(default_factory=list)  # 项目级收藏：句子
    style_requirements: str = ""  # 项目风格要求
    work_requirements: str = ""  # 工作要求
    scratchpad: list[str] = Field(default_factory=list)  # 写作灵感备忘录（助手提炼/用户指示/即时要点）
    questionnaire_summary: str = ""  # 问卷总结（AI 生成）
    created_at: str = ""
    updated_at: str = ""


class UserProfile(BaseModel):
    """用户画像与综合收藏夹（参考文本统一归属项目）。"""

    id: str = "user_self"
    name: str = "我"
    coach_mode: bool = True  # 公文私教教学模式开关：解释"为什么这么写/这么改"
    preferences: list[str] = Field(default_factory=list)  # 写作偏好（如"喜欢短句""避免官方腔"）
    memory_enabled: bool = True  # 助手对话长期记忆开关：自动提炼偏好
    weaknesses: list[str] = Field(default_factory=list)  # 常见弱点
    bias_warnings: list[str] = Field(default_factory=list)  # 潜在 bias 预警
    favorite_terms: list[str] = Field(default_factory=list)  # 综合收藏夹：词汇
    favorite_phrases: list[str] = Field(default_factory=list)  # 综合收藏夹：句子
    created_at: str = ""
    updated_at: str = ""


class WorkflowEvent(BaseModel):
    seq: int = 0
    type: str = ""
    step: str = ""
    payload: dict[str, Any] = Field(default_factory=dict)
    ts: float = 0.0


class AgentResponse(BaseModel):
    role: str = ""
    concerns: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    mode: str = "rule"  # llm | rule


class LLMConfig(BaseModel):
    name: str = "默认配置"
    provider: str = "openai"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000
    enabled: bool = False
    # 联网搜索（可选）：填 key 启用运行时联网检索最新政策/讲话
    search_provider: str = "tavily"
    search_api_key: str = ""


class AssistantConfig(BaseModel):
    """辅助轨道配置（免费 GLM-4-Flash）：内部轻任务，随叫随到的小帮手。"""

    enabled: bool = False
    provider: str = "zhipu"
    api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    api_key: str = ""
    model: str = "glm-4-flash"
    temperature: float = 0.3
    max_tokens: int = 2000
