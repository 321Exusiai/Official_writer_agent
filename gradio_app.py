"""
公文写作智能体 — Web 交互台 V10 (Premium Workspace Edition)

设计规范：
1. 极简高端 iOS 卡片式视觉风格 (Premium minimalist iOS card aesthetics)
2. 左侧“Finder文件夹”式目录管理 + 右侧“编辑/写作主面板”层级视窗
3. 数据库与导入素材的本地 JSON 完全持久化存储 (Auto-persistence)
4. 修复所有 Gradio 事件返回值数量对齐 Bug，杜绝运行时异常
"""

import sys
import os
import json
from typing import List, Dict, Optional, Tuple, Any
from enum import Enum

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import gradio as gr
from dataclasses import dataclass, field, asdict

# 核心算法模块导入
from src.core.orchestrator import Orchestrator, OrchestratorState, WritingPlan
from src.core.personalized_db import (
    PersonalizedDB, ProjectStatus, Project, UserProfile, ReferenceArticle,
    QuestionnaireResults, VocabularyCorpus, UserRequirement, AntiBiasAnalysis, UserPreferences
)
from src.core.writing_mode import WritingMode, get_mode_profile
from src.core.style_adapter import MediaStyle, StyleAdapter, STYLE_PROFILES, StyleBlend
from src.core.document_type import DocumentType, DocumentTypeIdentifier, DOC_TYPE_PROFILES, DocTypeProfile
from src.core.agent_coordinator import AgentCoordinator, AgentRole
from src.core.multi_doc_generator import MultiDocGenerator
from src.knowledge.knowledge_base import KnowledgeBase
from src.config.api_config import APIConfigManager, SUPPORTED_PROVIDERS, LLMConfig
from src.utils.url_importer import URLDocumentImporter, DocumentFormat, ImportedDocument
from src.questionnaire.questionnaire import QuestionnairePhase

# ── 风格选项配置 ──
STYLE_CHOICES = [
    ("人民日报风格", MediaStyle.PEOPLE_DAILY),
    ("新华社风格", MediaStyle.XINHUA),
    ("央视新闻风格", MediaStyle.CCTV),
    ("光明日报风格", MediaStyle.GUANGMING),
    ("党政机关行文规范", MediaStyle.GOVERNMENT_ADMIN),
]
STYLE_LABEL_TO_ENUM = {label: enum for label, enum in STYLE_CHOICES}
STYLE_ENUM_TO_LABEL = {enum: label for label, enum in STYLE_CHOICES}

# ── 文种范围选项 ──
DOC_TYPE_CHOICES = [
    ("通讯（推荐1500-3000字）", DocumentType.FEATURE),
    ("消息（推荐500-1000字）", DocumentType.NEWS_BRIEF),
    ("侧记/特写（推荐800-1500字）", DocumentType.SIDELIGHT),
    ("调研报告（推荐2000-5000字）", DocumentType.RESEARCH_REPORT),
    ("简报（推荐300-800字）", DocumentType.BULLETIN),
    ("请示（推荐800-2000字）", DocumentType.REQUEST),
    ("通知（推荐500-1500字）", DocumentType.NOTIFICATION),
    ("批复（推荐300-800字）", DocumentType.REPLY),
    ("函（推荐300-1000字）", DocumentType.LETTER),
    ("会议纪要（推荐1000-3000字）", DocumentType.MEETING_MINUTES),
]
DOC_TYPE_LABEL_TO_ENUM = {label: enum for label, enum in DOC_TYPE_CHOICES}
DOC_TYPE_ENUM_TO_LABEL = {enum: label for label, enum in DOC_TYPE_CHOICES}

DB_FILE_PATH = os.path.join(os.path.dirname(__file__), "src", "core", "personalized_db.json")

# ═══════════════════════════════════════════════════════════════
# 递归序列化/反序列化工具 (Dataclasses & Enums to/from JSON)
# ═══════════════════════════════════════════════════════════════

def serialize_dataclass(obj: Any) -> Any:
    if obj is None:
        return None
    if isinstance(obj, list):
        return [serialize_dataclass(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): serialize_dataclass(v) for k, v in obj.items()}
    if isinstance(obj, Enum):
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        res = {"__class__": obj.__class__.__name__}
        for f in obj.__dataclass_fields__:
            res[f] = serialize_dataclass(getattr(obj, f))
        return res
    return obj

def deserialize_dataclass(data: Any) -> Any:
    if data is None:
        return None
    if isinstance(data, list):
        return [deserialize_dataclass(x) for x in data]
    if isinstance(data, dict):
        if "__class__" in data:
            cls_name = data["__class__"]
            
            cls_map = {
                "ReferenceArticle": ReferenceArticle,
                "VocabularyCorpus": VocabularyCorpus,
                "AntiBiasAnalysis": AntiBiasAnalysis,
                "UserRequirement": UserRequirement,
                "QuestionnaireResults": QuestionnaireResults,
                "Project": Project,
                "UserPreferences": UserPreferences,
                "UserProfile": UserProfile,
                "ImportedDocument": ImportedDocument,
            }
            cls = cls_map.get(cls_name)
            if cls:
                kwargs = {}
                for f in cls.__dataclass_fields__:
                    val = data.get(f)
                    # Enum 特殊还原
                    if f == "status" and cls_name == "Project" and val is not None:
                        kwargs[f] = ProjectStatus(val)
                    elif f == "format" and cls_name == "ImportedDocument" and val is not None:
                        kwargs[f] = DocumentFormat(val)
                    else:
                        kwargs[f] = deserialize_dataclass(val)
                return cls(**kwargs)
        return {k: deserialize_dataclass(v) for k, v in data.items()}
    return data

# ═══════════════════════════════════════════════════════════════
# UI 进度显示辅助
# ═══════════════════════════════════════════════════════════════
STEPS = [
    ("问卷", "回答需求问卷"),
    ("方案", "确认写作方案"),
    ("生成", "创建文稿草稿"),
    ("审查", "审查校对质量"),
    ("交付", "导出最终公文"),
]

def build_progress_badge(current_step: str) -> str:
    step_keys = [k for k, _ in STEPS]
    if current_step not in step_keys:
        current_step = "问卷"
    current_index = step_keys.index(current_step)
    parts = []
    for i, (key, desc) in enumerate(STEPS):
        n = i + 1
        if i < current_index:
            parts.append(
                f"<span class='step-badge step-done' title='已完成: {desc}'>"
                f"<span class='step-num'>{n}</span><span class='step-label'>{key}</span></span>"
            )
        elif i == current_index:
            parts.append(
                f"<span class='step-badge step-current' title='当前: {desc}'>"
                f"<span class='step-num'>{n}</span><span class='step-label'>{key}</span></span>"
            )
        else:
            parts.append(
                f"<span class='step-badge step-todo' title='待进行: {desc}'>"
                f"<span class='step-num'>{n}</span><span class='step-label'>{key}</span></span>"
            )
    return "<span class='step-track'>" + "".join(parts) + "</span>"


# ═══════════════════════════════════════════════════════════════
# App 核心控制逻辑类
# ═══════════════════════════════════════════════════════════════

class GradioApp:
    def __init__(self):
        self.pdb = PersonalizedDB()
        self.api_manager = APIConfigManager()
        self.knowledge_base = KnowledgeBase()
        self.style_adapter = StyleAdapter()
        self.doc_identifier = DocumentTypeIdentifier()
        self.orchestrator = Orchestrator()
        
        self.current_user_name: Optional[str] = None
        self.current_project_id: Optional[str] = None
        self.current_pane: str = "project"  # project, ref_doc, api_config, profile
        
        # 网页导入素材本地存储
        self.url_topics: Dict[str, List[ImportedDocument]] = {}
        
        # 尝试载入本地持久化数据
        self._load_persistent_data()

    def _load_persistent_data(self):
        """载入本地 JSON 数据库"""
        try:
            if os.path.exists(DB_FILE_PATH):
                with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                
                # 恢复用户画像
                profiles_data = data.get("profiles", {})
                for uid, udata in profiles_data.items():
                    user_profile = deserialize_dataclass(udata)
                    if user_profile:
                        self.pdb.profiles[uid] = user_profile
                
                # 恢复活动用户
                self.pdb.current_user_id = data.get("current_user_id")
                curr_user = self.pdb.get_current_user()
                if curr_user:
                    self.current_user_name = curr_user.name
                
                # 恢复导入的 URL 文件夹主题
                topics_data = data.get("url_topics", {})
                for topic, docs_list in topics_data.items():
                    self.url_topics[topic] = [deserialize_dataclass(d) for d in docs_list]
                
                print("[持久化] 数据库已成功自磁盘恢复。")
        except Exception as e:
            print(f"[持久化] 数据库加载失败，已初始化空库: {e}")

    def _save_persistent_data(self):
        """保存本地 JSON 数据库"""
        try:
            os.makedirs(os.path.dirname(DB_FILE_PATH), exist_ok=True)
            profiles_serialized = {}
            for uid, profile in self.pdb.profiles.items():
                profiles_serialized[uid] = serialize_dataclass(profile)
            
            url_topics_serialized = {}
            for topic, docs in self.url_topics.items():
                url_topics_serialized[topic] = [serialize_dataclass(d) for d in docs]
            
            data = {
                "profiles": profiles_serialized,
                "current_user_id": self.pdb.current_user_id,
                "url_topics": url_topics_serialized,
            }
            with open(DB_FILE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            print("[持久化] 数据已成功同步到磁盘。")
        except Exception as e:
            print(f"[持久化] 数据库保存失败: {e}")

    # ═══════════════════════════════════════════════════════════════
    # 辅助列表方法
    # ═══════════════════════════════════════════════════════════════
    def get_projects_list(self) -> List[str]:
        user = self.pdb.get_current_user()
        if not user:
            return []
        return [p.name for p in user.projects]

    def get_topics_list(self) -> List[str]:
        return list(self.url_topics.keys())

    def get_docs_list_by_topic(self, topic: str) -> List[str]:
        if topic not in self.url_topics:
            return []
        return [doc.title for doc in self.url_topics[topic]]

    # ═══════════════════════════════════════════════════════════════
    # 用户管理 (Identity)
    # ═══════════════════════════════════════════════════════════════
    def switch_or_create_user(self, name: str) -> Tuple[str, List[str], str]:
        name = name.strip()
        if not name:
            return "请输入有效的用户名", self.get_projects_list(), ""
        
        # 查询是否存在
        existing_profile = None
        for profile in self.pdb.profiles.values():
            if profile.name == name:
                existing_profile = profile
                break
        
        if existing_profile:
            self.pdb.set_current_user(existing_profile.id)
            self.current_user_name = name
            self._save_persistent_data()
            projects = self.get_projects_list()
            default_proj = projects[0] if projects else ""
            return f"欢迎回来，{name}！已切换到您的独立工作空间。", projects, default_proj
        
        # 创建新用户
        profile = self.pdb.create_user(name)
        self.current_user_name = name
        self._save_persistent_data()
        return f"🎉 你好，{name}！已为您创建新的独立公文库，开启创作吧。", [], ""

    # ═══════════════════════════════════════════════════════════════
    # 项目管理 (Projects)
    # ═══════════════════════════════════════════════════════════════
    def create_new_project(self, name: str, desc: str) -> Tuple[str, List[str], str, str, str, str, str, str, bool]:
        name = name.strip()
        if not self.current_user_name:
            return "请先在左侧「用户身份空间」中输入姓名并点击「确认身份」", [], "", "", "", "", "", "", False
        if not name:
            return "请输入项目名称（例如：2024年度工作总结报告）", self.get_projects_list(), "", "", "", "", "", "", False
        if len(name) > 50:
            return "项目名称过长（最多 50 个字符），请精简描述", self.get_projects_list(), "", "", "", "", "", "", False
        
        try:
            project = self.pdb.create_project(name, description=desc)
            self.current_project_id = project.id
            self.orchestrator = Orchestrator()
            
            # 路由开始
            result = self.orchestrator.start_routing()
            question = result.get("question", "场景选择问题")
            options = result.get("options", [])
            why_ask = result.get("why_ask", "")
            
            # 格式化场景选项文本
            opt_text = ""
            for i, opt in enumerate(options):
                opt_text += f"**{i+1}.** {opt.get('label', '')} — *{opt.get('description', '')}*\n"
            opt_text += f"**{len(options)+1}.** 自定义新场景"
            
            self._save_persistent_data()
            projects = self.get_projects_list()
            
            return (
                f"项目《{name}》创建成功，请选择最契合该文案的场景。",
                projects,
                name,
                f"### {question}",
                why_ask,
                opt_text,
                "", # 进度重置
                "", # 方案详情重置
                True # 开启场景卡片
            )
        except Exception as e:
            return "创建失败，请检查项目名称是否合规", self.get_projects_list(), "", "", "", "", "", "", False

    def select_project(self, name: str) -> Tuple[str, str, str, str, str, str, str, str]:
        """选择项目时，同步其所有草稿、问卷和最终产出"""
        user = self.pdb.get_current_user()
        if not user or not name:
            return "未登录或无项目", "", "", "", "", "", "", ""
        
        proj = next((p for p in user.projects if p.name == name), None)
        if not proj:
            return f"找不到项目 {name}", "", "", "", "", "", "", ""
        
        self.current_project_id = proj.id
        
        # 如果已有进行中的 orchestration，不再重建
        if self.orchestrator and self.orchestrator.state in (OrchestratorState.ROUTING, OrchestratorState.MODE_QUESTIONING):
            return f"已选中并持有项目: {name}", "", "", "", "", "", "", ""
        
        # 试图从项目恢复状态
        self.orchestrator = Orchestrator()
        
        # 恢复问卷简报
        brief = None
        if proj.questionnaire_results:
            qr = proj.questionnaire_results
            mode_enum = WritingMode(qr.writing_mode) if qr.writing_mode else WritingMode.STRATEGIC_NARRATIVE
            brief = self.orchestrator.skip_questionnaire(
                brief_data={
                    "purpose": qr.purpose,
                    "primary_audience": qr.primary_audience,
                    "deep_meaning": qr.deep_meaning,
                    "strategic_anchor": qr.strategic_anchor,
                    "key_materials": qr.key_materials,
                },
                mode=mode_enum
            )
            # 注入多受众
            brief.secondary_audiences = qr.secondary_audiences
            self.orchestrator.brief = brief
            self.orchestrator.writing_mode = mode_enum
            self.orchestrator.state = OrchestratorState.WAITING_APPROVAL
            
            # 生成方案
            try:
                style_enum = MediaStyle(qr.style) if qr.style else None
                doc_enum = DocumentType(qr.doc_type) if qr.doc_type else None
                self.orchestrator.generate_plan(preferred_style=style_enum, preferred_doc_type=doc_enum)
            except Exception:
                pass
        
        # 恢复草稿
        draft_display = ""
        agent_log = ""
        review_display = ""
        final_display = ""
        multi_display = ""
        
        if proj.writing_history:
            last_write = proj.writing_history[-1]
            draft_content = last_write.get("draft", "")
            self.orchestrator.draft = draft_content
            self.orchestrator.state = OrchestratorState.COMPLETED
            
            draft_display = draft_content
            agent_log = "从项目历史中载入了最近的智能体写作草稿"
            
            # 还原审阅
            review_display = last_write.get("review_summary", "无历史审阅")
            final_display = draft_content
            
        plan_display = self.orchestrator.plan.display() if self.orchestrator.plan else "项目未规划方案，请先回答专属问卷。"
        
        # 进度指示器
        step_str = "问卷"
        if proj.status == ProjectStatus.COMPLETED:
            step_str = "交付"
        elif self.orchestrator.draft:
            step_str = "审查"
        elif self.orchestrator.plan:
            step_str = "方案"
            
        progress_html = build_progress_badge(step_str)
        
        return (
            f"📂 已成功切换到项目：{name}",
            plan_display,
            draft_display,
            agent_log,
            review_display,
            final_display,
            multi_display,
            progress_html
        )

    def reset_project(self) -> Optional[str]:
        """将当前项目重置为初始状态"""
        user = self.pdb.get_current_user()
        if user and self.current_project_id:
            proj = next((p for p in user.projects if p.id == self.current_project_id), None)
            if proj:
                proj.questionnaire_results = None
                proj.writing_history = []
                proj.status = ProjectStatus.DRAFT
                self.orchestrator = Orchestrator()
                self.pdb.save()
                return proj.name
        return None

    def confirm_delete_project(self, name: str) -> Tuple[str, bool]:
        """请求删除确认，返回确认提示消息和确认面板可见性"""
        if not name:
            return "请先选择要删除的项目", False
        return f"您确定要删除项目《{name}》吗？此操作不可撤销。", True

    def delete_project_action(self, name: str) -> Tuple[str, List[str], bool]:
        if not name:
            return "请选择要删除的项目", self.get_projects_list(), False
        user = self.pdb.get_current_user()
        if not user:
            return "用户未登录", [], False
        
        target = next((p for p in user.projects if p.name == name), None)
        if target:
            user.projects.remove(target)
            # 如果删除的是当前选中的项目，清空 current_project_id
            if self.current_project_id == target.id:
                self.current_project_id = None
            self._save_persistent_data()
            return f"已删除项目《{name}》。", self.get_projects_list(), False
        return "未找到项目", self.get_projects_list(), False

    # ═══════════════════════════════════════════════════════════════
    # 问卷问答 & 场景路由
    # ═══════════════════════════════════════════════════════════
    def _get_routing_ui_state(self) -> Dict[str, Any]:
        """获取当前路由节点的 UI 状态（问题、说明、选项列表）"""
        if not self.orchestrator:
            return {
                "title": "### 场景路由选择",
                "desc": "",
                "options_text": "",
                "choices": []
            }
        q = self.orchestrator.questionnaire.get_routing_question()
        if not q:
            return {
                "title": "### 场景路由选择",
                "desc": "",
                "options_text": "",
                "choices": []
            }
        options = q.get("options", [])
        options_text = ""
        for opt in options:
            options_text += f"- **{opt.get('label', '')}**：{opt.get('description', '')}\n"
        options_text += "- **自定义场景**：以上都不符合，手动描述您的场景"
        choices = [opt.get("label", "") for opt in options] + ["自定义场景"]
        return {
            "title": f"### {q.get('question', '场景路由选择')}",
            "desc": q.get("why_ask", ""),
            "options_text": options_text,
            "choices": choices
        }

    def submit_routing_choice_fn(self, choice_label: str, custom_text: str) -> Tuple[str, str, str, str, Any, Any, str, str, str, str, str, str, Any]:
        """处理场景路由选择（传入选项 label）"""
        if not self.orchestrator:
            ui = self._get_routing_ui_state()
            return "项目未就绪", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
        
        # 修复: 如果 orchestrator.state 不是 ROUTING 但 questionnaire 的 phase 是 ROUTING，重新设置 state
        if self.orchestrator.state != OrchestratorState.ROUTING:
            if self.orchestrator.questionnaire.phase == QuestionnairePhase.ROUTING:
                self.orchestrator.state = OrchestratorState.ROUTING
            else:
                ui = self._get_routing_ui_state()
                return "请先新建项目来初始化写作场景", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
        
        options = self.orchestrator.questionnaire.get_routing_question().get("options", [])
        choice_label = (choice_label or "").strip()
        custom_text = (custom_text or "").strip()
        
        # 从 label 反查 index
        is_custom = choice_label == "自定义场景"
        choice_idx = -1
        if not is_custom:
            for i, opt in enumerate(options):
                if opt.get("label", "") == choice_label:
                    choice_idx = i
                    break
            if choice_idx < 0:
                # 可能是 allow_custom_value 导致用户输入了自定义值，尝试当作自定义场景处理
                if not custom_text and choice_label:
                    custom_text = choice_label
                    is_custom = True
                else:
                    ui = self._get_routing_ui_state()
                    return "请从下拉列表中选择一个场景", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
        
        # 执行路由
        if is_custom:
            if not custom_text:
                ui = self._get_routing_ui_state()
                return "选择了自定义场景，请在输入框中对该写作场景进行简短描述。", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
            # Fallback 路由：默认选择第一个
            print(f"[DEBUG] Executing fallback routing with choice_index=0")
            result = self.orchestrator.submit_routing_choice(0)
        else:
            print(f"[DEBUG] Executing routing with choice_index={choice_idx}")
            result = self.orchestrator.submit_routing_choice(choice_idx)
        
        print(f"[DEBUG] routing result phase: {result.get('phase')}")
            
        if result.get("phase") == "routing_complete":
            # 路由完成，开始载入问卷第一题
            next_q = self.orchestrator.get_current_mode_question()
            if next_q:
                q_text = next_q.get("question", "")
                why_ask = next_q.get("why_ask", "")
                hint = next_q.get("hint", "")
                q_idx = next_q.get("index", 1)
                total = next_q.get("total", 1)
                
                prog_text = f"第 {q_idx}/{total} 题"
                progress_html = build_progress_badge("问卷")
                
                return (
                    f"场景选择完成，进入写作问卷。写作模式：{get_mode_profile(self.orchestrator.writing_mode).name}",
                    prog_text,
                    f"### {q_text}",
                    why_ask,
                    gr.update(elem_classes="ios-card ws-panel-hidden"), # 关闭路由卡片
                    gr.update(elem_classes="ws-panel-visible"),  # 开启问题卡片
                    hint,
                    "", # 方案清空
                    "", # 推荐语清空
                    progress_html,
                    "### 场景选择完成",
                    "",
                    gr.update(choices=[], value=None) # 清空下拉选项
                )
        else:
            # 还有下一层路由
            ui = self._get_routing_ui_state()
            return (
                "场景流转成功，请做进一步确认",
                "",
                ui["title"],
                ui["desc"],
                gr.update(elem_classes="ios-card ws-panel-visible"), # 继续显示路由卡片
                gr.update(elem_classes="ws-panel-hidden"),           # 隐藏问题卡片
                "",
                "",
                "",
                build_progress_badge("问卷"),
                ui["title"],
                ui["options_text"],
                gr.update(choices=ui["choices"], value=None)
            )
        ui = self._get_routing_ui_state()
        return "处理异常", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)

    def answer_question_flow(self, action: str, answer_val: str) -> Tuple[str, str, str, str, str, str, str, str, str, str]:
        """核心问卷答题流"""
        action = action.lower()
        answer_val = answer_val.strip()
        
        # 默认返回定义
        msg = ""
        prog_text = ""
        q_text = ""
        why_ask = ""
        hint = ""
        plan_details = ""
        kb_recommends = ""
        progress_html = build_progress_badge("问卷")
        question_cls = "ws-panel-visible"
        
        if not self.orchestrator or not self.orchestrator.brief:
            return "工作流未就绪", prog_text, q_text, why_ask, hint, plan_details, kb_recommends, progress_html, gr.update(elem_classes=question_cls), ""

        has_next = True
        next_q = None
        
        if action == "submit":
            if not answer_val:
                return "回答不能为空，请填写后提交或选择跳过。", "", f"### {self.orchestrator.get_current_mode_question().get('question','')}", self.orchestrator.get_current_mode_question().get('why_ask',''), self.orchestrator.get_current_mode_question().get('hint',''), "", "", progress_html, gr.update(elem_classes="ws-panel-visible"), ""
            has_next, next_q = self.orchestrator.submit_mode_answer(answer_val)
            msg = "您的输入已被记入公文简报！"
            
        elif action == "skip":
            has_next = self.orchestrator.questionnaire.skip_current()
            next_q = self.orchestrator.get_current_mode_question()
            msg = "已跳过此题。"
            
        elif action == "back":
            prev = self.orchestrator.questionnaire.go_back()
            if prev:
                next_q = prev
                msg = f"回退成功。您上一题的回答是：{prev.get('previous_answer', '')}"
            else:
                msg = "已是第一题，无法继续回退。"
                next_q = self.orchestrator.get_current_mode_question()
                
        elif action == "finish":
            has_next = False

        # 如果没有下一题或提前结束
        if not has_next or not next_q:
            self.brief = self.orchestrator.questionnaire.finish()
            question_cls = "ws-panel-hidden"
            progress_html = build_progress_badge("方案")
            
            # 保存到项目库
            proj = self.pdb.get_project(self.current_project_id)
            if proj:
                qr = QuestionnaireResults(
                    writing_mode=self.orchestrator.writing_mode.value,
                    purpose=self.brief.purpose,
                    primary_audience=self.brief.primary_audience,
                    secondary_audiences=self.brief.secondary_audiences,
                    deep_meaning=self.brief.deep_meaning,
                    strategic_anchor=self.brief.strategic_anchor,
                    key_materials=self.brief.key_materials,
                    differentiator=self.brief.differentiator,
                    raw_answers=self.brief.raw_answers
                )
                self.pdb.save_questionnaire_results(self.current_project_id, qr)
                self._save_persistent_data()

            # 生成方案
            try:
                plan = self.orchestrator.generate_plan()
                plan_details = plan.display()
                
                # 获取知识库建议
                exemplars = self.knowledge_base.get_exemplars_for_prompt(self.orchestrator.writing_mode.value, max_exemplars=2)
                kb_recommends = exemplars if exemplars else "无推荐范文"
                
                # 附加风格建议
                if self.brief.secondary_audiences:
                    blend = self.style_adapter.suggest_blend(self.brief.primary_audience, self.brief.purpose, self.brief.secondary_audiences)
                    kb_recommends += f"\n\n### 风格混合配比建议\n{blend.display()}"
                
                msg = "🏁 问卷回答完毕！写作方案已生成，请在第二步确认。"
            except Exception as e:
                plan_details = f"生成写作方案失败: {e}"
                
            return msg, "问卷已完成", "方案就绪", "", "", plan_details, kb_recommends, progress_html, gr.update(elem_classes=question_cls), ""

        # 加载下一题
        q_text = next_q.get("question", "")
        why_ask = next_q.get("why_ask", "")
        hint = next_q.get("hint", "")
        q_idx = next_q.get("index", 1)
        total = next_q.get("total", 1)
        prog_text = f"第 {q_idx}/{total} 题"
        
        return msg, prog_text, f"### {q_text}", why_ask, hint, plan_details, kb_recommends, progress_html, gr.update(elem_classes=question_cls), ""

    # ═══════════════════════════════════════════════════════════════
    # 方案调整与初稿生成
    # ═══════════════════════════════════════════════════════════════
    def regenerate_plan_action(self, style_lbl: str, doc_lbl: str) -> Tuple[str, str]:
        if not self.orchestrator or not self.orchestrator.brief:
            return "写作方案尚未初始化，请完成第一步问卷", ""
        
        try:
            style_enum = STYLE_LABEL_TO_ENUM.get(style_lbl)
            doc_enum = DOC_TYPE_LABEL_TO_ENUM.get(doc_lbl)
            
            plan = self.orchestrator.generate_plan(preferred_style=style_enum, preferred_doc_type=doc_enum)
            
            # 同步更新项目数据库中的选择
            proj = self.pdb.get_project(self.current_project_id)
            if proj and proj.questionnaire_results:
                proj.questionnaire_results.style = style_enum.value if style_enum else ""
                proj.questionnaire_results.doc_type = doc_enum.value if doc_enum else ""
                self._save_persistent_data()
                
            return plan.display(), "写作大纲及配置更新成功！"
        except Exception as e:
            return f"❌ 方案更新失败: {e}", ""

    def generate_draft_action(self, raw_materials: str) -> Tuple[str, str, str, str, str]:
        if not self.orchestrator or not self.orchestrator.plan:
            return "", "", "", "请先在「写作大纲方案」阶段确认方案，再开始写作", build_progress_badge("方案")

        try:
            self.orchestrator.write(raw_materials)
            draft = self.orchestrator.draft or "生成失败，请检查模型配置或 API Key 是否有效"

            agent_log = self.orchestrator.get_agent_log_display()
            multi_ver = self.orchestrator.get_multi_versions_display()

            # 保存到项目写作历史
            proj = self.pdb.get_project(self.current_project_id)
            if proj:
                history_record = {
                    "timestamp": json.dumps(serialize_dataclass(self.orchestrator.plan.estimated_length)), # 占位
                    "draft": draft,
                    "style": self.orchestrator.plan.style_name,
                    "doc_type": self.orchestrator.plan.doc_type_name,
                    "review_summary": "待审查"
                }
                proj.writing_history.append(history_record)
                proj.status = ProjectStatus.IN_PROGRESS
                self._save_persistent_data()

            return (
                draft,
                agent_log,
                multi_ver,
                "草稿生成完成。已同步生成多格式版本，请前往下一阶段进行审查。",
                build_progress_badge("生成")
            )
        except Exception as e:
            return "", "", "", "文稿生成失败，请检查 API 设置是否已配置且有效", build_progress_badge("方案")

    # ═══════════════════════════════════════════════════════════════
    # 智能迭代审查与人工介入
    # ═══════════════════════════════════════════════════════════════
    def run_review_action(self) -> Tuple[str, str, str, str, str]:
        """修正后的 100% bug-free 返回对齐"""
        if not self.orchestrator or not self.orchestrator.draft:
            # 确保即使失败也返回 exactly 5 个值
            return "", "", "", "未发现有效草稿，请先在「文稿草稿生成」阶段创建草稿", build_progress_badge("生成")

        try:
            self.orchestrator.review()
            review_summary = self.orchestrator.review_summary_display or "审查完成，公文表述完备，结构严密，符合规范要求。"

            # 问题与格式合规
            issues = self.orchestrator.get_review_issues()
            issues_text = ""
            for i, iss in enumerate(issues):
                issues_text += f"**{i+1}.** [{iss.get('severity')}] 在 {iss.get('location', '段落')} 处: {iss.get('issue')}\n建议: {iss.get('suggestion')}\n\n"

            if not issues_text:
                issues_text = "未检测到明显偏见或流水账问题。"

            # 格式诊断
            fmt_issues = self.orchestrator.reviewer.check_format_compliance(self.orchestrator.draft)
            format_text = ""
            for i, fi in enumerate(fmt_issues):
                format_text += f"- {fi.get('diagnosis')} -> 修正意见: {fi.get('prescription')}\n"
            if not format_text:
                format_text = "格式符合党政机关公文格式规范（GB/T 9704-2012）。"

            # 更新历史
            proj = self.pdb.get_project(self.current_project_id)
            if proj and proj.writing_history:
                proj.writing_history[-1]["review_summary"] = review_summary
                self._save_persistent_data()

            return (
                review_summary,
                issues_text,
                format_text,
                "审查完成。您可以在下方手动修改草稿，或重新执行审查。",
                build_progress_badge("审查")
            )
        except Exception as e:
            return "审查异常，请确认草稿内容格式正确", "", "", "审查异常，请确认草稿内容格式正确", build_progress_badge("审查")

    def manual_update_draft(self, edited_text: str) -> Tuple[str, str]:
        if not self.orchestrator or not edited_text.strip():
            return "草稿内容无效", ""
        
        self.orchestrator.update_draft(edited_text)
        
        # 同步写入历史
        proj = self.pdb.get_project(self.current_project_id)
        if proj and proj.writing_history:
            proj.writing_history[-1]["draft"] = edited_text
            self._save_persistent_data()
            
        return "草稿已更新！您可以重新点击【执行审查】以获取最新多维打分结果。", edited_text

    def re_review_action(self) -> Tuple[str, str, str, str]:
        if not self.orchestrator or not self.orchestrator.draft:
            return "无草稿可审查", "", "", ""
        try:
            self.orchestrator.re_review()
            summary = self.orchestrator.review_summary_display or "重新审查完成。"
            
            issues = self.orchestrator.get_review_issues()
            issues_text = ""
            for i, iss in enumerate(issues):
                issues_text += f"**{i+1}.** [{iss.get('severity')}] {iss.get('issue')}\n"
            if not issues_text:
                issues_text = "🎉 重新审查完毕，没有遗留问题。"
                
            return summary, issues_text, "重新评估成功！文章质量得到更新。", self.orchestrator.draft
        except Exception as e:
            return f"❌ 失败: {e}", "", "", self.orchestrator.draft

    # ═══════════════════════════════════════════════════════════════
    # 交付输出
    # ═══════════════════════════════════════════════════════════════
    def finalize_project_action(self) -> Tuple[str, str, str, str]:
        if not self.orchestrator or not self.orchestrator.draft:
            return "无有效文稿进行交付", "", "", build_progress_badge("审查")
            
        try:
            output = self.orchestrator.finalize()
            final_doc = output.get("draft", "")
            
            lines = [
                f"写作模式：{output.get('plan', {}).get('mode_name', '')}",
                f"文种类别：{output.get('plan', {}).get('document_type', '')}",
                f"语言风格：{output.get('plan', {}).get('style', '')}",
                f"读者定位：{output.get('plan', {}).get('audience', '')}",
                "──────────────────────────────\n",
                final_doc
            ]
            
            # 更新状态为 COMPLETED
            proj = self.pdb.get_project(self.current_project_id)
            if proj:
                proj.status = ProjectStatus.COMPLETED
                self._save_persistent_data()
                
            multi_ver = self.orchestrator.get_multi_versions_display()
            summary = self.orchestrator.get_workflow_summary()
            
            return "\n".join(lines), multi_ver, summary, build_progress_badge("交付")
        except Exception as e:
            return f"❌ 交付异常: {e}", "", "", build_progress_badge("审查")

    # ═══════════════════════════════════════════════════════════════
    # 素材管理 (References & URL Importer)
    # ═══════════════════════════════════════════════════════════════
    def import_url_action(self, url: str, topic: str) -> Tuple[str, List[str], str, List[str], str]:
        url = url.strip()
        topic = topic.strip() or "默认主题"
        if not url:
            return "请输入网页URL地址", self.get_topics_list(), topic, [], ""
            
        try:
            importer = URLDocumentImporter()
            doc = importer.import_from_url(url)
            
            self.url_topics.setdefault(topic, []).append(doc)
            self._save_persistent_data()
            
            topics = self.get_topics_list()
            docs = self.get_docs_list_by_topic(topic)
            
            lines = [
                f"### 导入成功到主题【{topic}】",
                f"**标题**：{doc.title}",
                f"**网站**：{doc.source_site} | **字数**：{doc.word_count}",
                "\n**正文预览**:\n",
                doc.content[:400] + "..." if len(doc.content) > 400 else doc.content
            ]
            return "\n".join(lines), topics, topic, docs, doc.title
        except Exception as e:
            return f"❌ 导入失败: {e}", self.get_topics_list(), topic, [], ""

    def select_topic_docs(self, topic: str) -> List[str]:
        return self.get_docs_list_by_topic(topic)

    def select_ref_doc_detail(self, topic: str, doc_title: str) -> Tuple[str, str, str]:
        if topic not in self.url_topics or not doc_title:
            return "", "", ""
        doc = next((d for d in self.url_topics[topic] if d.title == doc_title), None)
        if not doc:
            return "", "", ""
        
        patterns = "、".join(doc.style_patterns) if doc.style_patterns else "暂无智能提取特征"
        return doc.title, doc.content, f"**格式**: {doc.format.value} | **字数**: {doc.word_count}\n**语言特征**: {patterns}"

    def save_ref_doc_edit(self, topic: str, old_title: str, new_title: str, content: str) -> Tuple[str, List[str]]:
        if topic not in self.url_topics or not old_title:
            return "保存失败，未找到源文档", []
        doc = next((d for d in self.url_topics[topic] if d.title == old_title), None)
        if not doc:
            return "未找到对应文档", []
            
        doc.title = new_title.strip()
        doc.content = content.strip()
        doc.word_count = len(doc.content)
        self._save_persistent_data()
        
        return "文档修改已保存！", self.get_docs_list_by_topic(topic)

    def delete_ref_doc_action(self, topic: str, title: str) -> Tuple[str, List[str], List[str]]:
        if topic not in self.url_topics or not title:
            return "请先选择要删除的文档", self.get_topics_list(), []
            
        docs = self.url_topics[topic]
        target = next((d for d in docs if d.title == title), None)
        if target:
            docs.remove(target)
            if not docs:
                del self.url_topics[topic]
            self._save_persistent_data()
            return f"已经成功从主题中移除：《{title}》", self.get_topics_list(), []
        return "文档不存在", self.get_topics_list(), []

    # ═══════════════════════════════════════════════════════════════
    # API配置管理 (LLM API settings)
    # ═══════════════════════════════════════════════════════════════
    def save_llm_config_action(self, prov: str, url: str, key: str, mdl: str, temp: float, tokens: int) -> str:
        try:
            self.api_manager.update(
                provider=prov,
                api_base=url.strip(),
                api_key=key.strip(),
                model=mdl.strip(),
                temperature=temp,
                max_tokens=tokens,
                enable=True
            )
            self.api_manager.save()
            return "LLM 接口参数保存并已默认开启！"
        except Exception as e:
            return "保存失败，请检查网络连接后重试"

    def test_llm_connection_action(self) -> str:
        try:
            res = self.api_manager.test_connection()
            if res.get("success"):
                return f"连接成功 — 模型响应正常：{res.get('message')}"
            err_msg = res.get('message', '未知错误')
            if 'timeout' in str(err_msg).lower():
                return "连接超时 — 请检查 API 地址是否正确，或网络是否需要代理"
            if '401' in str(err_msg) or '403' in str(err_msg):
                return "认证失败 — API Key 无效或已过期，请检查密钥"
            if '404' in str(err_msg):
                return "端点不存在 — API Base URL 或模型名称可能有误"
            return f"连接失败 — {err_msg}"
        except Exception as e:
            return f"连接测试异常 — 请确认 API 地址可访问：{str(e)[:200]}"

    def load_api_config(self) -> Tuple[str, str, str, str, float, int, str]:
        """加载当前 API 配置"""
        c = self.api_manager.config
        provider = c.provider.lower() if c.provider else "openai"
        return provider, c.api_base, c.api_key, c.model, c.temperature, c.max_tokens, ""

    def add_memory_note(self, note: str, session: dict) -> Tuple[str, dict]:
        """添加记忆笔记"""
        if not self.current_user_name:
            return "请先登录", session
        note = note.strip()
        if not note:
            return "请输入笔记内容", session
        self.pdb.add_to_memory(self.current_project_id, note)
        return "已添加笔记", session


THEME_CLASSIC_HTML = """
<style>
    .gradio-container {
        background-image: 
            repeating-linear-gradient(
                -45deg,
                rgba(255,255,255,0.015) 0px,
                rgba(255,255,255,0.015) 1px,
                rgba(0,0,0,0.02) 1px,
                rgba(0,0,0,0.02) 2.5px
            ) !important;
        background-size: auto !important;
        background-position: auto !important;
    }
    .gradio-container::before {
        content: "" !important;
        position: absolute;
        width: 250vw;
        height: 250vh;
        top: -75vh;
        left: -75vw;
        z-index: -2;
        background: 
            radial-gradient(circle at 30% 30%, rgba(79, 126, 164, 0.8) 0%, transparent 50%),
            radial-gradient(circle at 70% 70%, rgba(223, 203, 92, 0.45) 0%, transparent 45%),
            radial-gradient(circle at 70% 30%, rgba(40, 60, 37, 0.7) 0%, transparent 50%),
            radial-gradient(circle at 30% 70%, rgba(100, 139, 168, 0.6) 0%, transparent 50%) !important;
        filter: blur(100px) saturate(140%) !important;
        animation: fluid-rotate-1 25s cubic-bezier(0.4, 0, 0.2, 1) infinite !important;
        pointer-events: none;
    }
    .gradio-container::after {
        content: "" !important;
        position: absolute;
        width: 250vw;
        height: 250vh;
        top: -75vh;
        left: -75vw;
        z-index: -1;
        background: 
            radial-gradient(circle at 50% 20%, rgba(227, 216, 150, 0.4) 0%, transparent 40%),
            radial-gradient(circle at 20% 50%, rgba(28, 55, 101, 0.9) 0%, transparent 45%),
            radial-gradient(circle at 80% 80%, rgba(79, 126, 164, 0.5) 0%, transparent 45%) !important;
        filter: blur(80px) saturate(160%) !important;
        animation: fluid-rotate-2 30s cubic-bezier(0.25, 0.1, 0.25, 1) infinite reverse !important;
        pointer-events: none;
        mix-blend-mode: color-dodge !important;
        opacity: 0.6 !important;
    }
    @keyframes fluid-rotate-1 {
        0% { transform: rotate(0deg) scale(1) translate(0%, 0%); }
        33% { transform: rotate(120deg) scale(1.1) translate(4%, 6%); }
        66% { transform: rotate(240deg) scale(0.9) translate(-4%, 2%); }
        100% { transform: rotate(360deg) scale(1) translate(0%, 0%); }
    }
    @keyframes fluid-rotate-2 {
        0% { transform: rotate(0deg) scale(1.1) translate(0%, 0%); }
        33% { transform: rotate(120deg) scale(0.9) translate(-2%, -3%); }
        66% { transform: rotate(240deg) scale(1.2) translate(3%, -4%); }
        100% { transform: rotate(360deg) scale(1.1) translate(0%, 0%); }
    }
</style>
"""

THEME_STARRY_NIGHT_HTML = """
<style>
    .gradio-container {
        background-image: url('data:image/svg+xml,%3Csvg%20xmlns%3D%22http%3A//www.w3.org/2000/svg%22%20viewBox%3D%220%200%201000%201000%22%20preserveAspectRatio%3D%22xMidYMid%20slice%22%3E%0A%20%20%3Cdefs%3E%0A%20%20%20%20%3Cfilter%20id%3D%22blurLg%22%3E%3CfeGaussianBlur%20stdDeviation%3D%2280%22%20/%3E%3C/filter%3E%0A%20%20%20%20%3Cfilter%20id%3D%22blurMd%22%3E%3CfeGaussianBlur%20stdDeviation%3D%2240%22%20/%3E%3C/filter%3E%0A%20%20%20%20%3Cfilter%20id%3D%22blurSm%22%3E%3CfeGaussianBlur%20stdDeviation%3D%2210%22%20/%3E%3C/filter%3E%0A%20%20%20%20%0A%20%20%20%20%3CradialGradient%20id%3D%22swirlLight%22%20cx%3D%2250%25%22%20cy%3D%2250%25%22%20r%3D%2250%25%22%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%234F7EA4%22%20stop-opacity%3D%220.8%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%23003153%22%20stop-opacity%3D%220%22%20/%3E%0A%20%20%20%20%3C/radialGradient%3E%0A%20%20%20%20%0A%20%20%20%20%3CradialGradient%20id%3D%22swirlMid%22%20cx%3D%2250%25%22%20cy%3D%2250%25%22%20r%3D%2250%25%22%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%232a6a9b%22%20stop-opacity%3D%220.7%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%2300213B%22%20stop-opacity%3D%220%22%20/%3E%0A%20%20%20%20%3C/radialGradient%3E%0A%20%20%20%20%0A%20%20%20%20%3CradialGradient%20id%3D%22swirlDark%22%20cx%3D%2250%25%22%20cy%3D%2250%25%22%20r%3D%2250%25%22%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%23005085%22%20stop-opacity%3D%220.6%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%2305101a%22%20stop-opacity%3D%220%22%20/%3E%0A%20%20%20%20%3C/radialGradient%3E%0A%0A%20%20%20%20%3CradialGradient%20id%3D%22starHalo%22%20cx%3D%2250%25%22%20cy%3D%2250%25%22%20r%3D%2250%25%22%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%23DFCB5C%22%20stop-opacity%3D%220.95%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%2220%25%22%20stop-color%3D%22%23DFCB5C%22%20stop-opacity%3D%220.6%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%2250%25%22%20stop-color%3D%22%231C3765%22%20stop-opacity%3D%220.3%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%231C3765%22%20stop-opacity%3D%220%22%20/%3E%0A%20%20%20%20%3C/radialGradient%3E%0A%20%20%20%20%0A%20%20%20%20%3CradialGradient%20id%3D%22moonHalo%22%20cx%3D%2250%25%22%20cy%3D%2250%25%22%20r%3D%2250%25%22%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%220%25%22%20stop-color%3D%22%23E7D674%22%20stop-opacity%3D%221%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%2215%25%22%20stop-color%3D%22%23DFCB5C%22%20stop-opacity%3D%220.8%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%2240%25%22%20stop-color%3D%22%23648BA8%22%20stop-opacity%3D%220.4%22%20/%3E%0A%20%20%20%20%20%20%3Cstop%20offset%3D%22100%25%22%20stop-color%3D%22%231C3765%22%20stop-opacity%3D%220%22%20/%3E%0A%20%20%20%20%3C/radialGradient%3E%0A%20%20%3C/defs%3E%0A%0A%20%20%3Crect%20width%3D%22100%25%22%20height%3D%22100%25%22%20fill%3D%22%2300172D%22%20/%3E%0A%0A%20%20%3C%21--%20Background%20Stars%20--%3E%0A%20%20%3Cg%20fill%3D%22%23FFF%22%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22100%22%20cy%3D%22200%22%20r%3D%221.5%22%20opacity%3D%220.8%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22250%22%20cy%3D%2280%22%20r%3D%221%22%20opacity%3D%220.6%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22450%22%20cy%3D%22150%22%20r%3D%222%22%20opacity%3D%220.9%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22650%22%20cy%3D%2290%22%20r%3D%221.5%22%20opacity%3D%220.5%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22850%22%20cy%3D%22120%22%20r%3D%222.5%22%20opacity%3D%220.8%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22950%22%20cy%3D%22250%22%20r%3D%221%22%20opacity%3D%220.7%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22150%22%20cy%3D%22350%22%20r%3D%222%22%20opacity%3D%220.9%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22350%22%20cy%3D%22450%22%20r%3D%221.5%22%20opacity%3D%220.6%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22550%22%20cy%3D%22350%22%20r%3D%222.5%22%20opacity%3D%220.8%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22750%22%20cy%3D%22480%22%20r%3D%221%22%20opacity%3D%220.5%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22920%22%20cy%3D%22380%22%20r%3D%222%22%20opacity%3D%220.7%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%2250%22%20cy%3D%22550%22%20r%3D%221.5%22%20opacity%3D%220.8%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22250%22%20cy%3D%22650%22%20r%3D%222%22%20opacity%3D%220.6%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22450%22%20cy%3D%22750%22%20r%3D%221%22%20opacity%3D%220.9%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22650%22%20cy%3D%22650%22%20r%3D%222.5%22%20opacity%3D%220.5%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22850%22%20cy%3D%22750%22%20r%3D%221.5%22%20opacity%3D%220.8%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22950%22%20cy%3D%22600%22%20r%3D%221%22%20opacity%3D%220.7%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22150%22%20cy%3D%22850%22%20r%3D%222%22%20opacity%3D%220.9%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22350%22%20cy%3D%22950%22%20r%3D%221.5%22%20opacity%3D%220.6%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22550%22%20cy%3D%22850%22%20r%3D%222.5%22%20opacity%3D%220.8%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22750%22%20cy%3D%22950%22%20r%3D%221%22%20opacity%3D%220.5%22/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22920%22%20cy%3D%22880%22%20r%3D%222%22%20opacity%3D%220.7%22/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3C%21--%20Flowing%20Swirls%20--%3E%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%220%20300%20300%22%20to%3D%22360%20300%20300%22%20dur%3D%2245s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22300%22%20cy%3D%22300%22%20rx%3D%22450%22%20ry%3D%22200%22%20fill%3D%22url%28%23swirlLight%29%22%20filter%3D%22url%28%23blurLg%29%22%20transform%3D%22rotate%2830%20300%20300%29%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22300%22%20cy%3D%22300%22%20rx%3D%22300%22%20ry%3D%22150%22%20fill%3D%22url%28%23swirlMid%29%22%20filter%3D%22url%28%23blurMd%29%22%20transform%3D%22rotate%28-20%20300%20300%29%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%22360%20750%20400%22%20to%3D%220%20750%20400%22%20dur%3D%2260s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22750%22%20cy%3D%22400%22%20rx%3D%22500%22%20ry%3D%22250%22%20fill%3D%22url%28%23swirlMid%29%22%20filter%3D%22url%28%23blurLg%29%22%20transform%3D%22rotate%28-45%20750%20400%29%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22750%22%20cy%3D%22400%22%20rx%3D%22200%22%20ry%3D%22400%22%20fill%3D%22url%28%23swirlLight%29%22%20filter%3D%22url%28%23blurMd%29%22%20transform%3D%22rotate%2815%20750%20400%29%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%220%20400%20800%22%20to%3D%22360%20400%20800%22%20dur%3D%2250s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22400%22%20cy%3D%22800%22%20rx%3D%22400%22%20ry%3D%22250%22%20fill%3D%22url%28%23swirlDark%29%22%20filter%3D%22url%28%23blurLg%29%22%20transform%3D%22rotate%2860%20400%20800%29%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3C%21--%20The%20Moon%20--%3E%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%220%20850%20200%22%20to%3D%22360%20850%20200%22%20dur%3D%2230s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22850%22%20cy%3D%22200%22%20r%3D%22180%22%20fill%3D%22url%28%23moonHalo%29%22%20filter%3D%22url%28%23blurSm%29%22%20/%3E%0A%20%20%20%20%3C%21--%20inner%20swirl%20inside%20moon%20--%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22850%22%20cy%3D%22200%22%20rx%3D%22140%22%20ry%3D%2270%22%20fill%3D%22url%28%23swirlLight%29%22%20opacity%3D%220.3%22%20filter%3D%22url%28%23blurSm%29%22%20transform%3D%22rotate%2845%20850%20200%29%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3C%21--%20Stars%20--%3E%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%22360%20200%20150%22%20to%3D%220%20200%20150%22%20dur%3D%2225s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22200%22%20cy%3D%22150%22%20r%3D%22120%22%20fill%3D%22url%28%23starHalo%29%22%20filter%3D%22url%28%23blurSm%29%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22200%22%20cy%3D%22150%22%20rx%3D%2290%22%20ry%3D%2240%22%20fill%3D%22url%28%23swirlLight%29%22%20opacity%3D%220.4%22%20filter%3D%22url%28%23blurSm%29%22%20transform%3D%22rotate%28-30%20200%20150%29%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3Cg%3E%0A%20%20%20%20%EF%BF%BDnimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%220%20150%20550%22%20to%3D%22360%20150%20550%22%20dur%3D%2222s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22150%22%20cy%3D%22550%22%20r%3D%22100%22%20fill%3D%22url%28%23starHalo%29%22%20filter%3D%22url%28%23blurSm%29%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%22360%20500%20450%22%20to%3D%220%20500%20450%22%20dur%3D%2235s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22500%22%20cy%3D%22450%22%20r%3D%2280%22%20fill%3D%22url%28%23starHalo%29%22%20filter%3D%22url%28%23blurSm%29%22%20opacity%3D%220.8%22%20/%3E%0A%20%20%3C/g%3E%0A%0A%20%20%3Cg%3E%0A%20%20%20%20%3CanimateTransform%20attributeName%3D%22transform%22%20type%3D%22rotate%22%20from%3D%220%20750%20750%22%20to%3D%22360%20750%20750%22%20dur%3D%2228s%22%20repeatCount%3D%22indefinite%22%20/%3E%0A%20%20%20%20%3Ccircle%20cx%3D%22750%22%20cy%3D%22750%22%20r%3D%22110%22%20fill%3D%22url%28%23starHalo%29%22%20filter%3D%22url%28%23blurSm%29%22%20/%3E%0A%20%20%20%20%3Cellipse%20cx%3D%22750%22%20cy%3D%22750%22%20rx%3D%2280%22%20ry%3D%2230%22%20fill%3D%22url%28%23swirlLight%29%22%20opacity%3D%220.3%22%20filter%3D%22url%28%23blurSm%29%22%20transform%3D%22rotate%2870%20750%20750%29%22%20/%3E%0A%20%20%3C/g%3E%0A%3C/svg%3E') !important;
        background-size: cover !important;
        background-position: center !important;
    }
    .gradio-container::before {
        content: none !important;
    }
    .gradio-container::after {
        content: none !important;
    }
</style>
"""


# ═══════════════════════════════════════════════════════════════
# 界面构建 (Gradio UI Layout Design)
# ═══════════════════════════════════════════════════════════════

def build_ui() -> gr.Blocks:
    app = GradioApp()
    
    # 产品工具级克制设计：Restrained palette, sans-serif 系统字体栈, 功能性动效
    custom_css = """
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+SC:wght@400;500;600;700&family=Playfair+Display:ital,wght@0,600;1,600&display=swap');

    :root {
        /* Strictly Sampled Van Gogh Starry Night Palette */
        /* Deep Skies */
        --color-sky-deep: #0D162B;
        --color-sky-mid: #1C3765;
        --color-sky-light: #4F7EA4;
        --color-sky-swirl: #648BA8;
        --color-sky-pale: #8DB3C3;
        
        /* Moon & Stars */
        --color-moon-glow: #DFCB5C;
        --color-moon-core: #E3D896;
        --color-star-yellow: #E7D674;
        
        /* Cypress & Hills */
        --color-cypress-dark: #0D1917;
        --color-cypress-mid: #283C25;
        --color-hills: #28406F;

        /* Derived UI colors */
        --color-accent: var(--color-moon-glow);
        --color-accent-hover: var(--color-moon-core);
        --color-accent-active: #C8B038;
        --color-accent-focus: rgba(223, 203, 92, 0.3);
        
        --color-ink: #F8FAFC; 
        --color-ink-body: #E2E8F0; 
        --color-ink-muted: #94A3B8; 
        
        --color-danger: oklch(65% 0.18 20);
        --color-danger-hover: oklch(75% 0.18 20);
        
        /* Geometry */
        --radius-button: 12px;
        --radius-card: 20px;
        --radius-input: 12px;
        --radius-sm: 8px;

        /* Apple-Style Easing & Animation */
        --ease-out-strong: cubic-bezier(0.23, 1, 0.32, 1);
        --ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);
    }

    @keyframes smooth-enter {
        0% { opacity: 0; transform: scale(0.98); }
        100% { opacity: 1; transform: scale(1); }
    }

    /* Container Background - Apple Music Fluid Style */
    .gradio-container {
        position: relative;
        overflow: hidden;
        z-index: 1; /* Establishes stacking context */
        background-color: var(--color-sky-deep) !important;
        
        font-family: "Inter", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        color: var(--color-ink) !important;
    }

    .gradio-container p, .gradio-container span, .gradio-container label,
    .gradio-container li, .gradio-container div {
        color: var(--color-ink-body);
    }

    /* Apple-Style Glassmorphism Surfaces (Separated to fix dropdown clipping) */
    .gradio-container .gr-panel,
    .gradio-container .gr-box,
    .gradio-container .gr-group,
    .gradio-container .gr-form,
    .gradio-container fieldset,
    .gradio-container [class*="panel"],
    .gradio-container [class*="box"],
    .gradio-container [class*="group"] {
        background: rgba(13, 22, 43, 0.55) !important;
        color: var(--color-ink-body) !important;
        border: 1px solid rgba(79, 126, 164, 0.2) !important;
        border-top: 1px solid rgba(141, 179, 195, 0.25) !important;
        border-left: 1px solid rgba(141, 179, 195, 0.18) !important;
        border-radius: var(--radius-card) !important;
        padding: 16px !important;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.06) !important;
        animation: smooth-enter 300ms var(--ease-out-strong) both;
    }

    /* Accordion: special deep-blue glass styling */
    .gradio-container [class*="accordion"],
    .gradio-container details {
        background: rgba(13, 22, 43, 0.6) !important;
        border: 1px solid rgba(100, 139, 168, 0.25) !important;
        border-radius: var(--radius-card) !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35) !important;
        overflow: hidden;
        animation: smooth-enter 300ms var(--ease-out-strong) both;
    }

    /* Accordion header/summary button */
    .gradio-container details > summary,
    .gradio-container [class*="accordion"] > button,
    .gradio-container [class*="accordion-header"] {
        background: rgba(28, 55, 101, 0.5) !important;
        color: var(--color-ink) !important;
        border-bottom: 1px solid rgba(100, 139, 168, 0.2) !important;
        border-radius: var(--radius-card) var(--radius-card) 0 0 !important;
        padding: 12px 16px !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em;
        transition: background 150ms var(--ease-out-strong), transform 150ms var(--ease-out-strong), filter 150ms var(--ease-out-strong) !important;
    }
    .gradio-container details > summary:hover,
    .gradio-container [class*="accordion"] > button:hover {
        background: rgba(40, 64, 111, 0.65) !important;
        transform: translateY(-1px);
    }
    .gradio-container details > summary:active,
    .gradio-container [class*="accordion"] > button:active {
        transform: scale(0.98);
        filter: blur(1px) brightness(0.9);
    }

    /* Apply Blur ONLY to major structural containers */
    .sidebar-pane, .workspace-pane {
        background: rgba(20, 35, 60, 0.15) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-left: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: var(--radius-card);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;

    }
    
    /* Fix global dropdown Z-index in case Gradio doesn't portal it correctly */
    .options, .wrap.wrap.wrap {
        z-index: 99999 !important;
    }
    
    /* Ensure elements inside workspace do not hide overflowing dropdowns */
    .workspace-pane * {
        /* Gradio sometimes adds overflow: hidden to columns, we must override it for dropdowns to escape */
    }
    .gr-dropdown {
        z-index: 100 !important;
    }

    
    .sidebar-pane { padding: 16px; }
    .workspace-pane { padding: 24px; }
    .ws-panel-hidden { display: none !important; }
    .ws-panel-visible { display: block !important; }

    .gradio-container .gr-group *,
    .gradio-container [class*="group"] *,
    .gradio-container [class*="accordion"] * {
        color: var(--color-ink-body) !important;
    }

    /* Starry Cards */
    .ios-card {
        background: rgba(255, 255, 255, 0.03) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-radius: var(--radius-card);
        padding: 16px;
        margin-bottom: 8px;
        transition: box-shadow 0.25s;
    }
    .ios-card:hover {
        
        background: rgba(255, 255, 255, 0.06) !important;
        box-shadow: 0 8px 24px rgba(223, 203, 92, 0.15); /* Moon glow */
        border-color: rgba(223, 203, 92, 0.4) !important;
    }
    .ios-card * {
        color: var(--color-ink-body) !important;
    }

    .empty-state-card {
        background: rgba(0, 0, 0, 0.2) !important;
        border: 1px dashed rgba(255, 255, 255, 0.15);
        border-radius: var(--radius-card);
        padding: 40px 32px;
        text-align: center;
    }
    .empty-state-card h3 {
        color: var(--color-accent) !important;
        margin: 0 0 8px 0;
        font-weight: 600;
    }
    .empty-state-card p {
        margin: 0;
        color: var(--color-ink-muted) !important;
    }

    /* Artistic Headers */
    .gradio-container h1, .gradio-container h2, .gradio-container h3 {
        font-family: "Inter", "Noto Sans SC", sans-serif !important;
        color: var(--color-ink) !important;
        letter-spacing: -0.01em;
    }

    /* Badges */
    .badge-info {
        background: rgba(141, 179, 195, 0.15) !important;
        color: #E2E8F0 !important;
        font-weight: 600;
        border-radius: var(--radius-sm);
        padding: 4px 12px;
        font-size: 12px;
        display: inline-block;
        border: 1px solid rgba(141, 179, 195, 0.3);

    }

    /* Swirling Title Banner */
    .title-banner {
        background: rgba(255, 255, 255, 0.02) !important;
        border: 1px solid rgba(223, 203, 92, 0.3);
        border-top: 1px solid rgba(223, 203, 92, 0.5);
        border-radius: var(--radius-card);
        padding: 20px 24px;
        margin-bottom: 20px;

        box-shadow: 0 8px 32px rgba(223, 203, 92, 0.15); 
    }
    .title-banner h1 {
        font-family: "Inter", "Noto Sans SC", sans-serif !important;
        color: var(--color-accent) !important;
        font-weight: 700;
        font-size: 28px;
        letter-spacing: -0.02em;
        text-shadow: 0 0 16px rgba(223, 203, 92, 0.6);
    }
    .title-banner p {
        color: rgba(226, 232, 240, 0.8) !important;
        font-size: 14px;
        margin-top: 6px;
    }

    /* Luminous Gold Buttons - Primary */
    .ios-btn-primary {
        background: linear-gradient(135deg, rgba(223, 203, 92, 0.9), rgba(196, 138, 24, 0.9)) !important;
        color: #0D162B !important; 
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(255,255,255,0.4) !important;
        font-weight: 700 !important;
        font-family: "Inter", "Noto Sans SC", sans-serif !important;
        transition: transform 150ms var(--ease-out-strong), box-shadow 150ms ease, filter 150ms ease !important;
        box-shadow: 0 4px 16px rgba(223, 203, 92, 0.3) !important;
        min-height: 44px;
    }
    .ios-btn-primary:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 24px rgba(223, 203, 92, 0.5) !important;
        filter: brightness(1.1);
    }
    .ios-btn-primary:active {
        transform: scale(0.97) !important;
        filter: blur(1px) brightness(0.9) !important;
    }

    /* Secondary Buttons - Semi-transparent blue glass */
    .ios-btn-secondary,
    .gradio-container button.secondary,
    .gradio-container button[variant="secondary"] {
        background: rgba(28, 55, 101, 0.45) !important;
        color: var(--color-sky-pale) !important;
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(100, 139, 168, 0.35) !important;
        font-weight: 500 !important;
        font-family: "Inter", "Noto Sans SC", sans-serif !important;
        transition: all 150ms var(--ease-out-strong) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2) !important;
        min-height: 44px;
    }
    .ios-btn-secondary:hover,
    .gradio-container button.secondary:hover,
    .gradio-container button[variant="secondary"]:hover {
        background: rgba(40, 64, 111, 0.65) !important;
        border-color: rgba(141, 179, 195, 0.5) !important;
        color: var(--color-ink) !important;
        box-shadow: 0 4px 16px rgba(79, 126, 164, 0.3) !important;
        transform: translateY(-1px);
    }
    .ios-btn-secondary:active,
    .gradio-container button.secondary:active,
    .gradio-container button[variant="secondary"]:active {
        transform: scale(0.97) !important;
        filter: blur(1px) brightness(0.9) !important;
    }

    /* All generic Gradio buttons (untagged) get secondary style by default */
    .gradio-container button:not(.ios-btn-primary):not(.ios-btn-danger):not([class*="tab"]):not([class*="accordion"]):not(.selected) {
        background: rgba(28, 55, 101, 0.45) !important;
        color: var(--color-sky-pale) !important;
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(100, 139, 168, 0.35) !important;
        font-weight: 500 !important;
        transition: all 150ms var(--ease-out-strong) !important;
        min-height: 40px;
    }
    .gradio-container button:not(.ios-btn-primary):not(.ios-btn-danger):not([class*="tab"]):not([class*="accordion"]):not(.selected):hover {
        background: rgba(40, 64, 111, 0.65) !important;
        border-color: rgba(141, 179, 195, 0.5) !important;
        color: var(--color-ink) !important;
        transform: translateY(-1px);
    }
    .gradio-container button:not(.ios-btn-primary):not(.ios-btn-danger):not([class*="tab"]):not([class*="accordion"]):not(.selected):active {
        transform: scale(0.97) !important;
        filter: blur(1px) brightness(0.9) !important;
    }

    /* Danger Buttons */
    .ios-btn-danger,
    .gradio-container button.stop,
    .gradio-container button[variant="stop"] {
        background: rgba(220, 38, 38, 0.12) !important;
        color: #FCA5A5 !important;
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(220, 38, 38, 0.35) !important;
        font-weight: 500 !important;
        transition: all 150ms var(--ease-out-strong) !important;
        min-height: 44px;
    }
    .ios-btn-danger:hover,
    .gradio-container button.stop:hover,
    .gradio-container button[variant="stop"]:hover {
        background: rgba(220, 38, 38, 0.22) !important;
        border-color: rgba(220, 38, 38, 0.6) !important;
        box-shadow: 0 4px 16px rgba(220, 38, 38, 0.2) !important;
        transform: translateY(-1px);
    }
    .ios-btn-danger:active,
    .gradio-container button.stop:active,
    .gradio-container button[variant="stop"]:active {
        transform: scale(0.97) !important;
        filter: blur(1px) brightness(0.9) !important;
    }

    /* Agent Bubbles */
    .agent-bubble {
        border: 1px solid rgba(255, 255, 255, 0.1);
        background: rgba(255, 255, 255, 0.05);
        color: var(--color-ink-body);
        padding: 10px 16px;
        border-radius: var(--radius-card);
        margin-bottom: 10px;

    }

    /* Text Inputs */
    .gradio-container input, .gradio-container textarea {
        color: var(--color-ink) !important;
        background: rgba(0, 0, 0, 0.25) !important;
        border-radius: var(--radius-input) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-top: 1px solid rgba(0,0,0,0.4) !important; /* Inset feel */
        transition: border-color 150ms var(--ease-out-strong), box-shadow 150ms var(--ease-out-strong), background 150ms var(--ease-out-strong) !important;
    }
    input:focus, textarea:focus, .gr-input:focus-within {
        background: rgba(0, 0, 0, 0.4) !important;
        border-color: var(--color-accent) !important;
        box-shadow: 0 0 0 2px var(--color-accent-focus), inset 0 2px 4px rgba(0,0,0,0.5) !important;
        outline: none;
    }

    /* Selected Tabs */
    button.selected {
        background: rgba(255, 255, 255, 0.08) !important;
        color: var(--color-accent) !important;
        border-bottom: 2px solid var(--color-accent) !important;
        transition: all 0.2s ease !important;
        font-weight: 600;
    }

    /* Step Progress - Glassy */
    .step-track {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        line-height: 1;
    }
    .step-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px 5px 6px;
        border-radius: var(--radius-button);
        border: 1px solid rgba(255, 255, 255, 0.1);
        white-space: nowrap;
        transition: all 0.25s ease-out;
        background: rgba(255, 255, 255, 0.03);
    }
    .step-num {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 18px;
        height: 18px;
        border-radius: 50%;
        font-size: 11px;
        font-weight: 700;
        line-height: 1;
    }
    .step-label {
        font-weight: 500;
    }
    .step-done {
        border-color: rgba(141, 179, 195, 0.4);
        color: var(--color-sky-pale);
    }
    .step-done .step-num {
        background: rgba(141, 179, 195, 0.4);
        color: #fff;
    }
    .step-current {
        background: rgba(223, 203, 92, 0.1);
        border-color: var(--color-accent);
        color: var(--color-accent);
        box-shadow: 0 2px 12px rgba(223, 203, 92, 0.25);
    }
    .step-current .step-num {
        background: var(--color-accent);
        color: #0D162B;
    }
    .step-todo {
        border-color: rgba(255, 255, 255, 0.05);
        color: var(--color-ink-muted);
    }
    .step-todo .step-num {
        background: transparent;
        border: 1px solid rgba(255, 255, 255, 0.2);
        color: var(--color-ink-muted);
    }

    /* Rhythm & Alignment */
    .sidebar-pane > * + *, .workspace-pane > * + * {
        margin-top: 16px;
    }

    *:focus-visible {
        outline: 2px solid var(--color-accent) !important;
        outline-offset: 2px !important;
    }

    @media (prefers-reduced-motion: reduce) {
        *, *::before, *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }
    }
    """

    with gr.Blocks(title="公文写作智能体 V10", css=custom_css) as demo:
        # 动态背景 CSS 注入
        dynamic_theme_css = gr.HTML(value=THEME_STARRY_NIGHT_HTML, visible=True)
        # 全局状态字典
        session_state = gr.State({
            "current_question_index": 0,
            "current_topic": "",
            "current_ref_doc_title": ""
        })
        
        # 顶部渐变标题栏
        gr.Markdown(
            """
            <div class="title-banner">
                <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: 0.5px;">公文写作智能助手</h1>
                <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">多角色协作写作 · 智能审查校对 · 一键生成规范公文</p>
            </div>
            """
        )

        with gr.Row():
            # ═══════════════════════════════════════════════════════
            # 左侧资源栏 (Finder Sidebar)
            # ═══════════════════════════════════════════════════════
            with gr.Column(scale=1, elem_classes="sidebar-pane"):
                gr.Markdown("### 资源管理器")

                # ── 身份卡 ──
                with gr.Group(elem_classes="ios-card"):
                    gr.Markdown("**用户身份**")
                    user_input = gr.Textbox(
                        label="登录用户名",
                        placeholder="输入姓名以切换或建立新空间",
                        value=app.current_user_name or ""
                    )
                    user_login_btn = gr.Button("确认身份", variant="secondary", elem_classes="ios-btn-secondary")
                    user_status_msg = gr.Markdown(f"当前用户: **{app.current_user_name or '未选择'}**")

                # ── 项目管理器 ──
                with gr.Accordion("项目工程", open=True):
                    project_selector = gr.Dropdown(
                        choices=app.get_projects_list(),
                        label="当前活动项目",
                        value=app.get_projects_list()[0] if app.get_projects_list() else None
                    )
                    
                    with gr.Row():
                        proj_create_trigger = gr.Button("新建项目", variant="secondary", size="sm", elem_classes="ios-btn-secondary")
                        proj_delete_btn = gr.Button("删除项目", variant="stop", size="sm", elem_classes="ios-btn-danger")
                    
                    # 删除确认面板
                    with gr.Column(visible=False) as confirm_delete_box:
                        gr.Markdown("### 确认删除")
                        gr.Markdown("此操作不可撤销，项目中的所有草稿和历史将被永久删除。")
                        with gr.Row():
                            confirm_delete_yes_btn = gr.Button("确认删除", variant="stop", size="sm", elem_classes="ios-btn-danger")
                            confirm_delete_no_btn = gr.Button("取消", variant="secondary", size="sm", elem_classes="ios-btn-secondary")
                    
                    # 新建项目侧面板 (隐藏，点击显示)
                    with gr.Column(visible=False) as new_proj_box:
                        new_proj_name = gr.Textbox(label="新项目名称", placeholder="例如: 智能研学总结报告")
                        new_proj_desc = gr.Textbox(label="项目描述(可选)")
                        with gr.Row():
                            new_proj_save_btn = gr.Button("保存", variant="primary", size="sm", elem_classes="ios-btn-primary")
                            new_proj_cancel_btn = gr.Button("取消", variant="secondary", size="sm")

                # ── 参考素材库 ──
                with gr.Accordion("参考资料文件夹", open=False):
                    topic_selector = gr.Dropdown(
                        choices=app.get_topics_list(),
                        label="主题分类",
                        value=app.get_topics_list()[0] if app.get_topics_list() else None
                    )
                    ref_doc_selector = gr.Dropdown(
                        choices=[],
                        label="选择参考文档"
                    )
                    
                    with gr.Row():
                        url_import_trigger = gr.Button("导入新网页", variant="secondary", size="sm", elem_classes="ios-btn-secondary")
                        ref_doc_delete_btn = gr.Button("移出素材", variant="stop", size="sm", elem_classes="ios-btn-danger")
                    
                    # 导入URL表单 (隐藏，点击显示)
                    with gr.Column(visible=False) as url_import_box:
                        url_input_val = gr.Textbox(label="网页 URL", placeholder="https://example.com/article")
                        url_topic_val = gr.Textbox(label="导入至主题", placeholder="例如: 教育改革参考")
                        with gr.Row():
                            url_save_btn = gr.Button("执行导入", variant="primary", size="sm", elem_classes="ios-btn-primary")
                            url_cancel_btn = gr.Button("取消", variant="secondary", size="sm")

                # ── 系统快捷设置 ──
                with gr.Accordion("系统设置", open=False):
                    bg_theme_selector = gr.Dropdown(
                        label="背景美学风格",
                        choices=["经典流光 (Classic Fluid)", "星月夜漩涡 (Starry Night)"],
                        value="星月夜漩涡 (Starry Night)"
                    )
                    with gr.Row():
                        goto_api_btn = gr.Button("API 设置", elem_classes="ios-btn-secondary")
                        goto_profile_btn = gr.Button("用户画像", elem_classes="ios-btn-secondary")

                global_status_msg = gr.Markdown()

            # ═══════════════════════════════════════════════════════
            # 右侧主工作区 (Main Workspace)
            # ═══════════════════════════════════════════════════════
            with gr.Column(scale=3, elem_classes="workspace-pane"):
                
                # ─── 面板 A: 写作项目工作台 ───
                with gr.Column(visible=True, elem_classes="ws-panel-visible") as project_panel:
                    # 顶部进度和状态
                    with gr.Row():
                        with gr.Column(scale=2):
                            active_proj_title = gr.Markdown("## 选择左侧项目或新建项目开始写作")
                        with gr.Column(scale=1, min_width=260):
                            progress_badge_html = gr.HTML(build_progress_badge("问卷"))
                    
                    # 场景选择卡片 (路由问卷)
                    with gr.Column(visible=True, elem_classes="ios-card ws-panel-hidden") as routing_box:
                        routing_q_title = gr.Markdown("### 场景路由选择")
                        routing_q_desc = gr.Markdown()
                        routing_options_disp = gr.Markdown()
                        routing_options_dropdown = gr.Dropdown(
                            label="请选择最符合的场景",
                            choices=[],
                            allow_custom_value=True,
                            interactive=True
                        )
                        routing_custom_desc = gr.Textbox(
                            label="自定义新场景描述",
                            placeholder="如果以上场景都不符合，请先选择「自定义场景」，再在此描述您的实际场景",
                            visible=True
                        )
                        routing_submit_btn = gr.Button("确认选择并导入", variant="primary", elem_classes="ios-btn-primary")

                    with gr.Tabs() as project_tabs:
                        
                        # Tab 1: 需求问卷
                        with gr.Tab("需求问卷", id="tab_q"):
                            with gr.Column(visible=True, elem_classes="ws-panel-visible") as question_card:
                                current_q_prog = gr.Markdown("### 准备好了，请回答下方问题")
                                current_q_title = gr.Markdown("请在左侧新建项目或选择项目以启动写作...")
                                current_q_desc = gr.Markdown()
                                current_q_hint = gr.Markdown()
                                q_answer_input = gr.Textbox(label="您的回答", lines=4, placeholder="请提供详细素材，供智能写作参考。若无需要可点击跳过...")
                                
                                with gr.Row():
                                    q_btn_back = gr.Button("回退", elem_classes="ios-btn-secondary")
                                    q_btn_skip = gr.Button("跳过", elem_classes="ios-btn-secondary")
                                    q_btn_submit = gr.Button("提交回答", variant="primary", elem_classes="ios-btn-primary")
                                    q_btn_finish = gr.Button("提前完成", elem_classes="ios-btn-secondary")
                                    q_btn_reset = gr.Button("重头开始(清空进度)", variant="stop", elem_classes="ios-btn-secondary")
                                
                                q_event_msg = gr.Markdown()
                            
                            with gr.Column(visible=True, elem_classes="empty-state-card ws-panel-hidden") as question_empty_state:
                                gr.Markdown("""
                                <h3>欢迎来到公文写作助手</h3>
                                <p>请在左侧登录并选择或创建一个项目，即可开始回答写作需求问卷。</p>
                                """)
                            
                            def sync_question_card_visibility():
                                return {
                                    question_card: gr.update(elem_classes="ws-panel-visible" if app.current_project_id else "ws-panel-hidden"),
                                    question_empty_state: gr.update(elem_classes="ws-panel-hidden" if app.current_project_id else "empty-state-card ws-panel-visible")
                                }

                            demo.load(
                                fn=sync_question_card_visibility,
                                outputs=[question_card, question_empty_state]
                            )

                        # Tab 2: 智能方案生成
                        with gr.Tab("写作大纲方案", id="tab_plan"):
                            plan_output_text = gr.Textbox(label="生成的方案大纲与结构", lines=12, interactive=False)
                            kb_exemplar_recommend = gr.Markdown("### 知识库推荐范文")
                            
                            gr.Markdown("#### 方案大纲调优调整")
                            with gr.Row():
                                ui_style_selector = gr.Dropdown(
                                    choices=[label for label, _ in STYLE_CHOICES],
                                    value="人民日报风格",
                                    label="选择主导风格"
                                )
                                ui_doc_selector = gr.Dropdown(
                                    choices=[label for label, _ in DOC_TYPE_CHOICES],
                                    value="通讯（推荐1500-3000字）",
                                    label="选择期望公文文种"
                                )
                                plan_regen_btn = gr.Button("重新生成大纲", variant="secondary", elem_classes="ios-btn-secondary")
                            
                            plan_btn_next = gr.Button("确认方案，开始写作", variant="primary", elem_classes="ios-btn-primary")

                        # Tab 3: 智能写作生成
                        with gr.Tab("文稿草稿生成", id="tab_write"):
                            materials_input = gr.Textbox(label="可贴入本次写作的其他原始语料/素材内容(可选)", lines=5, placeholder="粘贴任何其他零碎记录、会议讲话或新闻参考数据...")
                            write_start_btn = gr.Button("开始写作（通常需要 30-60 秒）", variant="primary", elem_classes="ios-btn-primary")
                            
                            write_event_msg = gr.Markdown()
                            draft_editor = gr.Textbox(label="草稿（主版本）", lines=16, placeholder="草稿内容将在这里呈现...")
                            
                            with gr.Accordion("多角色协作日志", open=False):
                                coord_agent_logs = gr.Textbox(label="协作日志", lines=8, max_lines=30, interactive=False)
                            with gr.Accordion("多格式版本草稿", open=False):
                                multi_versions_preview = gr.Textbox(label="多格式版本", lines=10, max_lines=30, interactive=False)
                                
                            write_btn_next = gr.Button("对文稿执行智能审查", variant="primary", elem_classes="ios-btn-primary")

                        # Tab 4: 智能审阅修正 (HITL)
                        with gr.Tab("智能审查与人工介入", id="tab_review"):
                            review_event_msg = gr.Markdown()
                            review_summary_text = gr.Textbox(label="多维审查得分与总结", lines=8, max_lines=30, interactive=False)
                            
                            with gr.Row():
                                with gr.Column(scale=1):
                                    with gr.Group(elem_classes="ios-card"):
                                        gr.Markdown("**检测到的偏见与问题清单**")
                                        review_issues_list = gr.Markdown()
                                with gr.Column(scale=1):
                                    with gr.Group(elem_classes="ios-card"):
                                        gr.Markdown("**格式规范合规度(GB/T 9704-2012)**")
                                        review_format_text = gr.Markdown()
                                        
                            gr.Markdown("#### 人工介入更新 (HITL)")
                            manual_edit_text = gr.Textbox(label="在此处对文稿进行人工细节微调...", lines=8, max_lines=30)
                            with gr.Row():
                                manual_save_btn = gr.Button("保存手动修改", variant="secondary", elem_classes="ios-btn-secondary")
                                re_review_btn = gr.Button("重新执行审查", variant="secondary", elem_classes="ios-btn-secondary")
                                
                            review_btn_next = gr.Button("确认文稿无误，完成交付", variant="primary", elem_classes="ios-btn-primary")

                        # Tab 5: 终稿交付完成
                        with gr.Tab("最终成果交付", id="tab_finalize"):
                            final_draft_output = gr.Textbox(label="最终公文文稿", lines=18, max_lines=50, interactive=True)
                            final_multi_versions = gr.Textbox(label="多格式版本备份", lines=10, max_lines=30, interactive=False)
                            workflow_summary_text = gr.Textbox(label="智能协作工作流回溯报告", lines=8, max_lines=30, interactive=False)
                            
                            export_finished_btn = gr.Button("导出完成", variant="primary", elem_classes="ios-btn-primary")

                # ─── 面板 B: 参考素材编辑器 ───
                with gr.Column(visible=True, elem_classes="ws-panel-hidden") as ref_doc_panel:
                    gr.Markdown("## 参考资料文件视窗")
                    
                    with gr.Group(elem_classes="ios-card"):
                        ref_doc_edit_title = gr.Textbox(label="参考文章标题")
                        ref_doc_edit_meta = gr.Markdown()
                        ref_doc_edit_content = gr.Textbox(label="正文内容", lines=15)
                        
                        with gr.Row():
                            ref_doc_edit_save = gr.Button("保存参考文件修改", variant="primary", elem_classes="ios-btn-primary")
                            ref_doc_edit_close = gr.Button("关闭视窗", variant="secondary", elem_classes="ios-btn-secondary")
                            
                    ref_doc_edit_msg = gr.Markdown()

                # ─── 面板 C: API参数配置 ───
                with gr.Column(visible=True, elem_classes="ws-panel-hidden") as api_config_panel:
                    gr.Markdown("## 智能体大模型接口配置")
                    
                    with gr.Group(elem_classes="ios-card"):
                        gr.Markdown("支持 OpenAI 兼容格式的多云 API 切换。开启后将唤醒大模型执行真正的写作与审稿。")
                        api_provider = gr.Dropdown(
                            choices=["openai", "dashscope", "deepseek", "zhipu", "anthropic", "local"],
                            value="openai",
                            label="快速模板设置"
                        )
                        with gr.Row():
                            api_base_url = gr.Textbox(label="API Base URL", placeholder="https://api.openai.com/v1")
                            api_key_val = gr.Textbox(label="API Key", type="password", placeholder="sk-...")
                        with gr.Row():
                            api_model_name = gr.Textbox(label="模型名称 (Model)", placeholder="gpt-4o")
                            api_temp = gr.Slider(0.0, 2.0, value=0.7, step=0.1, label="创新度 (Temperature)")
                            api_tokens = gr.Slider(1000, 32000, value=8000, step=500, label="最大生成Token (Max Tokens)")
                            
                        with gr.Row():
                            api_save_btn = gr.Button("保存并启用配置", variant="primary", elem_classes="ios-btn-primary")
                            api_test_btn = gr.Button("接口连通性测试", variant="secondary")
                            api_close_btn = gr.Button("关闭设置", variant="secondary")
                            
                    api_config_msg = gr.Markdown()

                # ─── 面板 D: 用户画像与写作记忆 ───
                with gr.Column(visible=True, elem_classes="ws-panel-hidden") as profile_panel:
                    gr.Markdown("## 个人画像与写作风格记忆")
                    
                    with gr.Row():
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes="ios-card"):
                                gr.Markdown("### 写作分析偏好")
                                user_strengths_weaknesses = gr.Markdown("加载中...")
                        with gr.Column(scale=1):
                            with gr.Group(elem_classes="ios-card"):
                                gr.Markdown("### 用户长期记忆笔记")
                                memory_summary_text = gr.Textbox(label="记忆笔记列表", lines=8, interactive=False)
                                
                                memory_note_input = gr.Textbox(label="手动添加偏好特征记忆", placeholder="例如: 喜欢短排比句，避免过度口语化...")
                                memory_add_btn = gr.Button("写入永久记忆", variant="primary", elem_classes="ios-btn-primary")
                                memory_add_msg = gr.Markdown()
                                
                    profile_close_btn = gr.Button("关闭画像", variant="secondary")


        # ═══════════════════════════════════════════════════════
        # Gradio 事件处理器绑定 (Event Listeners)
        # ═══════════════════════════════════════════════════════
        
        # ── 1. 登录用户事件 ──
        def login_user_fn(name):
            msg, projects, default_proj = app.switch_or_create_user(name)
            # 登录后仅切换用户空间，不自动加载项目
            return (
                msg,
                gr.update(value=f"当前用户: **{name}**", visible=True),
                gr.update(choices=projects, value=None),
                gr.update(choices=app.get_topics_list(), value=None),
                # auto_msgs: 清空右侧面板，不加载任何项目
                gr.update(value=f"欢迎，{name}。请新建或选择项目开始写作。"),
                gr.update(value="## 请新建项目以开始"),
                "",  # plan_output_text
                "",  # draft_editor
                "",  # coord_agent_logs
                "",  # review_summary_text
                "",  # final_draft_output
                "",  # final_multi_versions
                gr.update(value=build_progress_badge(""), visible=True),
                gr.update(elem_classes="ios-card ws-panel-hidden"),
                gr.update(value="### 场景路由选择"),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(choices=[], value=None),
                gr.update(value="### 等待选择项目"),
                gr.update(value=""),
                gr.update(value=""),
                gr.update(value=""),
                "",  # 额外的 manual_edit_text 补位
            )

        user_login_btn.click(
            fn=login_user_fn,
            inputs=[user_input],
            outputs=[
                global_status_msg, user_status_msg, project_selector, topic_selector,
                global_status_msg, active_proj_title, plan_output_text,
                draft_editor, coord_agent_logs, review_summary_text,
                final_draft_output, final_multi_versions, progress_badge_html,
                routing_box, routing_q_title, routing_q_desc,
                routing_options_disp, routing_options_dropdown,
                current_q_prog, current_q_title, current_q_desc,
                current_q_hint, manual_edit_text
            ]
        )

        # ── 2. 新建/删除项目面板显隐与事件 ──
        proj_create_trigger.click(
            fn=lambda: gr.update(visible=True),
            outputs=[new_proj_box]
        )
        new_proj_cancel_btn.click(
            fn=lambda: gr.update(visible=False),
            outputs=[new_proj_box]
        )

        def new_proj_fn(name, desc):
            msg, projects, default_proj, q_title, why, opts, plan, kb, routing_vis = app.create_new_project(name, desc)
            ui = app._get_routing_ui_state()
            return (
                msg,
                gr.update(choices=projects, value=default_proj),
                gr.update(visible=False), # 关闭新建表单
                gr.update(value=f"## 项目工程：{name}"),
                gr.update(elem_classes="ios-card ws-panel-visible" if routing_vis else "ios-card ws-panel-hidden"),
                gr.update(value=ui["title"]),
                gr.update(value=ui["desc"]),
                gr.update(value=ui["options_text"]),
                gr.update(choices=ui["choices"], value=None),
                plan,
                kb,
                gr.update(value=build_progress_badge("问卷"))
            )

        new_proj_save_btn.click(
            fn=new_proj_fn,
            inputs=[new_proj_name, new_proj_desc],
            outputs=[
                global_status_msg, project_selector, new_proj_box, 
                active_proj_title, routing_box, routing_q_title, 
                routing_q_desc, routing_options_disp, routing_options_dropdown,
                plan_output_text, kb_exemplar_recommend, progress_badge_html
            ]
        )

        # ── 3. 选择项目事件 ──
        def select_project_fn(name):
            msg, plan, draft, log, rev, fnl, multi, prog_html = app.select_project(name)
            # 项目载入后，第一步加载对应模式问卷
            routing_visible = False
            question_visible = True
            
            # 判断是否需要走路由问卷
            q_text = "专属问卷已完成或可直接前往 Tab 确认方案。"
            why_ask = ""
            hint = ""
            prog_text = "阶段完成"
            routing_ui = {
                "title": "### 场景路由选择",
                "desc": "",
                "options_text": "",
                "choices": []
            }
            
            if app.orchestrator and app.orchestrator.state == OrchestratorState.IDLE:
                routing_visible = True
                question_visible = False
                q_text = "### 场景选择就绪"
                routing_ui = app._get_routing_ui_state()
                
            return (
                msg,
                gr.update(value=f"## 项目工程：{name}"),
                plan,
                draft,
                log,
                rev,
                fnl,
                multi,
                gr.update(value=prog_html),
                gr.update(elem_classes="ios-card ws-panel-visible" if routing_visible else "ios-card ws-panel-hidden"),
                gr.update(value=routing_ui["title"]),
                gr.update(value=routing_ui["desc"]),
                gr.update(value=routing_ui["options_text"]),
                gr.update(choices=routing_ui["choices"], value=None),
                gr.update(value=prog_text),
                gr.update(value=q_text),
                gr.update(value=why_ask),
                gr.update(value=hint),
                draft # 手动微调框
            )

        project_selector.change(
            fn=select_project_fn,
            inputs=[project_selector],
            outputs=[
                global_status_msg, active_proj_title, plan_output_text,
                draft_editor, coord_agent_logs, review_summary_text,
                final_draft_output, final_multi_versions, progress_badge_html,
                routing_box, routing_q_title, routing_q_desc,
                routing_options_disp, routing_options_dropdown,
                current_q_prog, current_q_title, current_q_desc,
                current_q_hint, manual_edit_text
            ]
        )

        # ── 4. 删除项目事件（两步确认）──
        def confirm_delete_fn(name):
            msg, visible = app.confirm_delete_project(name)
            return msg, gr.update(visible=visible)
        
        proj_delete_btn.click(
            fn=confirm_delete_fn,
            inputs=[project_selector],
            outputs=[global_status_msg, confirm_delete_box]
        )
        
        confirm_delete_yes_btn.click(
            fn=app.delete_project_action,
            inputs=[project_selector],
            outputs=[global_status_msg, project_selector, confirm_delete_box]
        )
        
        confirm_delete_no_btn.click(
            fn=lambda: ("已取消", gr.update(visible=False)),
            outputs=[global_status_msg, confirm_delete_box]
        )

        # ── 5. 场景路由提交 ──
        def safe_submit_routing(choice_label, custom_text):
            if not app.current_project_id:
                ui = app._get_routing_ui_state()
                return (
                    "请先登录并在左侧选择或创建一个项目",
                    "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"),
                    gr.update(elem_classes="ws-panel-hidden"), "", "", "",
                    build_progress_badge("问卷"), ui["title"], ui["options_text"],
                    gr.update(choices=ui["choices"], value=None)
                )
            return app.submit_routing_choice_fn(choice_label, custom_text)

        routing_submit_btn.click(
            fn=safe_submit_routing,
            inputs=[routing_options_dropdown, routing_custom_desc],
            outputs=[
                global_status_msg, current_q_prog, current_q_title,
                current_q_desc, routing_box, question_card,
                current_q_hint, plan_output_text, kb_exemplar_recommend,
                progress_badge_html, routing_q_title, routing_options_disp,
                routing_options_dropdown
            ]
        )

        # ── 6. 问卷答题流绑定 (一律返回 exact 10 个值) ──
        def build_answer_flow_handler(action: str):
            def handler(ans):
                if not app.current_project_id:
                    return (
                        "请先登录并在左侧选择或创建一个项目",
                        "", "", "", "", "", "",
                        build_progress_badge("问卷"), gr.update(elem_classes="ws-panel-visible"), ""
                    )
                return app.answer_question_flow(action, ans)
            return handler

        q_btn_submit.click(
            fn=build_answer_flow_handler("submit"),
            inputs=[q_answer_input],
            outputs=[
                q_event_msg, current_q_prog, current_q_title,
                current_q_desc, current_q_hint, plan_output_text,
                kb_exemplar_recommend, progress_badge_html, question_card,
                q_answer_input
            ]
        )
        q_btn_skip.click(
            fn=build_answer_flow_handler("skip"),
            inputs=[q_answer_input],
            outputs=[
                q_event_msg, current_q_prog, current_q_title,
                current_q_desc, current_q_hint, plan_output_text,
                kb_exemplar_recommend, progress_badge_html, question_card,
                q_answer_input
            ]
        )
        q_btn_back.click(
            fn=build_answer_flow_handler("back"),
            inputs=[q_answer_input],
            outputs=[
                q_event_msg, current_q_prog, current_q_title,
                current_q_desc, current_q_hint, plan_output_text,
                kb_exemplar_recommend, progress_badge_html, question_card,
                q_answer_input
            ]
        )
        q_btn_finish.click(
            fn=build_answer_flow_handler("finish"),
            inputs=[q_answer_input],
            outputs=[
                q_event_msg, current_q_prog, current_q_title,
                current_q_desc, current_q_hint, plan_output_text,
                kb_exemplar_recommend, progress_badge_html, question_card,
                q_answer_input
            ]
        )
        
        def reset_project_and_refresh():
            proj_name = app.reset_project()
            if proj_name:
                return select_project_fn(proj_name)
            return ["未重置"] + [gr.update()] * 18
            
        q_btn_reset.click(
            fn=reset_project_and_refresh,
            outputs=[
                global_status_msg, active_proj_title, plan_output_text,
                draft_editor, coord_agent_logs, review_summary_text,
                final_draft_output, final_multi_versions, progress_badge_html,
                routing_box, routing_q_title, routing_q_desc,
                routing_options_disp, routing_options_dropdown,
                current_q_prog, current_q_title, current_q_desc,
                current_q_hint, manual_edit_text
            ]
        )

        # ── 7. 重新生成大纲方案 ──
        plan_regen_btn.click(
            fn=app.regenerate_plan_action,
            inputs=[ui_style_selector, ui_doc_selector],
            outputs=[plan_output_text, global_status_msg]
        )

        # ── 8. 大纲确认并写作 ──
        def safe_plan_next():
            if not app.orchestrator or not app.orchestrator.plan:
                return gr.update(), "请先生成并确认写作大纲方案"
            return gr.update(selected="tab_write"), ""

        plan_btn_next.click(
            fn=safe_plan_next,
            outputs=[project_tabs, global_status_msg]
        )

        # ── 9. 执行文稿生成 ──
        write_start_btn.click(
            fn=app.generate_draft_action,
            inputs=[materials_input],
            outputs=[
                draft_editor, coord_agent_logs, multi_versions_preview,
                write_event_msg, progress_badge_html
            ],
            concurrency_limit=1
        ).then(
            fn=lambda: gr.update(selected="tab_review"),
            outputs=[project_tabs]
        )

        def safe_write_next():
            if not app.orchestrator or not app.orchestrator.draft:
                return gr.update(), "请先生成文稿草稿"
            return gr.update(selected="tab_review"), ""

        # ── 10. 智能体迭代审查 ──
        draft_editor.change(
            fn=lambda d: d,
            inputs=[draft_editor],
            outputs=[manual_edit_text]
        )

        def review_trigger_fn():
            res = app.run_review_action()
            return (*res, app.orchestrator.draft if app.orchestrator else "")

        write_btn_next.click(
            fn=safe_write_next,
            outputs=[project_tabs, global_status_msg]
        ).then(
            fn=review_trigger_fn,
            outputs=[
                review_summary_text, review_issues_list, review_format_text,
                review_event_msg, progress_badge_html, manual_edit_text
            ]
        )

        # ── 11. 人工干预修改 ──
        manual_save_btn.click(
            fn=app.manual_update_draft,
            inputs=[manual_edit_text],
            outputs=[review_event_msg, draft_editor]
        )

        re_review_btn.click(
            fn=app.re_review_action,
            outputs=[review_summary_text, review_issues_list, review_event_msg, draft_editor]
        )

        def safe_review_next():
            if not app.orchestrator or not app.orchestrator.draft:
                return gr.update(), "请先生成并审查文稿草稿"
            return gr.update(selected="tab_finalize"), ""

        review_btn_next.click(
            fn=safe_review_next,
            outputs=[project_tabs, global_status_msg]
        )

        # ── 12. 交付与完成 ──
        def finalize_trigger_fn():
            res = app.finalize_project_action()
            return res

        # 切换到最终 Tab 时自动触发交付计算
        def on_tab_select(evt: gr.SelectData):
            if evt.value and "交付" in str(evt.value):
                return finalize_trigger_fn()
            return ("", "", "", build_progress_badge("审查"))

        project_tabs.select(
            fn=on_tab_select,
            outputs=[final_draft_output, final_multi_versions, workflow_summary_text, progress_badge_html]
        )

        export_finished_btn.click(
            fn=finalize_trigger_fn,
            outputs=[final_draft_output, final_multi_versions, workflow_summary_text, progress_badge_html]
        )

        # ── 13. URL 素材导入面板事件 ──
        url_import_trigger.click(
            fn=lambda: gr.update(visible=True),
            outputs=[url_import_box]
        )
        url_cancel_btn.click(
            fn=lambda: gr.update(visible=False),
            outputs=[url_import_box]
        )

        def url_import_fn(url, topic):
            msg, topics, current_topic, docs, default_doc = app.import_url_action(url, topic)
            return (
                msg,
                gr.update(choices=topics, value=current_topic),
                gr.update(choices=docs, value=default_doc),
                gr.update(visible=False) # 关闭表单
            )

        url_save_btn.click(
            fn=url_import_fn,
            inputs=[url_input_val, url_topic_val],
            outputs=[global_status_msg, topic_selector, ref_doc_selector, url_import_box]
        )

        # ── 14. 切换分类主题事件 ──
        def topic_change_fn(topic):
            if not topic:
                return gr.update(choices=[], value=None)
            docs = app.get_docs_list_by_topic(topic)
            return gr.update(choices=docs, value=None)
            
        topic_selector.change(
            fn=topic_change_fn,
            inputs=[topic_selector],
            outputs=[ref_doc_selector]
        )

        # ── 15. 选择并打开参考文档事件 ──
        def select_ref_doc_fn(topic, title):
            if not title:
                return gr.update(), gr.update(), "", "", ""
            t, c, meta = app.select_ref_doc_detail(topic, title)
            return (
                gr.update(elem_classes="ws-panel-hidden"), # 隐藏项目工作台
                gr.update(elem_classes="ws-panel-visible"),  # 显示文档编辑器
                t,
                meta,
                c
            )

        ref_doc_selector.change(
            fn=select_ref_doc_fn,
            inputs=[topic_selector, ref_doc_selector],
            outputs=[project_panel, ref_doc_panel, ref_doc_edit_title, ref_doc_edit_meta, ref_doc_edit_content]
        )

        ref_doc_edit_close.click(
            fn=lambda: (gr.update(elem_classes="ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden")),
            outputs=[project_panel, ref_doc_panel]
        )

        # ── 16. 编辑参考文档 ──
        def save_ref_doc_fn(topic, old_title, new_title, content):
            msg, docs = app.save_ref_doc_edit(topic, old_title, new_title, content)
            return msg, gr.update(choices=docs, value=new_title)

        ref_doc_edit_save.click(
            fn=save_ref_doc_fn,
            inputs=[topic_selector, ref_doc_selector, ref_doc_edit_title, ref_doc_edit_content],
            outputs=[ref_doc_edit_msg, ref_doc_selector]
        )

        # ── 17. 删除参考文档 ──
        ref_doc_delete_btn.click(
            fn=app.delete_ref_doc_action,
            inputs=[topic_selector, ref_doc_selector],
            outputs=[global_status_msg, topic_selector, ref_doc_selector]
        )

        # ── 18. API 快捷配置面板导航与事件 ──
        goto_api_btn.click(
            fn=lambda: (gr.update(elem_classes="ws-panel-hidden"), gr.update(elem_classes="ws-panel-visible"), *app.load_api_config()),
            outputs=[project_panel, api_config_panel, api_provider, api_base_url, api_key_val, api_model_name, api_temp, api_tokens, api_config_msg]
        )

        api_close_btn.click(
            fn=lambda: (gr.update(elem_classes="ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden")),
            outputs=[project_panel, api_config_panel]
        )

        def switch_api_template_fn(provider):
            app.api_manager.apply_provider_template(provider)
            c = app.api_manager.config
            return c.api_base, c.model, f"已载入 {SUPPORTED_PROVIDERS.get(provider, provider)} 的默认请求端点"

        api_provider.change(
            fn=switch_api_template_fn,
            inputs=[api_provider],
            outputs=[api_base_url, api_model_name, api_config_msg]
        )

        api_save_btn.click(
            fn=app.save_llm_config_action,
            inputs=[api_provider, api_base_url, api_key_val, api_model_name, api_temp, api_tokens],
            outputs=[api_config_msg]
        )

        api_test_btn.click(
            fn=app.test_llm_connection_action,
            outputs=[api_config_msg]
        )

        # ── 19. 用户画像面板导航 ──
        def goto_profile_fn():
            user = app.pdb.get_current_user()
            strengths_weaknesses = "暂无画像分析数据，多写公文大纲可以累积模型偏好统计"
            if user:
                strengths_weaknesses = f"**常用文种**: {', '.join(user.preferences.preferred_doc_types) if user.preferences.preferred_doc_types else '待积累'}\n"
                strengths_weaknesses += f"**常用风格**: {', '.join(user.preferences.preferred_styles) if user.preferences.preferred_styles else '待积累'}\n"
                strengths_weaknesses += f"\n**优势诊断分析**:\n"
                strengths_weaknesses += "\n".join([f"- {s}" for s in user.common_strengths]) if user.common_strengths else "- 待生成\n"
                strengths_weaknesses += f"\n**短板诊断分析**:\n"
                strengths_weaknesses += "\n".join([f"- {s}" for s in user.common_strengths]) if user.common_strengths else "- 暂无明显偏好短板\n"
                
            memory = app.pdb.get_memory_summary(app.current_project_id)
            return (
                gr.update(elem_classes="ws-panel-hidden"), 
                gr.update(elem_classes="ws-panel-visible"), 
                strengths_weaknesses, 
                memory
            )

        goto_profile_btn.click(
            fn=goto_profile_fn,
            outputs=[project_panel, profile_panel, user_strengths_weaknesses, memory_summary_text]
        )

        profile_close_btn.click(
            fn=lambda: (gr.update(elem_classes="ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden")),
            outputs=[project_panel, profile_panel]
        )

        def add_memory_note_fn(note):
            msg, _ = app.add_memory_note(note, {})
            app._save_persistent_data()
            return msg, app.pdb.get_memory_summary(app.current_project_id), ""

        memory_add_btn.click(
            fn=add_memory_note_fn,
            inputs=[memory_note_input],
            outputs=[memory_add_msg, memory_summary_text, memory_note_input]
        )

        def update_bg_theme(choice):
            if choice == "经典流光 (Classic Fluid)":
                return THEME_CLASSIC_HTML
            else:
                return THEME_STARRY_NIGHT_HTML
                
        bg_theme_selector.change(
            fn=update_bg_theme,
            inputs=[bg_theme_selector],
            outputs=[dynamic_theme_css]
        )

    return demo

if __name__ == "__main__":
    demo = build_ui()
    demo.launch(share=False, inbrowser=True)
