"""
LLM API 配置模块

支持：
1. 多种 LLM 提供商（OpenAI、通义千问、DeepSeek、Claude、本地部署等）
2. 多 API 配置管理（添加/切换/删除多个 API）
3. 配置持久化（保存到本地 JSON 文件）
4. API 连接测试
5. 默认配置模板
"""

import json
import os
from typing import Dict, List, Optional, Any
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
    name: str = "默认配置"
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
            "name": self.name,
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
    """多 API 配置管理器"""

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = Path(config_path) if config_path else CONFIG_FILE
        self.configs: List[LLMConfig] = []
        self._active_index: int = 0
        self._load()

    @property
    def config(self) -> LLMConfig:
        """当前激活的配置"""
        if not self.configs:
            self.configs.append(LLMConfig())
        if self._active_index >= len(self.configs):
            self._active_index = 0
        return self.configs[self._active_index]

    @property
    def active_index(self) -> int:
        return self._active_index

    def get_all_configs(self) -> List[LLMConfig]:
        return self.configs

    def switch_to(self, index: int) -> LLMConfig:
        """切换到指定配置"""
        if 0 <= index < len(self.configs):
            self._active_index = index
            self.save()
        return self.config

    def add_config(self, name: str = "", provider: str = "openai") -> LLMConfig:
        """添加新配置"""
        cfg = LLMConfig(name=name or f"配置 {len(self.configs) + 1}", provider=provider)
        if provider in DEFAULT_CONFIGS:
            tpl = DEFAULT_CONFIGS[provider]
            cfg.api_base = tpl["api_base"]
            cfg.model = tpl["model"]
            cfg.api_key = tpl["api_key"]
        self.configs.append(cfg)
        self._active_index = len(self.configs) - 1
        self.save()
        return cfg

    def delete_config(self, index: int) -> bool:
        """删除指定配置"""
        if 0 <= index < len(self.configs) and len(self.configs) > 1:
            self.configs.pop(index)
            if self._active_index >= len(self.configs):
                self._active_index = len(self.configs) - 1
            self.save()
            return True
        return False

    def _load(self):
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    self.configs = [LLMConfig.from_dict(d) for d in data]
                elif isinstance(data, dict):
                    # 兼容旧版单配置格式
                    self.configs = [LLMConfig.from_dict(data)]
                if not self.configs:
                    self.configs = [LLMConfig()]
            except Exception:
                self.configs = [LLMConfig()]
        else:
            self.configs = [LLMConfig()]

    def save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump([c.to_dict() for c in self.configs], f, ensure_ascii=False, indent=2)

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

    def test_connection(self, config: LLMConfig = None) -> Dict[str, Any]:
        """
        测试 API 连接（带重试 + 分类错误处理）

        改进：
          - 重试机制（最多 2 次，指数退避）
          - 响应格式验证
          - 分类错误（超时/认证/限流/服务器/网络）
          - 返回结构化结果
        """
        cfg = config or self.config
        if not cfg.api_key:
            return {"success": False, "message": "API Key 为空，请先填写"}
        if not cfg.api_base:
            return {"success": False, "message": "API Base URL 为空，请先填写"}
        if not cfg.model:
            return {"success": False, "message": "模型名称为空，请先填写"}

        import time

        max_retries = 2
        last_error: str = ""

        for attempt in range(max_retries):
            try:
                import requests
                headers = {"Authorization": f"Bearer {cfg.api_key}", "Content-Type": "application/json"}
                payload = {
                    "model": cfg.model,
                    "messages": [{"role": "user", "content": "回复OK"}],
                    "max_tokens": 10,
                }
                url = cfg.api_base.rstrip("/") + "/chat/completions"
                response = requests.post(url, headers=headers, json=payload, timeout=min(cfg.timeout, 30))

                # 分类 HTTP 状态码
                if response.status_code == 401:
                    return {"success": False, "message": "API Key 无效或已过期，请检查密钥"}
                if response.status_code == 403:
                    return {"success": False, "message": "API Key 无权限访问该模型，请检查账户权限"}
                if response.status_code == 404:
                    return {"success": False, "message": "端点不存在，请检查 API Base URL 或模型名称"}
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        time.sleep(5)
                        continue
                    return {"success": False, "message": "请求频率过高，请稍后重试"}
                if response.status_code >= 500:
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    return {"success": False, "message": "API 服务器内部错误，请稍后重试"}

                response.raise_for_status()

                # 响应格式验证
                data = response.json()
                choices = data.get("choices", [])
                if not choices:
                    return {"success": False, "message": "API 返回格式异常：缺少 choices 字段"}

                content = choices[0].get("message", {}).get("content", "")
                if not content:
                    return {"success": False, "message": "API 返回内容为空，模型可能未正确响应"}

                return {"success": True, "message": f"连接成功，模型响应正常：{content[:30]}"}

            except requests.exceptions.Timeout:
                last_error = "请求超时，请检查网络或增加超时时间"
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            except requests.exceptions.ConnectionError:
                last_error = "无法连接到 API 服务器，请检查网络或 Base URL"
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
            except json.JSONDecodeError:
                return {"success": False, "message": "API 返回的数据格式异常（非有效 JSON），可能 Base URL 错误"}
            except Exception as e:
                error_msg = str(e)
                if "401" in error_msg or "unauthorized" in error_msg.lower():
                    return {"success": False, "message": "API Key 无效或已过期"}
                if "403" in error_msg:
                    return {"success": False, "message": "API Key 无权限访问"}
                if "429" in error_msg:
                    return {"success": False, "message": "请求频率过高，请稍后重试"}
                last_error = f"连接失败：{error_msg[:100]}"
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue

        return {"success": False, "message": last_error}

    def is_enabled(self) -> bool:
        return self.config.enable and bool(self.config.api_key) and bool(self.config.api_base)
