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
import json
import uuid


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
            except Exception as e:
                style_notes = f"自动抓取失败：{str(e)}"

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
                import time
                time.sleep(delay)
        return articles

    def extract_patterns_from_article(self, article: ReferenceArticle) -> List[str]:
        """从用户上传的参考文章中提取风格模式"""
        patterns = []
        content = article.content

        if len(content) < 500:
            return patterns

        sentences = content.split("。")
        if len(sentences) > 10:
            patterns.append("多使用短句（平均{}字/句）".format(int(len(content) / len(sentences))))

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

    def get_memory_summary(self, project_id: Optional[str] = None) -> str:
        """获取记忆摘要"""
        user = self.get_current_user()
        if not user:
            return "无用户数据"

        lines = ["【用户记忆摘要】", ""]
        lines.append(f"用户：{user.name}")
        lines.append(f"项目数：{len(user.projects)}")
        lines.append(f"活跃时间：{user.last_active}")
        lines.append("")

        if user.preferences and user.preferences.preferred_writing_modes:
            lines.append(f"常用写作模式：{', '.join(user.preferences.preferred_writing_modes)}")

        if user.common_strengths:
            lines.append(f"常见优势：{', '.join(user.common_strengths)}")

        if project_id:
            project = self.get_project(project_id)
            if project:
                lines.append("")
                lines.append(f"【项目记忆：{project.name}】")
                lines.append(f"状态：{project.status.value}")
                lines.append(f"修改次数：{project.revision_count}")

                if project.questionnaire_results:
                    lines.append(f"写作模式：{project.questionnaire_results.writing_mode}")
                    lines.append(f"文种：{project.questionnaire_results.doc_type}")

                if project.vocabulary_corpus:
                    corpus = project.vocabulary_corpus
                    lines.append(f"自定义术语：{', '.join(corpus.custom_terms[:5])}")
                    lines.append(f"禁用词：{', '.join(corpus.forbidden_words[:5])}")

        if user.memory_notes:
            lines.append("")
            lines.append(f"【记忆笔记】")
            lines.append(user.memory_notes)

        return "\n".join(lines)

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
            most_used = max(set(user.preferences.preferred_styles), key=user.preferences.preferred_styles.count)
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
        """导出用户数据为JSON"""
        target_id = user_id or self.current_user_id
        if not target_id or target_id not in self.profiles:
            return "{}"

        profile = self.profiles[target_id]
        data = {
            "id": profile.id,
            "name": profile.name,
            "created_at": profile.created_at,
            "last_active": profile.last_active,
            "preferences": {
                "preferred_writing_modes": profile.preferences.preferred_writing_modes if profile.preferences else [],
                "preferred_doc_types": profile.preferences.preferred_doc_types if profile.preferences else [],
                "preferred_styles": profile.preferences.preferred_styles if profile.preferences else [],
                "typical_length_range": profile.preferences.typical_length_range if profile.preferences else [800, 2000],
            },
            "projects": [
                {
                    "id": p.id,
                    "name": p.name,
                    "status": p.status.value,
                    "questionnaire_results": {
                        "writing_mode": p.questionnaire_results.writing_mode if p.questionnaire_results else "",
                        "doc_type": p.questionnaire_results.doc_type if p.questionnaire_results else "",
                        "style": p.questionnaire_results.style if p.questionnaire_results else "",
                    } if p.questionnaire_results else None,
                    "vocabulary_corpus": {
                        "custom_terms": p.vocabulary_corpus.custom_terms if p.vocabulary_corpus else [],
                        "forbidden_words": p.vocabulary_corpus.forbidden_words if p.vocabulary_corpus else [],
                    } if p.vocabulary_corpus else None,
                }
                for p in profile.projects
            ],
            "memory_notes": profile.memory_notes,
        }

        return json.dumps(data, ensure_ascii=False, indent=2)

    def import_from_json(self, json_data: str) -> Optional[UserProfile]:
        """从JSON导入用户数据"""
        data = json.loads(json_data)

        user_id = data.get("id")
        if not user_id:
            return None

        profile = UserProfile(
            id=user_id,
            name=data.get("name", ""),
            created_at=data.get("created_at", ""),
            last_active=data.get("last_active", ""),
            memory_notes=data.get("memory_notes", ""),
        )

        prefs_data = data.get("preferences", {})
        profile.preferences = UserPreferences(
            preferred_writing_modes=prefs_data.get("preferred_writing_modes", []),
            preferred_doc_types=prefs_data.get("preferred_doc_types", []),
            preferred_styles=prefs_data.get("preferred_styles", []),
            typical_length_range=tuple(prefs_data.get("typical_length_range", [800, 2000])),
        )

        for proj_data in data.get("projects", []):
            proj = Project(
                id=proj_data["id"],
                name=proj_data["name"],
                status=ProjectStatus(proj_data.get("status", "draft")),
            )

            qr_data = proj_data.get("questionnaire_results")
            if qr_data:
                proj.questionnaire_results = QuestionnaireResults(
                    writing_mode=qr_data.get("writing_mode", ""),
                    doc_type=qr_data.get("doc_type", ""),
                    style=qr_data.get("style", ""),
                )

            vocab_data = proj_data.get("vocabulary_corpus")
            if vocab_data:
                proj.vocabulary_corpus = VocabularyCorpus(
                    id=f"vocab_{proj.id}",
                    project_id=proj.id,
                    custom_terms=vocab_data.get("custom_terms", []),
                    forbidden_words=vocab_data.get("forbidden_words", []),
                )

            profile.projects.append(proj)

        self.profiles[user_id] = profile
        self.current_user_id = user_id
        return profile
