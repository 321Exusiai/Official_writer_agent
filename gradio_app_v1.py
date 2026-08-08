"""
公文写作智能体 — Web 交互台 V11 (GovWrite Craft Studio)

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
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import gradio as gr
from dataclasses import dataclass, field, asdict

# 核心算法模块导入
from src.core.orchestrator import Orchestrator, OrchestratorState
from src.core.personalized_db import (
    PersonalizedDB, ProjectStatus, Project, UserProfile, ReferenceArticle,
    QuestionnaireResults, VocabularyCorpus, UserRequirement, AntiBiasAnalysis, UserPreferences
)
from src.core.writing_mode import WritingMode, get_mode_profile
from src.core.style_adapter import MediaStyle, StyleAdapter
from src.core.document_type import DocumentType
from src.knowledge.knowledge_base import KnowledgeBase
from src.config.api_config import APIConfigManager, SUPPORTED_PROVIDERS
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
        self.orchestrator = self._new_orchestrator()
        
        self.current_user_name: Optional[str] = None
        self.current_project_id: Optional[str] = None
        self.current_pane: str = "project"  # project, ref_doc, api_config, profile
        
        # 网页导入素材本地存储
        self.url_topics: Dict[str, List[ImportedDocument]] = {}
        
        # 尝试载入本地持久化数据
        self._load_persistent_data()

    def _new_orchestrator(self):
        """创建编排器实例，并注入用户记忆（偏好/历史/常见错误）与持久化数据库实例"""
        orch = Orchestrator()
        # 注入与 UI 侧同一的持久化实例，保证工具能读到项目数据（修复假状态）
        orch.set_personalized_db(self.pdb)
        try:
            memory_text = self.pdb.get_memory_summary(
                self.current_project_id if self.current_project_id else None
            )
            if memory_text and memory_text != "无用户数据":
                orch.set_user_memory(memory_text)
        except Exception:
            pass
        return orch

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
            # 原子写入：先写临时文件再替换，避免写入中途异常导致数据库损坏
            tmp_path = DB_FILE_PATH + ".tmp"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            os.replace(tmp_path, DB_FILE_PATH)
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
            self.orchestrator = self._new_orchestrator()
            
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
            return f"创建失败: {e}", self.get_projects_list(), "", "", "", "", "", "", False

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
        self.orchestrator = self._new_orchestrator()
        
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
                self.orchestrator = self._new_orchestrator()
                self._save_persistent_data()
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
            # 如果删除的是当前选中的项目，清空 current_project_id 并重置编排器
            if self.current_project_id == target.id:
                self.current_project_id = None
                self.orchestrator = self._new_orchestrator()
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
        
        routing_q = self.orchestrator.questionnaire.get_routing_question() or {}
        options = routing_q.get("options", [])
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
        custom_note = ""
        if is_custom:
            if not custom_text:
                ui = self._get_routing_ui_state()
                return "选择了自定义场景，请在输入框中对该写作场景进行简短描述。", "", "", "", gr.update(elem_classes="ios-card ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden"), "", "", "", "", ui["title"], ui["options_text"], gr.update(choices=ui["choices"], value=None)
            # 自定义场景描述不再被丢弃——写入写作简报，后续写作与审查都会用到；
            # 路由本身按默认场景进入流程（决策树不支持按自由文本路由）
            try:
                if self.orchestrator and self.orchestrator.brief:
                    base = self.orchestrator.brief.key_materials or ""
                    self.orchestrator.brief.key_materials = (
                        (base + "\n" if base else "") + f"【自定义场景描述】{custom_text}"
                    )
                    custom_note = "（已记录你的场景描述，将并入写作简报）"
            except Exception:
                pass
            print(f"[DEBUG] Custom routing recorded: {custom_text[:60]}")
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
                    f"✅ 锚定成功！我们将采用【{get_mode_profile(self.orchestrator.writing_mode).name}】笔法。{custom_note} 为了写出带感的好文章，请回答这几个关键问题：",
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
                "收到，为了更精准地定位你的需求，请做进一步细分：",
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
                cur_q = self.orchestrator.get_current_mode_question() or {}
                return "回答不能为空，请填写后提交或选择跳过。", "", f"### {cur_q.get('question','')}", cur_q.get('why_ask',''), cur_q.get('hint',''), "", "", progress_html, gr.update(elem_classes="ws-panel-visible"), ""
            has_next, next_q = self.orchestrator.submit_mode_answer(answer_val)
            msg = "您的输入已被记入公文简报！"
            
        elif action == "skip":
            has_next = self.orchestrator.questionnaire.skip_current()
            next_q = self.orchestrator.get_current_mode_question()
            msg = "已跳过此题。"
            
        elif action == "back":
            prev = self.orchestrator.questionnaire.go_back()
            if prev:
                # go_back 返回值缺少 why_ask/hint 键，从当前题目补全以保证 UI 上下文完整
                cur_q = self.orchestrator.get_current_mode_question() or {}
                next_q = {**cur_q, **prev}
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

    def generate_draft_action(self, raw_materials: str, temperature: float = 0.7, progress=gr.Progress()) -> Tuple[str, str, str, str, str]:
        if not self.orchestrator or not self.orchestrator.plan:
            return "", "", "", "请先在「写作大纲方案」阶段确认方案，再开始写作", build_progress_badge("方案")

        try:
            def _progress_cb(p, desc):
                progress(p, desc=desc)
            self.orchestrator.temperature = temperature
            self.orchestrator.write(raw_materials, progress_callback=_progress_cb)
            progress(1.0, desc="草稿生成完成")
            draft = self.orchestrator.draft or "生成失败，请检查模型配置或 API Key 是否有效"

            agent_log = self.orchestrator.get_agent_log_display()
            multi_ver = self.orchestrator.get_multi_versions_display()

            # 保存到项目写作历史
            proj = self.pdb.get_project(self.current_project_id)
            if proj:
                history_record = {
                    "timestamp": datetime.now().isoformat(),
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
                "✅ 草稿已生成！由于系统已移除自动跳页，请点击上方【智能审查与人工介入】进入下一步。",
                build_progress_badge("生成")
            )
        except Exception as e:
            return "", "", "", f"文稿生成失败，请检查 API 设置是否已配置且有效: {e}", build_progress_badge("方案")

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
                source = iss.get("source", "规则引擎")
                source_tag = "🤖 AI深度审查" if source == "AI深度审查" else "🔍 规则引擎"
                ver_tag = f"（第{iss.get('draft_version', i+1)}版）" if iss.get("draft_version") else ""
                issues_text += f"**{i+1}.** {source_tag}{ver_tag} [{iss.get('severity')}] 在 {iss.get('location', '段落')} 处: {iss.get('issue')}\n建议: {iss.get('suggestion')}\n\n"

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
            return f"审查异常，请确认草稿内容格式正确: {e}", "", "", f"审查异常，请确认草稿内容格式正确: {e}", build_progress_badge("审查")

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
                source = iss.get("source", "规则引擎")
                source_tag = "🤖 AI深度审查" if source == "AI深度审查" else "🔍 规则引擎"
                ver_tag = f"（第{iss.get('draft_version', i+1)}版）" if iss.get("draft_version") else ""
                issues_text += f"**{i+1}.** {source_tag}{ver_tag} [{iss.get('severity')}] {iss.get('issue')}\n"
            if not issues_text:
                issues_text = "🎉 重新审查完毕，没有遗留问题。"
                
            return summary, issues_text, "重新评估成功！文章质量得到更新。", self.orchestrator.draft
        except Exception as e:
            return f"❌ 失败: {e}", "", "", self.orchestrator.draft

    # ═══════════════════════════════════════════════════════════════
    # Agent Hub 辅助方法 (V11)
    # ═══════════════════════════════════════════════════════════════
    def get_agent_chatbot_messages(self) -> List[Dict[str, str]]:
        """解析 orchestrator.agent_log 为 chatbot 消息列表 (OpenAI messages 格式)"""
        if not self.orchestrator or not self.orchestrator.agent_log:
            return []
        messages = []
        for entry in self.orchestrator.agent_log:
            entry = entry.strip()
            if not entry:
                continue
            if entry.startswith("["):
                bracket_end = entry.find("]")
                if bracket_end > 0:
                    role = entry[1:bracket_end]
                    message = entry[bracket_end + 1:].strip()
                    messages.append({"role": "assistant", "content": f"**{role}**: {message}"})
                else:
                    messages.append({"role": "assistant", "content": entry})
            else:
                messages.append({"role": "assistant", "content": entry})
        return messages

    def build_review_heatmap(self) -> str:
        """构建审查热力图 HTML（5 维度条形图卡片）"""
        color_map = {
            "green":  {"bar": "#238636", "text": "#3fb950", "label": "良好"},
            "yellow": {"bar": "#DFCB5C", "text": "#DFCB5C", "label": "注意"},
            "red":    {"bar": "#F85149", "text": "#ff7b72", "label": "问题"},
            "gray":   {"bar": "#3d4f6b", "text": "#6b7fa3", "label": "待审"},
        }
        # 默认分数 (待审)
        dim_scores = {"格式": (0, "gray"), "事实": (0, "gray"), "逻辑": (0, "gray"), "战略": (0, "gray"), "纪律": (0, "gray")}
        if self.orchestrator and self.orchestrator.review_results:
            # 有审查结果时初始化为满分绿色
            dim_scores = {"格式": (100, "green"), "事实": (100, "green"), "逻辑": (100, "green"), "战略": (100, "green"), "纪律": (100, "green")}
            issues = self.orchestrator.get_review_issues()
            dim_keywords = {
                "格式": ["格式", "规范"],
                "事实": ["事实", "准确"],
                "逻辑": ["逻辑", "一致", "结构"],
                "战略": ["战略", "主体", "赋能", "借势", "导向", "突出"],
                "纪律": ["纪律", "瘦身", "简洁", "合规", "渲染", "适配"],
            }
            # 按严重程度扣分
            severity_deduct = {"critical": 40, "major": 25, "minor": 12, "suggestion": 5}
            for iss in issues:
                round_name = iss.get("round_name", "")
                severity = iss.get("severity", "minor")
                deduct = severity_deduct.get(severity, 5)
                for dim_key, keywords in dim_keywords.items():
                    if any(kw in round_name for kw in keywords):
                        cur_score, _ = dim_scores[dim_key]
                        new_score = max(0, cur_score - deduct)
                        if new_score < 60:
                            color = "red"
                        elif new_score < 80:
                            color = "yellow"
                        else:
                            color = "green"
                        dim_scores[dim_key] = (new_score, color)
                        break
        # 构建条形图 HTML
        rows = []
        for dim, (score, color) in dim_scores.items():
            c = color_map[color]
            bar_w = score if score > 0 else 4
            label_text = c["label"] if score == 0 else f"{score}"
            rows.append(
                f'<div style="display:flex;align-items:center;gap:8px;margin:5px 0;">'
                f'<span style="width:28px;font-size:11px;color:#8B949E;flex-shrink:0;">{dim}</span>'
                f'<div style="flex:1;background:rgba(255,255,255,0.06);border-radius:4px;height:8px;overflow:hidden;">'
                f'<div style="width:{bar_w}%;height:100%;background:{c["bar"]};border-radius:4px;'
                f'transition:width 0.6s cubic-bezier(0.23,1,0.32,1);"></div></div>'
                f'<span style="width:26px;font-size:11px;color:{c["text"]};text-align:right;flex-shrink:0;">{label_text}</span>'
                f'</div>'
            )
        status = "审查完成" if self.orchestrator and self.orchestrator.review_results else "等待审查"
        return (
            '<div style="padding:4px 2px;">'
            + ''.join(rows)
            + f'<div style="margin-top:6px;font-size:10px;color:#4d637f;text-align:right;">{status}</div>'
            + '</div>'
        )

    def format_agent_messages_html(self) -> str:
        """将 agent_log 格式化为精美的 HTML 气泡流（替代 gr.Chatbot）"""
        if not self.orchestrator or not self.orchestrator.agent_log:
            return (
                '<div style="padding:20px 12px;text-align:center;">'
                '<div style="color:#3d4f6b;font-size:12px;">暂无 Agent 通信记录</div>'
                '<div style="color:#2a3a52;font-size:11px;margin-top:4px;">写作开始后此处将显示多 Agent 协同过程</div>'
                '</div>'
            )
        role_styles = {
            "Writer":      ("#1a3a5c", "#4F7EA4", "✍"),
            "Reviewer":    ("#1a2e1a", "#238636", "🔍"),
            "Coordinator": ("#2a2010", "#DFCB5C", "⚡"),
            "Orchestrator":("#1e1530", "#8b5cf6", "🧭"),
            "System":      ("#1a1a2e", "#484F58", "ℹ"),
        }
        bubbles = []
        for entry in self.orchestrator.agent_log:
            entry = (entry or "").strip()
            if not entry:
                continue
            role, message = "System", entry
            if entry.startswith("["):
                bracket_end = entry.find("]")
                if bracket_end > 0:
                    role = entry[1:bracket_end].strip()
                    message = entry[bracket_end + 1:].strip()
            bg, border, icon = role_styles.get(role, role_styles["System"])
            bubbles.append(
                f'<div style="margin:6px 0;padding:8px 10px;background:{bg};'
                f'border-left:2px solid {border};border-radius:0 8px 8px 0;'
                f'font-size:12px;line-height:1.5;">'
                f'<span style="color:{border};font-weight:600;font-size:11px;">{icon} {role}</span>'
                f'<div style="color:#c9d1d9;margin-top:3px;word-break:break-word;">{message}</div>'
                f'</div>'
            )
        return (
            '<div style="max-height:220px;overflow-y:auto;padding:4px;'
            'scrollbar-width:thin;scrollbar-color:#2a3a52 transparent;">'
            + ''.join(bubbles)
            + '</div>'
        )

    def get_antibias_display(self) -> str:
        """获取反偏见分析显示文本"""
        user = self.pdb.get_current_user()
        if not user:
            return "暂无偏见分析数据，完成更多写作后系统将自动分析。"
        anti_bias = getattr(user, "global_anti_bias", None)
        if anti_bias:
            lines = []
            if anti_bias.user_bias_patterns:
                lines.append("**检测到的偏见模式：**")
                for p in anti_bias.user_bias_patterns:
                    lines.append(f"- {p}")
            if anti_bias.counter_perspectives:
                lines.append("\n**反向视角建议：**")
                for p in anti_bias.counter_perspectives:
                    lines.append(f"- {p}")
            if anti_bias.innovative_angles:
                lines.append("\n**创新角度：**")
                for p in anti_bias.innovative_angles:
                    lines.append(f"- {p}")
            if anti_bias.analysis_notes:
                lines.append(f"\n**分析备注：** {anti_bias.analysis_notes}")
            return "\n".join(lines) if lines else "暂无偏见分析数据，完成更多写作后系统将自动分析。"
        return "暂无偏见分析数据，完成更多写作后系统将自动分析。"

    def get_hitl_quick_issues(self) -> str:
        """获取 HITL 快捷操作建议（前 5 个最重要问题）"""
        if not self.orchestrator:
            return "未检测到明显问题，文稿质量良好。"
        issues = self.orchestrator.get_review_issues()
        if not issues:
            return "未检测到明显问题，文稿质量良好。"
        severity_order = {"critical": 0, "major": 1, "minor": 2, "suggestion": 3}
        sorted_issues = sorted(issues, key=lambda x: severity_order.get(x.get("severity", "minor"), 2))
        lines = []
        for iss in sorted_issues[:5]:
            severity = iss.get("severity", "unknown")
            location = iss.get("location", "段落")
            issue = iss.get("issue", "")
            suggestion = iss.get("suggestion", "")
            source = iss.get("source", "规则引擎")
            source_tag = "🤖 " if source == "AI深度审查" else "🔍 "
            lines.append(f"- {source_tag}[{severity}] {location}: {issue} -> {suggestion}")
        return "\n".join(lines)

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

        # 校验 URL scheme，仅允许 http/https，防止 file:// 等协议带来安全风险
        from urllib.parse import urlparse
        parsed = urlparse(url)
        if parsed.scheme not in ('http', 'https'):
            return "仅支持 http/https 链接", self.get_topics_list(), topic, [], ""

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

    def inject_ref_docs_to_materials(self, topic: str, doc_titles: List[str], 
                                      use_style: bool, current_materials: str) -> Tuple[str, str]:
        """将选中的参考文档内容注入到写作素材区"""
        if not topic or not doc_titles or topic not in self.url_topics:
            return current_materials, "⚠️ 请先选择参考主题和文档"
        
        injected_parts = []
        style_parts = []
        
        for title in doc_titles:
            doc = next((d for d in self.url_topics[topic] if d.title == title), None)
            if not doc:
                continue
            injected_parts.append(f"【参考素材：{doc.title}】\n来源：{doc.source_site or '未知'}\n{doc.content}")
            if use_style and doc.style_patterns:
                style_parts.append(f"- {doc.title}: {'、'.join(doc.style_patterns)}")
        
        if not injected_parts:
            return current_materials, "⚠️ 未找到匹配的参考文档"
        
        injection = "\n\n".join(injected_parts)
        if style_parts:
            injection += f"\n\n【风格特征参考】\n" + "\n".join(style_parts)
        
        if current_materials and current_materials.strip():
            new_materials = f"{current_materials.strip()}\n\n---\n{injection}"
        else:
            new_materials = injection
        
        return new_materials, f"✅ 已注入 {len(injected_parts)} 篇参考文档到素材区"

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
    # 扩展素材管理 (Reference Library Extensions)
    # ═══════════════════════════════════════════════════════════════
    def search_ref_docs(self, query: str, topic: str, fmt: str, source: str, sort_by: str) -> List[List[Any]]:
        """搜索并过滤参考文档，返回供 HTML 表格渲染的二维数组"""
        results = []
        # 如果 topic 是 "全部主题"，则遍历所有；否则只找当前主题
        topics_to_search = self.url_topics.keys() if topic == "全部主题" or not topic else [topic]
        
        for t in topics_to_search:
            docs = self.url_topics.get(t, [])
            for doc in docs:
                # 过滤
                if query and query.lower() not in doc.title.lower() and query.lower() not in doc.content.lower():
                    continue
                if fmt and fmt != "全部格式" and doc.format.value != fmt:
                    continue
                if source and source != "全部来源" and doc.source_site != source:
                    continue
                
                # 构建行 [文档ID(用 主题:::标题 表示唯一), 标题, 格式, 字数, 日期, 来源, 所属主题]
                doc_id = f"{t}:::{doc.title}"
                date_str = doc.published_date[:10] if doc.published_date else "未知"
                results.append([doc_id, doc.title, doc.format.value, doc.word_count, date_str, doc.source_site or "未知", t])
        
        # 排序
        if sort_by == "最新发布":
            results.sort(key=lambda x: x[4], reverse=True)
        elif sort_by == "字数最多":
            results.sort(key=lambda x: x[3], reverse=True)
        elif sort_by == "字数最少":
            results.sort(key=lambda x: x[3])
        else: # 默认按相关度/原顺序
            pass
            
        return results

    def get_all_sources_list(self) -> List[str]:
        """提取所有参考文档中的独立来源"""
        sources = set()
        for docs in self.url_topics.values():
            for doc in docs:
                if doc.source_site:
                    sources.add(doc.source_site)
        return ["全部来源"] + sorted(list(sources))

    def get_all_formats_list(self) -> List[str]:
        """提取所有文档格式"""
        return ["全部格式"] + [f.value for f in DocumentFormat]

    def batch_delete_ref_docs(self, doc_ids_str: str) -> Tuple[str, List[str], List[str]]:
        """批量删除文档"""
        if not doc_ids_str:
            return "未选择任何文档", self.get_topics_list(), []
        
        doc_ids = [did.strip() for did in doc_ids_str.split(",") if did.strip()]
        deleted_count = 0
        for doc_id in doc_ids:
            if ":::" not in doc_id: continue
            topic, title = doc_id.split(":::", 1)
            if topic in self.url_topics:
                docs = self.url_topics[topic]
                target = next((d for d in docs if d.title == title), None)
                if target:
                    docs.remove(target)
                    deleted_count += 1
                    if not docs:
                        del self.url_topics[topic]
        
        if deleted_count > 0:
            self._save_persistent_data()
            return f"成功删除 {deleted_count} 篇文档", self.get_topics_list(), []
        return "未能删除任何文档", self.get_topics_list(), []

    def get_doc_detail_markdown(self, doc_id: str) -> Tuple[str, str]:
        """获取带有多维度的详细文档信息（Markdown 格式）"""
        if not doc_id or ":::" not in doc_id:
            return "", "请选择文档查看详情"
            
        topic, title = doc_id.split(":::", 1)
        if topic not in self.url_topics:
            return "", "找不到文档对应的主题"
            
        doc = next((d for d in self.url_topics[topic] if d.title == title), None)
        if not doc:
            return "", "文档已被删除或不存在"
            
        patterns = "、".join(doc.style_patterns) if doc.style_patterns else "暂无智能提取特征"
        meta_md = f"""### {doc.title}
**作者/机构**: {doc.author or '未知'} | **发布日期**: {doc.published_date or '未知'} | **来源**: {doc.source_site or '未知'}
**格式**: {doc.format.value} | **字数**: {doc.word_count} | **所属主题**: {topic}
**语言特征**: {patterns}"""
        
        if doc.url:
            meta_md += f" | **原文链接**: [{doc.url}]({doc.url})"
            
        return doc.title, meta_md

    def create_topic(self, name: str) -> Tuple[str, List[str]]:
        name = name.strip()
        if not name:
            return "主题名不能为空", self.get_topics_list()
        if name in self.url_topics:
            return "主题已存在", self.get_topics_list()
        self.url_topics[name] = []
        self._save_persistent_data()
        return f"主题【{name}】创建成功", self.get_topics_list()

    def rename_topic(self, old_name: str, new_name: str) -> Tuple[str, List[str]]:
        new_name = new_name.strip()
        if old_name not in self.url_topics:
            return "原主题不存在", self.get_topics_list()
        if not new_name or new_name in self.url_topics:
            return "新主题名无效或已存在", self.get_topics_list()
        self.url_topics[new_name] = self.url_topics.pop(old_name)
        self._save_persistent_data()
        return f"已重命名为【{new_name}】", self.get_topics_list()

    def delete_topic(self, name: str) -> Tuple[str, List[str]]:
        if name in self.url_topics:
            doc_count = len(self.url_topics[name])
            del self.url_topics[name]
            self._save_persistent_data()
            return f"主题【{name}】及其 {doc_count} 篇文档已删除", self.get_topics_list()
        return "主题不存在", self.get_topics_list()

    # ═══════════════════════════════════════════════════════════════
    # 其他后端模块扩展方法
    # ═══════════════════════════════════════════════════════════════
    def get_doc_type_recommendation(self) -> str:
        """根据当前 brief 获取推荐文种"""
        if not self.orchestrator or not self.orchestrator.brief:
            return "完成上一阶段问卷后，系统将自动推荐合适文种。"
        
        try:
            # 懒加载 DocumentTypeIdentifier 以避免作用域问题
            from src.core.document_type import DocumentTypeIdentifier
            if not hasattr(self.orchestrator, 'doc_identifier') or self.orchestrator.doc_identifier is None:
                self.orchestrator.doc_identifier = DocumentTypeIdentifier()
                
            recommendations = self.orchestrator.doc_identifier.identify(self.orchestrator.brief)
            if not recommendations:
                return "暂无文种推荐"
                
            res = "### 💡 智能文种推荐\n"
            for i, (profile, score) in enumerate(recommendations[:3]):
                confidence = score * 100
                res += f"**{i+1}. {profile.name_cn}** (匹配度: {confidence:.0f}%)\n"
                res += f"> 结构模板：{profile.structure_mode}\n\n"
            return res
        except Exception as e:
            return f"推荐失败: {e}"

    def get_recommended_doc_enum(self) -> Optional[DocumentType]:
        """
        根据问卷路由 subtype 与识别结果，返回适合下拉框默认值的文种枚举。
        subtype 是用户路由阶段的确定性强信号，优先映射；识别结果兜底。
        均无法映射到下拉框 10 个选项时返回 None（保持下拉框当前值）。
        """
        if not self.orchestrator or not self.orchestrator.brief:
            return None

        # 1) 路由 subtype 优先映射（仅映射到下拉框选项范围内的文种）
        subtype_to_doc = {
            "news_brief": DocumentType.NEWS_BRIEF,
            "feature": DocumentType.FEATURE,
            "sidelight": DocumentType.SIDELIGHT,
            "research_report": DocumentType.RESEARCH_REPORT,
            "bulletin": DocumentType.BULLETIN,
            "minutes": DocumentType.MEETING_MINUTES,
            # 行文方向：下行/上行/平行文分别映射到下拉框中语义最接近的文种
            "upward": DocumentType.REQUEST,
            "downward": DocumentType.NOTIFICATION,
            "parallel": DocumentType.LETTER,
        }
        doc = subtype_to_doc.get((self.orchestrator.brief.subtype or "").strip())
        if doc is not None:
            return doc

        # 2) 识别结果兜底：取第一个存在于下拉框选项中的推荐
        try:
            from src.core.document_type import DocumentTypeIdentifier
            if not hasattr(self.orchestrator, 'doc_identifier') or self.orchestrator.doc_identifier is None:
                self.orchestrator.doc_identifier = DocumentTypeIdentifier()
            recommendations = self.orchestrator.doc_identifier.identify(self.orchestrator.brief)
            for profile, score in recommendations:
                if score > 0 and profile.doc_type in DOC_TYPE_ENUM_TO_LABEL:
                    return profile.doc_type
        except Exception:
            pass
        return None

    def get_style_detail_display(self, style_lbl: str, intensity: float) -> Tuple[str, str]:
        """获取风格特征详情和混合建议"""
        if not style_lbl:
            return "请选择主要风格", "无混合建议"
            
        style_enum = None
        for k, v in STYLE_LABEL_TO_ENUM.items():
            if k == style_lbl:
                style_enum = v
                break
                
        if not style_enum:
            return "未知的风格", "无混合建议"
            
        try:
            from src.core.style_adapter import STYLE_PROFILES
            profile = STYLE_PROFILES.get(style_enum)
            if not profile:
                return "无此风格详情", ""
                
            # 根据强度调整显示
            intensity_desc = "标准" if 0.4 <= intensity <= 0.7 else "强烈" if intensity > 0.7 else "微弱"
            
            detail = f"""### {profile.name} 特征详情 (当前强度: {intensity_desc})
- **情感基调**: {profile.tone}
- **语言特征**: {', '.join(profile.language_features)}
- **禁止模式**: {', '.join(profile.forbidden_patterns)}
- **文学度**: {profile.literary_level} | **数据密度**: {profile.data_density} | **政策关联度**: {profile.policy_relevance}"""

            blend = "无需混合建议"
            if self.orchestrator and self.orchestrator.brief and self.orchestrator.brief.secondary_audiences:
                try:
                    b = self.style_adapter.suggest_blend(self.orchestrator.brief.primary_audience, self.orchestrator.brief.purpose, self.orchestrator.brief.secondary_audiences)
                    blend = f"### 风格混合建议\n{b.display()}\n*建议原因*: {b.reasoning}"
                except Exception:
                    pass
            
            return detail, blend
        except Exception as e:
            return f"获取详情失败: {e}", ""

    def get_token_stats_display(self) -> str:
        """获取交付阶段的 Token 与成本统计"""
        if not self.orchestrator:
            return "无统计数据"
        try:
            stats = self.orchestrator.get_api_stats()
            opt_report = stats.get("optimization_report", "暂无优化报告")
            calls = stats.get("api_calls", 0)
            fails = stats.get("api_failures", 0)
            return f"### 📊 API 请求与成本优化统计\n- 总调用成功次数: {calls}\n- 失败重试次数: {fails}\n\n{opt_report}"
        except Exception as e:
            return f"统计获取失败: {e}"

    def get_review_history_display(self) -> str:
        """获取审查历史的时间线展示"""
        if not self.orchestrator or not hasattr(self.orchestrator.reviewer, 'review_history'):
            return "暂无审查历史"
            
        history = self.orchestrator.reviewer.review_history
        if not history:
            return "尚未执行多维审查"
            
        res = "### 🔍 多维度智能审查轨迹\n"
        for i, h in enumerate(history):
            status = "✅ 通过" if h.passed else f"⚠️ 发现 {len(h.findings)} 处问题"
            res += f"**轮次 {i+1}：{h.round_name}** | 得分：{h.overall_score:.1f} | 状态：{status}\n"
            if h.findings:
                for f in h.findings[:2]:  # 最多展示2条代表性发现
                    res += f"> - [{f.severity.value}] {f.issue}\n"
                if len(h.findings) > 2:
                    res += f"> - ...及其他 {len(h.findings)-2} 处建议\n"
            res += "\n"
        return res

    def get_kb_diagnostics_display(self, text: str) -> str:
        """获取知识库对当前草稿的诊断结果"""
        if not text:
            return "请先在上方输入内容或生成草稿。"
            
        try:
            diags = self.knowledge_base.diagnose_text(text)
            if not diags:
                return "✅ 知识库合规性检查通过，未发现常见错敏词。"
                
            res = "### 🚨 知识库诊断结果\n"
            for d in diags:
                res += f"- **检测项**: `{d.get('error_key', '未知')}`\n  - **诊断**: {d.get('diagnosis', '')}\n  - **建议**: {d.get('prescription', '')}\n\n"
            return res
        except Exception as e:
            return f"诊断失败: {e}"

    def get_vocab_corpus_summary(self) -> str:
        """获取词汇语料库摘要"""
        if not self.current_project_id:
            return "请先创建并选择项目"
            
        try:
            proj = self.pdb.get_project(self.current_project_id)
            if not proj: return "项目不存在"
            if not proj.vocabulary_corpus:
                return "尚未创建项目专属词汇语料库"
            vc = proj.vocabulary_corpus
            res = f"**个性化词汇语料库**\n\n"
            res += f"- 必用关键词 ({len(vc.required_keywords)}): {', '.join(vc.required_keywords) if vc.required_keywords else '无'}\n"
            res += f"- 禁用违禁词 ({len(vc.forbidden_words)}): {', '.join(vc.forbidden_words) if vc.forbidden_words else '无'}\n"
            res += f"- 自定义术语 ({len(vc.custom_terms)}): {', '.join(vc.custom_terms) if vc.custom_terms else '无'}\n"
            return res
        except Exception as e:
            return f"获取失败: {e}"

    def add_vocab_keyword(self, word: str) -> Tuple[str, str]:
        if not word.strip() or not self.current_project_id: return "无效输入或未选择项目", self.get_vocab_corpus_summary()
        self.pdb.add_required_keyword(self.current_project_id, word.strip())
        self._save_persistent_data()
        return f"已添加必用词: {word}", self.get_vocab_corpus_summary()
        
    def add_vocab_forbidden(self, word: str) -> Tuple[str, str]:
        if not word.strip() or not self.current_project_id: return "无效输入或未选择项目", self.get_vocab_corpus_summary()
        self.pdb.add_forbidden_word(self.current_project_id, word.strip())
        self._save_persistent_data()
        return f"已添加禁用词: {word}", self.get_vocab_corpus_summary()

    def get_agent_coordination_report(self) -> str:
        """获取 Agent Hub 多智能体协商详情卡片"""
        if not self.orchestrator or not self.orchestrator.coordinator:
            return "多智能体尚未初始化"
        try:
            report = self.orchestrator.coordinator.get_coordination_report()
            stats = report.get('communication_stats', {})
            total = stats.get('total_messages', 0)
            
            res = f"### ⚡ 多智能体协商过程全景监控\n**总消息流转**: {total} 条\n\n"
            
            debates = report.get('recent_debates', [])
            if debates:
                res += "#### ⚔️ 核心分歧与共识\n"
                for d in debates:
                    res += f"**讨论点**: {d.get('topic')}\n"
                    res += f"- 🖊️ Writer 视角: {d.get('writer')}\n"
                    res += f"- 🔍 Reviewer 视角: {d.get('reviewer')}\n"
                    res += f"- 🤝 达成共识 (经 {d.get('rounds')} 轮): {d.get('consensus')}\n\n"
                    
            consults = report.get('recent_consultations', [])
            if consults:
                res += "#### 🏛️ 专家智囊团会商摘要\n"
                for c in consults:
                    res += f"- 议题 `{c.get('topic', '未知')}` : 收获 {len(c.get('responses', {}))} 份专家意见，Orchestrator 采纳策略：{c.get('decision', '未知')}\n"
                    
            return res
        except Exception as e:
            return f"获取协商报告失败: {e}"

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
            return f"保存失败，请检查网络连接后重试: {e}"

    def test_llm_connection_action(self) -> str:
        try:
            res = self.api_manager.test_connection()
            if res.get("success"):
                return f"连接成功 — 模型响应正常：{res.get('message')}"
            # 优先使用结构化状态码，字符串匹配仅作 fallback
            status_code = res.get("status_code")
            err_msg = res.get('message', '未知错误')
            if status_code:
                if status_code in (401, 403):
                    return "认证失败 — API Key 无效或已过期，请检查密钥"
                if status_code == 404:
                    return "端点不存在 — API Base URL 或模型名称可能有误"
                if status_code == 429:
                    return "请求频率过高，请稍后重试"
                if status_code >= 500:
                    return "API 服务器内部错误，请稍后重试"
            # fallback: 字符串匹配
            if 'timeout' in str(err_msg).lower():
                return "连接超时 — 请检查 API 地址是否正确，或网络是否需要代理"
            if '401' in str(err_msg) or '403' in str(err_msg):
                return "认证失败 — API Key 无效或已过期，请检查密钥"
            if '404' in str(err_msg):
                return "端点不存在 — API Base URL 或模型名称可能有误"
            return f"连接失败 — {err_msg}"
        except Exception as e:
            # 优先从异常对象提取 HTTP 状态码（如 requests.HTTPError 携带的 response）
            resp = getattr(e, "response", None)
            status_code = getattr(resp, "status_code", None) if resp is not None else None
            if status_code in (401, 403):
                return "认证失败 — API Key 无效或已过期，请检查密钥"
            if status_code == 404:
                return "端点不存在 — API Base URL 或模型名称可能有误"
            if status_code == 429:
                return "请求频率过高，请稍后重试"
            # fallback: 字符串匹配
            err_str = str(e)
            if 'timeout' in err_str.lower():
                return "连接超时 — 请检查 API 地址是否正确，或网络是否需要代理"
            return f"连接测试异常 — 请确认 API 地址可访问：{err_str[:200]}"

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
        filter: blur(100px) saturate(120%) !important;
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
        filter: blur(80px) saturate(130%) !important;
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
    /* 星月夜：背景改为内联 SVG（SMIL 动画真正执行），容器透明以透出背景 */
    .gradio-container {
        background: transparent !important;
    }
    .gradio-container::before,
    .gradio-container::after {
        content: none !important;
    }
    #starry-night-bg {
        position: fixed;
        inset: 0;
        width: 100%;
        height: 100%;
        z-index: -1;
        pointer-events: none;
    }
    @media (prefers-reduced-motion: reduce) {
        #starry-night-bg animateTransform,
        #starry-night-bg animate,
        #starry-night-bg animateMotion {
            display: none !important;
        }
    }
</style>
<svg id="starry-night-bg" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 1000" preserveAspectRatio="xMidYMid slice" aria-hidden="true">
  <defs>
    <filter id="blurLg"><feGaussianBlur stdDeviation="24"/></filter>
    <filter id="blurMd"><feGaussianBlur stdDeviation="12"/></filter>
    <filter id="blurSm"><feGaussianBlur stdDeviation="6"/></filter>
    <radialGradient id="swirlLight" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#4F7EA4" stop-opacity="0.8"/>
      <stop offset="100%" stop-color="#003153" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="swirlMid" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#2a6a9b" stop-opacity="0.7"/>
      <stop offset="100%" stop-color="#00213B" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="swirlDark" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#005085" stop-opacity="0.6"/>
      <stop offset="100%" stop-color="#05101a" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="starHalo" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#DFCB5C" stop-opacity="0.95"/>
      <stop offset="20%" stop-color="#DFCB5C" stop-opacity="0.6"/>
      <stop offset="50%" stop-color="#1C3765" stop-opacity="0.3"/>
      <stop offset="100%" stop-color="#1C3765" stop-opacity="0"/>
    </radialGradient>
    <radialGradient id="moonHalo" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#E7D674" stop-opacity="1"/>
      <stop offset="15%" stop-color="#DFCB5C" stop-opacity="0.8"/>
      <stop offset="40%" stop-color="#648BA8" stop-opacity="0.4"/>
      <stop offset="100%" stop-color="#1C3765" stop-opacity="0"/>
    </radialGradient>
  </defs>

  <rect width="100%" height="100%" fill="#00172D"/>

  <!-- 背景星点（静态，零成本） -->
  <g fill="#FFF">
    <circle cx="100" cy="200" r="1.5" opacity="0.8"/>
    <circle cx="250" cy="80" r="1" opacity="0.6"/>
    <circle cx="450" cy="150" r="2" opacity="0.9"/>
    <circle cx="650" cy="90" r="1.5" opacity="0.5"/>
    <circle cx="850" cy="120" r="2.5" opacity="0.8"/>
    <circle cx="950" cy="250" r="1" opacity="0.7"/>
    <circle cx="150" cy="350" r="2" opacity="0.9"/>
    <circle cx="350" cy="450" r="1.5" opacity="0.6"/>
    <circle cx="550" cy="350" r="2.5" opacity="0.8"/>
    <circle cx="750" cy="480" r="1" opacity="0.5"/>
    <circle cx="920" cy="380" r="2" opacity="0.7"/>
    <circle cx="50" cy="550" r="1.5" opacity="0.8"/>
    <circle cx="250" cy="650" r="2" opacity="0.6"/>
    <circle cx="450" cy="750" r="1" opacity="0.9"/>
    <circle cx="650" cy="650" r="2.5" opacity="0.5"/>
    <circle cx="850" cy="750" r="1.5" opacity="0.8"/>
    <circle cx="950" cy="600" r="1" opacity="0.7"/>
    <circle cx="150" cy="850" r="2" opacity="0.9"/>
    <circle cx="350" cy="950" r="1.5" opacity="0.6"/>
    <circle cx="550" cy="850" r="2.5" opacity="0.8"/>
    <circle cx="750" cy="950" r="1" opacity="0.5"/>
    <circle cx="920" cy="880" r="2" opacity="0.7"/>
  </g>

  <!-- 流动漩涡（SMIL 旋转 + 模糊光晕） -->
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 300 300" to="360 300 300" dur="45s" repeatCount="indefinite"/>
    <ellipse cx="300" cy="300" rx="450" ry="200" fill="url(#swirlLight)" filter="url(#blurLg)" transform="rotate(30 300 300)"/>
    <ellipse cx="300" cy="300" rx="300" ry="150" fill="url(#swirlMid)" filter="url(#blurMd)" transform="rotate(-20 300 300)"/>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="360 750 400" to="0 750 400" dur="60s" repeatCount="indefinite"/>
    <ellipse cx="750" cy="400" rx="500" ry="250" fill="url(#swirlMid)" filter="url(#blurLg)" transform="rotate(-45 750 400)"/>
    <ellipse cx="750" cy="400" rx="200" ry="400" fill="url(#swirlLight)" filter="url(#blurMd)" transform="rotate(15 750 400)"/>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 400 800" to="360 400 800" dur="50s" repeatCount="indefinite"/>
    <ellipse cx="400" cy="800" rx="400" ry="250" fill="url(#swirlDark)" filter="url(#blurLg)" transform="rotate(60 400 800)"/>
  </g>

  <!-- 月亮 -->
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 850 200" to="360 850 200" dur="30s" repeatCount="indefinite"/>
    <circle cx="850" cy="200" r="180" fill="url(#moonHalo)" filter="url(#blurSm)"/>
    <ellipse cx="850" cy="200" rx="140" ry="70" fill="url(#swirlLight)" opacity="0.3" filter="url(#blurSm)" transform="rotate(45 850 200)"/>
  </g>

  <!-- 星晕 -->
  <g>
    <animateTransform attributeName="transform" type="rotate" from="360 200 150" to="0 200 150" dur="25s" repeatCount="indefinite"/>
    <circle cx="200" cy="150" r="120" fill="url(#starHalo)" filter="url(#blurSm)"/>
    <ellipse cx="200" cy="150" rx="90" ry="40" fill="url(#swirlLight)" opacity="0.4" filter="url(#blurSm)" transform="rotate(-30 200 150)"/>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 150 550" to="360 150 550" dur="22s" repeatCount="indefinite"/>
    <circle cx="150" cy="550" r="100" fill="url(#starHalo)" filter="url(#blurSm)"/>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="360 500 450" to="0 500 450" dur="35s" repeatCount="indefinite"/>
    <circle cx="500" cy="450" r="80" fill="url(#starHalo)" filter="url(#blurSm)" opacity="0.8"/>
  </g>
  <g>
    <animateTransform attributeName="transform" type="rotate" from="0 750 750" to="360 750 750" dur="28s" repeatCount="indefinite"/>
    <circle cx="750" cy="750" r="110" fill="url(#starHalo)" filter="url(#blurSm)"/>
    <ellipse cx="750" cy="750" rx="80" ry="30" fill="url(#swirlLight)" opacity="0.3" filter="url(#blurSm)" transform="rotate(70 750 750)"/>
  </g>
</svg>
"""


THEME_APPLE_MINIMAL_HTML = """
<style>
    /* 苹果极简主题：浅色、克制动效、单一强调色，遵循 Apple HIG 克制原则 */
    :root {
        --color-ink: #1D1D1F !important;
        --color-ink-body: #3A3A3C !important;
        --color-ink-muted: #86868B !important;
        --color-accent: #0A84FF !important;
        --color-accent-hover: #2E95FF !important;
        --color-accent-active: #0071E3 !important;
        --color-accent-focus: rgba(10, 132, 255, 0.25) !important;
        --color-sky-pale: #6E6E73 !important;
    }
    .gradio-container {
        background: #F5F5F7 !important;
        color: #1D1D1F !important;
    }
    .gradio-container::before,
    .gradio-container::after {
        content: none !important;
    }
    .gradio-container h1, .gradio-container h2, .gradio-container h3 {
        color: #1D1D1F !important;
    }
    .gradio-container p, .gradio-container span, .gradio-container label,
    .gradio-container li, .gradio-container div {
        color: #3A3A3C !important;
    }
    .sidebar-pane, .workspace-pane {
        background: rgba(255, 255, 255, 0.85) !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
    }
    .ios-card, .empty-state-card {
        background: #FFFFFF !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
    }
    .ios-card:hover {
        background: #FFFFFF !important;
        border-color: rgba(10, 132, 255, 0.3) !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08) !important;
    }
    .gradio-container [class*="accordion"],
    .gradio-container details {
        background: #FFFFFF !important;
        backdrop-filter: none !important;
        -webkit-backdrop-filter: none !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
    }
    .gradio-container details > summary,
    .gradio-container [class*="accordion"] > button,
    .gradio-container [class*="accordion-header"] {
        background: #F5F5F7 !important;
        color: #1D1D1F !important;
        border-bottom: 1px solid rgba(0, 0, 0, 0.06) !important;
    }
    .ios-btn-primary {
        background: #0A84FF !important;
        color: #FFFFFF !important;
        border: none !important;
        box-shadow: none !important;
        text-shadow: none !important;
    }
    .ios-btn-primary:hover { background: #2E95FF !important; transform: none !important; }
    .ios-btn-primary:active { background: #0071E3 !important; transform: none !important; filter: none !important; }
    .ios-btn-secondary,
    .gradio-container button.secondary,
    .gradio-container button[variant="secondary"] {
        background: #FFFFFF !important;
        color: #1D1D1F !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        box-shadow: none !important;
    }
    .ios-btn-secondary:hover { background: #EBEBED !important; transform: none !important; }
    .ios-btn-danger {
        background: #FFFFFF !important;
        color: #FF3B30 !important;
        border: 1px solid rgba(255, 59, 48, 0.3) !important;
        box-shadow: none !important;
    }
    .ios-btn-danger:hover { background: #FFEBE9 !important; transform: none !important; }
    .gradio-container input:not([type="checkbox"]):not([type="radio"]),
    .gradio-container textarea {
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.12) !important;
        box-shadow: none !important;
        color: #1D1D1F !important;
    }
    .gradio-container input:not([type="checkbox"]):not([type="radio"]):focus,
    .gradio-container textarea:focus {
        background: #FFFFFF !important;
        border-color: #0A84FF !important;
        box-shadow: 0 0 0 3px rgba(10, 132, 255, 0.2) !important;
        outline: none !important;
    }
    .title-banner {
        background: #FFFFFF !important;
        border: 1px solid rgba(0, 0, 0, 0.08) !important;
        box-shadow: 0 1px 4px rgba(0, 0, 0, 0.06) !important;
    }
    .title-banner h1 { color: #1D1D1F !important; text-shadow: none !important; }
    .title-banner p { color: #6E6E73 !important; }
    .step-done { color: #0A84FF !important; }
    .step-done .step-num { background: rgba(10, 132, 255, 0.2) !important; color: #0A84FF !important; }
    .step-current {
        background: rgba(10, 132, 255, 0.1) !important;
        border-color: #0A84FF !important;
        color: #0A84FF !important;
        box-shadow: none !important;
    }
    .step-current .step-num { background: #0A84FF !important; color: #FFFFFF !important; }
    .agent-bubble { background: #F5F5F7 !important; border: 1px solid rgba(0, 0, 0, 0.06) !important; }
    .badge-info { background: rgba(10, 132, 255, 0.1) !important; color: #0A84FF !important; border-color: rgba(10, 132, 255, 0.2) !important; }
    .user-identity-bar { background: #FFFFFF !important; border: 1px solid rgba(0, 0, 0, 0.08) !important; }
    .sidebar-footer-btn { color: #86868B !important; }
    .sidebar-footer-btn:hover { background: rgba(0, 0, 0, 0.04) !important; color: #1D1D1F !important; }
    .empty-state-card p { color: #86868B !important; }
    .gradio-container .gr-group *,
    .gradio-container [class*="group"] *,
    .gradio-container [class*="accordion"] *,
    .ios-card * {
        color: #3A3A3C !important;
    }
    *:focus-visible { outline: 2px solid #0A84FF !important; }
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
        --color-ink-muted: #A8B8CC; 
        
        --color-danger: oklch(65% 0.18 20);
        --color-danger-hover: oklch(75% 0.18 20);
        
        /* Geometry */
        --radius-button: 14px;
        --radius-card: 22px;
        --radius-input: 12px;
        --radius-sm: 10px;

        /* Glass Effects */
        --blur-glass: blur(28px) saturate(130%);

        /* Apple-Style Easing & Animation */
        --ease-out-expo: cubic-bezier(0.23, 1, 0.32, 1);
        --ease-in-out-quart: cubic-bezier(0.77, 0, 0.175, 1);

        /* ── Override Gradio's built-in theme variables ──
           Gradio injects these into every container via its Svelte theme system.
           By overriding them here we guarantee transparent interiors
           regardless of which hashed class names Gradio uses internally. */
        --body-background-fill: transparent !important;
        --background-fill-primary: transparent !important;
        --background-fill-secondary: transparent !important;
        --border-color-primary: transparent !important;
        --block-background-fill: transparent !important;
        --block-border-color: transparent !important;
        --block-shadow: none !important;
        --panel-background-fill: transparent !important;
        --panel-border-color: transparent !important;
        --color-background-primary: transparent !important;
    }

    @keyframes smooth-enter {
        0% { opacity: 0; transform: scale(0.98); }
        100% { opacity: 1; transform: scale(1); }
    }

    /* Container Background - Apple Music Fluid Style */
    .gradio-container {
        position: relative;
        /* DO NOT set overflow: hidden — it clips the star background on some browsers */
        z-index: 1;
        background-color: var(--color-sky-deep) !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        padding: 2% 4% !important;
        font-family: "Inter", "Noto Sans SC", -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif !important;
        color: var(--color-ink) !important;
    }

    /* Nuclear reset: clear ALL Gradio internal wrapper borders, backgrounds, shadows.
       These classes are injected by Gradio's svelte runtime and can't be targeted reliably
       with a shallow child combinator (>). Use a descendant rule + !important. */
    .gradio-container .main,
    .gradio-container .wrap,
    .gradio-container .contain,
    .gradio-container .form,
    .gradio-container .gap,
    .gradio-container .flex,
    .gradio-container .block {
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        background: transparent !important;
    }

    .gradio-container p, .gradio-container span, .gradio-container label,
    .gradio-container li {
        color: var(--color-ink-body);
        text-wrap: pretty;
    }
    .gradio-container div {
        color: var(--color-ink-body);
    }

    /* 1. RESET GRADIO DEFAULT BOXES (Remove Matryoshka effect) */
    .gradio-container .gr-panel,
    .gradio-container .gr-group,
    .gradio-container .gr-form,
    .gradio-container fieldset,
    .gradio-container .gr-block,
    .gradio-container .gr-box {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* Accordion: special deep-blue glass styling */
    .gradio-container [class*="accordion"],
    .gradio-container details {
        background: rgba(13, 22, 43, 0.6) !important;
        backdrop-filter: var(--blur-glass) !important;
        -webkit-backdrop-filter: var(--blur-glass) !important;
        border: 1px solid rgba(100, 139, 168, 0.25) !important;
        border-radius: var(--radius-card) !important;
        box-shadow: 0 4px 24px rgba(0, 0, 0, 0.35) !important;
        overflow: hidden;
    }

    /* Ensure textarea scroll works inside accordions.
       The parent accordion has overflow:hidden for border-radius,
       but inner content must still scroll. */
    .gradio-container [class*="accordion"] > div,
    .gradio-container details > div:not(.summary) {
        overflow-y: auto !important;
        max-height: none !important;
    }
    .gradio-container textarea {
        overflow-y: auto !important;
        resize: vertical !important;
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
        transition: background 220ms var(--ease-out-expo), transform 200ms var(--ease-out-expo), filter 200ms var(--ease-out-expo) !important;
    }
    .gradio-container details > summary:hover,
    .gradio-container [class*="accordion"] > button:hover {
        background: rgba(40, 64, 111, 0.65) !important;
        transform: translateY(-0.5px);
    }
    .gradio-container details > summary:active,
    .gradio-container [class*="accordion"] > button:active {
        transform: scale(0.98);
        filter: brightness(0.85);
    }

    /* iOS-style chevron for Accordion toggle icons
       Replaces Gradio's default ▼ Unicode triangle with a thin
       rounded-line SVG chevron that matches iOS visual language. */
    .gradio-container button.label-wrap .icon {
        color: transparent !important;
        font-size: 0 !important;
        width: 14px !important;
        height: 14px !important;
        min-width: 14px !important;
        display: inline-block !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14' fill='none' stroke='%23A8B8CC' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 5l4 4 4-4'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 14px 14px !important;
        transition: transform 250ms var(--ease-out-expo), filter 200ms ease !important;
    }
    .gradio-container button.label-wrap:hover .icon {
        filter: brightness(1.4);
    }

    /* iOS-style chevron for Dropdown arrows
       Hides Gradio's filled triangle SVG and replaces it with the
       same thin rounded chevron. */
    .gradio-container .icon-wrap .dropdown-arrow {
        display: none !important;
    }
    .gradio-container .icon-wrap {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 14 14' fill='none' stroke='%23A8B8CC' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M3 5l4 4 4-4'/%3E%3C/svg%3E") !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 12px 12px !important;
    }

    /* Apply Blur ONLY to major structural containers */
    .sidebar-pane, .workspace-pane {
        background: rgba(20, 35, 60, 0.15) !important;
        backdrop-filter: var(--blur-glass) !important;
        -webkit-backdrop-filter: var(--blur-glass) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.15) !important;
        border-left: 1px solid rgba(255, 255, 255, 0.12) !important;
        border-radius: var(--radius-card);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3) !important;
    }
    
    /* ═══ FIX GRADIO DROPDOWN POSITIONING BROKEN BY BACKDROP-FILTER ═══
       backdrop-filter creates a new containing block for fixed/absolute elements. 
       We force the dropdown container to be relative and the options box to be 
       absolutely positioned exactly below it, overriding Gradio's inline JS coordinates. */
    .gradio-container .gr-dropdown > div {
        position: relative !important;
    }
    .gradio-container .gr-dropdown .options,
    .gradio-container .gr-dropdown ul.options {
        position: absolute !important;
        top: 100% !important;
        left: 0 !important;
        right: 0 !important;
        width: auto !important;
        transform: none !important;
        margin-top: 4px !important;
        z-index: 99999 !important;
    }
    
    /* Ensure elements inside workspace do not hide overflowing dropdowns */
    .gradio-container .sidebar-pane,
    .gradio-container .workspace-pane,
    .gradio-container .ios-card,
    .gradio-container [class*="accordion"],
    .gradio-container details,
    .gradio-container [class*="accordion"] > div,
    .gradio-container details > div,
    .gradio-container .gr-group,
    .gradio-container .wrap.svelte-1bndj1j /* dropdown wrap */,
    .gradio-container [class*="svelte-"] {
        /* Gradio sometimes adds overflow: hidden to columns, we must override it for dropdowns to escape */
        overflow: visible !important;
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

    /* Specific Glass Cards */
    .ios-card {
        background: rgba(13, 22, 43, 0.55) !important;
        backdrop-filter: var(--blur-glass) !important;
        -webkit-backdrop-filter: var(--blur-glass) !important;
        border: 1px solid rgba(79, 126, 164, 0.2) !important;
        border-top: 1px solid rgba(141, 179, 195, 0.25) !important;
        border-left: 1px solid rgba(141, 179, 195, 0.18) !important;
        border-radius: var(--radius-card) !important;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4), inset 0 1px 0 rgba(255,255,255,0.06) !important;
        transition: box-shadow 300ms var(--ease-out-expo), border-color 300ms var(--ease-out-expo);
    }
    .ios-card:hover {
        background: rgba(13, 22, 43, 0.65) !important;
        box-shadow: 0 8px 32px rgba(223, 203, 92, 0.15), inset 0 1px 0 rgba(255,255,255,0.06) !important; /* Moon glow */
        border-color: rgba(223, 203, 92, 0.3) !important;
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
        text-wrap: balance;
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

    /* Swirling Title Banner - borderless, pure glow */
    .title-banner {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 20px 24px 16px !important;
        margin-bottom: 12px;
        box-shadow: none !important;
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
        background: radial-gradient(80% 100% at 50% 0%, rgba(223, 203, 92, 0.4) 0%, rgba(196, 138, 24, 0.1) 50%, rgba(13, 22, 43, 0.9) 100%), #0D162B !important;
        color: #F8FAFC !important; 
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(223, 203, 92, 0.2) !important;
        font-weight: 600 !important;
        transition: transform 150ms var(--ease-out-expo), box-shadow 300ms var(--ease-out-expo), filter 150ms ease, background 300ms var(--ease-out-expo) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.2), 0 2px 8px rgba(0, 0, 0, 0.3) !important;
        min-height: 44px;
        text-shadow: 0 1px 2px rgba(0,0,0,0.5);
    }
    .ios-btn-primary:hover {
        transform: translateY(-0.5px);
        background: radial-gradient(100% 120% at 50% 50%, rgba(223, 203, 92, 0.5) 0%, rgba(196, 138, 24, 0.15) 50%, rgba(13, 22, 43, 0.95) 100%), #0D162B !important;
        border-color: rgba(223, 203, 92, 0.5) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.3), 0 6px 20px rgba(223, 203, 92, 0.25), 0 0 12px rgba(223, 203, 92, 0.15) !important;
    }
    .ios-btn-primary:active {
        transform: scale(0.97) !important;
        filter: brightness(0.9) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05), 0 1px 2px rgba(0, 0, 0, 0.2) !important;
    }

    /* Secondary Buttons - Semi-transparent blue glass */
    .ios-btn-secondary,
    .gradio-container button.secondary,
    .gradio-container button[variant="secondary"],
    .gradio-container button:not(.ios-btn-primary):not(.ios-btn-danger):not([class*="tab"]):not([class*="accordion"]):not(.selected) {
        background: radial-gradient(80% 100% at 50% 0%, rgba(100, 139, 168, 0.15) 0%, rgba(28, 55, 101, 0.2) 50%, rgba(13, 22, 43, 0.6) 100%), rgba(13, 22, 43, 0.7) !important;
        color: var(--color-ink-body) !important;
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(100, 139, 168, 0.2) !important;
        font-weight: 500 !important;
        transition: transform 150ms var(--ease-out-expo), box-shadow 300ms var(--ease-out-expo), filter 150ms ease, background 300ms var(--ease-out-expo), border-color 300ms ease !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 2px 6px rgba(0, 0, 0, 0.2) !important;
        min-height: 40px;
    }
    .ios-btn-secondary:hover,
    .gradio-container button.secondary:hover,
    .gradio-container button[variant="secondary"]:hover,
    .gradio-container button:not(.ios-btn-primary):not(.ios-btn-danger):not([class*="tab"]):not([class*="accordion"]):not(.selected):hover {
        transform: translateY(-0.5px);
        background: radial-gradient(100% 120% at 50% 50%, rgba(141, 179, 195, 0.25) 0%, rgba(40, 64, 111, 0.3) 50%, rgba(13, 22, 43, 0.8) 100%), rgba(13, 22, 43, 0.9) !important;
        border-color: rgba(141, 179, 195, 0.4) !important;
        color: var(--color-ink) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 4px 16px rgba(79, 126, 164, 0.2), 0 0 12px rgba(100, 139, 168, 0.1) !important;
    }
    .ios-btn-secondary:active,
    .gradio-container button.secondary:active,
    .gradio-container button[variant="secondary"]:active,
    .gradio-container button:not(.ios-btn-primary):not(.ios-btn-danger):not([class*="tab"]):not([class*="accordion"]):not(.selected):active {
        transform: scale(0.97) !important;
        filter: brightness(0.9) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02), 0 1px 2px rgba(0, 0, 0, 0.2) !important;
    }

    /* Danger Buttons */
    .ios-btn-danger,
    .gradio-container button.stop,
    .gradio-container button[variant="stop"] {
        background: radial-gradient(80% 100% at 50% 0%, rgba(220, 38, 38, 0.2) 0%, rgba(153, 27, 27, 0.1) 50%, rgba(13, 22, 43, 0.6) 100%), rgba(13, 22, 43, 0.7) !important;
        color: #FCA5A5 !important;
        border-radius: var(--radius-button) !important;
        border: 1px solid rgba(220, 38, 38, 0.3) !important;
        font-weight: 500 !important;
        transition: transform 150ms var(--ease-out-expo), box-shadow 300ms var(--ease-out-expo), filter 150ms ease, background 300ms var(--ease-out-expo) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08), 0 2px 6px rgba(0, 0, 0, 0.2) !important;
        min-height: 44px;
    }
    .ios-btn-danger:hover,
    .gradio-container button.stop:hover,
    .gradio-container button[variant="stop"]:hover {
        transform: translateY(-0.5px);
        background: radial-gradient(100% 120% at 50% 50%, rgba(220, 38, 38, 0.35) 0%, rgba(153, 27, 27, 0.15) 50%, rgba(13, 22, 43, 0.8) 100%), rgba(13, 22, 43, 0.9) !important;
        border-color: rgba(220, 38, 38, 0.5) !important;
        color: #FECACA !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.15), 0 4px 16px rgba(220, 38, 38, 0.25), 0 0 12px rgba(220, 38, 38, 0.15) !important;
    }
    .ios-btn-danger:active,
    .gradio-container button.stop:active,
    .gradio-container button[variant="stop"]:active {
        transform: scale(0.97) !important;
        filter: brightness(0.85) !important;
        box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.02), 0 1px 2px rgba(0, 0, 0, 0.2) !important;
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

    /* Unified Input Containers (The actual input fields, NOT the outer wrapper) */
    .gradio-container input:not([type="checkbox"]):not([type="radio"]), 
    .gradio-container textarea {
        background: rgba(0, 0, 0, 0.25) !important;
        border-radius: var(--radius-input) !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        border-top: 1px solid rgba(0, 0, 0, 0.4) !important;
        box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.2) !important;
        transition: border-color 150ms var(--ease-out-expo), box-shadow 150ms var(--ease-out-expo), background 150ms var(--ease-out-expo) !important;
        color: var(--color-ink) !important;
    }
    
    .gradio-container input:not([type="checkbox"]):not([type="radio"]):focus, 
    .gradio-container textarea:focus {
        background: rgba(0, 0, 0, 0.4) !important;
        border-color: var(--color-accent) !important;
        box-shadow: 0 0 0 2px var(--color-accent-focus), inset 0 2px 4px rgba(0,0,0,0.5) !important;
        outline: none !important;
    }


    /* Selected Tabs */
    button.selected {
        background: rgba(255, 255, 255, 0.08) !important;
        color: var(--color-accent) !important;
        border-bottom: 2px solid var(--color-accent) !important;
        transition: all 0.2s ease !important;
        font-weight: 600;
    }

    /* ═══ TABS REDESIGN ═══ */
    .gradio-container .tabitem {
        border: none !important;
        background: transparent !important;
        padding: 16px 0 0 0 !important;
    }
    .gradio-container .tabs {
        background: transparent !important;
        border: none !important;
    }
    .gradio-container .tab-nav {
        background: rgba(13, 22, 43, 0.4) !important;
        border: 1px solid rgba(141, 179, 195, 0.15) !important;
        border-radius: var(--radius-sm) !important;
        padding: 4px !important;
        gap: 4px !important;
        display: flex;
        flex-wrap: wrap;
    }
    .gradio-container .tab-nav > button {
        border: none !important;
        background: transparent !important;
        color: var(--color-ink-muted) !important;
        border-radius: calc(var(--radius-sm) - 2px) !important;
        padding: 6px 12px !important;
        font-weight: 500 !important;
        transition: all 0.2s ease !important;
    }
    .gradio-container .tab-nav > button.selected {
        background: rgba(255, 255, 255, 0.1) !important;
        color: var(--color-ink) !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.2) !important;
        border-bottom: none !important;
    }

    /* ═══ PROJECT HEADER ═══ */
    .project-header-row {
        align-items: center !important;
        margin-bottom: 12px !important;
        background: rgba(0, 0, 0, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.05);
        border-radius: var(--radius-sm);
        padding: 12px 16px !important;
    }
    .project-title-text h2, .project-title-text h3 {
        margin: 0 !important;
        font-size: 18px !important;
        color: var(--color-accent) !important;
        line-height: 1.3 !important;
    }
    .progress-badge-container {
        display: flex;
        justify-content: flex-end;
    }

    /* Step Progress - Glassy */
    .step-track {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        font-size: 13px;
        line-height: 1;
        font-variant-numeric: tabular-nums;
    }
    .step-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 10px 5px 6px;
        border-radius: var(--radius-button);
        border: 1px solid rgba(255, 255, 255, 0.1);
        white-space: nowrap;
        transition: background 250ms var(--ease-out-expo), border-color 250ms var(--ease-out-expo), color 250ms var(--ease-out-expo), box-shadow 250ms var(--ease-out-expo);
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

    /* New Sidebar Components */
    .user-identity-bar {
        background: rgba(13, 22, 43, 0.4) !important;
        border-radius: var(--radius-button);
        padding: 4px;
        display: flex;
        align-items: center;
        gap: 8px;
        border: 1px solid rgba(141, 179, 195, 0.15);
    }
    .user-status-text {
        font-size: 13px;
        color: var(--color-ink-muted) !important;
        padding-left: 4px;
        margin-top: 4px !important;
        margin-bottom: 12px !important;
    }
    .sidebar-footer {
        margin-top: 24px !important;
        padding-top: 16px;
        border-top: 1px solid rgba(255, 255, 255, 0.08);
    }
    .sidebar-footer-btn {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: var(--color-ink-muted) !important;
        font-size: 13px !important;
        padding: 8px !important;
        justify-content: flex-start !important;
        min-height: 32px !important;
    }
    .sidebar-footer-btn:hover {
        background: rgba(255, 255, 255, 0.05) !important;
        color: var(--color-ink) !important;
    }


    /* ═══ THREE-COLUMN LAYOUT SYSTEM (V11.1 MERGED) ═══ */
    .layout-three-col {
        display: flex !important;
        flex-direction: row !important;
        gap: 16px;
        min-height: calc(100dvh - 100px);
    }
    .layout-three-col > .col-sidebar {
        flex: 0 0 300px !important;
        max-width: 300px !important;
        min-width: 250px !important;
        overflow-y: auto;
    }
    .layout-three-col > .col-canvas {
        flex: 1 1 0 !important;
        min-width: 480px !important;
        overflow-y: auto;
    }
    .layout-three-col > .col-agent-hub {
        flex: 0 0 300px !important;
        max-width: 300px !important;
        min-width: 250px !important;
        overflow-y: auto;
    }
    @media (max-width: 1280px) {
        .layout-three-col > .col-agent-hub {
            flex: 0 0 250px !important;
            max-width: 250px !important;
        }
    }
    @media (max-width: 1024px) {
        .layout-three-col {
            flex-direction: column !important;
        }
        .layout-three-col > .col-sidebar,
        .layout-three-col > .col-agent-hub {
            flex: 1 1 auto !important;
            max-width: 100% !important;
        }
    }
    /* Agent Hub card styling */
    .agent-hub-card {
        background: rgba(13, 22, 43, 0.45) !important;
        backdrop-filter: var(--blur-glass) !important;
        -webkit-backdrop-filter: var(--blur-glass) !important;
        border: 1px solid rgba(100, 139, 168, 0.2) !important;
        border-top: 1px solid rgba(141, 179, 195, 0.25) !important;
        border-radius: var(--radius-card) !important;
        padding: 16px;
        margin-bottom: 12px;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3), inset 0 1px 0 rgba(255,255,255,0.04) !important;
    }
    .agent-hub-card * { color: var(--color-ink-body) !important; }
    .agent-hub-card h3, .agent-hub-card h4 {
        color: var(--color-ink) !important;
        font-size: 14px;
        font-weight: 600;
        margin-bottom: 8px;
    }
    /* Heatmap dots */
    .review-dot { display: inline-block; width: 10px; height: 10px; border-radius: 50%; margin-right: 4px; }
    .review-dot.green { background: #238636; }
    .review-dot.yellow { background: #DFCB5C; }
    .review-dot.red { background: #F85149; }
    .review-dot.gray { background: #484F58; }

    /* prefers-reduced-motion: keep opacity/color feedback; remove movement & scale */
    @media (prefers-reduced-motion: reduce) {
        /* Remove ALL movement, scaling, and sliding — these cause vestibular discomfort */
        *,
        *::before,
        *::after {
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
        }
        /* Collapse transitions to opacity/color only — NO transform, NO blur */
        .ios-btn-primary,
        .ios-btn-secondary,
        .ios-btn-danger,
        .gradio-container button {
            transition: opacity 150ms ease, background 150ms ease, border-color 150ms ease !important;
        }
        .ios-btn-primary:hover,
        .ios-btn-secondary:hover,
        .ios-btn-danger:hover,
        .gradio-container button:hover {
            transform: none !important;
        }
        .ios-btn-primary:active,
        .ios-btn-secondary:active,
        .ios-btn-danger:active,
        .gradio-container button:active {
            transform: none !important;
            opacity: 0.75 !important;
            filter: none !important;
        }
        .gradio-container details > summary:hover,
        .gradio-container [class*="accordion"] > button:hover {
            transform: none !important;
        }
        .gradio-container details > summary:active,
        .gradio-container [class*="accordion"] > button:active {
            transform: none !important;
            filter: brightness(0.85) !important;
        }
        .ios-card:hover {
            transform: none !important;
        }
        .step-badge {
            transition: background 150ms ease, border-color 150ms ease, color 150ms ease !important;
        }
        /* 禁用 SVG SMIL 动画 - 不受 animation-* 属性控制，需单独隐藏 */
        animateTransform,
        animate,
        animateMotion {
            display: none !important;
        }
    }



    /* ═══ BORDER & BOX NUCLEAR RESET (V11.1) ═══ */
    /* Eliminate all unwanted borders from Gradio HTML/Markdown wrapper divs */
    .gradio-container .prose,
    .gradio-container [data-testid="html"],
    .gradio-container [data-testid="markdown"],
    .gradio-container .output-html,
    .gradio-container .output-markdown {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }
    /* Fix: gr.HTML parent wrapper always gets a default border in some Gradio versions */
    .gradio-container div[class*="svelte-"] > div[class*="wrap"] {
        border: none !important;
        background: transparent !important;
        box-shadow: none !important;
    }
    /* Accordion content area: allow full scroll, remove any clip */
    .gradio-container details > div,
    .gradio-container [class*="accordion"] > div:not(button):not(summary) {
        overflow: visible !important;
        max-height: none !important;
    }
    /* But the agent hub HTML scroll area manages its own max-height */
    .gradio-container .agent-log-html > div { overflow: visible !important; }

    /* ═══ AGENT HUB PANEL HEADER ═══ */
    .agent-hub-title {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px 10px;
        border-bottom: 1px solid rgba(100,139,168,0.18);
        margin-bottom: 10px;
    }
    .agent-hub-title .dot {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--color-accent);
        box-shadow: 0 0 6px rgba(223,203,92,0.6);
        animation: pulse-dot 2.5s ease-in-out infinite;
    }
    @keyframes pulse-dot {
        0%, 100% { opacity: 1; transform: scale(1); }
        50% { opacity: 0.5; transform: scale(0.85); }
    }
    .agent-hub-title h3 {
        margin: 0 !important;
        font-size: 14px !important;
        font-weight: 600 !important;
        color: var(--color-ink) !important;
        letter-spacing: 0.02em;
    }

    /* ═══ AGENT LOG HTML PANEL ═══ */
    .agent-log-html {
        background: rgba(5, 12, 25, 0.6) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(40,60,95,0.5) !important;
        overflow: hidden !important;
        min-height: 80px;
    }
    .agent-log-html * { color: inherit !important; }

    /* ═══ SLIDER ACCENT COLOR ═══ */
    .gradio-container input[type="range"] {
        accent-color: var(--color-accent) !important;
    }
    .gradio-container .wrap.svelte-fwbhsv input[type="range"]::-webkit-slider-thumb {
        background: var(--color-accent) !important;
    }

    /* ═══ REVIEW HEATMAP WRAPPER ═══ */
    .review-heatmap-wrap {
        background: rgba(5,12,25,0.5) !important;
        border-radius: 12px !important;
        border: 1px solid rgba(40,60,95,0.4) !important;
        padding: 10px 12px !important;
    }

    /* ═══ EMPTY STATE — AGENT HUB ═══ */
    .agent-empty-state {
        padding: 16px 12px;
        text-align: center;
        border: 1px dashed rgba(60,85,120,0.4);
        border-radius: 10px;
        margin: 4px 0;
    }

    /* ═══ SHOW COPY BUTTON STYLE ═══ */
    .gradio-container .copy-text-button {
        opacity: 0.4;
        transition: opacity 200ms ease;
    }
    .gradio-container .copy-text-button:hover { opacity: 1; }

    /* ═══ PROGRESS BADGE WRAPPER: no border ═══ */
    .gradio-container [data-testid="html"] {
        border: none !important;
        background: transparent !important;
    }
    """

    with gr.Blocks(title="公文写作智能体 V11", css=custom_css) as demo:
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
            <div class="title-banner" role="banner">
                <h1 style="margin: 0; font-size: 28px; font-weight: 700; letter-spacing: 0.5px;">公文写作智能助手</h1>
                <p style="margin: 6px 0 0 0; opacity: 0.9; font-size: 14px;">多角色协作写作 · 智能审查校对 · 一键生成规范公文</p>
            </div>
            """
        )

        with gr.Row(elem_classes="layout-three-col"):
            # ═══════════════════════════════════════════════════════
            # 左侧资源栏 (Finder Sidebar)
            # ═══════════════════════════════════════════════════════
            with gr.Column(scale=1, elem_classes="sidebar-pane col-sidebar"):
                # ── 身份栏 ──
                with gr.Row(elem_classes="user-identity-bar"):
                    user_input = gr.Textbox(
                        label="用户名",
                        show_label=False,
                        placeholder="输入姓名以切换或建立新空间",
                        value=app.current_user_name or "",
                        scale=2
                    )
                    user_login_btn = gr.Button("确认身份", variant="secondary", elem_classes="ios-btn-secondary", scale=1)
                
                user_status_msg = gr.Markdown(f"当前用户: **{app.current_user_name or '未选择'}**", elem_classes="user-status-text")

                # ── 项目管理器 ──
                with gr.Accordion("项目工程", open=True):
                    project_selector = gr.Dropdown(
                        choices=app.get_projects_list(),
                        label="当前活动项目",
                        show_label=True,
                        value=app.get_projects_list()[0] if app.get_projects_list() else None
                    )
                    with gr.Row():
                        proj_create_trigger = gr.Button("新建项目", variant="secondary", size="sm", elem_classes="ios-btn-secondary")
                        proj_delete_btn = gr.Button("删除项目", variant="secondary", size="sm", elem_classes="ios-btn-danger")
                    
                    # 删除确认面板
                    with gr.Column(visible=False) as confirm_delete_box:
                        gr.Markdown("### 确认删除")
                        gr.Markdown("此操作不可撤销，项目将被永久删除。")
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
                with gr.Accordion("参考资料库", open=False):
                    open_ref_lib_btn = gr.Button("📚 打开知识与参考资料库", variant="secondary", elem_classes="ios-btn-secondary")
                    gr.Markdown("<small>点击进入独立的工作台面板，进行搜索、过滤与深度管理。</small>")

                # ── 底部快捷操作 & 系统设置 ──
                with gr.Accordion("系统与个性化", open=False):
                    bg_theme_selector = gr.Dropdown(
                        label="背景美学风格",
                        choices=["星月夜漩涡 (Starry Night)", "经典流光 (Classic Fluid)", "苹果极简 (Apple Minimal)"],
                        value="星月夜漩涡 (Starry Night)"
                    )
                
                with gr.Row(elem_classes="sidebar-footer"):
                    goto_api_btn = gr.Button("API 设置", elem_classes="ios-btn-secondary sidebar-footer-btn")
                    goto_profile_btn = gr.Button("用户画像", elem_classes="ios-btn-secondary sidebar-footer-btn")

                global_status_msg = gr.Markdown()

            # ═══════════════════════════════════════════════════════
            # 右侧主工作区 (Main Workspace)
            # ═══════════════════════════════════════════════════════
            with gr.Column(scale=2, elem_classes="workspace-pane col-canvas"):
                
                # ─── 面板 0: 空状态启动页 ───
                with gr.Column(visible=True, elem_classes="empty-state-card ws-panel-visible") as splash_screen:
                    gr.Markdown("""
                    <div style="text-align: center; padding: 120px 20px;">
                        <h2 style="font-size: 28px; margin-bottom: 16px;">欢迎来到公文写作智能助手</h2>
                        <p style="color: var(--color-ink-muted); font-size: 16px; margin-bottom: 24px;">请在左侧登录并选择或创建一个项目工程，即可开始您的沉浸式写作流程。</p>
                        <div style="display: inline-flex; align-items: center; gap: 8px; color: var(--color-accent); font-weight: 500;">
                            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m15 18-6-6 6-6"/></svg>
                            请在左侧栏开始操作
                        </div>
                    </div>
                    """)

                # ─── 面板 A: 写作项目工作台 ───
                with gr.Column(visible=False, elem_classes="ws-panel-hidden") as project_panel:
                    # 顶部进度和状态
                    with gr.Row(elem_classes="project-header-row"):
                        with gr.Column(scale=1, min_width=300):
                            active_proj_title = gr.Markdown("### 选择左侧项目或新建项目开始写作", elem_classes="project-title-text")
                        with gr.Column(scale=0, min_width=320, elem_classes="progress-badge-container"):
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
                                    q_btn_back = gr.Button("回退", elem_classes="ios-btn-secondary", size="sm")
                                    q_btn_skip = gr.Button("跳过", elem_classes="ios-btn-secondary", size="sm")
                                    q_btn_finish = gr.Button("提前完成", elem_classes="ios-btn-secondary", size="sm")
                                    q_btn_reset = gr.Button("清空进度", variant="stop", elem_classes="ios-btn-danger", size="sm")
                                
                                with gr.Row():
                                    q_btn_submit = gr.Button("提交回答", variant="primary", elem_classes="ios-btn-primary", size="lg")
                                
                                with gr.Column(visible=False) as confirm_reset_box:
                                    gr.Markdown("⚠️ **危险操作**：确定要清空当前问卷的所有进度并重头开始吗？此操作无法撤销。")
                                    with gr.Row():
                                        confirm_reset_btn = gr.Button("确认清空", variant="stop", elem_classes="ios-btn-danger")
                                        cancel_reset_btn = gr.Button("取消", elem_classes="ios-btn-secondary")
                                
                                q_event_msg = gr.Markdown()
                            
                            def sync_workspace_visibility(proj_name=None):
                                has_proj = bool(proj_name) if proj_name is not None else bool(app.current_project_id)
                                return {
                                    project_panel: gr.update(elem_classes="ws-panel-visible" if has_proj else "ws-panel-hidden"),
                                    splash_screen: gr.update(elem_classes="ws-panel-hidden" if has_proj else "empty-state-card ws-panel-visible")
                                }

                            demo.load(
                                fn=sync_workspace_visibility,
                                outputs=[project_panel, splash_screen]
                            )
                            project_selector.change(
                                fn=sync_workspace_visibility,
                                inputs=[project_selector],
                                outputs=[project_panel, splash_screen]
                            )

                        # Tab 2: 智能方案生成
                        with gr.Tab("写作大纲方案", id="tab_plan"):
                            plan_output_text = gr.Textbox(label="生成的方案大纲与结构", lines=18, interactive=False, show_copy_button=True)
                            
                            with gr.Row():
                                with gr.Column(scale=1):
                                    doc_type_recommend_md = gr.Markdown("### 💡 智能文种推荐\n(完成问卷后自动推荐)")
                                with gr.Column(scale=1):
                                    kb_exemplar_recommend = gr.Markdown("### 📚 知识库推荐范文")
                            
                            gr.Markdown("#### 方案大纲调优调整")
                            with gr.Row():
                                ui_doc_selector = gr.Dropdown(
                                    choices=[label for label, _ in DOC_TYPE_CHOICES],
                                    value="通讯（推荐1500-3000字）",
                                    label="覆盖/确认最终公文文种",
                                    scale=2
                                )
                                plan_regen_btn = gr.Button("重新生成大纲", variant="secondary", elem_classes="ios-btn-secondary", scale=1)
                                
                            gr.Markdown("#### 风格调校")
                            with gr.Row():
                                ui_style_selector = gr.Dropdown(
                                    choices=[label for label, _ in STYLE_CHOICES],
                                    value="人民日报风格",
                                    label="选择主导风格",
                                    scale=1
                                )
                                style_intensity_slider = gr.Slider(0.0, 1.0, value=0.5, step=0.1, label="风格强度", scale=1)
                            
                            with gr.Row():
                                with gr.Column(scale=1):
                                    style_detail_md = gr.Markdown("请选择风格查看特征详情...")
                                with gr.Column(scale=1):
                                    style_blend_md = gr.Markdown("混合风格建议...")
                            
                            plan_btn_next = gr.Button("确认方案，开始写作", variant="primary", elem_classes="ios-btn-primary")

                        # Tab 3: 智能写作生成
                        with gr.Tab("文稿草稿生成", id="tab_write"):
                            # 参考资料选择器（从已导入的资料库中选择，内容将自动注入写作素材）
                            with gr.Accordion("📚 参考资料辅助（可选）", open=True):
                                gr.Markdown(
                                    "<small>从左侧已导入的参考资料中选择，系统将自动提取其内容与风格特征，"
                                    "作为本次写作的参考素材注入智能体。可在左侧「参考资料库」导入新网页。</small>"
                                )
                                ref_topic_for_write = gr.Dropdown(
                                    choices=app.get_topics_list(),
                                    label="选择参考主题",
                                    interactive=True
                                )
                                ref_doc_for_write = gr.Dropdown(
                                    choices=[],
                                    label="选择参考文档（可多选）",
                                    multiselect=True,
                                    interactive=True,
                                    info="选中后，其正文内容将自动追加到下方素材区"
                                )
                                ref_use_style = gr.Checkbox(
                                    label="同时提取风格特征供智能体学习",
                                    value=True,
                                    info="自动提取参考文档的句式、用语等风格特征"
                                )
                                ref_inject_btn = gr.Button("📥 注入参考素材到下方素材区", variant="secondary", size="sm", elem_classes="ios-btn-secondary")
                            
                            materials_input = gr.Textbox(label="可贴入本次写作的其他原始语料/素材内容(可选)", lines=5, placeholder="粘贴任何其他零碎记录、会议讲话或新闻参考数据...\n也可点击上方「注入参考素材」自动填入已导入的参考资料内容。")
                            write_start_btn = gr.Button("开始写作（多智能体协商 + 生成，首次可能需要 1-3 分钟）", variant="primary", elem_classes="ios-btn-primary")
                            
                            write_event_msg = gr.Markdown()
                            draft_editor = gr.Textbox(label="草稿（主版本）", lines=22, placeholder="草稿内容将在这里呈现...", show_copy_button=True)
                            
                            with gr.Accordion("多角色协作日志", open=False):
                                coord_agent_logs = gr.Textbox(label="协作日志", lines=8, interactive=False)
                            with gr.Accordion("多格式版本草稿", open=False):
                                multi_versions_preview = gr.Textbox(label="多格式版本", lines=10, interactive=False)
                                
                            write_btn_next = gr.Button("对文稿执行智能审查", variant="primary", elem_classes="ios-btn-primary")

                        # Tab 4: 智能审阅修正 (HITL)
                        with gr.Tab("智能审查与人工介入", id="tab_review"):
                            review_event_msg = gr.Markdown()
                            review_summary_text = gr.Textbox(label="多维审查得分与总结", lines=12, interactive=False, show_copy_button=True)
                            
                            with gr.Accordion("🕒 智能审查迭代历史", open=False):
                                review_iteration_history_md = gr.Markdown("暂无审查历史")
                                
                            with gr.Accordion("🚨 知识库合规诊断", open=False):
                                kb_diagnosis_detail_md = gr.Markdown("暂无诊断结果")
                            
                            with gr.Row():
                                with gr.Column(scale=1):
                                    with gr.Group(elem_classes="ios-card"):
                                        gr.Markdown("**检测到的偏见与问题清单**")
                                        review_issues_list = gr.Markdown()
                                with gr.Column(scale=1):
                                    with gr.Group(elem_classes="ios-card"):
                                        gr.Markdown("**格式规范合规度(GB/T 9704-2012 国家党政机关公文格式标准)**")
                                        review_format_text = gr.Markdown()
                                        
                            gr.Markdown("#### 人工介入更新 (HITL: Human-in-the-loop)")
                            manual_edit_text = gr.Textbox(label="在此处对文稿进行人工细节微调...", lines=14)
                            with gr.Row():
                                manual_save_btn = gr.Button("保存手动修改", variant="secondary", elem_classes="ios-btn-secondary")
                                re_review_btn = gr.Button("重新执行审查", variant="secondary", elem_classes="ios-btn-secondary")
                                
                            review_btn_next = gr.Button("确认文稿无误，完成交付", variant="primary", elem_classes="ios-btn-primary")

                        # Tab 5: 终稿交付完成
                        with gr.Tab("最终成果交付", id="tab_finalize"):
                            final_draft_output = gr.Textbox(label="最终公文文稿", lines=24, interactive=True, show_copy_button=True)
                            
                            with gr.Row():
                                with gr.Column(scale=1):
                                    final_multi_versions = gr.Textbox(label="多格式版本备份", lines=12, interactive=False, show_copy_button=True)
                                with gr.Column(scale=1):
                                    workflow_summary_text = gr.Textbox(label="智能协作工作流回溯报告", lines=12, interactive=False)
                            
                            with gr.Accordion("📊 API 成本与 Token 优化统计", open=False):
                                token_stats_md = gr.Markdown("无统计数据")
                                
                            export_finished_btn = gr.Button("导出完成", variant="primary", elem_classes="ios-btn-primary")

                # ─── 面板 B: 参考素材资料库 (重构版) ───
                with gr.Column(visible=True, elem_classes="ws-panel-hidden") as ref_doc_panel:
                    gr.Markdown("## 📚 知识与参考资料库")
                    
                    with gr.Group(elem_classes="ios-card"):
                        with gr.Row():
                            ref_search_query = gr.Textbox(label="搜索关键词", placeholder="输入标题或正文...", scale=3)
                            ref_filter_topic = gr.Dropdown(label="按主题过滤", choices=["全部主题"] + app.get_topics_list(), value="全部主题", scale=2)
                            ref_filter_format = gr.Dropdown(label="按格式过滤", choices=["全部格式"], value="全部格式", scale=2)
                            ref_filter_source = gr.Dropdown(label="按来源过滤", choices=["全部来源"], value="全部来源", scale=2)
                            ref_sort_by = gr.Dropdown(label="排序方式", choices=["默认", "最新发布", "字数最多", "字数最少"], value="默认", scale=2)
                            ref_search_btn = gr.Button("🔍 搜索", variant="primary", scale=1)
                            
                        ref_docs_table = gr.Dataframe(
                            headers=["文档ID", "标题", "格式", "字数", "日期", "来源", "所属主题"],
                            datatype=["str", "str", "str", "number", "str", "str", "str"],
                            col_count=(7, "fixed"),
                            interactive=False,
                            wrap=True
                        )
                        gr.Markdown("<small>提示：在上方表格**点击任意一行**即可在下方查看该文档详情。</small>")
                        
                        with gr.Row():
                            url_import_trigger = gr.Button("📥 导入新网页", variant="secondary", size="sm")
                            topic_manage_trigger = gr.Button("🗂️ 主题管理", variant="secondary", size="sm")
                            ref_batch_delete_trigger = gr.Button("🗑️ 批量删除", variant="secondary", size="sm")
                            ref_panel_close_btn = gr.Button("❌ 返回项目", variant="secondary", size="sm")
                            
                        # 导入URL表单 (隐藏)
                        with gr.Column(visible=False) as url_import_box:
                            gr.Markdown("### 📥 导入新网页")
                            url_input_val = gr.Textbox(label="网页 URL", placeholder="https://example.com/article")
                            url_topic_val = gr.Textbox(label="导入至主题", placeholder="例如: 教育改革参考")
                            with gr.Row():
                                url_save_btn = gr.Button("执行导入", variant="primary", size="sm", elem_classes="ios-btn-primary")
                                url_cancel_btn = gr.Button("取消", variant="secondary", size="sm")
                                
                        # 主题管理表单 (隐藏)
                        with gr.Column(visible=False) as topic_manage_box:
                            gr.Markdown("### 🗂️ 主题管理")
                            with gr.Row():
                                topic_create_name = gr.Textbox(label="新建主题名称", scale=2)
                                topic_create_btn = gr.Button("新建", variant="primary", scale=1)
                            with gr.Row():
                                topic_rename_old = gr.Dropdown(label="原主题名", choices=app.get_topics_list(), scale=1)
                                topic_rename_new = gr.Textbox(label="新主题名", scale=1)
                                topic_rename_btn = gr.Button("重命名", variant="primary", scale=1)
                            with gr.Row():
                                topic_delete_name = gr.Dropdown(label="要删除的主题", choices=app.get_topics_list(), scale=2)
                                topic_delete_btn = gr.Button("删除主题", variant="stop", scale=1)
                            topic_manage_cancel = gr.Button("关闭管理", size="sm")
                            
                        # 批量删除辅助框
                        with gr.Column(visible=False) as batch_delete_box:
                            gr.Markdown("### 🗑️ 批量删除文档")
                            batch_delete_ids = gr.Textbox(label="要删除的文档ID", placeholder="输入表格中第一列的文档ID，多个用逗号分隔")
                            with gr.Row():
                                confirm_batch_delete_btn = gr.Button("确认删除", variant="stop", elem_classes="ios-btn-danger")
                                cancel_batch_delete_btn = gr.Button("取消")

                    # 选中文档详情区域
                    with gr.Column(visible=False) as ref_doc_detail_box:
                        gr.Markdown("### 📄 文档详情与操作")
                        with gr.Group(elem_classes="ios-card"):
                            # 隐藏存放当前选中的 doc_id 状态
                            current_selected_doc_id = gr.State("")
                            
                            ref_doc_edit_meta = gr.Markdown()
                            ref_doc_edit_title = gr.Textbox(label="修改标题", interactive=True)
                            ref_doc_edit_content = gr.Textbox(label="正文内容预览/编辑", lines=10, interactive=True)
                            
                            with gr.Row():
                                ref_doc_edit_save = gr.Button("💾 保存修改", variant="primary")
                                ref_doc_import_to_write = gr.Button("📥 注入当前文稿素材区", variant="secondary")
                                ref_doc_detail_close = gr.Button("🔼 收起详情", variant="secondary")
                                
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
                            api_temp = gr.Slider(0.0, 2.0, value=0.7, step=0.1, label="创新度默认值 (保存到配置)", info="实际写作使用右侧「Agent 决策大脑」的创新温度滑杆")
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
                                
                    with gr.Group(elem_classes="ios-card"):
                        gr.Markdown("### 📚 专属词汇语料库管理 (Vocabulary Corpus)")
                        with gr.Row():
                            with gr.Column(scale=1):
                                vocab_corpus_summary_md = gr.Markdown("加载中...")
                            with gr.Column(scale=1):
                                vocab_keyword_input = gr.Textbox(label="添加必用关键词", placeholder="如: 新质生产力")
                                vocab_keyword_btn = gr.Button("添加必用词", size="sm")
                                vocab_forbidden_input = gr.Textbox(label="添加禁用/违禁词", placeholder="如: 遥遥领先")
                                vocab_forbidden_btn = gr.Button("添加禁用词", size="sm")
                                vocab_msg = gr.Markdown()
                                
                    profile_close_btn = gr.Button("关闭画像", variant="secondary")


            # ═══════════════════════════════════════════════════════
            # 右侧 Agent 决策大脑 (Agent Hub) — V11 新增
            # ═══════════════════════════════════════════════════════
            with gr.Column(scale=1, elem_classes="sidebar-pane col-agent-hub"):
                # 装饰标题（带脸动脉冲圆点）
                gr.HTML("""
                    <div class="agent-hub-title">
                        <div class="dot" aria-hidden="true"></div>
                        <h3>Agent 决策大脑</h3>
                    </div>
                """)
                
                # ── Agent 协商总线可视化 — 替换为无黑框的 HTML 渲染 ──
                with gr.Accordion("协商总线日志", open=True):
                    agent_coord_chatbot = gr.HTML(
                        value=app.format_agent_messages_html(),
                        elem_classes="agent-log-html"
                    )
                    
                with gr.Accordion("多智能体协同全景视图", open=False):
                    agent_coordination_report_md = gr.Markdown("暂无协同数据")
                
                # ── 五轮审查热力图 ──
                with gr.Accordion("审查热力图", open=True):
                    review_heatmap_html = gr.HTML(
                        value=app.build_review_heatmap(),
                        elem_classes="review-heatmap-wrap"
                    )
                
                # ── 反偏见洞察 (AntiBiasAnalysis) ──
                with gr.Accordion("反偏见洞察", open=False):
                    antibias_display = gr.Markdown(app.get_antibias_display())
                    antibias_temp_slider = gr.Slider(
                        label="创新温度 (Temperature)",
                        minimum=0.0, maximum=2.0, value=0.7, step=0.1,
                        info="越高越激进创新，越低越保守安全"
                    )
                
                # ── HITL 快捷操作 ──
                with gr.Accordion("审查建议速览", open=False):
                    hitl_quick_issues = gr.Markdown(
                        "<div class='agent-empty-state' style='color:var(--color-ink-muted);font-size:12px;'>"
                        "审查完成后，关键修改建议将在此列出。</div>"
                    )



        # ═══════════════════════════════════════════════════════
        # Gradio 事件处理器绑定 (Event Listeners)
        # ═══════════════════════════════════════════════════════
        
        # ── 1. 登录用户事件 ──
        def login_user_fn(name):
            msg, projects, default_proj = app.switch_or_create_user(name)
            # 登录后仅切换用户空间，不自动加载项目
            msg = msg + f"\n\n欢迎，{name}。请新建或选择项目开始写作。"
            return (
                msg,
                gr.update(value=f"当前用户: **{name}**", visible=True),
                gr.update(choices=projects, value=None),
                gr.update(value="### 请新建项目以开始"),
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
                "",  # manual_edit_text
                app.format_agent_messages_html(),  # agent_coord_chatbot (gr.HTML)
                app.build_review_heatmap(),  # review_heatmap_html
                app.get_antibias_display(),  # antibias_display
                "",  # hitl_quick_issues
            )

        user_login_btn.click(
            fn=login_user_fn,
            inputs=[user_input],
            outputs=[
                global_status_msg, user_status_msg, project_selector,
                active_proj_title, plan_output_text,
                draft_editor, coord_agent_logs, review_summary_text,
                final_draft_output, final_multi_versions, progress_badge_html,
                routing_box, routing_q_title, routing_q_desc,
                routing_options_disp, routing_options_dropdown,
                current_q_prog, current_q_title, current_q_desc,
                current_q_hint, manual_edit_text,
                agent_coord_chatbot, review_heatmap_html, antibias_display, hitl_quick_issues
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
                gr.update(value=f"### 项目工程：{name}"),
                gr.update(elem_classes="ios-card ws-panel-visible" if routing_vis else "ios-card ws-panel-hidden"),
                gr.update(value=ui["title"]),
                gr.update(value=ui["desc"]),
                gr.update(value=ui["options_text"]),
                gr.update(choices=ui["choices"], value=None),
                plan,
                kb,
                gr.update(value=build_progress_badge("问卷")),
                app.format_agent_messages_html(),  # agent_coord_chatbot (gr.HTML)
            )

        new_proj_save_btn.click(
            fn=new_proj_fn,
            inputs=[new_proj_name, new_proj_desc],
            outputs=[
                global_status_msg, project_selector, new_proj_box, 
                active_proj_title, routing_box, routing_q_title, 
                routing_q_desc, routing_options_disp, routing_options_dropdown,
                plan_output_text, kb_exemplar_recommend, progress_badge_html,
                agent_coord_chatbot
            ]
        )

        # ── 3. 选择项目事件 ──
        def select_project_fn(name):
            if not name:
                # 删除项目/登出后下拉框被清空时，显示中性提示而非报错
                return (
                    "请选择或新建一个项目开始写作",
                    gr.update(value="## 请新建或选择项目"),
                    "", "", "", "", "", "",
                    gr.update(value=build_progress_badge("")),
                    gr.update(elem_classes="ios-card ws-panel-hidden"),
                    gr.update(value="### 场景路由选择"),
                    gr.update(value=""),
                    gr.update(value=""),
                    gr.update(choices=[], value=None),
                    gr.update(value=""),
                    gr.update(value="### 等待选择项目"),
                    gr.update(value=""),
                    gr.update(value=""),
                    "",
                    app.format_agent_messages_html(),  # agent_coord_chatbot (gr.HTML)
                )
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
                gr.update(value=f"### 项目工程：{name}"),
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
                draft,  # manual_edit_text
                app.format_agent_messages_html(),  # agent_coord_chatbot (gr.HTML)
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
                current_q_hint, manual_edit_text,
                agent_coord_chatbot
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
        
        def delete_project_fn(name):
            msg, projects, _ = app.delete_project_action(name)
            cleared = app.current_project_id is None
            return (
                msg,
                gr.update(choices=projects, value=None),
                gr.update(visible=False),
                gr.update(value="## 请新建或选择项目") if cleared else gr.update(),
                "" if cleared else gr.update(),  # plan_output_text
                "" if cleared else gr.update(),  # draft_editor
                "" if cleared else gr.update(),  # coord_agent_logs
                "" if cleared else gr.update(),  # review_summary_text
                "" if cleared else gr.update(),  # final_draft_output
                "" if cleared else gr.update(),  # final_multi_versions
                gr.update(value=build_progress_badge("")) if cleared else gr.update(),
                "" if cleared else gr.update(),  # manual_edit_text
                app.format_agent_messages_html() if cleared else gr.update(),  # agent_coord_chatbot (gr.HTML)
            )

        confirm_delete_yes_btn.click(
            fn=delete_project_fn,
            inputs=[project_selector],
            outputs=[
                global_status_msg, project_selector, confirm_delete_box,
                active_proj_title, plan_output_text, draft_editor,
                coord_agent_logs, review_summary_text, final_draft_output,
                final_multi_versions, progress_badge_html, manual_edit_text,
                agent_coord_chatbot
            ]
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
        
        def show_confirm_reset():
            return gr.update(visible=True)
            
        def hide_confirm_reset():
            return gr.update(visible=False)
            
        q_btn_reset.click(
            fn=show_confirm_reset,
            outputs=[confirm_reset_box]
        )
        
        cancel_reset_btn.click(
            fn=hide_confirm_reset,
            outputs=[confirm_reset_box]
        )
        
        def reset_project_and_refresh():
            proj_name = app.reset_project()
            if proj_name:
                results = list(select_project_fn(proj_name))
                results.append(gr.update(visible=False))
                return results
            return ["未重置"] + [gr.update()] * 19 + [gr.update(visible=False)]

        confirm_reset_btn.click(
            fn=reset_project_and_refresh,
            outputs=[
                global_status_msg, active_proj_title, plan_output_text,
                draft_editor, coord_agent_logs, review_summary_text,
                final_draft_output, final_multi_versions, progress_badge_html,
                routing_box, routing_q_title, routing_q_desc,
                routing_options_disp, routing_options_dropdown,
                current_q_prog, current_q_title, current_q_desc,
                current_q_hint, manual_edit_text, agent_coord_chatbot,
                confirm_reset_box
            ]
        )

        # ── 7. 重新生成大纲方案 ──
        plan_regen_btn.click(
            fn=app.regenerate_plan_action,
            inputs=[ui_style_selector, ui_doc_selector],
            outputs=[plan_output_text, global_status_msg]
        )

        # ── 8. 大纲确认并写作 ──
        # 先用当前下拉框选择重新生成方案，确保风格/文种与用户选择一致
        def safe_plan_next(style_lbl, doc_lbl):
            if not app.orchestrator or not app.orchestrator.brief:
                return gr.update(), gr.update(), "请先完成问卷"
            plan_display, msg = app.regenerate_plan_action(style_lbl, doc_lbl)
            if "失败" in msg:
                return gr.update(), gr.update(), msg
            return gr.update(selected="tab_write"), plan_display, msg

        plan_btn_next.click(
            fn=safe_plan_next,
            inputs=[ui_style_selector, ui_doc_selector],
            outputs=[project_tabs, plan_output_text, global_status_msg]
        )

        # ── 8b. 写作Tab - 参考资料选择器联动 ──
        def write_topic_change_fn(topic):
            if not topic:
                return gr.update(choices=[], value=None)
            docs = app.get_docs_list_by_topic(topic)
            return gr.update(choices=docs, value=None)

        ref_topic_for_write.change(
            fn=write_topic_change_fn,
            inputs=[ref_topic_for_write],
            outputs=[ref_doc_for_write]
        )

        # ── 8c. 写作Tab - 注入参考素材到素材区 ──
        def inject_ref_to_materials_fn(topic, doc_titles, use_style, current_materials):
            new_materials, msg = app.inject_ref_docs_to_materials(topic, doc_titles, use_style, current_materials)
            return new_materials, msg

        ref_inject_btn.click(
            fn=inject_ref_to_materials_fn,
            inputs=[ref_topic_for_write, ref_doc_for_write, ref_use_style, materials_input],
            outputs=[materials_input, write_event_msg]
        )

        # ── 9. 执行文稿生成 ──
        # V11.1: 使用 format_agent_messages_html() 替代旧的 get_agent_chatbot_messages()
        def generate_and_update_hub(raw_materials, temperature, progress=gr.Progress()):
            draft, agent_log, multi_ver, msg, prog = app.generate_draft_action(raw_materials, temperature, progress)
            agent_html = app.format_agent_messages_html()
            return draft, agent_log, multi_ver, msg, prog, agent_html, app.build_review_heatmap()

        write_start_btn.click(
            fn=generate_and_update_hub,
            inputs=[materials_input, antibias_temp_slider],
            outputs=[
                draft_editor, coord_agent_logs, multi_versions_preview,
                write_event_msg, progress_badge_html, agent_coord_chatbot,
                review_heatmap_html
            ],
            concurrency_limit=1
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
            heatmap_html = app.build_review_heatmap()
            antibias_text = app.get_antibias_display()
            agent_html = app.format_agent_messages_html()  # 使用 HTML 格式渲染
            hitl_issues = app.get_hitl_quick_issues()
            return (*res, app.orchestrator.draft if app.orchestrator else "", heatmap_html, antibias_text, agent_html, hitl_issues)

        write_btn_next.click(
            fn=safe_write_next,
            outputs=[project_tabs, global_status_msg]
        ).then(
            fn=review_trigger_fn,
            outputs=[
                review_summary_text, review_issues_list, review_format_text,
                review_event_msg, progress_badge_html, manual_edit_text,
                review_heatmap_html, antibias_display,
                agent_coord_chatbot, hitl_quick_issues
            ]
        )

        # ── 11. 人工干预修改 ──
        manual_save_btn.click(
            fn=app.manual_update_draft,
            inputs=[manual_edit_text],
            outputs=[review_event_msg, draft_editor]
        )

        def re_review_trigger_fn():
            summary, issues_text, msg, draft = app.re_review_action()
            return summary, issues_text, msg, draft, app.build_review_heatmap(), app.get_hitl_quick_issues()

        re_review_btn.click(
            fn=re_review_trigger_fn,
            outputs=[review_summary_text, review_issues_list, review_event_msg, draft_editor, review_heatmap_html, hitl_quick_issues]
        )

        def safe_review_next():
            if not app.orchestrator or not app.orchestrator.draft:
                return gr.update(), "请先生成并审查文稿草稿"
            return gr.update(selected="tab_finalize"), ""

        # ── 提前定义 finalize，供 .then() 引用 ──
        def finalize_trigger_fn():
            res = app.finalize_project_action()
            return (*res, app.get_antibias_display())

        review_btn_next.click(
            fn=safe_review_next,
            outputs=[project_tabs, global_status_msg]
        ).then(
            fn=finalize_trigger_fn,
            outputs=[final_draft_output, final_multi_versions, workflow_summary_text, progress_badge_html, antibias_display]
        )

        # ── 12. 交付与完成（"导出完成"按钮的显式触发）──
        export_finished_btn.click(
            fn=finalize_trigger_fn,
            outputs=[final_draft_output, final_multi_versions, workflow_summary_text, progress_badge_html, antibias_display]
        )

        # ── 13. 参考资料库 (Reference Library) 面板导航与事件 ──
        open_ref_lib_btn.click(
            fn=lambda: (gr.update(elem_classes="ws-panel-hidden"), gr.update(elem_classes="ws-panel-visible")),
            outputs=[project_panel, ref_doc_panel]
        )
        ref_panel_close_btn.click(
            fn=lambda: (gr.update(elem_classes="ws-panel-visible"), gr.update(elem_classes="ws-panel-hidden")),
            outputs=[project_panel, ref_doc_panel]
        )

        def do_ref_search(query, topic, fmt, source, sort_by):
            data = app.search_ref_docs(query, topic, fmt, source, sort_by)
            return gr.update(value=data)

        ref_search_btn.click(
            fn=do_ref_search,
            inputs=[ref_search_query, ref_filter_topic, ref_filter_format, ref_filter_source, ref_sort_by],
            outputs=[ref_docs_table]
        )

        def ref_table_select(evt: gr.SelectData, table_data):
            if not table_data or evt.index[0] >= len(table_data):
                return gr.update(visible=False), "", "", "", ""
            row_idx = evt.index[0]
            doc_id = table_data[row_idx][0]
            # 获取详情
            title, meta_md = app.get_doc_detail_markdown(doc_id)
            if not title:
                return gr.update(visible=False), "", "", meta_md, ""
                
            topic, _ = doc_id.split(":::", 1)
            doc = next((d for d in app.url_topics[topic] if d.title == title), None)
            content = doc.content if doc else ""
            
            return gr.update(visible=True), doc_id, title, meta_md, content

        ref_docs_table.select(
            fn=ref_table_select,
            inputs=[ref_docs_table],
            outputs=[ref_doc_detail_box, current_selected_doc_id, ref_doc_edit_title, ref_doc_edit_meta, ref_doc_edit_content]
        )

        ref_doc_detail_close.click(
            fn=lambda: gr.update(visible=False),
            outputs=[ref_doc_detail_box]
        )

        # ── 14. 导入URL/主题管理/批量删除 (表单开关) ──
        url_import_trigger.click(fn=lambda: gr.update(visible=True), outputs=[url_import_box])
        url_cancel_btn.click(fn=lambda: gr.update(visible=False), outputs=[url_import_box])
        
        topic_manage_trigger.click(fn=lambda: gr.update(visible=True), outputs=[topic_manage_box])
        topic_manage_cancel.click(fn=lambda: gr.update(visible=False), outputs=[topic_manage_box])
        
        ref_batch_delete_trigger.click(fn=lambda: gr.update(visible=True), outputs=[batch_delete_box])
        cancel_batch_delete_btn.click(fn=lambda: gr.update(visible=False), outputs=[batch_delete_box])

        # ── 15. 执行导入URL事件 ──
        def url_import_fn(url, topic):
            msg, topics, current_topic, _, _ = app.import_url_action(url, topic)
            # 导入完成后自动触发一次搜索刷新表格
            new_data = app.search_ref_docs("", "全部主题", "全部格式", "全部来源", "默认")
            return (
                msg, 
                gr.update(visible=False), # 关闭表单
                gr.update(choices=["全部主题"] + topics), # 更新搜索栏下拉
                gr.update(choices=["全部主题"] + topics), # 更新主题管理下拉
                gr.update(value=new_data) # 更新表格
            )

        url_save_btn.click(
            fn=url_import_fn,
            inputs=[url_input_val, url_topic_val],
            outputs=[global_status_msg, url_import_box, ref_filter_topic, topic_delete_name, ref_docs_table]
        )

        # ── 16. 编辑选中的参考文档 ──
        def save_ref_doc_fn(doc_id, new_title, content):
            if not doc_id or ":::" not in doc_id:
                return "保存失败: 找不到文档ID"
            topic, old_title = doc_id.split(":::", 1)
            msg, _ = app.save_ref_doc_edit(topic, old_title, new_title, content)
            return msg

        ref_doc_edit_save.click(
            fn=save_ref_doc_fn,
            inputs=[current_selected_doc_id, ref_doc_edit_title, ref_doc_edit_content],
            outputs=[ref_doc_edit_msg]
        )

        # ── 17. 批量删除与主题管理操作 ──
        def do_batch_delete(doc_ids_str):
            msg, topics, _ = app.batch_delete_ref_docs(doc_ids_str)
            new_data = app.search_ref_docs("", "全部主题", "全部格式", "全部来源", "默认")
            return msg, gr.update(visible=False), gr.update(choices=["全部主题"]+topics), gr.update(value=new_data)
            
        confirm_batch_delete_btn.click(
            fn=do_batch_delete,
            inputs=[batch_delete_ids],
            outputs=[global_status_msg, batch_delete_box, ref_filter_topic, ref_docs_table]
        )
        
        def do_topic_create(name):
            msg, topics = app.create_topic(name)
            return msg, gr.update(choices=["全部主题"]+topics), gr.update(choices=["全部主题"]+topics)
            
        topic_create_btn.click(fn=do_topic_create, inputs=[topic_create_name], outputs=[global_status_msg, ref_filter_topic, topic_delete_name])
        
        def do_topic_delete(name):
            msg, topics = app.delete_topic(name)
            new_data = app.search_ref_docs("", "全部主题", "全部格式", "全部来源", "默认")
            return msg, gr.update(choices=["全部主题"]+topics), gr.update(choices=["全部主题"]+topics), gr.update(value=new_data)
            
        topic_delete_btn.click(fn=do_topic_delete, inputs=[topic_delete_name], outputs=[global_status_msg, ref_filter_topic, topic_delete_name, ref_docs_table])

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
                if user.common_error_patterns:
                    strengths_weaknesses += "\n".join([f"- {err.get('error_key', '')}: {err.get('diagnosis', '')}" for err in user.common_error_patterns])
                else:
                    strengths_weaknesses += "- 暂无明显偏好短板\n"
                
            memory = app.pdb.get_memory_summary(app.current_project_id)
            vocab = app.get_vocab_corpus_summary()
            return (
                gr.update(elem_classes="ws-panel-hidden"), 
                gr.update(elem_classes="ws-panel-visible"), 
                strengths_weaknesses, 
                memory,
                vocab
            )

        goto_profile_btn.click(
            fn=goto_profile_fn,
            outputs=[project_panel, profile_panel, user_strengths_weaknesses, memory_summary_text, vocab_corpus_summary_md]
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

        # ── 20. 词汇语料库事件 ──
        vocab_keyword_btn.click(
            fn=app.add_vocab_keyword,
            inputs=[vocab_keyword_input],
            outputs=[vocab_msg, vocab_corpus_summary_md]
        )
        vocab_forbidden_btn.click(
            fn=app.add_vocab_forbidden,
            inputs=[vocab_forbidden_input],
            outputs=[vocab_msg, vocab_corpus_summary_md]
        )

        # ── 21. 扩展组件交互更新 (Plan, Review, Finalize, Agent Hub) ──
        def update_plan_components():
            # 联动：问卷路由方向(subtype)传导到文种下拉框默认值，避免行政模式默认生成"通讯"
            md = app.get_doc_type_recommendation()
            doc_enum = app.get_recommended_doc_enum()
            dd_update = gr.update(value=DOC_TYPE_ENUM_TO_LABEL[doc_enum]) if doc_enum else gr.update()
            return md, dd_update
            
        # 当问卷提交/提前完成时更新文种推荐与下拉框默认值
        # （V11 布局无对应"下一题"按钮，改挂在 submit/finish 上）
        q_btn_submit.click(
            fn=update_plan_components,
            outputs=[doc_type_recommend_md, ui_doc_selector]
        )
        q_btn_finish.click(
            fn=update_plan_components,
            outputs=[doc_type_recommend_md, ui_doc_selector]
        )

        def update_style_components(style_lbl, intensity):
            return app.get_style_detail_display(style_lbl, intensity)
            
        ui_style_selector.change(fn=update_style_components, inputs=[ui_style_selector, style_intensity_slider], outputs=[style_detail_md, style_blend_md])
        style_intensity_slider.change(fn=update_style_components, inputs=[ui_style_selector, style_intensity_slider], outputs=[style_detail_md, style_blend_md])

        # 注意：此处使用 .then 附加在原有的 write_btn_next 和 re_review_btn 上，
        # 因为原逻辑中 write_btn_next 已经绑定了 safe_write_next，不应该覆盖原有绑定。
        # 我们用 .then 追加更新辅助组件
        def update_review_components():
            history = app.get_review_history_display()
            hub = app.get_agent_coordination_report()
            # 获取 draft_editor 的内容不太方便通过 then 直接拿，但由于我们不修改核心流，
            # 这里的 text 参数可以留空，后续可以进一步优化。
            # 这里简单起见，我们只更新没有外部依赖的内容。
            # 为了获取诊断，我们需要传入最新的草稿，这会比较复杂，因为在链式调用中。
            # 最好是通过 gradio 的 gr.State 或者直接绑定一个读取最新草稿的函数。
            # 但是最简单的方案：不直接在 .then 绑定无参数的方法，而是额外在草稿更新时更新诊断。
            return history, hub

        write_btn_next.click(
            fn=update_review_components,
            outputs=[review_iteration_history_md, agent_coordination_report_md]
        )
        
        re_review_btn.click(
            fn=update_review_components,
            outputs=[review_iteration_history_md, agent_coordination_report_md]
        )
        
        def do_kb_diagnosis(text):
            return app.get_kb_diagnostics_display(text)
            
        draft_editor.change(fn=do_kb_diagnosis, inputs=[draft_editor], outputs=[kb_diagnosis_detail_md])
        manual_edit_text.change(fn=do_kb_diagnosis, inputs=[manual_edit_text], outputs=[kb_diagnosis_detail_md])

        def update_finalize_components():
            return app.get_token_stats_display()

        review_btn_next.click(
            fn=update_finalize_components,
            outputs=[token_stats_md]
        )


        def update_bg_theme(choice):
            if choice == "经典流光 (Classic Fluid)":
                return THEME_CLASSIC_HTML
            if choice == "苹果极简 (Apple Minimal)":
                return THEME_APPLE_MINIMAL_HTML
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
