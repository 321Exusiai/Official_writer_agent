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
from typing import Any, Dict, Optional, Callable
from collections import OrderedDict


class PromptCache:
    """
    轻量级内存缓存，用于缓存 prompt 构建结果。
    使用 OrderedDict 实现 LRU 淘汰策略，性能优化：
    - get/set 操作均为 O(1)
    - 避免 list.remove() 的 O(n) 开销
    """

    def __init__(self, maxsize: int = 128):
        self._cache: OrderedDict[str, str] = OrderedDict()
        self._maxsize = maxsize

    def get(self, key: str) -> Optional[str]:
        if key in self._cache:
            # 移动到末尾表示最近使用
            self._cache.move_to_end(key)
            return self._cache[key]
        return None

    def set(self, key: str, value: str):
        if key in self._cache:
            # 更新现有键，移动到末尾
            self._cache.move_to_end(key)
            self._cache[key] = value
        else:
            # 新增键
            if len(self._cache) >= self._maxsize:
                # 淘汰最久未使用的（第一个）
                self._cache.popitem(last=False)
            self._cache[key] = value

    def invalidate(self, key: str = None):
        if key:
            self._cache.pop(key, None)
        else:
            self._cache.clear()

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