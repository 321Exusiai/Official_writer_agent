"""完整备份 / 恢复 —— 全量导出所有本地数据（项目 + 画像 + 配置 + 密钥）。

- 导出：GET /backup/export → 单个 JSON（含 schema_version 与导出时间）。
- 恢复：POST /backup/import ← 备份 JSON，原子写回三个数据文件并重置密钥缓存。
- 前端入口：设置面板「备份与恢复」。
"""

import json
import os
import time
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..storage import crypto
from .projects import store

router = APIRouter(tags=["backup"])

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
APP_NAME = "writer_studio"
BACKUP_VERSION = 1

_FILES = ("projects.json", "profile.json", "llm_config.json")


@router.get("/backup/export")
def export_backup():
    """全量导出：projects + profile + llm_config（密文）+ 加密密钥。"""
    payload = {
        "app": APP_NAME,
        "version": BACKUP_VERSION,
        "exported_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "data": {},
    }
    for name in _FILES:
        path = DATA_DIR / name
        payload["data"][name] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    # 密钥一并导出，保证恢复后密文可解密
    if crypto.KEY_PATH.exists():
        payload["data"][".secret.key"] = crypto.KEY_PATH.read_text(encoding="utf-8")
    return payload


class ImportBody(BaseModel):
    backup: dict


@router.post("/backup/import")
def import_backup(body: ImportBody):
    """恢复备份：校验来源后原子写回，重置内存缓存与密钥。"""
    backup = body.backup
    if backup.get("app") != APP_NAME:
        raise HTTPException(400, "不是本应用的备份文件")
    data = backup.get("data") or {}
    # 1) 密钥最先恢复（后续写回的内容含密文，需用备份的密钥解密）
    if data.get(".secret.key"):
        try:
            crypto.reset_key(data[".secret.key"].encode("utf-8"))
        except Exception as e:
            raise HTTPException(400, f"密钥恢复失败：{e}") from e
    # 2) 原子写回各数据文件
    for name in _FILES:
        if name not in data:
            continue
        path = DATA_DIR / name
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(data[name], ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, path)
    # 3) 重置内存缓存（Store 单例重载；配置/画像每次读取都走文件，无需额外处理）
    store.reload()
    return {"restored": True, "exported_at": backup.get("exported_at", ""), "files": list(data.keys())}
