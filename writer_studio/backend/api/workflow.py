"""工作流路由（薄路由：绑定参数 → 驱动 engine → 持久化 → 返回）。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.engine import WorkflowEngine
from .projects import store

router = APIRouter(tags=["workflow"])
ENGINES: dict = {}


class AnswerBody(BaseModel):
    text: str


def get_engine(pid: str) -> WorkflowEngine:
    project = store.get_project(pid)
    if not project:
        raise HTTPException(404, "项目不存在")
    if pid not in ENGINES:
        ENGINES[pid] = WorkflowEngine(project)
    return ENGINES[pid]


def _persist(pid: str, eng: WorkflowEngine):
    store.update_project(pid, eng.project)


@router.post("/projects/{pid}/workflow/start")
def start(pid: str):
    eng = get_engine(pid)
    return eng.start()


@router.post("/projects/{pid}/workflow/answer")
def answer(pid: str, body: AnswerBody):
    eng = get_engine(pid)
    result = eng.answer(body.text)
    _persist(pid, eng)
    return result


@router.post("/projects/{pid}/workflow/confirm")
def confirm(pid: str):
    eng = get_engine(pid)
    result = eng.confirm_plan()
    _persist(pid, eng)
    return result


@router.post("/projects/{pid}/workflow/review")
def review(pid: str):
    eng = get_engine(pid)
    result = eng.review()
    _persist(pid, eng)
    return result


@router.post("/projects/{pid}/workflow/finalize")
def finalize(pid: str):
    eng = get_engine(pid)
    result = eng.finalize()
    _persist(pid, eng)
    return result


@router.get("/projects/{pid}/workflow/state")
def state(pid: str):
    eng = get_engine(pid)
    return eng.get_state()
