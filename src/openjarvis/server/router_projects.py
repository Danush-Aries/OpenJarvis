"""FastAPI routes for project management and neural graph APIs."""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException

from openjarvis.projects.store import ProjectStore
from openjarvis.projects.models import Project, Task, Milestone

logger = logging.getLogger(__name__)

projects_router = APIRouter(prefix="/v1/projects", tags=["projects"])

# ---------------------------------------------------------------------------
# Lazy store singleton
# ---------------------------------------------------------------------------
_store: Optional[ProjectStore] = None


def get_store() -> ProjectStore:
    global _store
    if _store is None:
        _store = ProjectStore()
    return _store


# ---------------------------------------------------------------------------
# Project endpoints
# ---------------------------------------------------------------------------


@projects_router.get("")
async def list_projects(status: Optional[str] = None):
    store = get_store()
    projects = store.list_projects(status=status)
    return {"projects": [p.to_dict() for p in projects]}


@projects_router.post("")
async def create_project(body: Dict[str, Any]):
    store = get_store()
    project = Project(
        name=body.get("name", ""),
        description=body.get("description", ""),
        goals=body.get("goals", []),
        tags=body.get("tags", []),
        priority=body.get("priority", 0),
    )
    store.create_project(project)
    return {"project": project.to_dict()}


@projects_router.get("/{project_id}")
async def get_project(project_id: str):
    store = get_store()
    project = store.get_project(project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    progress = store.get_project_progress(project_id)
    tasks = store.list_tasks(project_id)
    milestones = store.list_milestones(project_id)
    return {
        "project": project.to_dict(),
        "progress": progress,
        "tasks": [t.to_dict() for t in tasks],
        "milestones": [m.to_dict() for m in milestones],
    }


@projects_router.patch("/{project_id}")
async def update_project(project_id: str, body: Dict[str, Any]):
    store = get_store()
    project = store.update_project(project_id, body)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"project": project.to_dict()}


@projects_router.delete("/{project_id}")
async def delete_project(project_id: str):
    store = get_store()
    ok = store.delete_project(project_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Task endpoints
# ---------------------------------------------------------------------------


@projects_router.post("/{project_id}/tasks")
async def create_task(project_id: str, body: Dict[str, Any]):
    store = get_store()
    task = Task(
        project_id=project_id,
        title=body.get("title", ""),
        description=body.get("description", ""),
        priority=body.get("priority", 0),
        depends_on=body.get("depends_on", []),
    )
    store.create_task(task)
    return {"task": task.to_dict()}


@projects_router.get("/{project_id}/tasks")
async def list_tasks(project_id: str, status: Optional[str] = None):
    store = get_store()
    tasks = store.list_tasks(project_id, status=status)
    return {"tasks": [t.to_dict() for t in tasks]}


@projects_router.patch("/tasks/{task_id}")
async def update_task(task_id: str, body: Dict[str, Any]):
    store = get_store()
    task = store.update_task(task_id, body)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"task": task.to_dict()}


@projects_router.delete("/tasks/{task_id}")
async def delete_task(task_id: str):
    store = get_store()
    ok = store.delete_task(task_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Task not found")
    return {"status": "deleted"}


# ---------------------------------------------------------------------------
# Milestone endpoints
# ---------------------------------------------------------------------------


@projects_router.post("/{project_id}/milestones")
async def create_milestone(project_id: str, body: Dict[str, Any]):
    store = get_store()
    milestone = Milestone(project_id=project_id, name=body.get("name", ""))
    store.create_milestone(milestone)
    return {"milestone": milestone.to_dict()}


@projects_router.patch("/milestones/{milestone_id}")
async def update_milestone(milestone_id: str, body: Dict[str, Any]):
    store = get_store()
    milestone = store.update_milestone(milestone_id, body.get("completed", False))
    if not milestone:
        raise HTTPException(status_code=404, detail="Milestone not found")
    return {"milestone": milestone.to_dict()}


# ---------------------------------------------------------------------------
# Auto-execution
# ---------------------------------------------------------------------------


@projects_router.post("/{project_id}/execute")
async def execute_project(project_id: str):
    from openjarvis.agents.auto_executor import AutoExecutor
    executor = AutoExecutor(store=get_store())
    result = executor.execute_project(project_id)
    return result
