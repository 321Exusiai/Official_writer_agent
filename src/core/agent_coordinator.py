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
from collections import deque
import json
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


# 各 Agent 职责矩阵（供系统全景注入，LLM 可见性保障）
AGENT_RESPONSIBILITY_MATRIX = {
    AgentRole.ORCHESTRATOR: "总指挥：拥有最终决策权，统一调度各 Agent，对结果负总责",
    AgentRole.WRITER: "主笔：起草与修订文稿，关注内容充实、表达清晰、素材运用",
    AgentRole.REVIEWER: "审稿人：质量把关，关注事实准确性、格式合规性、语言规范性",
    AgentRole.STYLE_ADAPTER: "风格专家：文种-风格匹配、风格强度适配",
    AgentRole.KNOWLEDGE_BASE: "知识库：推送标杆范文、规范术语、写作提示",
    AgentRole.DOC_TYPE_IDENTIFIER: "文种专家：文种选择与行文规则把关",
    AgentRole.PERSONALIZED_DB: "用户画像：历史偏好、常见弱点与反偏见",
}

# 角色展示名（协商/决策/辩论/注入时让 LLM 明确"谁说了什么"）
ROLE_DISPLAY_NAMES = {
    AgentRole.ORCHESTRATOR: "Orchestrator（总指挥）",
    AgentRole.WRITER: "Writer（主笔）",
    AgentRole.REVIEWER: "Reviewer（审稿人）",
    AgentRole.STYLE_ADAPTER: "StyleAdapter（风格专家）",
    AgentRole.KNOWLEDGE_BASE: "KnowledgeBase（知识库）",
    AgentRole.DOC_TYPE_IDENTIFIER: "DocTypeIdentifier（文种专家）",
    AgentRole.PERSONALIZED_DB: "PersonalizedDB（用户画像）",
}


def role_display_name(role: AgentRole) -> str:
    """角色展示名（协商/决策/辩论/注入时用）"""
    return ROLE_DISPLAY_NAMES.get(role, role.value if role else "未知角色")


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
        self._history = deque(maxlen=500)
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
            try:
                handler(msg)
            except Exception:
                pass

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

        # Token 优化集成
        import threading
        self._lock = threading.Lock()
        from ..utils.token_optimizer import ContextManager, CacheAligner, ModelRouter
        from ..utils.response_cache import cached_prompt, store_prompt, make_cache_key
        self._context_mgr = ContextManager()
        self._cache_aligner = CacheAligner()
        self._model_router = ModelRouter()

        # 持久化状态 — 用于真实预警检测
        self._raw_materials: str = ""
        self._writing_mode: str = ""
        self._draft_word_count: int = 0
        self._has_style_conflict: bool = False

    def set_context(
        self,
        raw_materials: str = "",
        writing_mode: str = "",
        draft_word_count: int = 0,
        has_style_conflict: bool = False,
    ):
        """由 Orchestrator 在调用前注入上下文，用于真实预警检测"""
        self._raw_materials = raw_materials
        self._writing_mode = writing_mode
        self._draft_word_count = draft_word_count
        self._has_style_conflict = has_style_conflict

        # 首次注入时注册内置订阅者（懒初始化，确保 context 已准备好）
        if not self.bus._subscribers.get(MessageType.DECISION, []) and not self.bus._subscribers.get(MessageType.ALERT, []):
            self._register_builtin_subscribers()

    def _register_builtin_subscribers(self):
        """注册内置的 Agent 事件订阅者（实现真正的消息驱动联动）"""
        # 订阅决策事件 → 自动更新 agent log
        def on_decision(msg: AgentMessage):
            payload = msg.payload
            self.consultation_log.append({
                "topic": payload.get("topic", ""),
                "decision": payload.get("decision", ""),
                "rationale": payload.get("rationale", ""),
                "timestamp": msg.timestamp,
            })

        # 订阅预警事件 → 自动加入预警列表
        def on_alert(msg: AgentMessage):
            self._proactive_alerts.append(msg)

        # 订阅共识事件 → 自动记录辩论结果
        def on_consensus(msg: AgentMessage):
            payload = msg.payload
            self.consultation_log.append({
                "type": "consensus",
                "topic": payload.get("topic", ""),
                "consensus": payload.get("consensus", ""),
                "timestamp": msg.timestamp,
            })

        self.bus.subscribe(MessageType.DECISION, on_decision)
        self.bus.subscribe(MessageType.ALERT, on_alert)
        self.bus.subscribe(MessageType.PROACTIVE_REPORT, on_alert)
        self.bus.subscribe(MessageType.CONSENSUS, on_consensus)

    # ═══ 民主协商机制 ═══

    def consult_before_decision(
        self,
        decision_topic: str,
        participants: List[AgentRole],
        context: Dict[str, Any] = None,
        llm_call: Callable = None,
        max_rounds: int = 1,
    ) -> Dict[AgentRole, Dict[str, Any]]:
        """
        决策前民主协商（V3：真多轮）

        流程：
        1. Orchestrator 发出协商议题
        2. Round 1：各参与 Agent 发表意见（LLM 生成，规则匹配兜底）
        3. Round 2+：把上一轮各方意见带角色标签回传，各 Agent 回应/确认/修正
        4. Orchestrator 汇总意见，做出最终决策

        Args:
            decision_topic: 协商议题
            participants: 参与协商的 Agent
            context: 协商背景信息（包含 plan、brief、writing_mode 等）
            llm_call: LLM 调用函数 (system_prompt, user_prompt) -> str，None 时使用规则匹配
            max_rounds: 协商轮数（>=1）。每多一轮增加参与者数量次 LLM 调用。

        Returns:
            各 Agent 的反馈意见
        """
        if not participants:
            return {}

        consultation_msg = AgentMessage.create(
            sender=AgentRole.ORCHESTRATOR,
            receiver=AgentRole.ORCHESTRATOR,
            msg_type=MessageType.CONSULTATION,
            action="consult",
            payload={
                "topic": decision_topic,
                "participants": [p.value for p in participants],
                "rounds": max_rounds,
            },
            priority=MessagePriority.HIGH,
        )
        self.bus.send(consultation_msg)

        from concurrent.futures import ThreadPoolExecutor

        responses: Dict[AgentRole, Dict[str, Any]] = {}

        for round_idx in range(max(1, max_rounds)):
            # 上一轮意见摘要（带角色标签），供本轮各 Agent 回应
            prior_opinions = self._summarize_opinions(responses) if round_idx > 0 else ""

            requests = {}
            for agent_role in participants:
                request = AgentMessage.create(
                    sender=AgentRole.ORCHESTRATOR,
                    receiver=agent_role,
                    msg_type=MessageType.CONSULTATION,
                    action="request_opinion",
                    payload={
                        "topic": decision_topic,
                        "context": context or {},
                        "round": round_idx + 1,
                    },
                )
                self.bus.send(request)
                requests[agent_role] = request

            def query_agent(agent_role):
                if llm_call:
                    response = self._llm_agent_response(
                        agent_role, decision_topic, context or {}, llm_call,
                        round_idx=round_idx, prior_opinions=prior_opinions,
                    )
                else:
                    response = self._simulate_agent_response(agent_role, decision_topic, context)
                return agent_role, response

            with ThreadPoolExecutor(max_workers=len(participants)) as executor:
                future_to_role = {executor.submit(query_agent, role): role for role in participants}
                for future in future_to_role:
                    agent_role, response = future.result()
                    responses[agent_role] = response

                    request = requests[agent_role]
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
            "rounds": max_rounds,
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
        llm_call: Callable = None,
    ) -> DebateResult:
        """
        运行辩论，达成共识（V2 升级版）

        流程：
        1. 双方各自陈述立场
        2. 各自反驳对方（优先使用 LLM，规则兜底）
        3. 寻找共同点，形成共识（优先使用 LLM）
        4. Orchestrator 做出最终裁决

        Args:
            topic: 辩论议题
            writer_position: Writer 立场
            reviewer_position: Reviewer 立场
            max_rounds: 最大辩论轮次
            llm_call: LLM 调用函数，None 时使用规则匹配

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
            if llm_call:
                writer_rebuttal = self._llm_rebuttal(
                    AgentRole.WRITER, topic, reviewer_position, round_num, llm_call
                )
                reviewer_rebuttal = self._llm_rebuttal(
                    AgentRole.REVIEWER, topic, writer_position, round_num, llm_call
                )
            else:
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

            # 订阅者通知：辩论轮次完成（传递 AgentMessage 而非裸 dict）
            debate_notification = AgentMessage.create(
                sender=AgentRole.ORCHESTRATOR,
                receiver=AgentRole.ORCHESTRATOR,
                msg_type=MessageType.DEBATE,
                action=f"debate_round_{round_num + 1}",
                payload={"round": round_num + 1, "writer": writer_position, "reviewer": reviewer_position},
            )
            self.bus.send(debate_notification)

        if llm_call:
            consensus = self._llm_consensus(topic, writer_position, reviewer_position, llm_call)
        else:
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
        llm_call: Callable = None,
    ) -> Dict[str, Any]:
        """
        民主集中制决策：先民主（征询）后集中（决策）

        Args:
            topic: 决策议题
            consultation_responses: 协商阶段收集的各 Agent 意见
            proactive_reports: 主动上报的问题
            llm_call: 传入时用 LLM 基于各方意见生成最终决策与理由；失败/缺省时回退模板

        Returns:
            最终决策（含 role_opinions 角色归属）
        """
        decision = {
            "topic": topic,
            "consultation_count": len(consultation_responses) if consultation_responses else 0,
            "alert_count": len(proactive_reports) if proactive_reports else 0,
            "decision": "",
            "rationale": "",
        }

        # 保留角色归属：谁说了什么（多轮协商的结构化输出，注入时按角色呈现）
        role_opinions: Dict[str, Dict[str, List[str]]] = {}
        if consultation_responses:
            for role, resp in consultation_responses.items():
                role_opinions[role.value] = {
                    "concerns": resp.get("concerns", []),
                    "suggestions": resp.get("suggestions", []),
                }
                if resp.get("concerns"):
                    decision.setdefault("concerns", []).extend(resp["concerns"])
                if resp.get("suggestions"):
                    decision.setdefault("suggestions", []).extend(resp["suggestions"])
        decision["role_opinions"] = role_opinions

        if proactive_reports:
            for report in proactive_reports:
                decision.setdefault("alerts", []).append(report.get("alert", ""))

        if llm_call:
            llm_decision, llm_rationale = self._llm_orchestrator_decision(topic, decision, llm_call)
            decision["decision"] = llm_decision or self._orchestrator_decision(topic, decision)
            decision["rationale"] = llm_rationale or f"基于{decision['consultation_count']}方意见和{decision['alert_count']}个预警"
        else:
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
        round_idx: int = 0,
        prior_opinions: str = "",
    ) -> Dict[str, Any]:
        """
        使用 LLM 生成 Agent 的协商意见（V3：系统全景可见 + 多轮回应）

        Token 优化集成：
          C. ContextManager：多轮协商历史分层管理（省 80-90%）
          D. CacheAligner：静态角色描述前置 + 动态议题后置（省 50-90%）
          F. ModelRouter：按议题复杂度分类，简单任务可用便宜模型
        """
        role_profiles = {
            AgentRole.WRITER: (
                "你负责起草文稿（Writer Agent）。"
                "关注三件事：内容是否充实、表达是否清晰、素材是否用到位。"
                "如果素材不够或者方向有偏差，直接说出来，不要硬写。"
                "不同文体有不同写法，法定公文开门见山，新闻通讯讲究主体性，别用一套方法套所有场景。"
            ),
            AgentRole.REVIEWER: (
                "你负责质量把关（Reviewer Agent）。"
                "关注事实准确性、格式合规性、语言规范性。"
                "发现问题要给出具体位置和修改方向，不只是说'有问题'。"
                "审查标准按文体区分：法定公文查四要求（准确、简明、朴实、得体）和格式规范，新闻通讯查主体性和叙事质量。"
            ),
            AgentRole.STYLE_ADAPTER: (
                "你负责风格适配（Style Adapter Agent）。"
                "关注文种与风格是否匹配、风格强度是否合适。"
                "行政公文不该用文学风格，新闻稿不该套公文格式，这些冲突要提前预警。"
                "风格是为内容服务的，不是反过来。"
            ),
            AgentRole.KNOWLEDGE_BASE: (
                "你负责范文和术语支持（Knowledge Base Agent）。"
                "关注当前写作任务有没有可参考的标杆范文、术语用得准不准。"
                "有好的参考素材就推送给主笔，但范文是学结构不是抄句子。"
                "术语要结合具体场景用，生搬硬套不如不用。"
            ),
            AgentRole.DOC_TYPE_IDENTIFIER: (
                "你负责文种辨析（Document Type Agent）。"
                "关注文种选择对不对、格式符不符合该文种的规范。"
                "请示不能一文多事、报告不能夹带请示、函不能用于上下级——这些行文规则问题你来把关。"
                "文种选错了，后面写得再好也是白费。"
            ),
            AgentRole.PERSONALIZED_DB: (
                "你负责用户画像（Personalized DB Agent）。"
                "关注用户的历史偏好和常见弱点。"
                "如果用户上次犯过同类错误，提醒一下；如果用户偏好某种风格，可以建议。"
                "但个性化不是迁就，用户习惯里的毛病该指出还是要指出。"
            ),
        }

        plan_info = context.get("plan", "")
        brief_info = context.get("brief", "")
        writing_mode = context.get("writing_mode", "")
        env_state_info = context.get("env_state", "")
        user_memory_info = context.get("user_memory", "")

        # ── Strategy D: 缓存对齐（静态角色描述前置 + 动态议题后置）──
        # 系统全景：让协商 Agent 看到系统提示词、各 Agent 职责、工具职责（LLM 可见性保障）
        static_part = self.build_agent_orientation()
        static_part += "\n\n" + role_profiles.get(agent_role, "你是一名公文写作专家。")
        # ── Strategy E: 隐式推理（协商场景直接给结果，省70%推理token）──
        from ..utils.token_optimizer import ImplicitReasoning
        static_part += "\n\n" + ImplicitReasoning.get_injection("basic")
        static_part += "\n\n请用JSON格式输出你的意见，只输出JSON，不要有其他内容。"

        dynamic_part = f"""请就以下议题发表你的专业意见。

**协商议题**：{topic}

**写作模式**：{writing_mode}
**环境状态**：
{env_state_info or "（暂无）"}

**用户记忆**：
{user_memory_info or "（暂无）"}

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

        # 多轮协商：附上其他 Agent 上一轮意见，要求回应（真多轮）
        if round_idx > 0 and prior_opinions:
            dynamic_part += f"""

**其他 Agent 的上一轮意见（请逐一回应：认同的确认、分歧的说明理由，再给出你的最终意见）**：
{prior_opinions}"""

        # CacheAligner 重排：静态前置 + 动态后置
        system_prompt = self._cache_aligner.reorder_for_cache(static_part, "")
        user_prompt = dynamic_part

        # ── Strategy D: LRU 缓存检查（相同 agent+topic+round 直接返回）──
        from ..utils.response_cache import cached_prompt, store_prompt, make_cache_key
        cache_key = make_cache_key(
            agent_role.value, topic, writing_mode, round_idx,
            plan_info, brief_info, env_state_info, user_memory_info,
        )
        with self._lock:
            cached = cached_prompt("agent_consultation", cache_key)
        if cached:
            return self._parse_llm_json_response(cached, agent_role)

        # ── Strategy F: 模型路由（按议题复杂度分类）──
        task_level = self._model_router.classify_task(topic)
        # task_level 可用于未来按复杂度选择不同模型

        # ── Strategy C: 上下文管理（记录协商历史）──
        with self._lock:
            self._context_mgr.add_message("system", f"[{agent_role.value}] 议题: {topic[:100]}")

        try:
            raw = llm_call(system_prompt, user_prompt)

            # 记录 LLM 响应到上下文管理器
            with self._lock:
                self._context_mgr.add_message("assistant", raw[:200] if raw else "")

            # 缓存成功响应
            if raw and len(raw) > 10 and "占位文本" not in raw:
                with self._lock:
                    store_prompt("agent_consultation", raw, cache_key)

            return self._parse_llm_json_response(raw, agent_role)
        except Exception:
            # LLM 调用失败时回退到规则匹配
            return self._simulate_agent_response(agent_role, topic, context)

    # ═══ 系统全景与协商辅助（LLM 可见性保障 / 真多轮）═══

    def build_agent_orientation(self) -> str:
        """
        生成系统全景文本：工作流状态机 + 各 Agent 职责矩阵 + 工具职责清单。

        注入到协商/决策/辩论的 LLM system prompt，让 LLM 能看到整个系统：
        有哪些组件、每个 Agent 的职责、有哪些工具及各自用途。
        """
        lines = [
            "# 系统全景（多智能体公文写作系统）",
            "",
            "## 工作流状态机",
            "IDLE → ROUTING（决策树路由）→ MODE_QUESTIONING（模式问卷）→ PLANNING（规划与协商）"
            "→ WRITING（写作）→ REVIEWING（迭代审查/辩论）→ COMPLETED",
            "",
            "## 各 Agent 职责矩阵",
        ]
        for role in AgentRole:
            if role != AgentRole.ORCHESTRATOR:
                lines.append(f"- {role_display_name(role)}：{AGENT_RESPONSIBILITY_MATRIX.get(role, '')}")
        lines.append(f"- {role_display_name(AgentRole.ORCHESTRATOR)}：{AGENT_RESPONSIBILITY_MATRIX.get(AgentRole.ORCHESTRATOR, '')}")
        lines.append("")
        lines.append("## 可用工具及职责")
        try:
            from ..config.tool_definitions import TOOL_DEFINITIONS
            for t in TOOL_DEFINITIONS:
                lines.append(f"- {t.name}：{t.description}")
        except Exception:
            lines.append("（工具清单不可用）")
        return "\n".join(lines)

    def _summarize_opinions(self, responses: Dict[AgentRole, Dict[str, Any]]) -> str:
        """把上一轮各方意见汇总为带角色标签的文本（多轮协商反馈用）"""
        lines = []
        for role, resp in responses.items():
            parts = [f"【{role_display_name(role)}】"]
            for c in (resp.get("concerns") or [])[:2]:
                parts.append(f"  关注：{c}")
            for s in (resp.get("suggestions") or [])[:2]:
                parts.append(f"  建议：{s}")
            if len(parts) > 1:
                lines.append("\n".join(parts))
        return "\n".join(lines)

    def _format_role_opinions(self, role_opinions: Dict[str, Dict[str, List[str]]]) -> str:
        """把带角色归属的意见格式化为文本（决策 LLM 调用输入）"""
        lines = []
        for role_value, opinions in role_opinions.items():
            try:
                role = AgentRole(role_value)
            except ValueError:
                role = None
            name = role_display_name(role) if role else role_value
            parts = [f"【{name}】"]
            for c in (opinions.get("concerns") or [])[:2]:
                parts.append(f"  关注：{c}")
            for s in (opinions.get("suggestions") or [])[:2]:
                parts.append(f"  建议：{s}")
            if len(parts) > 1:
                lines.append("\n".join(parts))
        return "\n".join(lines)

    def _llm_orchestrator_decision(
        self, topic: str, decision: Dict[str, Any], llm_call: Callable
    ) -> Tuple[str, str]:
        """用 LLM 基于各方意见生成最终决策与理由（Orchestrator 裁决），失败返回空"""
        opinions_text = self._format_role_opinions(decision.get("role_opinions", {}))
        system_prompt = (
            self.build_agent_orientation()
            + "\n\n你是 Orchestrator（总指挥），拥有最终决策权。"
            "在各方意见分歧时，依据文体规范与写作目标做出最终裁决。"
            "决策要具体可执行，不是和稀泥。"
            "\n\n请用JSON格式输出，只输出JSON："
            '{"decision": "最终决策", "rationale": "决策依据（结合各方意见说明）"}'
        )
        user_prompt = f"""协商议题：{topic}

各方意见：
{opinions_text or "（无意见）"}

请给出最终决策与决策依据："""
        try:
            raw = llm_call(system_prompt, user_prompt)
            if not raw or "占位文本" in raw:
                return "", ""
            json_str = raw.strip()
            if "```json" in json_str:
                json_str = json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in json_str:
                json_str = json_str.split("```")[1].split("```")[0].strip()
            data = json.loads(json_str)
            return data.get("decision", ""), data.get("rationale", "")
        except Exception:
            return "", ""

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
        """基于真实上下文检测各 Agent 需要主动上报的问题"""
        if agent_role == AgentRole.WRITER:
            if not self._raw_materials or len(self._raw_materials.strip()) < 10:
                return {
                    "alert": "Writer: 检测到 raw_materials 为空或极短，将基于简报自行组织内容",
                    "severity": "minor",
                    "agent": "writer",
                }
            if self._draft_word_count > 0 and self._draft_word_count < 100:
                return {
                    "alert": f"Writer: 初稿仅 {self._draft_word_count} 字，可能内容不充分",
                    "severity": "minor",
                    "agent": "writer",
                }
        elif agent_role == AgentRole.REVIEWER:
            if not self._writing_mode:
                return {
                    "alert": "Reviewer: 待审稿件未指定写作模式，使用默认模式审查",
                    "severity": "major",
                    "agent": "reviewer",
                }
        elif agent_role == AgentRole.STYLE_ADAPTER:
            if self._has_style_conflict:
                return {
                    "alert": "Style Adapter: 检测到风格冲突，建议选用主辅风格混合模式",
                    "severity": "major",
                    "agent": "style_adapter",
                }
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

    def _llm_rebuttal(
        self,
        agent_role: AgentRole,
        topic: str,
        opponent_position: str,
        round_num: int,
        llm_call: Callable,
    ) -> str:
        """使用 LLM 生成辩论反驳（V3：注入系统全景，明确双方职责）"""
        role_name = "撰写方" if agent_role == AgentRole.WRITER else "审查方"
        system_prompt = (
            self.build_agent_orientation()
            + "\n\n你是"
            + role_name
            + "，正在参与文稿质量讨论。"
            "对方提出了意见，你需要从专业角度回应：认同合理的部分，解释有分歧的部分。"
            "聚焦具体问题，不要泛泛而谈，也不要为了反驳而反驳。"
        )
        user_prompt = f"""辩论议题：{topic}

对方（{'审查方' if agent_role == AgentRole.WRITER else '撰写方'}）的观点：
{opponent_position}

这是第 {round_num + 1} 轮反驳。请输出你的反驳观点（不超过200字）："""
        try:
            result = llm_call(system_prompt, user_prompt)
            if result and len(result.strip()) > 5:
                return result.strip()[:500]
        except Exception:
            pass
        return self._simulate_rebuttal(agent_role, topic, opponent_position, round_num)

    def _llm_consensus(
        self,
        topic: str,
        writer_pos: str,
        reviewer_pos: str,
        llm_call: Callable,
    ) -> str:
        """使用 LLM 生成共识（V3：注入系统全景）"""
        system_prompt = (
            self.build_agent_orientation()
            + "\n\n你需要在撰写方和审查方之间找到平衡。"
            "两边都有道理时，看哪个更符合文体规范和读者需求。"
            "给出具体的处理方案，不是和稀泥。"
        )
        user_prompt = f"""辩论议题：{topic}

撰写方最终立场：
{writer_pos}

审查方最终立场：
{reviewer_pos}

请给出一个兼顾双方关切的共识方案（不超过300字）："""
        try:
            result = llm_call(system_prompt, user_prompt)
            if result and len(result.strip()) > 5:
                return result.strip()[:500]
        except Exception:
            pass
        return self._reach_consensus(topic, writer_pos, reviewer_pos)

    def _orchestrator_decision(self, topic: str, decision: Dict) -> str:
        decisions = {
            "风格": f"确定风格方案：结合用户偏好和质量要求，选择最优风格配置",
            "文种": f"确定文种方案：根据篇幅和素材分析，推荐最匹配文种",
            "质量": f"确定质量标准：启用全维度审查，确保稿件质量",
        }

        for key, val in decisions.items():
            if key in topic:
                return val

        return f"经民主协商，确定{topic}的执行方案"

    # ═══ 报告 ═══

    def get_coordination_report(self) -> Dict[str, Any]:
        return {
            "communication_stats": self.bus.get_communication_stats(),
            "consultations": len(self.consultation_log),
            "debates": len(self.debate_results),
            "proactive_alerts": len(self._proactive_alerts),
            "recent_consultations": self.consultation_log[-3:] if self.consultation_log else [],
            "recent_debates": [d.to_dict() for d in self.debate_results[-3:]] if self.debate_results else [],
            "cache_stats": self._cache_aligner.get_cache_stats(),
            "context_messages": self._context_mgr._total_messages,
        }
