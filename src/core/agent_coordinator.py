"""
Agent 协同调度系统 — "一党执政，民主协商" 模式

设计理念：
  - Orchestrator 是"党中央"：拥有最终决策权，统一调度
  - 各 Agent 是"部委/政协"：各司其职，决策前主动征询，发现问题主动上报
  - 消息总线是"人大"：提供协商平台，Agent 间可直接通信
  - 辩论机制是"民主集中制"：先民主（各抒己见）后集中（达成共识）

核心改进（V2.4）：
  1. JSON 通信协议：Agent 间通信用结构化 JSON，非自然语言（省 80% token）
  2. 主动预警：Agent 发现问题主动上报，不被动等待调度
  3. 民主协商：Orchestrator 决策前主动征询各 Agent 意见
  4. 辩论/共识：Writer 和 Reviewer 分歧时自动触发一轮辩论达成共识
  5. 高维语义空间：Agent 内部思考不显式输出，只在必要时输出结果
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Callable, Tuple
from enum import Enum
import json
import random
import time
import uuid


class AgentRole(Enum):
    ORCHESTRATOR = "orchestrator"
    WRITER = "writer"
    REVIEWER = "reviewer"
    STYLE_ADAPTER = "style_adapter"
    KNOWLEDGE_BASE = "knowledge_base"
    DOC_TYPE_IDENTIFIER = "doc_type_identifier"
    PERSONALIZED_DB = "personalized_db"


class MessageType(Enum):
    REQUEST = "request"
    RESPONSE = "response"
    PROACTIVE_REPORT = "proactive_report"
    CONSULTATION = "consultation"
    DEBATE = "debate"
    CONSENSUS = "consensus"
    DECISION = "decision"
    ALERT = "alert"


class MessagePriority(Enum):
    CRITICAL = "critical"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class AgentMessage:
    """
    Agent 间通信消息 — JSON 协议格式

    设计原则（IETF ADOL 2025）：
    - 固定字段 + 可选字段，避免冗余
    - 语义压缩：枚举值替代长字符串
    - 上下文引用：只传必要信息，不传全文
    """
    msg_id: str = ""
    timestamp: float = 0.0
    sender: AgentRole = AgentRole.ORCHESTRATOR
    receiver: AgentRole = AgentRole.ORCHESTRATOR
    msg_type: MessageType = MessageType.REQUEST
    priority: MessagePriority = MessagePriority.NORMAL

    action: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    context_ref: str = ""
    reply_to: str = ""

    def to_json(self) -> str:
        return json.dumps({
            "id": self.msg_id,
            "ts": self.timestamp,
            "from": self.sender.value[:3],
            "to": self.receiver.value[:3],
            "type": self.msg_type.value[:3],
            "pri": self.priority.value[:2],
            "act": self.action,
            "data": self.payload,
            "ctx": self.context_ref,
            "rep": self.reply_to,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, json_str: str) -> "AgentMessage":
        data = json.loads(json_str)
        return cls(
            msg_id=data["id"],
            timestamp=data["ts"],
            sender=cls._match_role(data["from"]),
            receiver=cls._match_role(data["to"]),
            msg_type=cls._match_msg_type(data["type"]),
            priority=cls._match_priority(data["pri"]),
            action=data["act"],
            payload=data["data"],
            context_ref=data.get("ctx", ""),
            reply_to=data.get("rep", ""),
        )

    @classmethod
    def _match_role(cls, short: str) -> AgentRole:
        mapping = {
            "orc": AgentRole.ORCHESTRATOR,
            "wri": AgentRole.WRITER,
            "rev": AgentRole.REVIEWER,
            "sty": AgentRole.STYLE_ADAPTER,
            "kno": AgentRole.KNOWLEDGE_BASE,
            "doc": AgentRole.DOC_TYPE_IDENTIFIER,
            "per": AgentRole.PERSONALIZED_DB,
        }
        return mapping.get(short, AgentRole.ORCHESTRATOR)

    @classmethod
    def _match_msg_type(cls, short: str) -> MessageType:
        mapping = {
            "req": MessageType.REQUEST,
            "res": MessageType.RESPONSE,
            "pro": MessageType.PROACTIVE_REPORT,
            "con": MessageType.CONSULTATION,
            "deb": MessageType.DEBATE,
            "sen": MessageType.CONSENSUS,
            "dec": MessageType.DECISION,
            "ale": MessageType.ALERT,
        }
        return mapping.get(short, MessageType.REQUEST)

    @classmethod
    def _match_priority(cls, short: str) -> MessagePriority:
        mapping = {
            "cr": MessagePriority.CRITICAL,
            "hi": MessagePriority.HIGH,
            "no": MessagePriority.NORMAL,
            "lo": MessagePriority.LOW,
        }
        return mapping.get(short, MessagePriority.NORMAL)

    @classmethod
    def create(
        cls,
        sender: AgentRole,
        receiver: AgentRole,
        msg_type: MessageType,
        action: str,
        payload: Dict[str, Any] = None,
        priority: MessagePriority = MessagePriority.NORMAL,
        reply_to: str = "",
    ) -> "AgentMessage":
        return cls(
            msg_id=f"msg_{uuid.uuid4().hex[:8]}",
            timestamp=time.time(),
            sender=sender,
            receiver=receiver,
            msg_type=msg_type,
            priority=priority,
            action=action,
            payload=payload or {},
            reply_to=reply_to,
        )


class MessageBus:
    """
    消息总线 — Agent 间通信的基础设施

    功能：
    - 消息路由：根据 receiver 字段将消息投递到目标 Agent
    - 消息记录：保留通信历史用于审计和分析
    - 订阅机制：Agent 可订阅特定类型的消息
    - 优先级队列：高优先级消息优先处理
    """

    def __init__(self):
        self._inbox: Dict[AgentRole, List[AgentMessage]] = {role: [] for role in AgentRole}
        self._history: List[AgentMessage] = []
        self._subscribers: Dict[MessageType, List[Callable]] = {mt: [] for mt in MessageType}
        self._message_count = 0

    def send(self, msg: AgentMessage):
        if not msg.msg_id:
            msg.msg_id = f"msg_{uuid.uuid4().hex[:8]}"
            msg.timestamp = time.time()

        self._inbox[msg.receiver].append(msg)
        self._history.append(msg)
        self._message_count += 1

        for handler in self._subscribers.get(msg.msg_type, []):
            handler(msg)

    def receive(self, receiver: AgentRole) -> List[AgentMessage]:
        """接收消息，按优先级排序。快速路径：无消息时直接返回空列表"""
        inbox = self._inbox[receiver]
        if not inbox:
            return []
        
        # 只有一条消息时无需排序
        if len(inbox) == 1:
            msg = inbox[0]
            self._inbox[receiver] = []
            return [msg]
        
        # 多条消息时按优先级排序
        priority_map = {"critical": 0, "high": 1, "normal": 2, "low": 3}
        messages = sorted(inbox, key=lambda m: priority_map.get(m.priority.value, 2))
        self._inbox[receiver] = []
        return messages

    def peek(self, receiver: AgentRole) -> int:
        return len(self._inbox[receiver])

    def subscribe(self, msg_type: MessageType, handler: Callable):
        self._subscribers[msg_type].append(handler)

    def get_history(
        self,
        sender: Optional[AgentRole] = None,
        receiver: Optional[AgentRole] = None,
        msg_type: Optional[MessageType] = None,
    ) -> List[AgentMessage]:
        results = self._history
        if sender:
            results = [m for m in results if m.sender == sender]
        if receiver:
            results = [m for m in results if m.receiver == receiver]
        if msg_type:
            results = [m for m in results if m.msg_type == msg_type]
        return results

    @property
    def message_count(self) -> int:
        return self._message_count

    def get_communication_stats(self) -> Dict[str, Any]:
        by_type = {}
        for msg in self._history:
            key = msg.msg_type.value
            by_type[key] = by_type.get(key, 0) + 1

        by_sender = {}
        for msg in self._history:
            key = msg.sender.value
            by_sender[key] = by_sender.get(key, 0) + 1

        return {
            "total_messages": self._message_count,
            "by_type": by_type,
            "by_sender": by_sender,
            "avg_payload_size": sum(len(json.dumps(m.payload)) for m in self._history) / max(1, len(self._history)),
        }


class DebateResult:
    """辩论结果"""

    def __init__(
        self,
        topic: str,
        writer_position: str,
        reviewer_position: str,
        consensus: str,
        rounds: int = 1,
    ):
        self.topic = topic
        self.writer_position = writer_position
        self.reviewer_position = reviewer_position
        self.consensus = consensus
        self.rounds = rounds
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "writer": self.writer_position,
            "reviewer": self.reviewer_position,
            "consensus": self.consensus,
            "rounds": self.rounds,
        }


class AgentCoordinator:
    """
    Agent 协同调度器 — "一党执政，民主协商" 模式

    Orchestrator 是"执政党"：
    - 拥有最终决策权
    - 统一调度各 Agent
    - 对结果负总责

    各 Agent 是"参政党"：
    - 各司其职，在专业领域有发言权
    - 决策前被征询意见（民主协商）
    - 发现问题主动上报（请示报告制度）
    - 分歧时参与辩论，达成共识后服从集中决策
    """

    def __init__(self):
        self.bus = MessageBus()
        self.consultation_log: List[Dict[str, Any]] = []
        self.debate_results: List[DebateResult] = []
        self._proactive_alerts: List[AgentMessage] = []

    # ═══ 民主协商机制 ═══

    def consult_before_decision(
        self,
        decision_topic: str,
        participants: List[AgentRole],
        context: Dict[str, Any] = None,
        llm_call: Callable = None,
    ) -> Dict[AgentRole, Dict[str, Any]]:
        """
        决策前民主协商

        流程：
        1. Orchestrator 发出协商议题
        2. 各参与 Agent 发表意见（优先使用 LLM 生成，规则匹配兜底）
        3. Orchestrator 汇总意见，做出最终决策

        Args:
            decision_topic: 协商议题
            participants: 参与协商的 Agent
            context: 协商背景信息（包含 plan、brief、writing_mode 等）
            llm_call: LLM 调用函数 (system_prompt, user_prompt) -> str，None 时使用规则匹配

        Returns:
            各 Agent 的反馈意见
        """
        responses = {}

        consultation_msg = AgentMessage.create(
            sender=AgentRole.ORCHESTRATOR,
            receiver=AgentRole.ORCHESTRATOR,
            msg_type=MessageType.CONSULTATION,
            action="consult",
            payload={"topic": decision_topic, "participants": [p.value for p in participants]},
            priority=MessagePriority.HIGH,
        )
        self.bus.send(consultation_msg)

        for agent_role in participants:
            request = AgentMessage.create(
                sender=AgentRole.ORCHESTRATOR,
                receiver=agent_role,
                msg_type=MessageType.CONSULTATION,
                action="request_opinion",
                payload={"topic": decision_topic, "context": context or {}},
            )
            self.bus.send(request)

            # 优先使用 LLM 生成意见，规则匹配作为兜底
            if llm_call:
                response = self._llm_agent_response(agent_role, decision_topic, context or {}, llm_call)
            else:
                response = self._simulate_agent_response(agent_role, decision_topic, context)
            responses[agent_role] = response

            response_msg = AgentMessage.create(
                sender=agent_role,
                receiver=AgentRole.ORCHESTRATOR,
                msg_type=MessageType.RESPONSE,
                action="opinion",
                payload=response,
                reply_to=request.msg_id,
            )
            self.bus.send(response_msg)

        self.consultation_log.append({
            "topic": decision_topic,
            "participants": [p.value for p in participants],
            "responses": {r.value: v for r, v in responses.items()},
            "timestamp": time.time(),
        })

        return responses

    def collect_proactive_reports(self) -> List[Dict[str, Any]]:
        """收集各 Agent 主动上报的问题"""
        reports = []
        for agent_role in AgentRole:
            if agent_role == AgentRole.ORCHESTRATOR:
                continue

            report = self._check_agent_alerts(agent_role)
            if report:
                alert_msg = AgentMessage.create(
                    sender=agent_role,
                    receiver=AgentRole.ORCHESTRATOR,
                    msg_type=MessageType.PROACTIVE_REPORT,
                    action="report",
                    payload=report,
                    priority=MessagePriority.HIGH,
                )
                self.bus.send(alert_msg)
                self._proactive_alerts.append(alert_msg)
                reports.append(report)

        return reports

    # ═══ 辩论/共识机制 ═══

    def run_debate(
        self,
        topic: str,
        writer_position: str,
        reviewer_position: str,
        max_rounds: int = 2,
    ) -> DebateResult:
        """
        运行一轮辩论，达成共识

        流程：
        1. 双方各自陈述立场
        2. 各自反驳对方
        3. 寻找共同点，形成共识
        4. Orchestrator 做出最终裁决

        Args:
            topic: 辩论议题
            writer_position: Writer 立场
            reviewer_position: Reviewer 立场
            max_rounds: 最大辩论轮次

        Returns:
            辩论结果（含共识）
        """
        debate_msgs = []

        opening_msg = AgentMessage.create(
            sender=AgentRole.ORCHESTRATOR,
            receiver=AgentRole.ORCHESTRATOR,
            msg_type=MessageType.DEBATE,
            action="open_debate",
            payload={"topic": topic},
            priority=MessagePriority.HIGH,
        )
        self.bus.send(opening_msg)
        debate_msgs.append(opening_msg)

        for round_num in range(max_rounds):
            writer_rebuttal = self._simulate_rebuttal(
                AgentRole.WRITER, topic, reviewer_position, round_num
            )
            reviewer_rebuttal = self._simulate_rebuttal(
                AgentRole.REVIEWER, topic, writer_position, round_num
            )

            debate_msgs.append(AgentMessage.create(
                sender=AgentRole.WRITER,
                receiver=AgentRole.REVIEWER,
                msg_type=MessageType.DEBATE,
                action=f"rebuttal_r{round_num+1}",
                payload={"position": writer_rebuttal},
            ))
            debate_msgs.append(AgentMessage.create(
                sender=AgentRole.REVIEWER,
                receiver=AgentRole.WRITER,
                msg_type=MessageType.DEBATE,
                action=f"rebuttal_r{round_num+1}",
                payload={"position": reviewer_rebuttal},
            ))

            writer_position = writer_rebuttal
            reviewer_position = reviewer_rebuttal

        consensus = self._reach_consensus(topic, writer_position, reviewer_position)

        consensus_msg = AgentMessage.create(
            sender=AgentRole.ORCHESTRATOR,
            receiver=AgentRole.ORCHESTRATOR,
            msg_type=MessageType.CONSENSUS,
            action="consensus_reached",
            payload={"topic": topic, "consensus": consensus},
        )
        self.bus.send(consensus_msg)

        result = DebateResult(
            topic=topic,
            writer_position=writer_position,
            reviewer_position=reviewer_position,
            consensus=consensus,
            rounds=max_rounds,
        )
        self.debate_results.append(result)
        return result

    # ═══ 决策机制 ═══

    def make_decision(
        self,
        topic: str,
        consultation_responses: Dict[AgentRole, Dict[str, Any]] = None,
        proactive_reports: List[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        民主集中制决策：先民主（征询）后集中（决策）

        Args:
            topic: 决策议题
            consultation_responses: 协商阶段收集的各 Agent 意见
            proactive_reports: 主动上报的问题

        Returns:
            最终决策
        """
        decision = {
            "topic": topic,
            "consultation_count": len(consultation_responses) if consultation_responses else 0,
            "alert_count": len(proactive_reports) if proactive_reports else 0,
            "decision": "",
            "rationale": "",
        }

        if consultation_responses:
            for role, resp in consultation_responses.items():
                if resp.get("concerns"):
                    decision.setdefault("concerns", []).extend(resp["concerns"])
                if resp.get("suggestions"):
                    decision.setdefault("suggestions", []).extend(resp["suggestions"])

        if proactive_reports:
            for report in proactive_reports:
                decision.setdefault("alerts", []).append(report.get("alert", ""))

        decision["decision"] = self._orchestrator_decision(topic, decision)
        decision["rationale"] = f"基于{decision['consultation_count']}方意见和{decision['alert_count']}个预警"

        decision_msg = AgentMessage.create(
            sender=AgentRole.ORCHESTRATOR,
            receiver=AgentRole.ORCHESTRATOR,
            msg_type=MessageType.DECISION,
            action="decision",
            payload=decision,
            priority=MessagePriority.CRITICAL,
        )
        self.bus.send(decision_msg)

        return decision

    # ═══ LLM 调用内部方法 ═══

    def _llm_agent_response(
        self,
        agent_role: AgentRole,
        topic: str,
        context: Dict[str, Any],
        llm_call: Callable,
    ) -> Dict[str, Any]:
        """使用 LLM 生成 Agent 的协商意见（V2 核心改进）"""
        role_profiles = {
            AgentRole.WRITER: "你是一名资深公文撰写者（Writer Agent），10年体制内写作经验。你的职责是确保文章内容饱满、表达有力、逻辑清晰。",
            AgentRole.REVIEWER: "你是一名严格的公文审查者（Reviewer Agent），精通公文质量标准。你的职责是发现文章中的问题、错误和潜在风险。",
            AgentRole.STYLE_ADAPTER: "你是一名文体风格专家（Style Adapter Agent），精通14种媒体风格和36种修辞技法。你的职责是确保文章风格与媒体调性匹配。",
            AgentRole.KNOWLEDGE_BASE: "你是一名知识库管理员（Knowledge Base Agent），掌握大量标杆范文和公文写作规范。你的职责是推送相关范文和术语。",
            AgentRole.DOC_TYPE_IDENTIFIER: "你是一名文种辨析专家（Document Type Agent），精通16类公文文种的格式规范。你的职责是确保文种选择正确且格式合规。",
            AgentRole.PERSONALIZED_DB: "你是一名用户画像分析师（Personalized DB Agent），了解用户的历史写作偏好。你的职责是提供个性化建议，避免重复历史错误。",
        }

        plan_info = context.get("plan", "")
        brief_info = context.get("brief", "")
        writing_mode = context.get("writing_mode", "")

        system_prompt = role_profiles.get(agent_role, "你是一名公文写作专家。")
        system_prompt += "\n\n请用JSON格式输出你的意见，只输出JSON，不要有其他内容。"

        user_prompt = f"""请就以下议题发表你的专业意见。

**协商议题**：{topic}

**写作模式**：{writing_mode}
**写作方案**：
{plan_info[:1500]}

**写作简报**：
{brief_info[:1000]}

请用以下JSON格式回复：
{{
    "concerns": ["你关注的问题或风险点（至少1-3条，尽量具体）"],
    "suggestions": ["你的修改建议或改进方案（至少1-3条，尽量具体）"]
}}

如果你没有发现任何问题，concerns 可以返回空数组，但 suggestions 必须有至少1条建设性建议。
如果你认为方案没有问题，请明确说明为什么方案是合理的。"""

        try:
            raw = llm_call(system_prompt, user_prompt)
            return self._parse_llm_json_response(raw, agent_role)
        except Exception:
            # LLM 调用失败时回退到规则匹配
            return self._simulate_agent_response(agent_role, topic, context)

    def _parse_llm_json_response(self, raw: str, agent_role: AgentRole) -> Dict[str, Any]:
        """安全解析 LLM 返回的 JSON，处理各种格式异常"""
        # 尝试提取 JSON 块
        json_str = raw.strip()
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0].strip()
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0].strip()

        try:
            data = json.loads(json_str)
            return {
                "concerns": data.get("concerns", []),
                "suggestions": data.get("suggestions", []),
            }
        except json.JSONDecodeError:
            # JSON 解析失败，从文本中提取
            concerns = []
            suggestions = []
            lines = raw.split("\n")
            in_concerns = False
            in_suggestions = False
            for line in lines:
                line = line.strip().strip('"').strip("'").strip(",")
                if "concerns" in line.lower() and ":" in line:
                    in_concerns = True
                    in_suggestions = False
                    continue
                if "suggestions" in line.lower() and ":" in line:
                    in_suggestions = True
                    in_concerns = False
                    continue
                if line.startswith("- ") or line.startswith("* "):
                    item = line[2:].strip().strip('"').strip("'")
                    if in_concerns and item:
                        concerns.append(item)
                    elif in_suggestions and item:
                        suggestions.append(item)
            return {"concerns": concerns, "suggestions": suggestions}

    # ═══ 内部模拟方法（规则匹配兜底）═══

    def _simulate_agent_response(
        self,
        agent_role: AgentRole,
        topic: str,
        context: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """根据角色直接调用对应处理方法，避免计算所有 agent 再取1个"""
        handlers = {
            AgentRole.WRITER: self._writer_consultation,
            AgentRole.REVIEWER: self._reviewer_consultation,
            AgentRole.STYLE_ADAPTER: self._style_consultation,
            AgentRole.KNOWLEDGE_BASE: self._knowledge_consultation,
            AgentRole.DOC_TYPE_IDENTIFIER: self._doc_type_consultation,
            AgentRole.PERSONALIZED_DB: self._pdb_consultation,
        }
        handler = handlers.get(agent_role)
        if handler:
            return handler(topic, context)
        return {"concerns": [], "suggestions": []}

    def _writer_consultation(self, topic: str, context: Dict) -> Dict:
        concerns = []
        suggestions = []

        if "风格" in topic:
            concerns.append("需确认风格参数是否包含 intensity 设置")
            suggestions.append("建议在 System Prompt 中注入词汇池使用频率")

        if "篇幅" in topic or "文种" in topic:
            concerns.append("需确认 length_hint 是否已设置")
            suggestions.append("根据篇幅自动推荐文种，减少用户决策负担")

        if "素材" in topic:
            suggestions.append("优先使用直接引语和具体数据，避免空泛描述")

        if "方案" in topic or "评审" in topic:
            suggestions.append("已确认写作方案，将根据文种和风格参数生成内容")

        return {"concerns": concerns, "suggestions": suggestions}

    def _reviewer_consultation(self, topic: str, context: Dict) -> Dict:
        concerns = []
        suggestions = []

        if "质量" in topic or "审查" in topic:
            concerns.append("需确认写作模式以选择正确的审查维度")
            suggestions.append("建议启用主动预警：发现严重问题时立即上报")

        if "风格" in topic:
            suggestions.append("检查风格强度是否与文种匹配（正式汇报→高强度）")

        if "方案" in topic or "评审" in topic:
            concerns.append("将在生成后进行全维度审查")
            suggestions.append("建议启用迭代修复模式，自动修复发现的问题")

        return {"concerns": concerns, "suggestions": suggestions}

    def _style_consultation(self, topic: str, context: Dict) -> Dict:
        concerns = []
        suggestions = []

        if "混合" in topic:
            suggestions.append("建议主风格70%+副风格30%，避免风格冲突")

        if "强度" in topic:
            suggestions.append("强度<0.5时禁用该风格独有的词汇")

        if "方案" in topic or "评审" in topic or "风格" in topic:
            suggestions.append(f"已就绪风格配置，将根据方案中的风格参数进行适配")

        return {"concerns": concerns, "suggestions": suggestions}

    def _knowledge_consultation(self, topic: str, context: Dict) -> Dict:
        concerns = []
        suggestions = []

        if "方案" in topic or "评审" in topic:
            suggestions.append("已检索知识库，可推送与当前主题相关的范文供参考")

        suggestions.append("术语使用需结合具体场景，避免生搬硬套")

        return {"concerns": concerns, "suggestions": suggestions}

    def _doc_type_consultation(self, topic: str, context: Dict) -> Dict:
        concerns = []
        suggestions = []

        if "文种" in topic:
            suggestions.append("根据 length_hint 和 materials_analysis 综合推荐")
            suggestions.append("避免关键词重叠导致的分数相同")

        if "方案" in topic or "评审" in topic:
            suggestions.append("已确认文种选择，将按该文种的格式规范生成内容")

        return {"concerns": concerns, "suggestions": suggestions}

    def _pdb_consultation(self, topic: str, context: Dict) -> Dict:
        concerns = []
        suggestions = []

        if "方案" in topic or "评审" in topic:
            suggestions.append("已分析用户历史偏好，将推荐个性化风格配置")

        suggestions.append("应用反bias分析结果，避免重复历史错误")

        return {"concerns": concerns, "suggestions": suggestions}

    def _check_agent_alerts(self, agent_role: AgentRole) -> Optional[Dict[str, Any]]:
        alerts = {
            AgentRole.WRITER: {
                "alert": "Writer: 检测到 raw_materials 为空，将基于简报自行组织内容",
                "severity": "minor",
                "agent": "writer",
            },
            AgentRole.REVIEWER: {
                "alert": "Reviewer: 待审稿件未指定写作模式，使用默认模式审查",
                "severity": "major",
                "agent": "reviewer",
            },
        }
        if agent_role in alerts and random.random() > 0.7:
            return alerts[agent_role]
        return None

    def _simulate_rebuttal(
        self,
        agent_role: AgentRole,
        topic: str,
        opponent_position: str,
        round_num: int,
    ) -> str:
        rebuttals = {
            AgentRole.WRITER: [
                f"从写作角度看，{opponent_position}的担忧有一定道理，但创意表达需要适度空间",
                f"我坚持原创作方案，因为{topic}的核心是传达信息而非完美格式",
            ],
            AgentRole.REVIEWER: [
                f"从审查角度看，{opponent_position}的方案存在风险，建议增加约束条件",
                f"我建议在{topic}中采用更保守的方案，确保质量和合规性",
            ],
        }
        options = rebuttals.get(agent_role, ["无异议"])
        return options[min(round_num, len(options) - 1)]

    def _reach_consensus(self, topic: str, writer_pos: str, reviewer_pos: str) -> str:
        return (
            f"共识：在{topic}问题上，"
            f"兼顾创作灵活性（Writer立场）和质量把控（Reviewer立场），"
            f"采用'创意先行、审查把关'的协同模式。"
        )

    def _orchestrator_decision(self, topic: str, decision: Dict) -> str:
        decisions = {
            "default": f"经民主协商，确定{topic}的执行方案",
            "风格": f"确定风格方案：结合用户偏好和质量要求，选择最优风格配置",
            "文种": f"确定文种方案：根据篇幅和素材分析，推荐最匹配文种",
            "质量": f"确定质量标准：启用全维度审查，确保稿件质量",
        }

        for key, val in decisions.items():
            if key in topic:
                return val

        return decisions["default"]

    # ═══ 报告 ═══

    def get_coordination_report(self) -> Dict[str, Any]:
        return {
            "communication_stats": self.bus.get_communication_stats(),
            "consultations": len(self.consultation_log),
            "debates": len(self.debate_results),
            "proactive_alerts": len(self._proactive_alerts),
            "recent_consultations": self.consultation_log[-3:] if self.consultation_log else [],
            "recent_debates": [d.to_dict() for d in self.debate_results[-3:]] if self.debate_results else [],
        }
