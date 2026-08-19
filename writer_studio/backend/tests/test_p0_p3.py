"""P0 安全 + P3 工程测试：密钥加密 / schema 迁移 / 备份恢复 / list 精简。"""

import json
import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from writer_studio.backend.main import app
from writer_studio.backend.storage import crypto
from writer_studio.backend.storage.schema import (
    CURRENT_CONFIG_VERSION,
    CURRENT_PROFILE_VERSION,
    CURRENT_PROJECTS_VERSION,
    migrate_config,
    migrate_profile,
    migrate_projects,
)
from writer_studio.backend.storage.store import Store

client = TestClient(app)


class TestCrypto(unittest.TestCase):
    def test_roundtrip(self):
        token = crypto.encrypt("sk-secret-123")
        self.assertTrue(crypto.is_encrypted(token))
        self.assertEqual(crypto.decrypt(token), "sk-secret-123")

    def test_ensure_encrypted_idempotent(self):
        token = crypto.ensure_encrypted("abc")
        self.assertEqual(crypto.ensure_encrypted(token), token)

    def test_plaintext_passthrough(self):
        self.assertEqual(crypto.decrypt("plain-not-token"), "plain-not-token")
        self.assertEqual(crypto.decrypt(""), "")

    def test_reset_key(self):
        # 用临时 key 路径验证 reset，避免污染真实密钥
        orig_path = crypto.KEY_PATH
        orig_key = crypto.KEY_PATH.read_bytes() if crypto.KEY_PATH.exists() else None
        fd, path = tempfile.mkstemp(suffix=".key")
        os.close(fd)
        try:
            crypto.KEY_PATH = Path(path)
            new_key = b"A" * 44
            crypto.reset_key(new_key)
            self.assertEqual(crypto.KEY_PATH.read_bytes(), new_key)
        finally:
            crypto.KEY_PATH = orig_path
            if orig_key is not None:
                crypto.reset_key(orig_key)
            else:
                crypto._FERNET = None


class TestSchemaMigration(unittest.TestCase):
    def test_projects_v0_top_level(self):
        raw = {"proj_1": {"id": "proj_1", "name": "旧项目"}}
        out = migrate_projects(raw)
        self.assertEqual(out["schema_version"], CURRENT_PROJECTS_VERSION)
        self.assertEqual(out["projects"]["proj_1"]["name"], "旧项目")

    def test_projects_v1(self):
        raw = {"schema_version": 1, "proj_1": {"id": "proj_1", "name": "x"}}
        out = migrate_projects(raw)
        self.assertEqual(out["schema_version"], CURRENT_PROJECTS_VERSION)
        self.assertIn("projects", out)

    def test_projects_already_current(self):
        raw = {"schema_version": CURRENT_PROJECTS_VERSION, "projects": {}}
        self.assertIs(migrate_projects(raw), raw)

    def test_profile_adds_version(self):
        out = migrate_profile({"preferences": ["喜欢短句"]})
        self.assertEqual(out["schema_version"], CURRENT_PROFILE_VERSION)
        self.assertEqual(out["preferences"], ["喜欢短句"])

    def test_config_adds_version(self):
        out = migrate_config({"configs": [], "active_index": 0})
        self.assertEqual(out["schema_version"], CURRENT_CONFIG_VERSION)


class TestBackup(unittest.TestCase):
    def setUp(self):
        # 隔离：backup 模块指向临时目录与临时 Store，绝不触碰真实数据
        import writer_studio.backend.api.backup as backup_mod

        self.tmpdir = Path(tempfile.mkdtemp())
        self._orig_dir = backup_mod.DATA_DIR
        self._orig_store = backup_mod.store
        backup_mod.DATA_DIR = self.tmpdir
        backup_mod.store = Store(self.tmpdir / "projects.json")
        # 放一个画像文件供导出
        (self.tmpdir / "profile.json").write_text(
            json.dumps({"schema_version": 1, "preferences": []}), encoding="utf-8"
        )
        self.backup_mod = backup_mod

    def tearDown(self):
        self.backup_mod.DATA_DIR = self._orig_dir
        self.backup_mod.store = self._orig_store

    def test_export_shape(self):
        r = client.get("/api/backup/export")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertEqual(d["app"], "writer_studio")
        self.assertIn("projects.json", d["data"])
        self.assertIn("profile.json", d["data"])
        self.assertIn("exported_at", d)

    def test_import_restores(self):
        backup = {
            "app": "writer_studio",
            "version": 1,
            "exported_at": "2026-01-01 00:00:00",
            "data": {
                "projects.json": {
                    "schema_version": 2,
                    "projects": {"proj_a": {"id": "proj_a", "name": "恢复的项目"}},
                },
                "profile.json": {"schema_version": 1, "preferences": ["喜欢短句"]},
            },
        }
        r = client.post("/api/backup/import", json={"backup": backup})
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()["restored"])
        # 临时 Store 应重载出恢复的项目
        self.assertIn("proj_a", self.backup_mod.store.projects)

    def test_import_wrong_app(self):
        r = client.post("/api/backup/import", json={"backup": {"app": "other", "data": {}}})
        self.assertEqual(r.status_code, 400)


class TestListSlim(unittest.TestCase):
    def test_list_returns_summary_not_full(self):
        pid = client.post("/api/projects", json={"name": "精简列表测试"}).json()["id"]
        try:
            lst = client.get("/api/projects").json()
            item = next(p for p in lst if p["id"] == pid)
            self.assertIn("ref_count", item)
            self.assertIn("has_draft", item)
            self.assertNotIn("draft", item)
            self.assertNotIn("references", item)
            # full=1 返回全量
            full = client.get("/api/projects?full=1").json()
            item_full = next(p for p in full if p["id"] == pid)
            self.assertEqual(item_full["id"], pid)
        finally:
            client.delete(f"/api/projects/{pid}")


if __name__ == "__main__":
    unittest.main()
