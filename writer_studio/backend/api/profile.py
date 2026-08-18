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


class TextRefBody(BaseModel):
    title: str = ""
    content: str = ""


class UrlRefBody(BaseModel):
    url: str


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
    p = load_profile()
    target = p.favorite_terms if body.kind == "term" else p.favorite_phrases
    if body.value not in target:
        target.append(body.value)
    save_profile(p)
    return {"added": body.value, "count": len(target)}


@router.delete("/profile/favorites")
def remove_favorite(kind: str, value: str):
    p = load_profile()
    target = p.favorite_terms if kind == "term" else p.favorite_phrases
    if value in target:
        target.remove(value)
    save_profile(p)
    return {"removed": value}


@router.post("/profile/references/url")
def add_ref_url(body: UrlRefBody):
    p = load_profile()
    try:
        ref = importer.import_from_url(body.url)
    except Exception as e:
        raise HTTPException(400, f"导入失败：{e}")
    ref.analysis = profile.analyze_reference(ref.content, ref.title)
    p.reference_articles.append(ref)
    save_profile(p)
    return ref


@router.post("/profile/references/text")
def add_ref_text(body: TextRefBody):
    p = load_profile()
    ref = importer.import_from_text(body.title, body.content)
    ref.analysis = profile.analyze_reference(ref.content, ref.title)
    p.reference_articles.append(ref)
    save_profile(p)
    return ref


@router.post("/profile/references/{rid}/analyze")
def analyze_ref(rid: str):
    p = load_profile()
    for ref in p.reference_articles:
        if ref.id == rid:
            ref.analysis = profile.analyze_reference(ref.content, ref.title)
            save_profile(p)
            return ref
    raise HTTPException(404, "参考文本不存在")


@router.delete("/profile/references/{rid}")
def delete_ref(rid: str):
    p = load_profile()
    p.reference_articles = [r for r in p.reference_articles if r.id != rid]
    save_profile(p)
    return {"deleted": rid}


@router.post("/profile/analyze")
def run_analysis():
    projects = store.list_projects()
    return profile.analyze_profile(projects)
