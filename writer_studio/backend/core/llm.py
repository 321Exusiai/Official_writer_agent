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
                data = json.loads(text[start : end + 1])
                return data if isinstance(data, dict) else None
            except json.JSONDecodeError:
                return None
        return None


def adaptive_temperature(mode: str, doc_type: str = "", stage: str = "draft", base_temp: float = 0.7) -> float:
    """根据写作模式、文种严谨度与流程阶段自适应决定采样温度，消除一刀切采样。"""
    if stage in ("review", "diagnose"):
        return 0.05  # 审查诊断需极度严谨确定，杜绝随机幻觉
    if stage == "consult":
        return 0.20  # 角色协商需逻辑严谨并保持专业针对性

    # 起草阶段：按文种与模式特性自适应
    if mode == "administrative":
        return 0.15  # 行政公文（请示/通知/批复/函）：严格合规无幻觉
    if mode == "objective_report":
        return 0.20  # 客观报告（调研/通报/述职）：事实数据严谨
    if mode == "informational":
        return 0.40  # 资讯快讯（新闻/报道）：平实准确略带生动
    if mode == "strategic_narrative":
        return 0.65  # 战略叙事与特写通讯：高立意叙事与情感张力
    if mode == "youth_engagement":
        return 0.70  # 年轻态与活动推文：活泼生动与高互动感

    # 兜底微调
    return max(0.1, min(1.0, base_temp))


class LLMClient:
    def __init__(self, config: LLMConfig = None):
        self.config = config or LLMConfig()
        self._client = httpx.Client(timeout=60.0)
        self.last_error: str = ""

    @property
    def available(self) -> bool:
        c = self.config
        return bool(c.enabled and c.api_key and c.api_base and c.model)

    def chat(self, system, user, temperature=None, max_tokens=None):
        """返回 LLM 文本；未配置/失败返回 None（调用方降级）。"""
        self.last_error = ""
        if not self.available:
            self.last_error = "LLM 未启用或配置不完整（需 api_key / api_base / model）"
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
        for attempt in range(3):
            try:
                resp = self._client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    choices = data.get("choices") or []
                    if choices:
                        content = choices[0].get("message", {}).get("content", "")
                        if content:
                            return content.strip()
                    self.last_error = "LLM 返回成功但内容为空"
                    return None
                if resp.status_code in (401, 403):
                    self.last_error = f"鉴权失败 (HTTP {resp.status_code})：请检查 API Key"
                    return None
                if resp.status_code == 404:
                    self.last_error = f"接口地址或模型未找到 (HTTP 404)：{self.config.api_base} / {self.config.model}"
                    return None
                if resp.status_code == 429:
                    self.last_error = f"请求过频 (HTTP 429 Rate Limit)，重试中 ({attempt + 1}/3)"
                else:
                    self.last_error = f"LLM 请求异常 (HTTP {resp.status_code})：{resp.text[:120]}"
            except httpx.TimeoutException:
                self.last_error = f"请求超时 (60s)，重试中 ({attempt + 1}/3)"
            except httpx.HTTPError as e:
                self.last_error = f"网络请求失败：{e}"
        return None

    def chat_stream(self, system, user, temperature=None, max_tokens=None):
        """流式生成器：Token-by-Token 实时产出文本片段。"""
        self.last_error = ""
        if not self.available:
            self.last_error = "LLM 未启用或配置不完整"
            return
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature if temperature is None else temperature,
            "max_tokens": self.config.max_tokens if max_tokens is None else max_tokens,
            "stream": True,
        }
        url = self.config.api_base.rstrip("/") + "/chat/completions"
        try:
            with self._client.stream("POST", url, json=payload, headers={"Authorization": f"Bearer {self.config.api_key}"}) as resp:
                if resp.status_code != 200:
                    self.last_error = f"流式请求异常 (HTTP {resp.status_code})"
                    return
                for line in resp.iter_lines():
                    if not line:
                        continue
                    line_str = line.decode("utf-8") if isinstance(line, bytes) else line
                    if line_str.startswith("data: "):
                        data_part = line_str[6:].strip()
                        if data_part == "[DONE]":
                            break
                        try:
                            chunk_data = json.loads(data_part)
                            delta = (chunk_data.get("choices") or [{}])[0].get("delta", {})
                            content = delta.get("content", "")
                            if content:
                                yield content
                        except json.JSONDecodeError:
                            pass
        except Exception as e:
            self.last_error = f"流式传输中断：{e}"

    def chat_json(self, system, user, temperature=None):
        """要求 LLM 输出 JSON 对象（原生 json_object + 正则清洗双重保障）。"""
        self.last_error = ""
        if not self.available:
            return None
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": self.config.temperature if temperature is None else temperature,
            "max_tokens": self.config.max_tokens,
            "response_format": {"type": "json_object"},
        }
        url = self.config.api_base.rstrip("/") + "/chat/completions"
        try:
            resp = self._client.post(
                url,
                json=payload,
                headers={"Authorization": f"Bearer {self.config.api_key}"},
            )
            if resp.status_code == 200:
                data = resp.json()
                choices = data.get("choices") or []
                if choices:
                    content = choices[0].get("message", {}).get("content", "")
                    if content:
                        parsed = _parse_json(content)
                        if parsed:
                            return parsed
        except Exception:
            pass
        # 兼容降级调用常规 chat 并解析
        raw = self.chat(system, user, temperature=temperature)
        return _parse_json(raw) if raw else None

    def chat_with_tools(self, system, user, tools, executor, max_rounds=3):
        """LLM 自主工具调用闭环（OpenAI 兼容 function calling）。

        tools: [{name, description, parameters(json schema)}]
        executor: callable(tool_name, args_dict) -> str，执行工具返回结果文本。
        返回最终文本；未配置/失败返回 None（调用方降级）。
        """
        if not self.available:
            return None
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        url = self.config.api_base.rstrip("/") + "/chat/completions"
        for _ in range(max_rounds):
            payload = {
                "model": self.config.model,
                "messages": messages,
                "temperature": self.config.temperature,
                "max_tokens": self.config.max_tokens,
                "tools": tools,
                "tool_choice": "auto",
            }
            try:
                resp = self._client.post(
                    url,
                    json=payload,
                    headers={"Authorization": f"Bearer {self.config.api_key}"},
                )
                if resp.status_code != 200:
                    return None
                data = resp.json()
                msg = (data.get("choices") or [{}])[0].get("message", {})
            except httpx.HTTPError:
                return None

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                return msg.get("content")

            messages.append(msg)
            for tc in tool_calls:
                fn = tc.get("function", {})
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except json.JSONDecodeError:
                    args = {}
                result = executor(name, args) or ""
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": tc.get("id", ""),
                        "content": result,
                    }
                )
        return None

    def close(self):
        self._client.close()
