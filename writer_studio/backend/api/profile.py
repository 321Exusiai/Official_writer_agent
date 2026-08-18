"""用户专属数据库路由：画像 / 收藏 / 参考文本解读 / 智能分析。"""
import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..core import importer, profile
from ..domain.schemas import ReferenceArticle, UserProfile
from .projects import store

router = APIRouter(tags=["profile"])
_PROFILE_PATH = Path(__file__).resolve().parent.parent / "data" / "profile.json"


def load_profile() -> UserProfile:
    if _PROFILE_PATH.exists():
        try:
            return UserProfile(**json.loads(_PROFILE_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return UserProfile(created_at=time.strftime("%Y-%m-%d %H:%M:%S"))


def save_profile(p: UserProfile):
    _PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    p.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
    tmp = _PROFILE_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(p.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _PROFILE_PATH)


class PrefBody(BaseModel):
    preferences: list = []


class FavoriteBody(BaseModel):
    kind: str  # term | phrase
    value: str
    project_id: str = ""  # 空 = 综合收藏夹；指定 = 项目收藏


def _favorite_target(project_id: str):
    """返回 (容器list, 保存函数)。综合收藏夹在 UserProfile，项目收藏在 Project。"""
    if project_id:
        p = store.get_project(project_id)
        if not p:
            raise HTTPException(404, "项目不存在")
        return p, lambda: store.update_project(project_id, p)
    prof = load_profile()
    return prof, lambda: save_profile(prof)


@router.get("/profile")
def get_profile():
    p = load_profile()
    return p


@router.get("/profile/overview")
def get_overview():
    """用户画像 + 基于项目的智能分析。"""
    p = load_profile()
    projects = store.list_projects()
    analysis = profile.analyze_profile(projects)
    return {
        "profile": p,
        "analysis": analysis,
        "projects": [
            {"id": pr.id, "name": pr.name, "status": pr.status.value,
             "style_requirements": pr.style_requirements,
             "questionnaire_summary": pr.questionnaire_summary}
            for pr in projects
        ],
    }


@router.post("/profile/preferences")
def update_preferences(body: PrefBody):
    p = load_profile()
    p.preferences = body.preferences
    save_profile(p)
    return p


@router.post("/profile/favorites")
def add_favorite(body: FavoriteBody):
    target, save = _favorite_target(body.project_id)
    lst = target.favorite_terms if body.kind == "term" else target.favorite_phrases
    if body.value not in lst:
        lst.append(body.value)
    save()
    return {"added": body.value, "count": len(lst), "project_id": body.project_id}


@router.delete("/profile/favorites")
def remove_favorite(kind: str, value: str, project_id: str = ""):
    target, save = _favorite_target(project_id)
    lst = target.favorite_terms if kind == "term" else target.favorite_phrases
    if value in lst:
        lst.remove(value)
    save()
    return {"removed": value}


@router.get("/profile/favorites")
def get_favorites(project_id: str = ""):
    """获取综合收藏夹（空）或项目收藏夹。"""
    if project_id:
        p = store.get_project(project_id)
        if not p:
            raise HTTPException(404, "项目不存在")
        return {"terms": p.favorite_terms, "phrases": p.favorite_phrases}
    prof = load_profile()
    return {"terms": prof.favorite_terms, "phrases": prof.favorite_phrases}


@router.post("/profile/analyze")
def run_analysis():
    projects = store.list_projects()
    return profile.analyze_profile(projects)
