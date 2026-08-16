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


class ReviewResult(BaseModel):
    round_name: str = ""
    passed: bool = True
    score: float = 100.0
    findings: List[ReviewFinding] = Field(default_factory=list)
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
    references: List[ReferenceArticle] = Field(default_factory=list)
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
    provider: str = "openai"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000
    enabled: bool = False
