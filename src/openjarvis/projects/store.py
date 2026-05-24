"""SQLite-backed storage for projects, tasks, and milestones."""

from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from openjarvis.projects.models import Milestone, Project, Task

logger = logging.getLogger(__name__)

DEFAULT_DB_DIR = Path.home() / ".config" / "openjarvis"


class ProjectStore:
    """Persistent SQLite store for project management data."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            DEFAULT_DB_DIR.mkdir(parents=True, exist_ok=True)
            db_path = DEFAULT_DB_DIR / "projects.db"
        self._path = Path(db_path)
        self._conn = sqlite3.connect(str(self._path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id          TEXT PRIMARY KEY,
            name        TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            status      TEXT NOT NULL DEFAULT 'planning',
            goals       TEXT NOT NULL DEFAULT '[]',
            tags        TEXT NOT NULL DEFAULT '[]',
            priority    INTEGER NOT NULL DEFAULT 0,
            deadline    REAL,
            created_at  REAL NOT NULL,
            updated_at  REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id              TEXT PRIMARY KEY,
            project_id      TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            title           TEXT NOT NULL DEFAULT '',
            description     TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'todo',
            priority        INTEGER NOT NULL DEFAULT 0,
            depends_on      TEXT NOT NULL DEFAULT '[]',
            assignee        TEXT NOT NULL DEFAULT '',
            estimated_hours REAL NOT NULL DEFAULT 0.0,
            actual_hours    REAL NOT NULL DEFAULT 0.0,
            created_at      REAL NOT NULL,
            updated_at      REAL NOT NULL
        );

        CREATE TABLE IF NOT EXISTS milestones (
            id          TEXT PRIMARY KEY,
            project_id  TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
            name        TEXT NOT NULL DEFAULT '',
            completed   INTEGER NOT NULL DEFAULT 0,
            created_at  REAL NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_tasks_project ON tasks(project_id);
        CREATE INDEX IF NOT EXISTS idx_milestones_project ON milestones(project_id);
        CREATE INDEX IF NOT EXISTS idx_projects_status ON projects(status);
        """)

    # ---- Project CRUD ------------------------------------------------------

    def create_project(self, project: Project) -> Project:
        self._conn.execute(
            """INSERT INTO projects (id, name, description, status, goals, tags, priority, deadline, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                project.id, project.name, project.description, project.status,
                json.dumps(project.goals), json.dumps(project.tags),
                project.priority, project.deadline,
                project.created_at, project.updated_at,
            ),
        )
        self._conn.commit()
        return project

    def get_project(self, project_id: str) -> Optional[Project]:
        row = self._conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        return Project.from_dict(dict(row)) if row else None

    def list_projects(self, status: Optional[str] = None) -> List[Project]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM projects WHERE status = ? ORDER BY priority DESC, created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM projects ORDER BY priority DESC, created_at DESC"
            ).fetchall()
        return [Project.from_dict(dict(r)) for r in rows]

    def update_project(self, project_id: str, updates: Dict[str, Any]) -> Optional[Project]:
        allowed = {"name", "description", "status", "goals", "tags", "priority", "deadline"}
        sets = []
        vals = []
        for key, val in updates.items():
            if key in allowed:
                if key in ("goals", "tags"):
                    val = json.dumps(val) if isinstance(val, (list, tuple)) else val
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return self.get_project(project_id)
        sets.append("updated_at = ?")
        vals.append(time.time())
        vals.append(project_id)
        self._conn.execute(
            f"UPDATE projects SET {', '.join(sets)} WHERE id = ?", vals
        )
        self._conn.commit()
        return self.get_project(project_id)

    def delete_project(self, project_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ---- Task CRUD ---------------------------------------------------------

    def create_task(self, task: Task) -> Task:
        self._conn.execute(
            """INSERT INTO tasks (id, project_id, title, description, status, priority, depends_on, assignee, estimated_hours, actual_hours, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                task.id, task.project_id, task.title, task.description,
                task.status, task.priority, json.dumps(task.depends_on),
                task.assignee, task.estimated_hours, task.actual_hours,
                task.created_at, task.updated_at,
            ),
        )
        self._conn.commit()
        return task

    def get_task(self, task_id: str) -> Optional[Task]:
        row = self._conn.execute(
            "SELECT * FROM tasks WHERE id = ?", (task_id,)
        ).fetchone()
        return Task.from_dict(dict(row)) if row else None

    def list_tasks(self, project_id: str, status: Optional[str] = None) -> List[Task]:
        if status:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? AND status = ? ORDER BY priority DESC, created_at ASC",
                (project_id, status),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT * FROM tasks WHERE project_id = ? ORDER BY priority DESC, created_at ASC",
                (project_id,),
            ).fetchall()
        return [Task.from_dict(dict(r)) for r in rows]

    def update_task(self, task_id: str, updates: Dict[str, Any]) -> Optional[Task]:
        allowed = {"title", "description", "status", "priority", "depends_on", "assignee", "estimated_hours", "actual_hours"}
        sets = []
        vals = []
        for key, val in updates.items():
            if key in allowed:
                if key == "depends_on":
                    val = json.dumps(val) if isinstance(val, (list, tuple)) else val
                sets.append(f"{key} = ?")
                vals.append(val)
        if not sets:
            return self.get_task(task_id)
        sets.append("updated_at = ?")
        vals.append(time.time())
        vals.append(task_id)
        self._conn.execute(
            f"UPDATE tasks SET {', '.join(sets)} WHERE id = ?", vals
        )
        self._conn.commit()
        return self.get_task(task_id)

    def delete_task(self, task_id: str) -> bool:
        cur = self._conn.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        self._conn.commit()
        return cur.rowcount > 0

    # ---- Milestone CRUD ----------------------------------------------------

    def create_milestone(self, milestone: Milestone) -> Milestone:
        self._conn.execute(
            "INSERT INTO milestones (id, project_id, name, completed, created_at) VALUES (?, ?, ?, ?, ?)",
            (milestone.id, milestone.project_id, milestone.name, int(milestone.completed), milestone.created_at),
        )
        self._conn.commit()
        return milestone

    def list_milestones(self, project_id: str) -> List[Milestone]:
        rows = self._conn.execute(
            "SELECT * FROM milestones WHERE project_id = ? ORDER BY created_at ASC",
            (project_id,),
        ).fetchall()
        return [Milestone.from_dict(dict(r)) for r in rows]

    def update_milestone(self, milestone_id: str, completed: bool) -> Optional[Milestone]:
        self._conn.execute(
            "UPDATE milestones SET completed = ? WHERE id = ?",
            (int(completed), milestone_id),
        )
        self._conn.commit()
        row = self._conn.execute(
            "SELECT * FROM milestones WHERE id = ?", (milestone_id,)
        ).fetchone()
        return Milestone.from_dict(dict(row)) if row else None

    # ---- Progress / Analytics ----------------------------------------------

    def get_project_progress(self, project_id: str) -> Dict[str, Any]:
        tasks = self.list_tasks(project_id)
        total = len(tasks)
        if total == 0:
            return {
                "percent_complete": 0,
                "total_tasks": 0,
                "completed_tasks": 0,
                "in_progress": 0,
                "todo": 0,
                "blocked": 0,
                "estimated_hours": 0.0,
                "actual_hours": 0.0,
                "milestones": 0,
            }
        completed = sum(1 for t in tasks if t.status == "done")
        in_progress = sum(1 for t in tasks if t.status == "in_progress")
        todo = sum(1 for t in tasks if t.status == "todo")
        blocked = sum(1 for t in tasks if t.status == "blocked")

        milestones = self.list_milestones(project_id)
        completed_ms = sum(1 for m in milestones if m.completed)

        return {
            "percent_complete": round((completed / total) * 100, 1),
            "total_tasks": total,
            "completed_tasks": completed,
            "in_progress": in_progress,
            "todo": todo,
            "blocked": blocked,
            "estimated_hours": sum(t.estimated_hours for t in tasks),
            "actual_hours": sum(t.actual_hours for t in tasks),
            "milestones": f"{completed_ms}/{len(milestones)}",
        }

    # ---- Cleanup -----------------------------------------------------------

    def close(self) -> None:
        self._conn.close()
