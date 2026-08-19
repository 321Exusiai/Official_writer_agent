"""API Key 加密存储 —— Fernet 对称加密落盘。

- 密钥保存在 data/.secret.key（首次生成，尽量收紧权限）。
- 落盘值均为 Fernet token（gAAAA... 开头）；内存/LLMClient 中使用解密后的明文。
- 对未加密的旧数据（明文 key）自动透传解密，保存时统一加密。
"""

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
KEY_PATH = DATA_DIR / ".secret.key"

_FERNET = None


def _fernet() -> Fernet:
    global _FERNET
    if _FERNET is None:
        _FERNET = Fernet(_load_or_create_key())
    return _FERNET


def _load_or_create_key() -> bytes:
    if KEY_PATH.exists():
        return KEY_PATH.read_bytes()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    key = Fernet.generate_key()
    KEY_PATH.write_bytes(key)
    try:
        os.chmod(KEY_PATH, 0o600)
    except OSError:
        pass
    return key


def is_encrypted(value: str) -> bool:
    """判断是否已是 Fernet token。"""
    return bool(value) and value.startswith("gAAAA")


def encrypt(plain: str) -> str:
    """明文 → 密文；空串原样返回。"""
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt(token: str) -> str:
    """密文 → 明文；明文/空串透传；解密失败（密钥变更等）返回原值并留待人工处理。"""
    if not token or not is_encrypted(token):
        return token
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except (InvalidToken, ValueError):
        return token


def ensure_encrypted(value: str) -> str:
    """幂等加密：已是密文则原样返回，否则加密。"""
    if not value or is_encrypted(value):
        return value
    return encrypt(value)


def ensure_decrypted(value: str) -> str:
    """幂等解密：明文原样返回，密文解密。"""
    return decrypt(value)


def reset_key(key_bytes: bytes):
    """恢复备份后重置密钥与缓存（供 backup/import 使用）。"""
    global _FERNET
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    KEY_PATH.write_bytes(key_bytes)
    try:
        os.chmod(KEY_PATH, 0o600)
    except OSError:
        pass
    _FERNET = None
