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
def list_doctypes(domain: str = ""):
    items = Registry.filter("doctypes", domain=domain or None)
    return [{"id": d["id"], "name_cn": d["name_cn"], "domain": d["domain"]} for d in items]


@router.get("/knowledge/styles")
def list_styles(domain: str = ""):
    items = Registry.filter("styles", domain=domain or None)
    return [{"id": s["id"], "name": s["name"], "domain": s["domain"]} for s in items]
