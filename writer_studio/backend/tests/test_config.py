"""多 API 配置管理测试。"""

import os
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from writer_studio.backend.api import config as cfg
from writer_studio.backend.main import app

client = TestClient(app)


class TestConfig(unittest.TestCase):
    def setUp(self):
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        self.tmp = Path(path)
        self._orig = cfg._CONFIG_PATH
        cfg._CONFIG_PATH = self.tmp
        cfg.save_config_set([cfg.LLMConfig(name="默认", provider="openai").model_dump()], 0)

    def tearDown(self):
        cfg._CONFIG_PATH = self._orig
        if self.tmp.exists():
            os.unlink(self.tmp)

    def test_get_configs_shape(self):
        r = client.get("/api/config")
        self.assertEqual(r.status_code, 200)
        d = r.json()
        self.assertIn("configs", d)
        self.assertIn("active_index", d)
        self.assertIn("templates", d)

    def test_save_new_and_switch(self):
        r = client.post(
            "/api/config/save",
            json={
                "name": "测试",
                "provider": "deepseek",
                "api_base": "http://x/v1",
                "api_key": "k",
                "model": "m",
                "enabled": True,
            },
        )
        self.assertEqual(r.json()["saved"], True)
        d = client.get("/api/config").json()
        idx = len(d["configs"]) - 1
        self.assertEqual(d["configs"][idx]["name"], "测试")
        r = client.post("/api/config/switch", json={"index": idx})
        self.assertEqual(r.json()["active_index"], idx)

    def test_masked_key(self):
        client.post(
            "/api/config/save",
            json={
                "name": "带key",
                "api_key": "sk-12345678",
                "model": "m",
                "enabled": True,
            },
        )
        d = client.get("/api/config").json()
        masked = [c for c in d["configs"] if c["name"] == "带key"][0]
        self.assertTrue(masked["api_key"].startswith("••••"))

    def test_delete_keeps_at_least_one(self):
        r = client.post("/api/config/delete", json={"index": 0})
        self.assertEqual(r.json()["deleted"], False)  # 仅一个配置，禁止删除


if __name__ == "__main__":
    unittest.main()
