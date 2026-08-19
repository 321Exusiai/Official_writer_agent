"""HTTP 级集成测试：项目 CRUD + 工作流全链路（无 Key 规则版）。"""

import unittest

from fastapi.testclient import TestClient

from writer_studio.backend.main import app

client = TestClient(app)


class TestAPI(unittest.TestCase):
    def test_health(self):
        self.assertEqual(client.get("/api/health").status_code, 200)

    def test_project_crud(self):
        r = client.post("/api/projects", json={"name": "CRUD测试"})
        self.assertEqual(r.status_code, 201)
        pid = r.json()["id"]
        self.assertIn("proj_", pid)
        lst = client.get("/api/projects").json()
        self.assertTrue(any(p["id"] == pid for p in lst))
        client.delete(f"/api/projects/{pid}")
        lst = client.get("/api/projects").json()
        self.assertFalse(any(p["id"] == pid for p in lst))

    def test_full_workflow_http(self):
        pid = client.post("/api/projects", json={"name": "流程测试"}).json()["id"]
        try:
            client.post(f"/api/projects/{pid}/workflow/start")
            client.post(f"/api/projects/{pid}/workflow/answer", json={"text": "1"})  # 内部行政
            client.post(f"/api/projects/{pid}/workflow/answer", json={"text": "1"})  # 下行文
            for ans in ["根据上级要求", "部署安全检查工作", "各二级单位", "通知"]:
                client.post(f"/api/projects/{pid}/workflow/answer", json={"text": ans})
            r = client.post(f"/api/projects/{pid}/workflow/confirm")
            self.assertEqual(r.status_code, 200)
            r = client.post(f"/api/projects/{pid}/workflow/review")
            self.assertEqual(r.status_code, 200)
            self.assertIn("score", r.json())
            r = client.post(f"/api/projects/{pid}/workflow/finalize")
            self.assertEqual(r.status_code, 200)
            st = client.get(f"/api/projects/{pid}/workflow/state").json()
            self.assertEqual(st["state"], "completed")
        finally:
            client.delete(f"/api/projects/{pid}")


if __name__ == "__main__":
    unittest.main()
