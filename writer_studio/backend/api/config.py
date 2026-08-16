"""LLM 多配置管理路由：多 API 配置增删改 + 切换启用 + 快捷模板 + 连通测试。

存储结构 data/llm_config.json：
    {"configs": [LLMConfig...], "active_index": N}
"""
import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.llm import LLMClient
from ..domain.schemas import LLMConfig

router = APIRouter(tags=["config"])
_CONFIG_PATH = Path(__file__).resolve().parent.parent / "data" / "llm_config.json"

# 常用 provider 快捷模板（人性化：一键填入）
PROVIDER_TEMPLATES = {
    "deepseek": {"name": "DeepSeek", "api_base": "https://api.deepseek.com/v1", "model": "deepseek-chat"},
    "qwen": {"name": "通义千问", "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1", "model": "qwen-plus"},
    "openai": {"name": "OpenAI", "api_base": "https://api.openai.com/v1", "model": "gpt-4o-mini"},
    "zhipu": {"name": "智谱 GLM", "api_base": "https://open.bigmodel.cn/api/paas/v4", "model": "glm-4-flash"},
    "ollama": {"name": "本地 Ollama", "api_base": "http://localhost:11434/v1", "model": "qwen2.5:7b"},
}


def load_config_set():
    """返回 (configs: list[dict], active_index: int)。"""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            configs = data.get("configs", [])
            idx = int(data.get("active_index", 0))
            if configs:
                return configs, min(max(idx, 0), len(configs) - 1)
        except Exception:
            pass
    return [LLMConfig(name="DeepSeek", provider="deepseek",
                      api_base="https://api.deepseek.com/v1", model="deepseek-chat").model_dump()], 0


def save_config_set(configs: list, active_index: int):
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"configs": configs, "active_index": active_index}, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _CONFIG_PATH)


def get_active_config() -> LLMConfig:
    configs, idx = load_config_set()
    if not configs:
        return LLMConfig()
    return LLMConfig(**configs[min(idx, len(configs) - 1)])


def get_client() -> LLMClient:
    return LLMClient(get_active_config())


def _mask(key: str) -> str:
    return "••••" + key[-4:] if key else ""


class ConfigBody(BaseModel):
    name: str = "默认配置"
    provider: str = "openai"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000
    enabled: bool = False
    search_provider: str = "tavily"
    search_api_key: str = ""


class SaveConfigBody(ConfigBody):
    index: int = -1  # -1 表示新增（按 name 匹配则更新）


class IndexBody(BaseModel):
    index: int


@router.get("/config")
def get_configs():
    configs, idx = load_config_set()
    masked = []
    for c in configs:
        d = dict(c)
        d["api_key"] = _mask(d.get("api_key", ""))
        d["search_api_key"] = _mask(d.get("search_api_key", ""))
        masked.append(d)
    return {"configs": masked, "active_index": idx, "templates": PROVIDER_TEMPLATES}


@router.post("/config/save")
def save_config(body: SaveConfigBody):
    configs, idx = load_config_set()
    payload = body.model_dump()
    payload.pop("index", None)
    target = body.index
    if target < 0:
        # 新增：按 name 匹配则更新，否则追加
        target = next((i for i, c in enumerate(configs) if c.get("name") == body.name), -1)
    if 0 <= target < len(configs):
        old = configs[target]
        if payload["api_key"].startswith("••••"):
            payload["api_key"] = old.get("api_key", "")
        if payload["search_api_key"].startswith("••••"):
            payload["search_api_key"] = old.get("search_api_key", "")
        configs[target] = payload
    else:
        configs.append(payload)
    save_config_set(configs, idx)
    return {"saved": True, "index": target if 0 <= target < len(configs) - 1 else len(configs) - 1}


@router.post("/config/delete")
def delete_config(body: IndexBody):
    configs, idx = load_config_set()
    if body.index < 0 or body.index >= len(configs) or len(configs) <= 1:
        return {"deleted": False, "message": "至少保留一个配置"}
    configs.pop(body.index)
    if idx > body.index:
        idx -= 1
    if idx >= len(configs):
        idx = len(configs) - 1
    save_config_set(configs, idx)
    return {"deleted": True, "active_index": idx}


@router.post("/config/switch")
def switch_config(body: IndexBody):
    configs, idx = load_config_set()
    if body.index < 0 or body.index >= len(configs):
        return {"switched": False}
    save_config_set(configs, body.index)
    return {"switched": True, "active_index": body.index}


@router.post("/config/test")
def test_config(body: ConfigBody):
    client = LLMClient(LLMConfig(**body.model_dump()))
    if not client.available:
        return {"ok": False, "message": "配置不完整：需 api_base、api_key、model 且 enabled=True"}
    raw = client.chat("你是助手。", "请只回复两个字：正常", max_tokens=10)
    return {"ok": raw is not None, "message": "连接成功" if raw is not None else "连接失败，请检查地址与密钥"}
