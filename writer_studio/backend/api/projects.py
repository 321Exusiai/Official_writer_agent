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
def list_projects(full: int = 0):
    """项目列表：默认返回精简摘要（不含草稿/版本/参考全文等大字段），
    full=1 返回全量（供备份/导出等场景）。"""
    if full:
        return store.list_projects()
    out = []
    for p in store.list_projects():
        out.append(
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "status": p.status.value,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
                "ref_count": len(p.references),
                "review_count": len(p.review_history) + len(p.review_results),
                "favorite_count": len(p.favorite_terms) + len(p.favorite_phrases),
                "has_draft": bool(p.draft),
                "questionnaire_summary": p.questionnaire_summary,
            }
        )
    return out


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


def _ingest_reference(p, ref):
    """导入参考文本：AI 解读 + 自动归纳高频词汇/引语句进项目收藏。"""
    from ..core import profile

    ref.analysis = profile.analyze_reference(ref.content, ref.title)
    p.references.append(ref)
    fav = profile.extract_favorites(ref.content)
    for t in fav["terms"]:
        if t and t not in p.favorite_terms:
            p.favorite_terms.append(t)
    for ph in fav["phrases"]:
        if ph and ph not in p.favorite_phrases:
            p.favorite_phrases.append(ph)
    store.update_project(p.id, p)
    return ref


@router.post("/projects/{pid}/references/url")
def import_url_reference(pid: str, body: UrlImportBody):
    from ..core import importer

    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    try:
        ref = importer.import_from_url(body.url)
    except Exception as e:
        raise HTTPException(400, f"导入失败：{e}") from e
    return _ingest_reference(p, ref)


@router.post("/projects/{pid}/references/text")
def import_text_reference(pid: str, body: TextImportBody):
    from ..core import importer

    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    ref = importer.import_from_text(body.title, body.content, body.source)
    return _ingest_reference(p, ref)


@router.delete("/projects/{pid}/references/{ref_id}")
def delete_reference(pid: str, ref_id: str):
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    p.references = [r for r in p.references if r.id != ref_id]
    store.update_project(pid, p)
    return {"deleted": ref_id}


@router.get("/projects/{pid}/export")
def export_project(pid: str):
    """导出项目完整数据（JSON），含个性化数据。"""
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p.model_dump()


@router.get("/projects/{pid}/export/docx")
def export_docx(pid: str, template_id: str = ""):
    """导出 GB/T 9704-2012 国家标准公文 Word (.docx) 文件。"""
    from urllib.parse import quote
    from fastapi.responses import Response
    from ..core.exporter import export_project_to_docx
    from ..storage.custom_kb import TemplateStore

    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")

    tpl = TemplateStore.get_by_id(template_id) if template_id else None
    buf = export_project_to_docx(p, tpl)

    filename = f"{p.name or '公文文稿'}.docx"
    encoded_filename = quote(filename)
    headers = {
        "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
        "Access-Control-Expose-Headers": "Content-Disposition",
    }
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers=headers,
    )


@router.get("/projects/{pid}/revisions")
def get_revisions(pid: str):
    """获取项目时光机版本历史快照列表。"""
    p = store.get_project(pid)
    if not p:
        raise HTTPException(404, "项目不存在")
    return p.revisions


@router.post("/projects/{pid}/revisions/{rev_id}/restore")
def restore_revision(pid: str, rev_id: str):
    """从时光机版本快照回滚草稿。"""
    p = store.restore_revision(pid, rev_id)
    if not p:
        raise HTTPException(404, "版本快照或项目不存在")
    return p


@router.get("/projects/search/history")
def search_history(q: str = ""):
    """跨所有历史项目草稿与素材进行 BM25 全文检索。"""
    if not q.strip():
        return []
    return store.search_projects(q.strip(), limit=8)


@router.get("/search")
def global_search(q: str = ""):
    """全局搜索：跨项目匹配名称/草稿/参考文本/收藏 + 用户综合收藏夹。"""
    if not q or not q.strip():
        return {"projects": [], "favorites": []}
    kw = q.strip().lower()
    results = []
    for p in store.list_projects():
        hit = kw in (p.name or "").lower() or kw in (p.draft or "").lower() or kw in (p.description or "").lower()
        refs = [r for r in p.references if kw in (r.title or "").lower() or kw in (r.content or "").lower()]
        favs = [t for t in list(p.favorite_terms) + list(p.favorite_phrases) if kw in (t or "").lower()]
        if hit or refs or favs:
            results.append({"id": p.id, "name": p.name, "matched_refs": len(refs), "matched_favs": len(favs)})
    favorites = []
    try:
        from .profile import load_profile

        prof = load_profile()
        favorites = [t for t in list(prof.favorite_terms) + list(prof.favorite_phrases) if kw in (t or "").lower()]
    except Exception:
        pass
    return {"projects": results, "favorites": favorites}

