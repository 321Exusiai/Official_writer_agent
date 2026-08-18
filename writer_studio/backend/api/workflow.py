"""工作流路由（薄路由：绑定参数 → 驱动 engine → 持久化 → 返回）。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.engine import WorkflowEngine
from .config import get_client
from .projects import store

router = APIRouter(tags=["workflow"])
ENGINES: dict = {}


class AnswerBody(BaseModel):
    text: str


class DraftBody(BaseModel):
    draft: str


def get_engine(pid: str) -> WorkflowEngine:
    project = store.get_project(pid)
    if not project:
        raise HTTPException(404, "项目不存在")
    if pid not in ENGINES:
        ENGINES[pid] = WorkflowEngine(project, llm=get_client())
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


@router.patch("/projects/{pid}/draft")
def update_draft(pid: str, body: DraftBody):
    """HITL-2：用户手动编辑草稿后写回。"""
    eng = get_engine(pid)
    eng.project.draft = body.draft
    _persist(pid, eng)
    return {"saved": True, "word_count": len(body.draft)}


@router.post("/projects/{pid}/workflow/finalize")
def finalize(pid: str):
    eng = get_engine(pid)
    result = eng.finalize()
    _persist(pid, eng)
    # 审查历史汇总进用户画像（weakness / bias）
    try:
        from ..core.profile import analyze_profile
        from .profile import load_profile, save_profile
        prof = load_profile()
        analysis = analyze_profile(store.list_projects())
        prof.weaknesses = analysis["weaknesses"]
        prof.bias_warnings = analysis["bias_warnings"]
        save_profile(prof)
    except Exception:
        pass
    return result


@router.get("/projects/{pid}/workflow/state")
def state(pid: str):
    eng = get_engine(pid)
    return eng.get_state()


class RollbackBody(BaseModel):
    step: str


class PlanBody(BaseModel):
    doc_type: str
    media_style: str


@router.post("/projects/{pid}/workflow/rollback")
def rollback(pid: str, body: RollbackBody):
    eng = get_engine(pid)
    result = eng.rollback_to(body.step)
    _persist(pid, eng)
    return result


@router.post("/projects/{pid}/workflow/plan")
def update_plan(pid: str, body: PlanBody):
    eng = get_engine(pid)
    try:
        result = eng.update_plan(body.doc_type, body.media_style)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e))
    _persist(pid, eng)
    return result
