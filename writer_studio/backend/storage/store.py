"""本地 JSON 持久化（原子写 tmp + os.replace）。"""
import json
import os
import time
import uuid
from pathlib import Path

from ..domain.schemas import Project, ProjectStatus

DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class Store:
    def __init__(self, path=None):
        self.path = Path(path) if path else DATA_DIR / "projects.json"
        self.projects: dict = {}
        self._load()

    def _load(self):
        if self.path.exists():
            raw = json.loads(self.path.read_text(encoding="utf-8"))
            self.projects = {k: Project(**v) for k, v in raw.items()}

    def _save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".json.tmp")
        payload = json.dumps(
            {k: v.model_dump() for k, v in self.projects.items()},
            ensure_ascii=False, indent=2,
        )
        tmp.write_text(payload, encoding="utf-8")
        os.replace(tmp, self.path)

    def create_project(self, name: str, description: str = "") -> Project:
        pid = f"proj_{uuid.uuid4().hex[:8]}"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        p = Project(id=pid, name=name, description=description, created_at=now, updated_at=now)
        self.projects[pid] = p
        self._save()
        return p

    def get_project(self, pid: str):
        return self.projects.get(pid)

    def list_projects(self):
        return list(self.projects.values())

    def update_project(self, pid: str, project: Project):
        if pid in self.projects:
            project.updated_at = time.strftime("%Y-%m-%d %H:%M:%S")
            self.projects[pid] = project
            self._save()

    def delete_project(self, pid: str) -> bool:
        if pid in self.projects:
            del self.projects[pid]
            self._save()
            return True
        return False
