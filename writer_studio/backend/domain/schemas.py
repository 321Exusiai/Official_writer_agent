"""领域数据模型 —— 全系统唯一数据真相（Pydantic v2）。

前后端共享字段命名；`core/` 领域逻辑与 `api/` 路由均消费本模块。
"""
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ProjectStatus(str, Enum):
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
    secondary_audiences: List[str] = Field(default_factory=list)
    deep_meaning: str = ""
    strategic_anchor: str = ""
    opportunity_context: str = ""
    key_materials: str = ""
    differentiator: str = ""
    length_hint: Optional[int] = None
    style_intensity: float = 1.0
    raw_answers: Dict[str, str] = Field(default_factory=dict)


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
    length_hint: Optional[int] = None
    iteration_count: int = 0
    draft_version: int = 0
    previous_issues: str = ""


class ReviewSeverity(str, Enum):
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
    findings: List[ReviewFinding] = Field(default_factory=list)
    dimension_scores: List[dict] = Field(default_factory=list)  # [{name, weight, score, deducted}]
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


class Project(BaseModel):
    id: str = ""
    name: str = ""
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    brief: Optional[Brief] = None
    plan: Optional[Plan] = None
    draft: str = ""
    final_draft: str = ""
    versions: List[DocVersion] = Field(default_factory=list)
    review_results: List[ReviewResult] = Field(default_factory=list)
    review_history: List[ReviewResult] = Field(default_factory=list)  # 多次写作的累计审查历史
    references: List[ReferenceArticle] = Field(default_factory=list)  # 项目参考文本（唯一归属）
    favorite_terms: List[str] = Field(default_factory=list)    # 项目级收藏：词汇
    favorite_phrases: List[str] = Field(default_factory=list)  # 项目级收藏：句子
    style_requirements: str = ""      # 项目风格要求
    work_requirements: str = ""       # 工作要求
    questionnaire_summary: str = ""   # 问卷总结（AI 生成）
    created_at: str = ""
    updated_at: str = ""


class UserProfile(BaseModel):
    """用户画像与综合收藏夹（参考文本统一归属项目）。"""

    id: str = "user_self"
    name: str = "我"
    preferences: List[str] = Field(default_factory=list)      # 写作偏好（如"喜欢短句""避免官方腔"）
    weaknesses: List[str] = Field(default_factory=list)       # 常见弱点
    bias_warnings: List[str] = Field(default_factory=list)    # 潜在 bias 预警
    favorite_terms: List[str] = Field(default_factory=list)   # 综合收藏夹：词汇
    favorite_phrases: List[str] = Field(default_factory=list) # 综合收藏夹：句子
    created_at: str = ""
    updated_at: str = ""


class WorkflowEvent(BaseModel):
    seq: int = 0
    type: str = ""
    step: str = ""
    payload: Dict[str, Any] = Field(default_factory=dict)
    ts: float = 0.0


class AgentResponse(BaseModel):
    role: str = ""
    concerns: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
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
