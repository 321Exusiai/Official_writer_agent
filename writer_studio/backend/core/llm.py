"""LLM 客户端 —— httpx 调用 + 重试 + JSON 解析 + 诚实降级。

available=False（未配置 Key）时所有调用返回 None，调用方走规则降级并标注 mode="rule"。
"""
import json

import httpx

from ..domain.schemas import LLMConfig


def _parse_json(raw: str):
    """从 LLM 输出提取 JSON 对象，失败返回 None。"""
    if not raw:
        return None
    text = raw.strip()
    if "```json" in text:
        text = text.split("```json")[1].split("```")[0].strip()
    elif "```" in text:
        text = text.split("```")[1].split("```")[0].strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None


class LLMClient:
    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig()
        self._client = httpx.Client(timeout=60.0)

    @property
    def available(self) -> bool:
        c = self.config
        return bool(c.enabled and c.api_key and c.api_base and c.model)

    def chat(self, system, user, temperature=None, max_tokens=None):
        """返回 LLM 文本；未配置/失败返回 None（调用方降级）。"""
        if not self.available:
            return None
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature if temperature is None else temperature,
            "max_tokens": self.config.max_tokens if max_tokens is None else max_tokens,
        }
        url = self.config.api_base.rstrip("/") + "/chat/completions"
        for _ in range(3):
            try:
                resp = self._client.post(
                    url, json=payload,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
                    return None
                if resp.status_code in (401, 403, 404):
                    return None
                # 429 / 5xx 走下一轮重试
            except httpx.HTTPError:
                pass
        return None

    def chat_json(self, system, user, temperature=None):
        """要求 LLM 输出 JSON 对象，解析失败返回 None。"""
        raw = self.chat(system, user, temperature=temperature)
        return _parse_json(raw) if raw else None

    def close(self):
        self._client.close()
