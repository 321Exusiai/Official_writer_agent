"""本地持久化 —— 单项目文件拆分 + 原子写 + 写锁 + 时光机快照 + BM25 全文检索。

可靠性与性能设计：
- 拆分存储：项目各自独立存储于 projects/{pid}.json，索引存储于 project_index.json
- 兼容迁移：自动检测历史 projects.json 并平滑无损迁移
- 时光机快照：草稿变更自动记录 Revision 版本快照
- BM25 跨项目检索：支持在历史稿件中全文搜索段落与素材
"""

import json
import os
import threading
import time
import uuid
from pathlib import Path

from ..core.retrieval import BM25
from ..domain.schemas import Project, Revision
from .schema import CURRENT_PROJECTS_VERSION, migrate_projects

DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# 进程内全局写锁
_WRITE_LOCK = threading.RLock()


class Store:
    def __init__(self, data_dir=None):
        p = Path(data_dir) if data_dir else DATA_DIR
        if p.suffix == ".json":
            p = p.parent
        self.data_dir = p
        self.legacy_path = self.data_dir / "projects.json"
        self.projects_dir = self.data_dir / "projects"
        self.index_path = self.data_dir / "project_index.json"
        self.projects: dict[str, Project] = {}
        self._init_and_migrate()

    def _init_and_migrate(self):
        with _WRITE_LOCK:
            self.projects_dir.mkdir(parents=True, exist_ok=True)
            # 1. 检查历史单体文件 projects.json，如有则执行迁移
            if self.legacy_path.exists() and not self.index_path.exists():
                try:
                    raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
                    raw = migrate_projects(raw)
                    items = raw.get("projects", raw)
                    for pid, pdata in items.items():
                        p = Project(**pdata)
                        self._save_single_project(p)
                except Exception:
                    pass
            # 2. 从 projects/ 目录加载所有项目
            self._load_all()

    def _load_all(self):
        with _WRITE_LOCK:
            self.projects = {}
            if self.projects_dir.exists():
                for pf in self.projects_dir.glob("*.json"):
                    try:
                        pdata = json.loads(pf.read_text(encoding="utf-8"))
                        p = Project(**pdata)
                        self.projects[p.id] = p
                    except Exception:
                        continue
            # 若 projects/ 为空但 legacy_path 存在（测试用例传入独立 path），则兼容加载
            if not self.projects and self.legacy_path.exists():
                try:
                    raw = json.loads(self.legacy_path.read_text(encoding="utf-8"))
                    raw = migrate_projects(raw)
                    items = raw.get("projects", raw)
                    self.projects = {k: Project(**v) for k, v in items.items()}
                except Exception:
                    pass

    def _save_single_project(self, project: Project):
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        pf = self.projects_dir / f"{project.id}.json"
        tmp = pf.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(project.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp, pf)
        # 同步更新轻量索引与兼容单体文件
        self._save_index_and_legacy()

    def _save_index_and_legacy(self):
        index_data = {
            p.id: {
                "id": p.id,
                "name": p.name,
                "status": p.status.value,
                "writing_mode": p.writing_mode or p.mode_value,
                "doc_type": p.doc_type,
                "created_at": p.created_at,
                "updated_at": p.updated_at,
            }
            for p in self.projects.values()
        }
        tmp_idx = self.index_path.with_suffix(".json.tmp")
        tmp_idx.write_text(json.dumps(index_data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_idx, self.index_path)

        # 同步保留 legacy projects.json 供旧工具读取
        legacy_payload = {
            "schema_version": CURRENT_PROJECTS_VERSION,
            "projects": {k: v.model_dump() for k, v in self.projects.items()},
        }
        tmp_leg = self.legacy_path.with_suffix(".json.tmp")
        tmp_leg.write_text(json.dumps(legacy_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(tmp_leg, self.legacy_path)

    def create_project(self, name: str, description: str = "") -> Project:
        pid = f"proj_{uuid.uuid4().hex[:8]}"
        now = time.strftime("%Y-%m-%d %H:%M:%S")
        p = Project(id=pid, name=name, description=description, created_at=now, updated_at=now)
        with _WRITE_LOCK:
            self.projects[pid] = p
            self._save_single_project(p)
        return p

    def get_project(self, pid: str) -> Project | None:
        with _WRITE_LOCK:
            if pid not in self.projects:
                pf = self.projects_dir / f"{pid}.json"
                if pf.exists():
                    try:
                        self.projects[pid] = Project(**json.loads(pf.read_text(encoding="utf-8")))
                    except Exception:
                        pass
            return self.projects.get(pid)

    def list_projects(self) -> list[Project]:
        with _WRITE_LOCK:
            return list(self.projects.values())

    def update_project(self, pid: str, project: Project, record_revision: bool = True, rev_summary: str = ""):
        with _WRITE_LOCK:
            if pid in self.projects:
                now = time.strftime("%Y-%m-%d %H:%M:%S")
                project.updated_at = now

                # 自动记录时光机版本快照（若草稿发生变动或尚未有快照）
                last_snapshot = project.revisions[0].draft_snapshot if project.revisions else ""
                if record_revision and project.draft and project.draft != last_snapshot:
                    rev_id = f"rev_{uuid.uuid4().hex[:6]}"
                    score = project.review_results[0].score if project.review_results else None
                    rev = Revision(
                        id=rev_id,
                        timestamp=now,
                        summary=rev_summary or f"编辑修改（字数 {len(project.draft)} 字）",
                        draft_snapshot=project.draft,
                        score=score,
                    )
                    # 保留最多 30 个版本快照
                    project.revisions.insert(0, rev)
                    project.revisions = project.revisions[:30]

                self.projects[pid] = project
                self._save_single_project(project)

    def restore_revision(self, pid: str, rev_id: str) -> Project | None:
        """从时光机快照回滚草稿。"""
        with _WRITE_LOCK:
            p = self.get_project(pid)
            if not p:
                return None
            target_rev = next((r for r in p.revisions if r.id == rev_id), None)
            if not target_rev:
                return None
            p.draft = target_rev.draft_snapshot
            self.update_project(pid, p, record_revision=True, rev_summary=f"回滚至版本 {target_rev.timestamp}")
            return p

    def delete_project(self, pid: str) -> bool:
        with _WRITE_LOCK:
            if pid in self.projects:
                del self.projects[pid]
                pf = self.projects_dir / f"{pid}.json"
                if pf.exists():
                    try:
                        pf.unlink()
                    except Exception:
                        pass
                self._save_index_and_legacy()
                return True
            return False

    def search_projects(self, query: str, limit: int = 10) -> list[dict]:
        """基于 BM25 跨所有历史项目草稿与素材进行全文检索。"""
        with _WRITE_LOCK:
            corpus = []
            for p in self.projects.values():
                purpose = (p.brief and p.brief.purpose) or ""
                scratchpad_str = " ".join(p.scratchpad or [])
                content = f"{p.name} {p.description} {p.draft} {scratchpad_str} {purpose}"
                if content.strip():
                    corpus.append({
                        "id": p.id,
                        "name": p.name,
                        "doc_type": p.doc_type,
                        "writing_mode": p.writing_mode or p.mode_value,
                        "draft_snippet": (p.draft[:160] + "…") if len(p.draft) > 160 else p.draft,
                        "content": content,
                        "updated_at": p.updated_at,
                    })
            if not corpus:
                return []
            bm = BM25(corpus, text_field="content")
            scored = bm.score(query)
            return [item for item, score in scored[:limit] if score > 0]

    def replace_all(self, projects: dict):
        with _WRITE_LOCK:
            self.projects = dict(projects)
            for p in self.projects.values():
                self._save_single_project(p)

    def reload(self):
        with _WRITE_LOCK:
            self.projects = {}
            self._load_all()

