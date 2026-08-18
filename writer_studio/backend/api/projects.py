"""项目 CRUD 路由（薄路由：绑定参数 → 调 store → 返回）。"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..storage.store import Store

router = APIRouter(tags=["projects"])
store = Store()


class ProjectCreate(BaseModel):
    name: str
    description: str = ""


@router.get("/projects")
def list_projects():
    return store.list_projects()


@router.post("/projects", status_code=201)
def create_project(body: ProjectCreate):
    return store.create_project(body.name, body.description)


@router.get("/projects/{pid}")
def get_project(pid: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p


@router.patch("/projects/{pid}")
def patch_project(pid: str, body: ProjectCreate):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    p.name = body.name
    if body.description:
        p.description = body.description
    # 有简报时自动生成问卷总结（供"我的空间"项目详情展示）
    if p.brief and not p.questionnaire_summary:
        from ..core.profile import summarize_questionnaire
        p.questionnaire_summary = summarize_questionnaire(p.brief)
    store.update_project(pid, p)
    return p


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    if not store.delete_project(pid):
        raise HTTPException(404, "项目不存在")
    return {"deleted": pid}


class UrlImportBody(BaseModel):
    url: str


class TextImportBody(BaseModel):
    title: str = ""
    content: str = ""
    source: str = "手动粘贴"


@router.post("/projects/{pid}/references/url")
def import_url_reference(pid: str, body: UrlImportBody):
    from ..core import importer
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    try:
        ref = importer.import_from_url(body.url)
    except Exception as e:
        raise HTTPException(400, f"导入失败：{e}")
    p.references.append(ref)
    store.update_project(pid, p)
    return ref


@router.post("/projects/{pid}/references/text")
def import_text_reference(pid: str, body: TextImportBody):
    from ..core import importer
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    ref = importer.import_from_text(body.title, body.content, body.source)
    p.references.append(ref)
    store.update_project(pid, p)
    return ref


@router.delete("/projects/{pid}/references/{ref_id}")
def delete_reference(pid: str, ref_id: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    p.references = [r for r in p.references if r.id != ref_id]
    store.update_project(pid, p)
    return {"deleted": ref_id}
