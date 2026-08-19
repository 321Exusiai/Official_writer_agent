"""LLM 双轨配置管理路由：主 API 多配置 + 辅助轨道（免费 GLM-4-Flash）。

存储结构 data/llm_config.json：
    {"configs": [LLMConfig...], "active_index": N, "assistant": AssistantConfig}
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from ..core.llm import LLMClient
from ..domain.schemas import AssistantConfig, LLMConfig
from ..storage import crypto

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
    """返回 (configs: list[dict], active_index: int)。

    读取时先做 schema 迁移，再解密 key（内存为明文，供 LLMClient 使用）。
    """
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            from ..storage.schema import CURRENT_CONFIG_VERSION, migrate_config

            migrated = migrate_config(data)
            configs = migrated.get("configs", [])
            idx = int(migrated.get("active_index", 0))
            if configs:
                # 旧版（含明文 key）→ 立即加密落盘，杜绝明文滞留
                if int(data.get("schema_version", 0)) < CURRENT_CONFIG_VERSION:
                    _migrate_persist(migrated)
                return _decrypt_configs(configs), min(max(idx, 0), len(configs) - 1)
        except Exception:
            pass
    return [
        LLMConfig(
            name="DeepSeek", provider="deepseek", api_base="https://api.deepseek.com/v1", model="deepseek-chat"
        ).model_dump()
    ], 0


def _migrate_persist(data: dict):
    """把迁移后的配置（明文 key）加密落盘。"""
    try:
        configs = data.get("configs", [])
        save_config_set(configs, int(data.get("active_index", 0)), data.get("assistant"))
    except Exception:
        pass


def _decrypt_configs(configs: list) -> list:
    """解密一批配置的 api_key / search_api_key（密文→明文）。"""
    out = []
    for c in configs:
        d = dict(c)
        for k in ("api_key", "search_api_key"):
            if d.get(k):
                d[k] = crypto.decrypt(d[k])
        out.append(d)
    return out


def _encrypt_configs(configs: list) -> list:
    """加密一批配置的 api_key / search_api_key（明文→密文，幂等）。"""
    out = []
    for c in configs:
        d = dict(c)
        for k in ("api_key", "search_api_key"):
            if d.get(k):
                d[k] = crypto.ensure_encrypted(d[k])
        out.append(d)
    return out


def save_config_set(configs: list, active_index: int, assistant: dict = None):
    payload = {"schema_version": 2, "configs": _encrypt_configs(configs), "active_index": active_index}
    if assistant is not None:
        payload["assistant"] = dict(assistant)
        if payload["assistant"].get("api_key"):
            payload["assistant"]["api_key"] = crypto.ensure_encrypted(payload["assistant"]["api_key"])
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = _CONFIG_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _CONFIG_PATH)


def load_assistant_config() -> AssistantConfig:
    """读取辅助轨道配置（免费 GLM-4-Flash），key 解密为明文。"""
    if _CONFIG_PATH.exists():
        try:
            data = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
            from ..storage.schema import migrate_config

            data = migrate_config(data)
            a = data.get("assistant")
            if a:
                a = dict(a)
                if a.get("api_key"):
                    a["api_key"] = crypto.decrypt(a["api_key"])
                return AssistantConfig(**a)
        except Exception:
            pass
    return AssistantConfig()


def get_active_config() -> LLMConfig:
    configs, idx = load_config_set()
    if not configs:
        return LLMConfig()
    return LLMConfig(**configs[min(idx, len(configs) - 1)])


def get_client() -> LLMClient:
    return LLMClient(get_active_config())


def get_assistant_client() -> LLMClient:
    """辅助轨道客户端（轻任务：资料整理/画像/协商/工具决策）。"""
    return LLMClient(load_assistant_config())


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


class AssistantBody(BaseModel):
    enabled: bool = False
    provider: str = "zhipu"
    api_base: str = "https://open.bigmodel.cn/api/paas/v4"
    api_key: str = ""
    model: str = "glm-4-flash"
    temperature: float = 0.3
    max_tokens: int = 2000


@router.get("/config")
def get_configs():
    configs, idx = load_config_set()
    masked = []
    for c in configs:
        d = dict(c)
        d["api_key"] = _mask(d.get("api_key", ""))
        d["search_api_key"] = _mask(d.get("search_api_key", ""))
        masked.append(d)
    assistant = load_assistant_config().model_dump()
    if assistant.get("api_key"):
        assistant["api_key"] = _mask(assistant["api_key"])
    return {"configs": masked, "active_index": idx, "templates": PROVIDER_TEMPLATES, "assistant": assistant}


@router.post("/config/assistant")
def save_assistant(body: AssistantBody):
    """保存辅助轨道配置（免费 GLM-4-Flash）。"""
    cfg = load_assistant_config()
    payload = body.model_dump()
    if payload["api_key"].startswith("••••"):
        payload["api_key"] = cfg.api_key
    assistant = AssistantConfig(**payload)
    configs, idx = load_config_set()
    save_config_set(configs, idx, assistant.model_dump())
    return {"saved": True, "enabled": assistant.enabled, "model": assistant.model}


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
