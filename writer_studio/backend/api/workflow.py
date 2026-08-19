"""工作流路由（薄路由：绑定参数 → 驱动 engine → 持久化 → 返回）。"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core.engine import WorkflowEngine
from .config import get_assistant_client, get_client
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
        # 双轨制：主模型写作/审查，辅助模型（GLM-4-Flash）协商/决策
        ENGINES[pid] = WorkflowEngine(project, llm=get_client(), assistant_llm=get_assistant_client())
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


class FixFindingBody(BaseModel):
    index: int


@router.post("/projects/{pid}/workflow/review/fix")
def fix_finding(pid: str, body: FixFindingBody):
    """HITL-3：修复单条审查发现（规则优先，LLM 兜底），修复后重新审查。"""
    eng = get_engine(pid)
    try:
        result = eng.fix_finding(body.index)
    except (ValueError, RuntimeError) as e:
        raise HTTPException(400, str(e)) from e
    _persist(pid, eng)
    return result


@router.post("/projects/{pid}/workflow/auto_heal")
def auto_heal(pid: str):
    """自动自愈收敛闭环：按重要级自动辩论修复并复审至85分以上，带回滚降级保护。"""
    eng = get_engine(pid)
    result = eng.auto_heal(target_score=85.0, max_rounds=3)
    _persist(pid, eng)
    return result


@router.post("/projects/{pid}/workflow/chunked_draft")
def chunked_draft(pid: str):
    """大纲驱动的分段递进起草。"""
    eng = get_engine(pid)
    draft = eng.chunked_draft()
    _persist(pid, eng)
    return {"draft": draft, "word_count": len(draft)}


@router.post("/projects/{pid}/workflow/red_team")
def red_team(pid: str):
    """模拟分管领导审签与舆情红蓝军压力测试。"""
    eng = get_engine(pid)
    result = eng.red_team_review()
    _persist(pid, eng)
    return result


class InlineTransformBody(BaseModel):
    selection: str
    action: str = "polish"
    context: str = ""


@router.post("/projects/{pid}/workflow/inline_transform")
def inline_transform(pid: str, body: InlineTransformBody):
    """划词局部 AI 伴写（升华金句/精简套话/政策校对/风格转换）。"""
    eng = get_engine(pid)
    result = eng.inline_transform(body.selection, body.action, body.context)
    return result


class WeightsBody(BaseModel):
    weights: dict[str, float]


@router.post("/projects/{pid}/workflow/weights")
def update_weights(pid: str, body: WeightsBody):
    """设置用户微调的专家决策权重。"""
    eng = get_engine(pid)
    eng.project.custom_role_weights = body.weights
    _persist(pid, eng)
    return {"weights": eng.project.custom_role_weights}


@router.patch("/projects/{pid}/draft")
def update_draft(pid: str, body: DraftBody):
    """HITL-2：用户手动编辑草稿后写回（自动记录时光机版本）。"""
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
        raise HTTPException(400, str(e)) from e
    _persist(pid, eng)
    return result
