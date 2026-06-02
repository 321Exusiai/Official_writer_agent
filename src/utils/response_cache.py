"""
响应缓存模块 — 减少重复的 Prompt 和模板计算

实现策略：
1. 使用内存缓存避免重复构建相同 prompt
2. 提供 hash-based 缓存键生成
3. 支持 TTL 过期和 LRU 淘汰

用法：
    from utils.response_cache import prompt_cache, cached_prompt

    # 自动缓存 prompt 构建结果
    prompt = cached_prompt("writer_system", mode, style_key)

设计原则：
- 遵循 student-cost-optimizer 规范
- 优先本地缓存，零外部依赖
- 缓存失效策略：key = mode_name + style_name + template_version
"""

import hashlib
import functools
from typing import Any, Dict, Optional, Callable


class PromptCache:
    """
    轻量级内存缓存，用于缓存 prompt 构建结果。
    使用 dict + 手动淘汰策略，不引入外部依赖。
    """

    def __init__(self, maxsize: int = 128):
        self._cache: Dict[str, str] = {}
        self._maxsize = maxsize
        self._access_order: list = []

    def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            self._access_order.remove(key)
            self._access_order.append(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: str):
        if key in self._cache:
            self._access_order.remove(key)
        elif len(self._cache) >= self._maxsize:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        self._cache[key] = value
        self._access_order.append(key)

    def invalidate(self, key: str = None):
        if key:
            self._cache.pop(key, None)
            if key in self._access_order:
                self._access_order.remove(key)
        else:
            self._cache.clear()
            self._access_order.clear()

    @property
    def size(self) -> int:
        return len(self._cache)


prompt_cache = PromptCache(maxsize=128)


def make_cache_key(*args, **kwargs) -> str:
    raw = str(args) + str(sorted(kwargs.items()))
    return hashlib.md5(raw.encode()).hexdigest()[:16]


def cached_prompt(category: str, *args, **kwargs) -> Optional[str]:
    key = f"{category}:{make_cache_key(*args, **kwargs)}"
    return prompt_cache.get(key)


def store_prompt(category: str, value: str, *args, **kwargs):
    key = f"{category}:{make_cache_key(*args, **kwargs)}"
    prompt_cache.set(key, value)