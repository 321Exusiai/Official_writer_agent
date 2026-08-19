"""数据 schema 版本化与迁移 —— 所有 JSON 数据文件统一带 schema_version。

版本约定：
- 顶层格式均为 {"schema_version": N, ...}。
- 加载时若缺 schema_version 视为 0（旧版），执行迁移链逐级升到当前版本。
- 迁移必须是纯函数：输入旧结构 dict，输出新结构 dict，绝不修改原对象。
"""

from __future__ import annotations

CURRENT_PROJECTS_VERSION = 2
CURRENT_PROFILE_VERSION = 1
CURRENT_CONFIG_VERSION = 2


# ── projects.json ──
def migrate_projects(raw: dict) -> dict:
    """projects.json 迁移。v0: 顶层直接是 {pid: project}；v1: 包 schema_version；v2: 统一 projects 嵌套。"""
    version = int(raw.get("schema_version", 0))
    if version >= CURRENT_PROJECTS_VERSION:
        return raw
    out = dict(raw)
    # v0 → v1：早期版本顶层就是项目 dict（无 schema_version）
    if version == 0 and "schema_version" not in out:
        out = {"schema_version": 1, **out}
        version = 1
    # v1 → v2：把项目统一收进 projects 键
    if version == 1:
        projects = out.get("projects")
        if not isinstance(projects, dict):
            projects = {k: v for k, v in out.items() if k != "schema_version"}
        return {"schema_version": 2, "projects": projects}
    return out


# ── profile.json ──
def migrate_profile(raw: dict) -> dict:
    """profile.json 迁移：无版本字段 → 补 schema_version=1。"""
    if isinstance(raw, dict) and "schema_version" in raw:
        return raw
    out = dict(raw or {})
    out["schema_version"] = CURRENT_PROFILE_VERSION
    return out


# ── llm_config.json ──
def migrate_config(raw: dict) -> dict:
    """llm_config.json 迁移。v2 起 api_key/search_api_key 为密文（Fernet token）。"""
    version = int(raw.get("schema_version", 0))
    if version >= CURRENT_CONFIG_VERSION:
        return raw
    out = dict(raw)
    out["schema_version"] = CURRENT_CONFIG_VERSION
    return out
