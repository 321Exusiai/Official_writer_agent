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
   ├→ 对外传播 → Q1: 深度/篇幅？
   │   ├→ 简短 → INFORMATIONAL (消息/快讯)
   │   ├→ 深度 → STRATEGIC_NARRATIVE (通讯/研学报道)
   │   └→ 场景 → INFORMATIONAL (侧记/特写)
   ├→ 内部行政 → Q1: 哪种行政文书？
   │   ├→ 通知/请示/批复/函 → ADMINISTRATIVE
   │   ├→ 纪要 → INFORMATIONAL
   │   └→ 通报 → OBJECTIVE_REPORT
   ├→ 活动记录 → Q1: 活动层级？
   │   ├→ 班级/团支/院系 → INFORMATIONAL
   │   └→ 研学/校际/重大 → STRATEGIC_NARRATIVE
   └→ 汇报总结 → Q1: 核心内容？
       ├→ 工作总结 → STRATEGIC_NARRATIVE
       ├→ 调研/事故 → OBJECTIVE_REPORT
       └→ 述职 → ADMINISTRATIVE
"""

from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional, List, Dict, Any, Tuple, Set

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

    length_hint: Optional[int] = None
    style_intensity: float = 1.0
    target_doc_types: List[str] = field(default_factory=list)

    raw_answers: Dict[str, str] = field(default_factory=dict)

    def is_complete(self) -> bool:
        if not self.writing_mode:
            return False
        return bool(self.purpose and self.primary_audience)

    def get_missing_fields(self) -> List[str]:
        missing = []
        if not self.writing_mode:
            missing.append("写作模式")
        if not self.purpose:
            missing.append("核心目的")
        if not self.primary_audience:
            missing.append("目标读者")
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
            "root": "不同类型的公文需要完全不同的写作方法论。先搞清楚要写什么，再决定怎么写。",
            "external_comm": "消息、通讯和侧记是完全不同的文体——篇幅、结构、语言都不同。选对文体比写好内容更重要。",
            "internal_admin": "行政文书有严格的行文规范——文种错了，格式和用语全都会错。",
            "activity_record": "班级活动和研学报道的写法完全不同——前者重真实记录，后者重战略叙事。",
            "report_summary": "工作总结和事故通报的写法天差地别——前者需要展示成绩，后者需要客观陈述。",
        }
        return whys.get(node_key, "不同的选择会导向完全不同的写作方法。")

    def submit_routing_choice(self, choice_index: int) -> Dict[str, Any]:
        """提交决策树选择，返回下一步或完成路由"""
        if self._routing_current_node not in DECISION_TREE:
            return {"phase": "error", "message": "路由已完成"}

        node = DECISION_TREE[self._routing_current_node]
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

        return {
            "qid": prev_q["id"],
            "question": prev_q["text"],
            "previous_answer": prev_answer,
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

    def _update_brief_from_answer(self, qid: str, answer: str):
        """根据问题ID更新简报字段"""
        field_map = {
            "sn_purpose": "purpose",
            "sn_audience": "primary_audience",
            "sn_deep_meaning": "deep_meaning",
            "sn_strategic_anchor": "strategic_anchor",
            "sn_opportunity": "opportunity_context",
            "sn_materials": "key_materials",
            "sn_differentiator": "differentiator",
            "or_subject": "purpose",
            "or_audience": "primary_audience",
            "or_data_sources": "key_materials",
            "or_core_findings": "deep_meaning",
            "ad_core_item": "purpose",
            "ad_recipient": "primary_audience",
            "ad_basis": "strategic_anchor",
            "ad_requirements": "key_materials",
            "info_5w1h": "purpose",
            "info_audience": "primary_audience",
            "info_highlight": "deep_meaning",
            "info_quotes": "key_materials",
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
            "sn_purpose": "💡 好文章的目的可以用一句话说清——'让___觉得___，从而___'。如果说不清，建议先想清楚再动笔。",
            "sn_audience": "💡 为具体的人写作。想象他/她坐在你对面，你只有30秒让他/她愿意继续读下去。",
            "sn_deep_meaning": "💡 '我们做了什么'是新闻，'这件事证明了什么'才是公文。从新闻到公文，差的不是字数，是这一层提炼。",
            "sn_strategic_anchor": "💡 任何一段行程如果说不清'为什么是这里'，那它就是脱离组织语境的孤岛。",
            "sn_opportunity": "💡 借势不是攀附，是建立有逻辑的关联。找到'更大叙事'的框架，文章就自动有了格局。",
            "sn_materials": "💡 真实感言>空泛表态，具体数据>形容词堆砌。没有硬素材——先去采访、收集，不要硬写。",
            "sn_differentiator": "💡 如果这篇文章换成别的单位署名也毫无违和感——说明你还没有找到'自己的故事'。",
            "or_subject": "💡 客观报告的第一步是界定范围——明确'要报告什么'和'不报告什么'同样重要。",
            "or_data_sources": "💡 单一信源的信息不可作为结论依据。至少两个独立来源交叉验证。",
            "or_core_findings": "💡 '加强管理''提高认识'是空话。'每周检查一次消防设备并登记'才是发现。",
            "ad_doc_type": "💡 文种错了，后面的格式、用语、行文方向全都会错。这一步不能错。",
            "ad_direction": "💡 上行文要恭敬（'妥否，请批示'），下行文可以要求（'请遵照执行'），平行文要协商（'请予支持为盼'）。",
            "ad_core_item": "💡 行政公文必须一事一文。如果想同时说两件事——写两份公文。",
            "ad_requirements": "💡 模糊的要求=无效的公文。时间、地点、责任人、完成标准——缺一不可。",
            "info_5w1h": "💡 如果一句话说不清5W1H，说明你还没搞清楚发生了什么。先去核实。",
            "info_highlight": "💡 读者只关心'这件事跟我有什么关系/有什么特别的'。找不到亮点=没有新闻价值。",
            "info_structure": "💡 如果读者只看前两段就关掉，他能知道最重要的信息吗？",
            "info_quotes": "💡 直接引语让文章'活'起来。没有引语的信息稿像没有盐的菜。",
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
            [s.strip() for s in legacy_secondary.split("；")]
            if legacy_secondary else []
        ),
    )
    return brief
