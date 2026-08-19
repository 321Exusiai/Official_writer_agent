"""辅助智能体路由：对话 + 工具清单（GLM-4-Flash 驱动，无 Key 时规则降级）。"""
from fastapi import APIRouter
from pydantic import BaseModel

from ..core.assistant import AssistantAgent, get_tools_info
from .config import get_assistant_client

router = APIRouter(tags=["assistant"])


class ChatBody(BaseModel):
    message: str
    history: list = []  # [{role, content}]


def _get_agent() -> AssistantAgent:
    return AssistantAgent(get_assistant_client())


@router.post("/assistant/chat")
def chat(body: ChatBody):
    agent = _get_agent()
    result = agent.chat(body.message, body.history)
    return result


@router.get("/assistant/tools")
def tools():
    return {"tools": get_tools_info(), "available": bool(get_assistant_client().available)}
