"""
主动发问模块 — 决策树分流 + 四模式专属问卷

核心设计理念：
原版的8个问题天然引导向"研学/新闻通讯"场景，对其他公文类型
（通知、请示、事故通报、简报、会议纪要等）完全失效。这告诉我们，单一的信息渠道本就存在严重的bias，再加上人的主观思考
，会出现很严重的问题。

新版解决这个bias：
1. 入口分流：先通过决策树确定写作模式
2. 模式专属问题：每种模式有自己的一套问题
3. 问题设计借鉴多来源方法论：党政机关规范、高校新闻采编规范、团学投稿规范等
4. 决策树与写作模式一一映射

分流逻辑：
  Q0: 核心目的是什么？
   ├-> 对外传播 -> Q1: 深度/篇幅？
   │   ├-> 新闻快讯 -> INFORMATIONAL (消息/快讯)
   │   ├-> 深度通讯 -> STRATEGIC_NARRATIVE (通讯/研学报道)
   │   └-> 特写侧记 -> STRATEGIC_NARRATIVE (侧记/特写)
   ├-> 内部行政 -> Q1: 行文方向？
   │   ├-> 上行文（请示/报告） -> ADMINISTRATIVE
   │   ├-> 下行文（通知/通报/批复/决定） -> ADMINISTRATIVE
   │   ├-> 平行文（函/意见/议案） -> ADMINISTRATIVE
   │   ├-> 公布性公文（公告/通告） -> ADMINISTRATIVE
   │   └-> 会议文书（纪要/决议） -> INFORMATIONAL
   ├-> 活动记录 -> Q1: 活动性质与调性？
   │   ├-> 社团招新/文艺汇演 -> YOUTH_ENGAGEMENT
   │   ├-> 班会/讲座/典礼 -> INFORMATIONAL
   │   ├-> 研学考察/社会实践 -> STRATEGIC_NARRATIVE
   │   ├-> 活动策划案 -> INFORMATIONAL
   │   └-> 活动总结 -> STRATEGIC_NARRATIVE
   └-> 汇报总结 -> Q1: 核心内容？
       ├-> 工作总结 -> STRATEGIC_NARRATIVE
       ├-> 调研报告 -> OBJECTIVE_REPORT
       ├-> 事故/问题通报 -> OBJECTIVE_REPORT
       ├-> 述职 -> ADMINISTRATIVE
       └-> 社会实践报告 -> OBJECTIVE_REPORT
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Set
import re

from ..core.writing_mode import (
    WritingMode,
    DECISION_TREE,
    navigate_tree,
    get_mode_questions,
    get_mode_profile,
    get_mode_description,
    ALL_PRINCIPLES,
)


class QuestionnairePhase(Enum):
    ROUTING = "routing"
    MODE_QUESTIONS = "mode_questions"
    COMPLETE = "complete"


@dataclass
class WritingBrief:
    """经过问卷后生成的写作简报 — 整个智能体的"战略输入" （V2.3）"""
    writing_mode: str = ""
    mode_display_name: str = ""
    subtype: str = ""

    purpose: str = ""
    primary_audience: str = ""
    secondary_audiences: List[str] = field(default_factory=list)
    deep_meaning: str = ""
    strategic_anchor: str = ""
    opportunity_context: str = ""
    key_materials: str = ""
    differentiator: str = ""

    # 保留字段：当前问卷流程未填充，供未来扩展使用
    length_hint: Optional[int] = None
    style_intensity: float = 1.0
    target_doc_types: List[str] = field(default_factory=list)

    raw_answers: Dict[str, str] = field(default_factory=dict)

    def is_complete(self) -> bool:
        if not self.writing_mode:
            return False
        return bool(self.purpose)

    def get_missing_fields(self) -> List[str]:
        missing = []
        if not self.writing_mode:
            missing.append("写作模式")
        if not self.purpose:
            missing.append("核心目的")
        return missing

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class Questionnaire:
    """
    新版交互式问卷（V3.1 操作人性化版）

    分两个阶段：
    1. ROUTING：通过决策树确定写作模式（2题）
    2. MODE_QUESTIONS：根据模式回答专属问题（6-7题）

    操作人性化：
    - 回退：输入 "back" 回退到上一题修改
    - 跳过：输入 "skip" 跳过不确定的问题
    - 上下文感知：每道题展示已填摘要，避免遗忘
    - 快捷模式：老用户可直接跳过问卷
    """

    def __init__(self):
        self.phase = QuestionnairePhase.ROUTING
        self.brief = WritingBrief()

        self._routing_path: List[int] = []
        self._routing_current_node: str = "root"
        self._routing_step: int = 0

        self._mode_question_index: int = 0
        self._mode_questions: List[Dict[str, str]] = []

        self._routing_history: List[Dict[str, Any]] = []

        self._answer_history: List[Dict[str, str]] = []
        self._skipped_questions: List[str] = []

    # ═══════════════════════════════════════════════════════════
    # ROUTING 阶段
    # ═══════════════════════════════════════════════════════════

    def get_routing_question(self) -> Optional[Dict[str, Any]]:
        """获取当前决策树节点的问题"""
        if self._routing_current_node not in DECISION_TREE:
            return None
        node = DECISION_TREE[self._routing_current_node]
        return {
            "phase": "routing",
            "step": self._routing_step + 1,
            "question": node["question"],
            "options": [
                {
                    "index": i,
                    "label": opt["label"],
                    "description": opt["description"],
                }
                for i, opt in enumerate(node["options"])
            ],
            "why_ask": self._get_routing_why(self._routing_current_node),
        }

    def _get_routing_why(self, node_key: str) -> str:
        whys = {
            "root": "写作没有万能模板，写给领导看和写给00后新生看，套路完全不同。先帮我锚定你的目标，我们再决定用哪套笔法。",
            "external_comm": "消息负责'快'，通讯负责'深'，特写负责'动人'。选对文体，比憋字数重要得多。",
            "internal_admin": "体制内的行政文书讲究'规矩'。选错文种，写得再文采飞扬也会被直接打回重写。",
            "activity_record": "办个草坪音乐节和办一场严肃的学术讲座，文风能一样吗？告诉我活动的真实调性，我来调整网感。",
            "report_summary": "总结要找亮点，通报要挖病根。千万别把检讨书写成了表扬信。",
        }
        return whys.get(node_key, "不同的场景需要完全不同的沟通策略，告诉我你在哪。")

    def submit_routing_choice(self, choice_index: int) -> Dict[str, Any]:
        """提交决策树选择，返回下一步或完成路由"""
        if self._routing_current_node not in DECISION_TREE:
            return {"phase": "error", "message": "路由已完成"}

        node = DECISION_TREE[self._routing_current_node]
        if choice_index < 0 or choice_index >= len(node["options"]):
            return {"phase": "error", "message": f"选择编号超出范围（0-{len(node['options'])-1}）"}
        option = node["options"][choice_index]

        self._routing_history.append({
            "node": self._routing_current_node,
            "choice": choice_index,
            "label": option["label"],
        })
        self._routing_path.append(choice_index)
        self._routing_step += 1

        if "mode" in option:
            mode = option["mode"]
            subtype = option.get("subtype", "")
            path_desc = " → ".join(h["label"] for h in self._routing_history)

            self.brief.writing_mode = mode.value
            self.brief.subtype = subtype
            self.brief.mode_display_name = path_desc

            # 修复 N10：从路由选项填充保留字段（目标文种/期望篇幅）
            self._fill_reserved_fields(option, subtype)

            profile = get_mode_profile(mode)
            self._mode_questions = get_mode_questions(mode)
            self.phase = QuestionnairePhase.MODE_QUESTIONS
            self._mode_question_index = 0

            return {
                "phase": "routing_complete",
                "mode": mode.value,
                "mode_name": profile.name,
                "mode_description": get_mode_description(mode),
                "subtype": subtype,
                "path": path_desc,
                "total_mode_questions": len(self._mode_questions),
            }

        next_key = option.get("next")
        if next_key and next_key in DECISION_TREE:
            self._routing_current_node = next_key
            return {
                "phase": "routing",
                "next_question": self.get_routing_question(),
            }

        return {"phase": "error", "message": "无法确定下一步"}

    # ═══════════════════════════════════════════════════════════
    # MODE QUESTIONS 阶段
    # ═══════════════════════════════════════════════════════════

    def get_current_mode_question(self) -> Optional[Dict[str, Any]]:
        """获取当前模式专属问题"""
        if self.phase != QuestionnairePhase.MODE_QUESTIONS:
            return None
        if self._mode_question_index >= len(self._mode_questions):
            return None

        q = self._mode_questions[self._mode_question_index]
        return {
            "phase": "mode_questions",
            "index": self._mode_question_index + 1,
            "total": len(self._mode_questions),
            "question": q["text"],
            "why_ask": q["why_ask"],
            "hint": q.get("hint", ""),
            "id": q["id"],
        }

    def submit_mode_answer(self, answer: str) -> bool:
        """提交模式专属问题的答案，返回是否还有下一个问题"""
        if self.phase != QuestionnairePhase.MODE_QUESTIONS:
            return False
        if self._mode_question_index >= len(self._mode_questions):
            return False

        q = self._mode_questions[self._mode_question_index]
        qid = q["id"]
        self.brief.raw_answers[qid] = answer
        self._answer_history.append({"qid": qid, "answer": answer})

        self._update_brief_from_answer(qid, answer)
        self._mode_question_index += 1

        return self._mode_question_index < len(self._mode_questions)

    def go_back(self) -> Optional[Dict[str, Any]]:
        """回退到上一题"""
        if self.phase != QuestionnairePhase.MODE_QUESTIONS:
            return None
        if self._mode_question_index <= 0:
            return None

        self._mode_question_index -= 1
        prev_q = self._mode_questions[self._mode_question_index]
        prev_answer = self.brief.raw_answers.get(prev_q["id"], "")

        if self._answer_history:
            self._answer_history.pop()

        return {
            "qid": prev_q["id"],
            "question": prev_q["text"],
            "previous_answer": prev_answer,
            "why_ask": prev_q.get("why_ask", ""),
            "hint": prev_q.get("hint", ""),
            "index": self._mode_question_index + 1,
            "total": len(self._mode_questions),
        }

    def skip_current(self) -> bool:
        """跳过当前问题"""
        if self.phase != QuestionnairePhase.MODE_QUESTIONS:
            return False
        if self._mode_question_index >= len(self._mode_questions):
            return False

        q = self._mode_questions[self._mode_question_index]
        self._skipped_questions.append(q["id"])
        self._mode_question_index += 1

        return self._mode_question_index < len(self._mode_questions)

    def get_filled_summary(self) -> str:
        """获取已填信息摘要（上下文感知）"""
        if not self.brief.writing_mode:
            return "（尚未确定写作模式）"

        lines = ["【已填信息】"]
        if self.brief.purpose:
            lines.append(f"  目的：{self.brief.purpose[:40]}...")
        if self.brief.primary_audience:
            lines.append(f"  读者：{self.brief.primary_audience}")
        if self.brief.deep_meaning:
            lines.append(f"  深意：{self.brief.deep_meaning[:40]}...")
        if self.brief.strategic_anchor:
            lines.append(f"  关联：{self.brief.strategic_anchor[:40]}...")
        if self.brief.opportunity_context:
            lines.append(f"  背景：{self.brief.opportunity_context[:40]}...")
        if self.brief.key_materials:
            lines.append(f"  素材：{self.brief.key_materials[:40]}...")
        if self.brief.differentiator:
            lines.append(f"  差异：{self.brief.differentiator[:40]}...")
        if not lines[1:]:
            lines.append("  （暂无，这是第一题）")
        return "\n".join(lines)

    def _fill_reserved_fields(self, option: Dict[str, Any], subtype: str):
        """填充 WritingBrief 保留字段（目标文种/期望篇幅，修复 N10 问卷路径不填充）"""
        brief = self.brief
        # 目标文种：subtype 直接匹配 DocumentType 枚举值时填充
        if not brief.target_doc_types and subtype:
            try:
                from ..core.document_type import DocumentType
                dt = DocumentType(subtype)
                brief.target_doc_types = [dt.value]
            except (ValueError, TypeError):
                pass
        # 期望篇幅：从路由选项标签解析（如"深度通讯——全景展现（1500-3000字）"）
        if brief.length_hint is None:
            m = re.search(r'(\d+)\s*[-~]\s*(\d+)\s*字', option.get("label", ""))
            if m:
                low, high = int(m.group(1)), int(m.group(2))
                brief.length_hint = (low + high) // 2

    def _update_brief_from_answer(self, qid: str, answer: str):
        """根据问题ID更新简报字段"""
        field_map = {
            "sn_vision": "strategic_anchor",
            "sn_logic": "deep_meaning",
            "sn_people": "key_materials",
            "sn_value": "differentiator",
            "sn_direction": "purpose",
            "or_problem": "purpose",
            "or_cause": "key_materials",
            "or_solution": "differentiator",
            "or_method": "deep_meaning",
            "ad_basis": "strategic_anchor",
            "ad_core": "purpose",
            "ad_route": "primary_audience",
            "ad_doc_type": "deep_meaning",
            "info_5w1h": "purpose",
            "info_lead": "deep_meaning",
            "info_quotes": "key_materials",
            "info_value": "differentiator",
            "info_plan": "strategic_anchor",
            "ye_vibe": "deep_meaning",
            "ye_identity": "differentiator",
            "ye_interaction": "key_materials",
            "ye_cta": "purpose",
            "ye_value": "strategic_anchor",
        }
        field_name = field_map.get(qid)
        if field_name:
            setattr(self.brief, field_name, answer)

    # ═══════════════════════════════════════════════════════════
    # 公用接口
    # ═══════════════════════════════════════════════════════════

    def is_complete(self) -> bool:
        return self.phase == QuestionnairePhase.COMPLETE or (
            self.phase == QuestionnairePhase.MODE_QUESTIONS
            and self._mode_question_index >= len(self._mode_questions)
        )

    def finish(self) -> WritingBrief:
        """标记问卷完成，返回简报"""
        self.phase = QuestionnairePhase.COMPLETE
        return self.brief

    def get_brief(self) -> WritingBrief:
        return self.brief

    def get_teaching_note(self) -> str:
        """根据当前问题生成教学提示"""
        notes = {
            "sn_vision": "💡 如果你只写了'办了个活动'，这篇文章就废了。想想这个活动怎么跟'大局'扯上关系。",
            "sn_logic": "💡 报喜不报忧那是流水账。告诉我你们当时有多惨、有多难，解决的过程才精彩。",
            "sn_people": "💡 别用'大家纷纷表示'这种套话敷衍我。去抓一个真实的眼神，或者一句带泥土味的抱怨。",
            "sn_value": "💡 如果这段经验换个学校也能直接套用，那它就毫无价值。找不同！",
            "or_problem": "💡 客观报告不是写小说。收起所有情绪，像外科医生一样精准描述'病灶'在哪。",
            "or_cause": "💡 别用'也许是'、'可能是'。用数据说话，或者告诉我谁为这个结论负责。",
            "or_solution": "💡 '加强领导'这种废话就别提了。如果你是执行者，你希望看到什么具体的指令？",
            "ad_basis": "💡 体制内不打无准备之仗。每一份红头文件，都要找到它生长的'土壤'和'根'。",
            "ad_core": "💡 如果你想在一份请示里要钱又要人，大概率会被打回来。一文一事是铁律。",
            "ad_route": "💡 给上级看要'请示'，给平级看要'商榷'。搞错对象，等于把信投错了邮筒。",
            "info_5w1h": "💡 别觉得5W1H基础。多少人写了800字，读者连活动在哪天办的都没找到。",
            "info_lead": "💡 读者很忙，只给你3秒钟。第一句话如果抓不住眼球，后面写出花也没人看。",
            "info_quotes": "💡 没有引语的新闻就是干巴巴的骨架。去找原话，带着当事人的体温。",
            "ye_vibe": "💡 不要写'充满激情与活力'这种AI套话！告诉我现场有谁在尖叫？有谁笑得直不起腰？",
            "ye_identity": "💡 别装老成。用只有你们社团懂的'黑话'或者内部梗，这叫圈层认同感。",
            "ye_interaction": "💡 完美的活动多无聊啊，一点小意外和大家的随机反应，才是推文里最抓人的点。",
            "ye_cta": "💡 别让读者看完就跑了。想让他们加群？留言？还是点赞？直接大胆地要求他们！",
            "sn_direction": "💡 新闻不是“有闻必录”。你选什么、不选什么、怎么编排，都在传递立场。党性和人民性是统一的，不是对立的。",
            "or_method": "💡 “没有调查就没有发言权”。如果你说不出调研方法，结论就是空中楼阁。告诉我你走访了谁、发了多少问卷、数据从哪来。",
            "ad_doc_type": "💡 请示要钱要批文，报告只汇报情况。把请示事项塞进报告里，是公文写作最常见的硬伤，必被退回。",
            "info_value": "💡 不是所有事都值得写新闻。时新性、重要性、接近性、显著性、趣味性五要素都不强的事，硬写出来也没人看。",
            "info_plan": "💡 策划案不是写散文。背景、主题、时间、地点、对象、内容、预算、安全预案——八要素缺一不可。主题要对仗，预算要明细，安全预案要有应急联络人。",
            "ye_value": "💡 纯娱乐的社团推文没有灵魂。好玩是外壳，育人属性才是团属媒体的立身之本。想想这篇推文的“思想落点”在哪。",
        }

        if self.phase == QuestionnairePhase.MODE_QUESTIONS:
            if self._mode_question_index > 0:
                prev_q = self._mode_questions[self._mode_question_index - 1]
                return notes.get(prev_q["id"], "")
        return ""

    def get_progress(self) -> Tuple[int, int, str]:
        """获取当前进度"""
        if self.phase == QuestionnairePhase.ROUTING:
            return (self._routing_step, 2, "路由分流")
        elif self.phase == QuestionnairePhase.MODE_QUESTIONS:
            return (
                self._mode_question_index,
                len(self._mode_questions),
                "模式专属问题",
            )
        return (0, 0, "已完成")

    def generate_brief_summary(self) -> str:
        """生成写作简报摘要"""
        if not self.brief.writing_mode:
            return "⚠️ 请先完成路由分流。"

        mode = WritingMode(self.brief.writing_mode)
        profile = get_mode_profile(mode)

        summary = "═══════════════════════════════════════════\n"
        summary += "  写 作 简 报\n"
        summary += "═══════════════════════════════════════════\n\n"

        summary += f"【写作模式】{profile.name}\n"
        summary += f"  路径：{self.brief.mode_display_name}\n"
        summary += f"  核心理念：{profile.tagline[:80]}...\n\n"

        if self.brief.purpose:
            summary += f"【核心事项/目的】\n{self.brief.purpose}\n\n"

        if self.brief.primary_audience:
            summary += f"【目标读者】\n{self.brief.primary_audience}\n\n"

        if self.brief.deep_meaning:
            summary += f"【深层含义/核心发现】\n{self.brief.deep_meaning}\n\n"

        if self.brief.strategic_anchor:
            summary += f"【战略关联/依据】\n{self.brief.strategic_anchor}\n\n"

        if self.brief.opportunity_context:
            summary += f"【借势机会/背景】\n{self.brief.opportunity_context}\n\n"

        if self.brief.key_materials:
            summary += f"【核心素材/数据】\n{self.brief.key_materials}\n\n"

        if self.brief.differentiator:
            summary += f"【差异化视角】\n{self.brief.differentiator}\n\n"

        summary += f"【适用写作原则】\n"
        for i, p in enumerate(profile.principles, 1):
            summary += f"  {i}. {p['name']}\n"

        summary += "═══════════════════════════════════════════\n"
        return summary

    # ═══════════════════════════════════════════════════════════
    # 兼容旧版接口（直接注入简报，跳过问卷）
    # ═══════════════════════════════════════════════════════════

    def skip_questionnaire(
        self,
        mode: WritingMode,
        purpose: str = "",
        primary_audience: str = "",
        **kwargs,
    ) -> WritingBrief:
        """跳过问卷，直接注入写作简报（兼容旧版API）"""
        self.brief.writing_mode = mode.value
        self.brief.mode_display_name = ALL_PRINCIPLES[mode].name
        self.brief.purpose = purpose
        self.brief.primary_audience = primary_audience
        self.brief.deep_meaning = kwargs.get("deep_meaning", "")
        self.brief.strategic_anchor = kwargs.get("strategic_anchor", "")
        self.brief.opportunity_context = kwargs.get("opportunity_context", "")
        self.brief.key_materials = kwargs.get("key_materials", "")
        self.brief.differentiator = kwargs.get("differentiator", "")
        self.brief.secondary_audiences = kwargs.get("secondary_audiences", [])
        self.phase = QuestionnairePhase.COMPLETE
        return self.brief


# ═══════════════════════════════════════════════════════════════
# 便捷函数
# ═══════════════════════════════════════════════════════════════

def create_brief_from_legacy_data(
    legacy_purpose: str = "",
    legacy_audience: str = "",
    legacy_deep_meaning: str = "",
    legacy_anchor: str = "",
    legacy_materials: str = "",
    legacy_differentiator: str = "",
    legacy_opportunity: str = "",
    legacy_secondary: str = "",
) -> WritingBrief:
    """
    从旧版数据创建新版简报
    旧版数据默认映射到 STRATEGIC_NARRATIVE 模式
    """
    brief = WritingBrief(
        writing_mode=WritingMode.STRATEGIC_NARRATIVE.value,
        mode_display_name="战略叙事模式（旧版兼容）",
        purpose=legacy_purpose,
        primary_audience=legacy_audience,
        deep_meaning=legacy_deep_meaning,
        strategic_anchor=legacy_anchor,
        key_materials=legacy_materials,
        differentiator=legacy_differentiator,
        opportunity_context=legacy_opportunity,
        secondary_audiences=(
            [s.strip() for s in re.split(r'[；;，,]', legacy_secondary) if s.strip()]
            if legacy_secondary else []
        ),
    )
    return brief
