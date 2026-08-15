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
    store.update_project(pid, p)
    return p


@router.delete("/projects/{pid}")
def delete_project(pid: str):
    if not store.delete_project(pid):
        raise HTTPException(404, "项目不存在")
    return {"deleted": pid}
