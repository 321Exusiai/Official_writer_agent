"""LLM 配置路由：读写配置 + 连通性测试（API Key 脱敏返回）。"""
import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.llm import LLMClient
from ..domain.schemas import LLMConfig

router = APIRouter(tags=["config"])
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "llm_config.json"


def load_config() -> LLMConfig:
    if _CONFIG_PATH.exists():
        try:
            return LLMConfig(**json.loads(_CONFIG_PATH.read_text(encoding="utf-8")))
        except Exception:
            pass
    return LLMConfig()


def save_config(cfg: LLMConfig):
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(cfg.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _CONFIG_PATH)


def get_client() -> LLMClient:
    return LLMClient(load_config())


class ConfigBody(BaseModel):
    provider: str = "openai"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000
    enabled: bool = False


@router.get("/config")
def get_config():
    cfg = load_config()
    d = cfg.model_dump()
    if d.get("api_key"):
        d["api_key"] = "••••" + d["api_key"][-4:]  # 脱敏
    return d


@router.post("/config")
def set_config(body: ConfigBody):
    cfg = load_config()
    payload = body.model_dump()
    if payload["api_key"].startswith("••••"):
        payload["api_key"] = cfg.api_key  # 保留原 key（用户未重填）
    for k, v in payload.items():
        setattr(cfg, k, v)
    save_config(cfg)
    return {"saved": True}


@router.post("/config/test")
def test_config(body: ConfigBody):
    client = LLMClient(LLMConfig(**body.model_dump()))
    if not client.available:
        return {"ok": False, "message": "配置不完整：需 api_base、api_key、model 且 enabled=True"}
    raw = client.chat("你是助手。", "请只回复两个字：正常", max_tokens=10)
    return {"ok": raw is not None, "message": "连接成功" if raw is not None else "连接失败，请检查地址与密钥"}
