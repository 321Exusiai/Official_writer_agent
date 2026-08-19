"""知识库路由：范文 / 术语 / 过渡句 / 格式化用语 查询。"""

from fastapi import APIRouter

from ..domain.registry import Registry

router = APIRouter(tags=["knowledge"])


@router.get("/knowledge/exemplars")
def list_exemplars(mode: str = "", doc_type: str = "", style: str = ""):
    items = list(Registry.load("exemplars").values())
    if mode:
        items = [i for i in items if i.get("writing_mode") == mode]
    if doc_type:
        items = [i for i in items if i.get("doc_type") == doc_type]
    if style:
        items = [i for i in items if i.get("style") == style]
    return items


@router.get("/knowledge/terminology")
def list_terminology():
    return Registry.load("terminology")


@router.get("/knowledge/transitions")
def list_transitions():
    return Registry.load("transitions")


@router.get("/knowledge/formulaic")
def list_formulaic():
    return Registry.load("formulaic")


@router.get("/knowledge/policy")
def list_policy():
    return list(Registry.load("policy").values())


@router.get("/knowledge/doctypes")
def list_doctypes(domain: str = "", mode: str = ""):
    items = list(Registry.load("doctypes").values())
    if mode:
        items = [d for d in items if mode in d.get("modes", [])]
    elif domain:
        items = [d for d in items if d["domain"] == domain]
    return [{"id": d["id"], "name_cn": d["name_cn"], "domain": d["domain"]} for d in items]


@router.get("/knowledge/styles")
def list_styles(domain: str = "", mode: str = ""):
    items = list(Registry.load("styles").values())
    if mode:
        items = [s for s in items if mode in s.get("modes", [])]
    elif domain:
        items = [s for s in items if s["domain"] == domain]
    return [{"id": s["id"], "name": s["name"], "domain": s["domain"]} for s in items]


# ── 单位专有知识库与自定义模板 ──
from pydantic import BaseModel, Field
from ..storage.custom_kb import CustomKnowledgeStore, TemplateStore
from ..domain.schemas import TemplateConfig


class CustomItemCreate(BaseModel):
    title: str
    content: str
    category: str = "policy"
    tags: list[str] = Field(default_factory=list)
    source: str = ""


@router.get("/knowledge/custom")
def list_custom_knowledge():
    """获取单位专有知识条目列表。"""
    return CustomKnowledgeStore.load_all()


@router.post("/knowledge/custom", status_code=201)
def add_custom_knowledge(body: CustomItemCreate):
    """新增单位专有知识条目。"""
    return CustomKnowledgeStore.add_item(
        title=body.title,
        content=body.content,
        category=body.category,
        tags=body.tags,
        source=body.source,
    )


@router.delete("/knowledge/custom/{item_id}")
def delete_custom_knowledge(item_id: str):
    """删除单位专有知识条目。"""
    success = CustomKnowledgeStore.delete_item(item_id)
    return {"deleted": success, "id": item_id}


@router.get("/knowledge/templates")
def list_templates():
    """获取可用公文排版模板列表。"""
    return TemplateStore.load_all()


@router.post("/knowledge/templates")
def add_template(config: TemplateConfig):
    """新增/更新公文排版模板。"""
    return TemplateStore.add_template(config)


@router.get("/knowledge/overview")
def get_knowledge_overview():
    """获取全库知识体量概览。"""
    return {
        "exemplars_count": len(Registry.load("exemplars")),
        "terminology_count": len(Registry.load("terminology")),
        "transitions_count": len(Registry.load("transitions")),
        "formulaic_count": len(Registry.load("formulaic")),
        "policy_count": len(Registry.load("policy")),
        "custom_count": len(CustomKnowledgeStore.load_all()),
        "templates_count": len(TemplateStore.load_all()),
    }

