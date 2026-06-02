"""
LLM API 配置模块

支持：
1. 多种 LLM 提供商（OpenAI、通义千问、DeepSeek、Claude、本地部署等）
2. 配置持久化（保存到本地 JSON 文件）
3. API 连接测试
4. 默认配置模板
"""

import json
import os
from typing import Dict, Optional, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path

SUPPORTED_PROVIDERS = {
    "openai": "OpenAI (GPT-4/3.5)",
    "dashscope": "通义千问 (Qwen)",
    "deepseek": "DeepSeek",
    "zhipu": "智谱 AI (GLM)",
    "anthropic": "Anthropic (Claude)",
    "local": "本地部署 (Ollama/vLLM)",
}

DEFAULT_CONFIGS = {
    "openai": {
        "api_base": "https://api.openai.com/v1",
        "model": "gpt-4o",
        "api_key": "",
    },
    "dashscope": {
        "api_base": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
        "api_key": "",
    },
    "deepseek": {
        "api_base": "https://api.deepseek.com/v1",
        "model": "deepseek-chat",
        "api_key": "",
    },
    "zhipu": {
        "api_base": "https://open.bigmodel.cn/api/paas/v4",
        "model": "glm-4-plus",
        "api_key": "",
    },
    "anthropic": {
        "api_base": "https://api.anthropic.com",
        "model": "claude-sonnet-4-20250514",
        "api_key": "",
    },
    "local": {
        "api_base": "http://localhost:11434/v1",
        "model": "qwen2.5:32b",
        "api_key": "ollama",
    },
}


@dataclass
class LLMConfig:
    provider: str = "openai"
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    temperature: float = 0.7
    max_tokens: int = 8000
    timeout: int = 60
    enable: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> "LLMConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "api_base": self.api_base,
            "api_key": self.api_key,
            "model": self.model,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
            "timeout": self.timeout,
            "enable": self.enable,
        }


CONFIG_DIR = Path(__file__).parent.parent
CONFIG_FILE = CONFIG_DIR / "api_config.json"


class APIConfigManager:
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else CONFIG_FILE
        self.config = self._load()

    def _load(self) -> LLMConfig:
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return LLMConfig.from_dict(data)
            except Exception:
                pass
        return LLMConfig()

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(self.config.to_dict(), f, ensure_ascii=False, indent=2)

    def apply_provider_template(self, provider: str) -> LLMConfig:
        if provider in DEFAULT_CONFIGS:
            template = DEFAULT_CONFIGS[provider]
            self.config.provider = provider
            self.config.api_base = template["api_base"]
            self.config.model = template["model"]
            if self.config.api_key == "":
                self.config.api_key = template["api_key"]
        return self.config

    def update(self, **kwargs) -> LLMConfig:
        for k, v in kwargs.items():
            if hasattr(self.config, k):
                setattr(self.config, k, v)
        return self.config

    def test_connection(self) -> Dict[str, Any]:
        """测试 API 连接"""
        if not self.config.api_key:
            return {"success": False, "message": "API Key 为空"}
        if not self.config.api_base:
            return {"success": False, "message": "API Base URL 为空"}

        try:
            import requests
            headers = {"Authorization": f"Bearer {self.config.api_key}", "Content-Type": "application/json"}
            payload = {
                "model": self.config.model,
                "messages": [{"role": "user", "content": "回复OK"}],
                "max_tokens": 10,
            }
            url = self.config.api_base.rstrip("/") + "/chat/completions"
            response = requests.post(url, headers=headers, json=payload, timeout=self.config.timeout)
            response.raise_for_status()
            data = response.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            return {"success": True, "message": f"连接成功！模型返回：{content[:30]}"}
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "无法连接到 API 服务器，请检查网络或 Base URL"}
        except requests.exceptions.Timeout:
            return {"success": False, "message": "请求超时，请检查网络或增加超时时间"}
        except Exception as e:
            error_msg = str(e)
            if "401" in error_msg or "unauthorized" in error_msg.lower():
                return {"success": False, "message": "API Key 无效或已过期"}
            if "403" in error_msg:
                return {"success": False, "message": "API Key 无权限访问"}
            if "429" in error_msg:
                return {"success": False, "message": "请求频率过高，请稍后重试"}
            if "500" in error_msg:
                return {"success": False, "message": "API 服务器内部错误"}
            return {"success": False, "message": f"连接失败：{error_msg[:100]}"}

    def is_enabled(self) -> bool:
        return self.config.enable and bool(self.config.api_key) and bool(self.config.api_base)
