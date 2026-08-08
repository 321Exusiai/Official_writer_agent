"""
个性化数据库模块 — 多级存储 + 记忆功能

设计目标：
1. 用户整体面貌（User Profile）
   - 基本信息、写作偏好、常用文种、常用风格
   - 历史写作记录、常见错误模式
   - 反bias分析结果

2. 用户项目/工作（Project）
   - 每个项目包含：
     a. 问卷填写结果
     b. 文章风格要求（支持用户上传参考文章）
     c. 当前需要用到的词汇和语料
     d. 用户要求 + 反向思考（避免bias、提出创新性看法）

3. 记忆功能
   - 记录用户历史选择、偏好、修改习惯
   - 根据记忆动态调整推荐和建议
   - 支持"温度"调节（temperature）用于创新性看法

层级结构：
  User Profile
    ├── Preferences (写作偏好)
    ├── History (历史写作记录)
    ├── AntiBiasProfile (反bias分析)
    └── Projects[] (多个项目)
         ├── QuestionnaireResults (问卷结果)
         ├── StyleRequirements (风格要求 + 参考文章)
         ├── VocabularyCorpus (当前词汇语料)
         └── UserRequirements (用户要求 + 反向分析)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
from collections import Counter
import json
import uuid
import time


class ProjectStatus(Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    ARCHIVED = "archived"


@dataclass
class ReferenceArticle:
    """用户上传的参考文章"""
    id: str
    title: str
    content: str
    upload_time: str
    style_notes: str = ""
    extracted_patterns: List[str] = field(default_factory=list)


@dataclass
class VocabularyCorpus:
    """项目级别的词汇和语料库"""
    id: str
    project_id: str
    custom_terms: List[str] = field(default_factory=list)
    custom_phrases: List[str] = field(default_factory=list)
    forbidden_words: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    style_vocabulary: Dict[str, List[str]] = field(default_factory=dict)
    created_at: str = ""
    updated_at: str = ""


@dataclass
class AntiBiasAnalysis:
    """反bias分析结果 — 避免用户主观偏见，提出创新性看法"""
    id: str
    user_bias_patterns: List[str] = field(default_factory=list)
    counter_perspectives: List[str] = field(default_factory=list)
    innovative_angles: List[str] = field(default_factory=list)
    temperature_adjustment: float = 1.0
    analysis_notes: str = ""
    created_at: str = ""


@dataclass
class UserRequirement:
    """用户对项目/文章的具体要求"""
    id: str
    description: str
    priority: str = "normal"
    anti_bias_analysis: Optional[AntiBiasAnalysis] = None
    creative_suggestions: List[str] = field(default_factory=list)
    weakness_analysis: str = ""
    created_at: str = ""


@dataclass
class QuestionnaireResults:
    """问卷填写结果存储"""
    writing_mode: str = ""
    doc_type: str = ""
    style: str = ""
    purpose: str = ""
    primary_audience: str = ""
    secondary_audiences: List[str] = field(default_factory=list)
    deep_meaning: str = ""
    strategic_anchor: str = ""
    key_materials: str = ""
    differentiator: str = ""
    raw_answers: Dict[str, str] = field(default_factory=dict)


@dataclass
class Project:
    """用户项目/工作 — 包含所有与该项目相关的信息"""
    id: str
    name: str
    description: str = ""
    status: ProjectStatus = ProjectStatus.DRAFT
    created_at: str = ""
    updated_at: str = ""

    questionnaire_results: Optional[QuestionnaireResults] = None
    style_requirements: List[ReferenceArticle] = field(default_factory=list)
    vocabulary_corpus: Optional[VocabularyCorpus] = None
    user_requirements: List[UserRequirement] = field(default_factory=list)
    anti_bias_profile: Optional[AntiBiasAnalysis] = None

    writing_history: List[Dict[str, Any]] = field(default_factory=list)
    revision_count: int = 0
    tags: List[str] = field(default_factory=list)


@dataclass
class WritingHistory:
    """用户历史写作记录"""
    id: str
    project_id: str
    writing_mode: str
    doc_type: str
    style: str
    created_at: str
    word_count: int = 0
    review_findings: List[Dict[str, str]] = field(default_factory=list)
    common_errors: List[str] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)


@dataclass
class UserPreferences:
    """用户写作偏好"""
    preferred_writing_modes: List[str] = field(default_factory=list)
    preferred_doc_types: List[str] = field(default_factory=list)
    preferred_styles: List[str] = field(default_factory=list)
    typical_length_range: tuple = (800, 2000)
    writing_frequency: str = ""
    common_themes: List[str] = field(default_factory=list)
    forbidden_patterns: List[str] = field(default_factory=list)
    preferred_transitions: List[str] = field(default_factory=list)


@dataclass
class UserProfile:
    """用户整体面貌 — 顶级存储"""
    id: str
    name: str
    created_at: str = ""
    last_active: str = ""

    preferences: Optional[UserPreferences] = None
    writing_history: List[WritingHistory] = field(default_factory=list)
    common_error_patterns: List[Dict[str, str]] = field(default_factory=list)
    common_strengths: List[str] = field(default_factory=list)

    projects: List[Project] = field(default_factory=list)
    global_anti_bias: Optional[AntiBiasAnalysis] = None

    memory_notes: str = ""


class PersonalizedDB:
    """
    个性化数据库管理器

    提供多级存储和记忆功能：
    - 用户级：UserProfile
    - 项目级：Project
    - 项目内：问卷结果、风格要求、词汇语料、用户要求
    - 记忆：历史偏好、反bias分析、动态调整
    """

    def __init__(self):
        self.profiles: Dict[str, UserProfile] = {}
        self.current_user_id: Optional[str] = None

    # ═══ 用户管理 ═══

    def create_user(self, name: str, preferences: Optional[UserPreferences] = None) -> UserProfile:
        user_id = f"user_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        profile = UserProfile(
            id=user_id,
            name=name,
            created_at=now,
            last_active=now,
            preferences=preferences or UserPreferences(),
        )

        self.profiles[user_id] = profile
        self.current_user_id = user_id
        return profile

    def get_user(self, user_id: str) -> Optional[UserProfile]:
        return self.profiles.get(user_id)

    def get_current_user(self) -> Optional[UserProfile]:
        if self.current_user_id:
            return self.profiles.get(self.current_user_id)
        return None

    def set_current_user(self, user_id: str):
        self.current_user_id = user_id
        if user_id in self.profiles:
            self.profiles[user_id].last_active = datetime.now().isoformat()

    # ═══ 项目管理 ═══

    def create_project(self, name: str, description: str = "", tags: Optional[List[str]] = None) -> Project:
        user = self.get_current_user()
        if not user:
            raise ValueError("请先创建或选择用户")

        project_id = f"proj_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        project = Project(
            id=project_id,
            name=name,
            description=description,
            status=ProjectStatus.DRAFT,
            created_at=now,
            updated_at=now,
            tags=tags or [],
        )

        user.projects.append(project)
        user.last_active = now
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        user = self.get_current_user()
        if not user:
            return None
        for proj in user.projects:
            if proj.id == project_id:
                return proj
        return None

    def list_projects(self, status: Optional[ProjectStatus] = None) -> List[Project]:
        user = self.get_current_user()
        if not user:
            return []
        if status:
            return [p for p in user.projects if p.status == status]
        return user.projects

    def update_project_status(self, project_id: str, status: ProjectStatus):
        project = self.get_project(project_id)
        if project:
            project.status = status
            project.updated_at = datetime.now().isoformat()

    def delete_project(self, project_id: str) -> bool:
        """删除项目"""
        user = self.get_current_user()
        if not user:
            raise ValueError("请先创建或选择用户")
        
        for i, proj in enumerate(user.projects):
            if proj.id == project_id:
                user.projects.pop(i)
                user.last_active = datetime.now().isoformat()
                return True
        return False

    def edit_project(self, project_id: str, name: str = "", description: str = "",
                     status: Optional[ProjectStatus] = None, tags: Optional[List[str]] = None) -> bool:
        """编辑项目信息"""
        project = self.get_project(project_id)
        if not project:
            return False
        if name is not None and name.strip():
            project.name = name
        if description is not None:
            project.description = description
        if status:
            project.status = status
        if tags is not None:
            project.tags = tags
        project.updated_at = datetime.now().isoformat()
        return True

    # ═══ 问卷结果管理 ═══

    def save_questionnaire_results(self, project_id: str, results: QuestionnaireResults):
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        project.questionnaire_results = results
        project.updated_at = datetime.now().isoformat()

        self._update_user_preferences_from_questionnaire(results)

    def get_questionnaire_results(self, project_id: str) -> Optional[QuestionnaireResults]:
        project = self.get_project(project_id)
        return project.questionnaire_results if project else None

    def _update_user_preferences_from_questionnaire(self, results: QuestionnaireResults):
        user = self.get_current_user()
        if not user or not user.preferences:
            return

        if results.writing_mode and results.writing_mode not in user.preferences.preferred_writing_modes:
            user.preferences.preferred_writing_modes.append(results.writing_mode)

        if results.doc_type and results.doc_type not in user.preferences.preferred_doc_types:
            user.preferences.preferred_doc_types.append(results.doc_type)

        if results.style and results.style not in user.preferences.preferred_styles:
            user.preferences.preferred_styles.append(results.style)

    # ═══ 参考文章管理 ═══

    def add_reference_article(self, project_id: str, title: str, content: str, style_notes: str = "") -> ReferenceArticle:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        article = ReferenceArticle(
            id=f"ref_{uuid.uuid4().hex[:8]}",
            title=title,
            content=content,
            upload_time=datetime.now().isoformat(),
            style_notes=style_notes,
        )

        project.style_requirements.append(article)
        project.updated_at = datetime.now().isoformat()
        return article

    def add_url_reference(self, project_id: str, url: str, title: str = "", content: str = "",
                          source_site: str = "", style_notes: str = "",
                          auto_fetch: bool = True) -> ReferenceArticle:
        """
        从 URL 添加参考文章到项目

        Args:
            project_id: 项目 ID
            url: 目标 URL
            title: 标题（留空则自动提取）
            content: 内容（留空则自动抓取）
            source_site: 来源网站
            style_notes: 风格备注
            auto_fetch: 是否自动抓取（当 title/content 为空时）

        Returns:
            ReferenceArticle 对象
        """
        from src.utils.url_importer import URLDocumentImporter

        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        article_title = title
        article_content = content

        if auto_fetch and (not title or not content):
            try:
                importer = URLDocumentImporter()
                doc = importer.import_from_url(url)
                article_title = article_title or doc.title
                article_content = article_content or doc.content
                source_site = source_site or doc.source_site
                style_notes = style_notes or "\n".join(doc.style_patterns)
            except Exception:
                fetch_fail_note = "自动抓取失败：无法从该URL获取内容，请手动填写标题和正文"
                style_notes = f"{style_notes}\n{fetch_fail_note}" if style_notes else fetch_fail_note

        article = ReferenceArticle(
            id=f"ref_{uuid.uuid4().hex[:8]}",
            title=article_title or "未知标题",
            content=article_content or "",
            upload_time=datetime.now().isoformat(),
            style_notes=style_notes,
        )

        project.style_requirements.append(article)
        project.updated_at = datetime.now().isoformat()
        return article

    def add_batch_urls(self, project_id: str, urls: List[str], delay: float = 1.0) -> List[ReferenceArticle]:
        """
        批量从 URL 添加参考文章

        Args:
            project_id: 项目 ID
            urls: URL 列表
            delay: 请求间隔（秒）

        Returns:
            ReferenceArticle 列表
        """
        articles = []
        for url in urls:
            article = self.add_url_reference(project_id, url, auto_fetch=True)
            articles.append(article)
            if delay > 0:
                time.sleep(delay)
        return articles

    def extract_patterns_from_article(self, article: ReferenceArticle) -> List[str]:
        """从用户上传的参考文章中提取风格模式"""
        patterns = []
        content = article.content

        if len(content) < 500:
            return patterns

        sentences = [s for s in content.split("。") if s.strip()]
        if sentences:
            avg_len = len(content) / len(sentences)
            if avg_len < 30:
                patterns.append("多使用短句（平均{}字/句）".format(int(avg_len)))
            elif avg_len > 60:
                patterns.append("多使用长句（平均{}字/句）".format(int(avg_len)))

        opening = content[:200]
        if any(kw in opening for kw in ["近日", "日前", "X月X日"]):
            patterns.append("开篇使用时间锚点")

        if "指出" in content or "强调" in content or "要求" in content:
            patterns.append("使用格式化引述用语")

        if "一是" in content or "二是" in content:
            patterns.append("使用序号分条结构")

        article.extracted_patterns = patterns
        return patterns

    # ═══ 词汇语料管理 ═══

    def create_vocabulary_corpus(self, project_id: str) -> VocabularyCorpus:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        now = datetime.now().isoformat()
        corpus = VocabularyCorpus(
            id=f"vocab_{uuid.uuid4().hex[:8]}",
            project_id=project_id,
            created_at=now,
            updated_at=now,
        )

        project.vocabulary_corpus = corpus
        project.updated_at = now
        return corpus

    def add_custom_term(self, project_id: str, term: str):
        corpus = self._get_or_create_corpus(project_id)
        if term not in corpus.custom_terms:
            corpus.custom_terms.append(term)
            corpus.updated_at = datetime.now().isoformat()

    def add_forbidden_word(self, project_id: str, word: str):
        corpus = self._get_or_create_corpus(project_id)
        if word not in corpus.forbidden_words:
            corpus.forbidden_words.append(word)
            corpus.updated_at = datetime.now().isoformat()

    def add_required_keyword(self, project_id: str, keyword: str):
        corpus = self._get_or_create_corpus(project_id)
        if keyword not in corpus.required_keywords:
            corpus.required_keywords.append(keyword)
            corpus.updated_at = datetime.now().isoformat()

    def _get_or_create_corpus(self, project_id: str) -> VocabularyCorpus:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")
        if not project.vocabulary_corpus:
            return self.create_vocabulary_corpus(project_id)
        return project.vocabulary_corpus

    # ═══ 用户要求与反bias分析 ═══

    def add_user_requirement(
        self,
        project_id: str,
        description: str,
        priority: str = "normal",
        enable_anti_bias: bool = True,
    ) -> UserRequirement:
        project = self.get_project(project_id)
        if not project:
            raise ValueError(f"项目 {project_id} 不存在")

        req = UserRequirement(
            id=f"req_{uuid.uuid4().hex[:8]}",
            description=description,
            priority=priority,
            created_at=datetime.now().isoformat(),
        )

        if enable_anti_bias:
            req.anti_bias_analysis = self._analyze_anti_bias(description, project)

        project.user_requirements.append(req)
        project.updated_at = datetime.now().isoformat()
        return req

    def _analyze_anti_bias(self, requirement: str, project: Project) -> AntiBiasAnalysis:
        """
        反bias分析 — 结合用户画像反向思考
        避免偏见，提出反向看法和创新型看法（提高temperature）
        分析文章可能的缺点
        """
        analysis = AntiBiasAnalysis(
            id=f"bias_{uuid.uuid4().hex[:8]}",
            created_at=datetime.now().isoformat(),
        )

        bias_patterns = []
        counter_perspectives = []
        innovative_angles = []

        user = self.get_current_user()

        if "正面" in requirement or "宣传" in requirement or "表彰" in requirement:
            bias_patterns.append("可能存在'只写优点不写缺点'的倾向")
            counter_perspectives.append("尝试加入1-2个'不完美但真实'的细节，增加可信度")
            innovative_angles.append("用'问题导向'替代'成绩导向'——先写不足，再写改进")

        if "总结" in requirement or "汇报" in requirement:
            bias_patterns.append("容易写成流水账，缺乏战略高度")
            counter_perspectives.append("用'战略叙事'替代'事项罗列'——每件事回答'为什么重要'")
            innovative_angles.append("加入'横向对比'——不仅和自己比，也和同行/标杆比")

        if "通知" in requirement or "请示" in requirement:
            bias_patterns.append("可能过度使用套话开头（'为贯彻落实……'）")
            counter_perspectives.append("尝试开门见山，直接说事项，减少铺垫")
            innovative_angles.append("用'问题导向'开头——先说问题，再说方案")

        if user and user.common_error_patterns:
            for err in user.common_error_patterns:
                bias_patterns.append(f"历史常见错误：{err.get('name', '')}")

        analysis.user_bias_patterns = bias_patterns
        analysis.counter_perspectives = counter_perspectives
        analysis.innovative_angles = innovative_angles
        analysis.temperature_adjustment = 1.2 if bias_patterns else 1.0
        analysis.analysis_notes = f"检测到 {len(bias_patterns)} 个潜在bias模式"

        return analysis

    def analyze_weaknesses(self, project_id: str, draft: str) -> str:
        """分析文章缺点"""
        project = self.get_project(project_id)
        if not project:
            return ""

        weaknesses = []

        if len(draft) < 500:
            weaknesses.append("篇幅偏短，可能缺乏深度和细节")

        if draft.count("。") < 10:
            weaknesses.append("段落过少，结构可能不够清晰")

        if "大家纷纷" in draft or "一致认为" in draft:
            weaknesses.append("使用了空泛表态，缺乏具体感言支撑")

        if "圆满" in draft or "顺利" in draft:
            weaknesses.append("使用了评价性词汇，建议用事实替代评价")

        if project.vocabulary_corpus and project.vocabulary_corpus.forbidden_words:
            for word in project.vocabulary_corpus.forbidden_words:
                if word in draft:
                    weaknesses.append(f"使用了禁用词汇：'{word}'")

        if project.questionnaire_results:
            qr = project.questionnaire_results
            if qr.writing_mode == "strategic_narrative":
                if not any(kw in draft for kw in ["战略", "部署", "培养", "理念"]):
                    weaknesses.append("缺少战略锚点句，未回扣培养理念或战略部署")

        return "\n".join(weaknesses) if weaknesses else "未发现明显缺点"

    # ═══ 记忆功能 ═══

    def add_to_memory(self, project_id: str, note: str):
        """添加记忆笔记"""
        user = self.get_current_user()
        if not user:
            return

        project = self.get_project(project_id)
        if project:
            project.updated_at = datetime.now().isoformat()

        if user.memory_notes:
            user.memory_notes += "\n" + note
        else:
            user.memory_notes = note

    def get_memory_summary(self, project_id: Optional[str] = None, focus: str = "full") -> str:
        """获取记忆摘要（结构化分类，支持按场景聚焦注入）

        Args:
            project_id: 项目ID，传入时附带项目级记忆
            focus: 注入场景
                - "full": 全部记忆（写作场景默认）
                - "errors": 仅常见错误/弱点/记忆笔记（审查场景，针对性核对）
                - "prefs": 仅偏好类（常用模式/优势/项目信息）
        """
        user = self.get_current_user()
        if not user:
            return "无用户数据"

        sections = self._build_memory_sections(user, project_id)
        if focus == "errors":
            keys = ["常见错误", "记忆笔记"]
        elif focus == "prefs":
            keys = ["用户概览", "偏好", "项目记忆"]
        else:
            keys = list(sections.keys())

        lines = []
        for key in keys:
            body = sections.get(key, "")
            if body:
                lines.append(body)
        return "\n".join(lines) if lines else "无用户数据"

    def _build_memory_sections(self, user, project_id: Optional[str] = None) -> Dict[str, str]:
        """把记忆按类型分类组装，便于按场景选择性注入（修复 1.3 结构化）"""
        sections: Dict[str, str] = {}

        overview = [f"用户：{user.name}", f"项目数：{len(user.projects)}", f"活跃时间：{user.last_active}"]
        sections["用户概览"] = "\n".join(overview)

        prefs_lines = []
        if user.preferences and user.preferences.preferred_writing_modes:
            prefs_lines.append(f"常用写作模式：{', '.join(user.preferences.preferred_writing_modes)}")
        if user.common_strengths:
            prefs_lines.append(f"常见优势：{', '.join(user.common_strengths)}")
        if prefs_lines:
            sections["偏好"] = "\n".join(prefs_lines)

        error_lines = []
        if user.common_error_patterns:
            errs = [e.get("name", "") for e in user.common_error_patterns if e.get("name")]
            if errs:
                error_lines.append(f"常见错误/弱点：{'；'.join(errs)}")
        if user.memory_notes:
            error_lines.append(f"记忆笔记：{user.memory_notes}")
        if error_lines:
            sections["常见错误"] = "\n".join(error_lines)

        if project_id:
            project = self.get_project(project_id)
            if project:
                proj_lines = [f"【项目记忆：{project.name}】", f"状态：{project.status.value}", f"修改次数：{project.revision_count}"]
                if project.questionnaire_results:
                    proj_lines.append(f"写作模式：{project.questionnaire_results.writing_mode}")
                    proj_lines.append(f"文种：{project.questionnaire_results.doc_type}")
                if project.vocabulary_corpus:
                    corpus = project.vocabulary_corpus
                    proj_lines.append(f"自定义术语：{', '.join(corpus.custom_terms[:5])}")
                    proj_lines.append(f"禁用词：{', '.join(corpus.forbidden_words[:5])}")
                sections["项目记忆"] = "\n".join(proj_lines)

        return sections

    # ═══ 智能推荐 ═══

    def get_style_recommendation(self, project_id: str) -> Dict[str, Any]:
        """基于用户历史偏好推荐风格"""
        user = self.get_current_user()
        if not user or not user.preferences:
            return {}

        project = self.get_project(project_id)
        if not project or not project.questionnaire_results:
            return {}

        qr = project.questionnaire_results

        recommendation = {
            "suggested_style": "",
            "suggested_vocabulary": [],
            "suggested_transitions": [],
            "bias_warnings": [],
            "creative_suggestions": [],
        }

        if qr.style:
            recommendation["suggested_style"] = qr.style

        if user.preferences.preferred_styles:
            most_used = Counter(user.preferences.preferred_styles).most_common(1)[0][0]
            if most_used != qr.style:
                recommendation["creative_suggestions"].append(
                    f"您常用{most_used}风格，本次可尝试{qr.style}以丰富写作多样性"
                )

        if project.vocabulary_corpus:
            recommendation["suggested_vocabulary"] = project.vocabulary_corpus.custom_terms[:10]

        if project.user_requirements:
            for req in project.user_requirements:
                if req.anti_bias_analysis:
                    recommendation["bias_warnings"].extend(req.anti_bias_analysis.user_bias_patterns)
                    recommendation["creative_suggestions"].extend(req.anti_bias_analysis.innovative_angles)

        return recommendation

    # ═══ 持久化 ═══

    def export_to_json(self, user_id: Optional[str] = None) -> str:
        """导出用户数据为JSON（完整序列化，含所有持久化字段）"""
        target_id = user_id or self.current_user_id
        if not target_id or target_id not in self.profiles:
            return "{}"

        profile = self.profiles[target_id]

        def serialize_ref_article(a: ReferenceArticle) -> dict:
            return {
                "id": a.id, "title": a.title, "content": a.content,
                "upload_time": a.upload_time, "style_notes": a.style_notes,
                "extracted_patterns": a.extracted_patterns,
            }

        def serialize_anti_bias(ab: AntiBiasAnalysis) -> dict:
            return {
                "id": ab.id,
                "user_bias_patterns": ab.user_bias_patterns,
                "counter_perspectives": ab.counter_perspectives,
                "innovative_angles": ab.innovative_angles,
                "temperature_adjustment": ab.temperature_adjustment,
                "analysis_notes": ab.analysis_notes,
                "created_at": ab.created_at,
            }

        def serialize_user_req(ur: UserRequirement) -> dict:
            return {
                "id": ur.id, "description": ur.description, "priority": ur.priority,
                "anti_bias_analysis": serialize_anti_bias(ur.anti_bias_analysis) if ur.anti_bias_analysis else None,
                "creative_suggestions": ur.creative_suggestions,
                "weakness_analysis": ur.weakness_analysis,
                "created_at": ur.created_at,
            }

        def serialize_qr(qr: QuestionnaireResults) -> dict:
            return {
                "writing_mode": qr.writing_mode, "doc_type": qr.doc_type, "style": qr.style,
                "purpose": qr.purpose, "primary_audience": qr.primary_audience,
                "secondary_audiences": qr.secondary_audiences,
                "deep_meaning": qr.deep_meaning, "strategic_anchor": qr.strategic_anchor,
                "key_materials": qr.key_materials, "differentiator": qr.differentiator,
                "raw_answers": qr.raw_answers,
            }

        def serialize_vocab(vc: VocabularyCorpus) -> dict:
            return {
                "id": vc.id, "project_id": vc.project_id,
                "custom_terms": vc.custom_terms, "custom_phrases": vc.custom_phrases,
                "forbidden_words": vc.forbidden_words, "required_keywords": vc.required_keywords,
                "style_vocabulary": vc.style_vocabulary,
                "created_at": vc.created_at, "updated_at": vc.updated_at,
            }

        def serialize_project(p: Project) -> dict:
            return {
                "id": p.id, "name": p.name, "description": p.description,
                "status": p.status.value,
                "created_at": p.created_at, "updated_at": p.updated_at,
                "questionnaire_results": serialize_qr(p.questionnaire_results) if p.questionnaire_results else None,
                "style_requirements": [serialize_ref_article(a) for a in p.style_requirements],
                "vocabulary_corpus": serialize_vocab(p.vocabulary_corpus) if p.vocabulary_corpus else None,
                "user_requirements": [serialize_user_req(ur) for ur in p.user_requirements],
                "anti_bias_profile": serialize_anti_bias(p.anti_bias_profile) if p.anti_bias_profile else None,
                "writing_history": p.writing_history,
                "revision_count": p.revision_count,
                "tags": p.tags,
            }

        data = {
            "id": profile.id,
            "name": profile.name,
            "created_at": profile.created_at,
            "last_active": profile.last_active,
            "preferences": {
                "preferred_writing_modes": profile.preferences.preferred_writing_modes if profile.preferences else [],
                "preferred_doc_types": profile.preferences.preferred_doc_types if profile.preferences else [],
                "preferred_styles": profile.preferences.preferred_styles if profile.preferences else [],
                "typical_length_range": list(profile.preferences.typical_length_range) if profile.preferences else [800, 2000],
                "writing_frequency": profile.preferences.writing_frequency if profile.preferences else "",
                "common_themes": profile.preferences.common_themes if profile.preferences else [],
                "forbidden_patterns": profile.preferences.forbidden_patterns if profile.preferences else [],
                "preferred_transitions": profile.preferences.preferred_transitions if profile.preferences else [],
            },
            "writing_history": [
                {"id": wh.id, "project_id": wh.project_id, "writing_mode": wh.writing_mode,
                 "doc_type": wh.doc_type, "style": wh.style, "created_at": wh.created_at,
                 "word_count": wh.word_count, "review_findings": wh.review_findings,
                 "common_errors": wh.common_errors, "strengths": wh.strengths}
                for wh in profile.writing_history
            ],
            "common_error_patterns": profile.common_error_patterns,
            "common_strengths": profile.common_strengths,
            "global_anti_bias": serialize_anti_bias(profile.global_anti_bias) if profile.global_anti_bias else None,
            "projects": [serialize_project(p) for p in profile.projects],
            "memory_notes": profile.memory_notes,
        }

        return json.dumps(data, ensure_ascii=False, indent=2)

    @staticmethod
    def _parse_project_status(status_value: Any) -> ProjectStatus:
        """解析项目状态枚举，非法值回退到 DRAFT"""
        try:
            return ProjectStatus(status_value)
        except (ValueError, TypeError):
            return ProjectStatus.DRAFT

    def import_from_json(self, json_data: str) -> Optional[UserProfile]:
        """从JSON导入用户数据（完整反序列化）"""
        try:
            data = json.loads(json_data)
        except (json.JSONDecodeError, TypeError):
            return None

        user_id = data.get("id")
        if not user_id:
            return None

        profile = UserProfile(
            id=user_id,
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            last_active=data.get("last_active", ""),
            memory_notes=data.get("memory_notes", ""),
            common_error_patterns=data.get("common_error_patterns", []),
            common_strengths=data.get("common_strengths", []),
        )

        prefs_data = data.get("preferences", {})
        profile.preferences = UserPreferences(
            preferred_writing_modes=prefs_data.get("preferred_writing_modes", []),
            preferred_doc_types=prefs_data.get("preferred_doc_types", []),
            preferred_styles=prefs_data.get("preferred_styles", []),
            typical_length_range=tuple(prefs_data.get("typical_length_range", [800, 2000])),
            writing_frequency=prefs_data.get("writing_frequency", ""),
            common_themes=prefs_data.get("common_themes", []),
            forbidden_patterns=prefs_data.get("forbidden_patterns", []),
            preferred_transitions=prefs_data.get("preferred_transitions", []),
        )

        # 反序列化 writing_history
        for wh_data in data.get("writing_history", []):
            profile.writing_history.append(WritingHistory(
                id=wh_data.get("id", f"wh_{uuid.uuid4().hex[:8]}"), project_id=wh_data.get("project_id", ""),
                writing_mode=wh_data.get("writing_mode", ""),
                doc_type=wh_data.get("doc_type", ""),
                style=wh_data.get("style", ""),
                created_at=wh_data.get("created_at", ""),
                word_count=wh_data.get("word_count", 0),
                review_findings=wh_data.get("review_findings", []),
                common_errors=wh_data.get("common_errors", []),
                strengths=wh_data.get("strengths", []),
            ))

        # 反序列化 global_anti_bias
        gab_data = data.get("global_anti_bias")
        if gab_data:
            profile.global_anti_bias = AntiBiasAnalysis(
                id=gab_data.get("id", f"ab_{uuid.uuid4().hex[:8]}"),
                user_bias_patterns=gab_data.get("user_bias_patterns", []),
                counter_perspectives=gab_data.get("counter_perspectives", []),
                innovative_angles=gab_data.get("innovative_angles", []),
                temperature_adjustment=gab_data.get("temperature_adjustment", 1.0),
                analysis_notes=gab_data.get("analysis_notes", ""),
                created_at=gab_data.get("created_at", ""),
            )

        for proj_data in data.get("projects", []):
            proj = Project(
                id=proj_data.get("id", f"proj_{uuid.uuid4().hex[:8]}"),
                name=proj_data.get("name", ""),
                description=proj_data.get("description", ""),
                status=self._parse_project_status(proj_data.get("status", "draft")),
                created_at=proj_data.get("created_at", ""),
                updated_at=proj_data.get("updated_at", ""),
                writing_history=proj_data.get("writing_history", []),
                revision_count=proj_data.get("revision_count", 0),
                tags=proj_data.get("tags", []),
            )

            qr_data = proj_data.get("questionnaire_results")
            if qr_data:
                proj.questionnaire_results = QuestionnaireResults(
                    writing_mode=qr_data.get("writing_mode", ""),
                    doc_type=qr_data.get("doc_type", ""),
                    style=qr_data.get("style", ""),
                    purpose=qr_data.get("purpose", ""),
                    primary_audience=qr_data.get("primary_audience", ""),
                    secondary_audiences=qr_data.get("secondary_audiences", []),
                    deep_meaning=qr_data.get("deep_meaning", ""),
                    strategic_anchor=qr_data.get("strategic_anchor", ""),
                    key_materials=qr_data.get("key_materials", ""),
                    differentiator=qr_data.get("differentiator", ""),
                    raw_answers=qr_data.get("raw_answers", {}),
                )

            for a_data in proj_data.get("style_requirements", []):
                proj.style_requirements.append(ReferenceArticle(
                    id=a_data.get("id", f"ref_{uuid.uuid4().hex[:8]}"), title=a_data.get("title", ""),
                    content=a_data.get("content", ""),
                    upload_time=a_data.get("upload_time", ""),
                    style_notes=a_data.get("style_notes", ""),
                    extracted_patterns=a_data.get("extracted_patterns", []),
                ))

            vocab_data = proj_data.get("vocabulary_corpus")
            if vocab_data:
                proj.vocabulary_corpus = VocabularyCorpus(
                    id=vocab_data.get("id", f"vocab_{proj.id}"),
                    project_id=vocab_data.get("project_id", proj.id),
                    custom_terms=vocab_data.get("custom_terms", []),
                    custom_phrases=vocab_data.get("custom_phrases", []),
                    forbidden_words=vocab_data.get("forbidden_words", []),
                    required_keywords=vocab_data.get("required_keywords", []),
                    style_vocabulary=vocab_data.get("style_vocabulary", {}),
                    created_at=vocab_data.get("created_at", ""),
                    updated_at=vocab_data.get("updated_at", ""),
                )

            for ur_data in proj_data.get("user_requirements", []):
                ab_data = ur_data.get("anti_bias_analysis")
                anti_bias = None
                if ab_data:
                    anti_bias = AntiBiasAnalysis(
                        id=ab_data.get("id", f"ab_{uuid.uuid4().hex[:8]}"),
                        user_bias_patterns=ab_data.get("user_bias_patterns", []),
                        counter_perspectives=ab_data.get("counter_perspectives", []),
                        innovative_angles=ab_data.get("innovative_angles", []),
                        temperature_adjustment=ab_data.get("temperature_adjustment", 1.0),
                        analysis_notes=ab_data.get("analysis_notes", ""),
                        created_at=ab_data.get("created_at", ""),
                    )
                proj.user_requirements.append(UserRequirement(
                    id=ur_data.get("id", f"ur_{uuid.uuid4().hex[:8]}"),
                    description=ur_data.get("description", ""),
                    priority=ur_data.get("priority", "normal"),
                    anti_bias_analysis=anti_bias,
                    creative_suggestions=ur_data.get("creative_suggestions", []),
                    weakness_analysis=ur_data.get("weakness_analysis", ""),
                    created_at=ur_data.get("created_at", ""),
                ))

            abp_data = proj_data.get("anti_bias_profile")
            if abp_data:
                proj.anti_bias_profile = AntiBiasAnalysis(
                    id=abp_data.get("id", f"ab_{uuid.uuid4().hex[:8]}"),
                    user_bias_patterns=abp_data.get("user_bias_patterns", []),
                    counter_perspectives=abp_data.get("counter_perspectives", []),
                    innovative_angles=abp_data.get("innovative_angles", []),
                    temperature_adjustment=abp_data.get("temperature_adjustment", 1.0),
                    analysis_notes=abp_data.get("analysis_notes", ""),
                    created_at=abp_data.get("created_at", ""),
                )

            profile.projects.append(proj)

        self.profiles[user_id] = profile
        self.current_user_id = user_id
        return profile
