"""ToolRegistry-registered tools for project management CRUD and autonomous execution."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from openjarvis.projects.models import Milestone, Project, Task
from openjarvis.projects.store import ProjectStore

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline registry (avoids upstream dependency issues)
# ---------------------------------------------------------------------------
_TOOLS: Dict[str, Any] = {}


def register(cls: Any) -> Any:
    _TOOLS[cls.__name__] = cls
    return cls


def get_tools() -> List[Any]:
    return list(_TOOLS.values())


def _get_store() -> ProjectStore:
    """Lazy singleton for the project store."""
    return ProjectStore()


# ---- Project Tools ---------------------------------------------------------

@register
class ProjectCreateTool:
    tool_id = "project_create"
    name = "Create Project"
    description = "Create a new project with name, description, goals, and optional metadata."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Project name"},
                "description": {"type": "string", "description": "Project description"},
                "goals": {"type": "array", "items": {"type": "string"}, "description": "List of project goals"},
                "tags": {"type": "array", "items": {"type": "string"}, "description": "Optional tags"},
                "priority": {"type": "integer", "description": "Priority (higher = more important)", "default": 0},
            },
            "required": ["name"],
        }

    def execute(self, name: str, description: str = "", goals: Optional[List[str]] = None,
                tags: Optional[List[str]] = None, priority: int = 0) -> Dict[str, Any]:
        store = _get_store()
        project = Project(name=name, description=description, goals=goals or [],
                          tags=tags or [], priority=priority)
        store.create_project(project)
        return {"status": "ok", "project": project.to_dict()}


@register
class ProjectListTool:
    tool_id = "project_list"
    name = "List Projects"
    description = "List all projects, optionally filtered by status."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["", "planning", "active", "paused", "completed", "cancelled"],
                    "description": "Filter by status (leave empty for all)",
                },
            },
        }

    def execute(self, status: str = "") -> Dict[str, Any]:
        store = _get_store()
        projects = store.list_projects(status=status or None)
        return {"status": "ok", "projects": [p.to_dict() for p in projects], "count": len(projects)}


@register
class ProjectGetTool:
    tool_id = "project_get"
    name = "Get Project"
    description = "Get a single project with its progress, tasks, and milestones."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
            },
            "required": ["project_id"],
        }

    def execute(self, project_id: str) -> Dict[str, Any]:
        store = _get_store()
        project = store.get_project(project_id)
        if not project:
            return {"status": "not_found", "project_id": project_id}
        progress = store.get_project_progress(project_id)
        tasks = store.list_tasks(project_id)
        milestones = store.list_milestones(project_id)
        return {
            "status": "ok",
            "project": project.to_dict(),
            "progress": progress,
            "tasks": [t.to_dict() for t in tasks],
            "milestones": [m.to_dict() for m in milestones],
        }


@register
class ProjectUpdateTool:
    tool_id = "project_update"
    name = "Update Project"
    description = "Update project fields like status, name, description, goals, priority."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "name": {"type": "string"},
                "description": {"type": "string"},
                "status": {"type": "string", "enum": ["planning", "active", "paused", "completed", "cancelled"]},
                "goals": {"type": "array", "items": {"type": "string"}},
                "priority": {"type": "integer"},
            },
            "required": ["project_id"],
        }

    def execute(self, project_id: str, **kwargs) -> Dict[str, Any]:
        store = _get_store()
        project = store.update_project(project_id, kwargs)
        if not project:
            return {"status": "not_found", "project_id": project_id}
        return {"status": "ok", "project": project.to_dict()}


# ---- Task Tools ------------------------------------------------------------

@register
class TaskCreateTool:
    tool_id = "task_create"
    name = "Create Task"
    description = "Create a new task within a project."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "title": {"type": "string", "description": "Task title"},
                "description": {"type": "string", "description": "Task description"},
                "priority": {"type": "integer", "description": "Priority", "default": 0},
                "depends_on": {"type": "array", "items": {"type": "string"}, "description": "Task IDs this depends on"},
            },
            "required": ["project_id", "title"],
        }

    def execute(self, project_id: str, title: str, description: str = "",
                priority: int = 0, depends_on: Optional[List[str]] = None) -> Dict[str, Any]:
        store = _get_store()
        task = Task(project_id=project_id, title=title, description=description,
                    priority=priority, depends_on=depends_on or [])
        store.create_task(task)
        return {"status": "ok", "task": task.to_dict()}


@register
class TaskUpdateTool:
    tool_id = "task_update"
    name = "Update Task"
    description = "Update task status, title, description, priority, or hours."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "task_id": {"type": "string", "description": "Task ID"},
                "status": {"type": "string", "enum": ["todo", "in_progress", "review", "done", "blocked", "cancelled"]},
                "title": {"type": "string"},
                "description": {"type": "string"},
                "priority": {"type": "integer"},
                "actual_hours": {"type": "number"},
            },
            "required": ["task_id"],
        }

    def execute(self, task_id: str, **kwargs) -> Dict[str, Any]:
        store = _get_store()
        task = store.update_task(task_id, kwargs)
        if not task:
            return {"status": "not_found", "task_id": task_id}
        return {"status": "ok", "task": task.to_dict()}


@register
class TaskListTool:
    tool_id = "task_list"
    name = "List Tasks"
    description = "List tasks for a project, optionally filtered by status."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "status": {"type": "string", "description": "Filter by status (optional)"},
            },
            "required": ["project_id"],
        }

    def execute(self, project_id: str, status: str = "") -> Dict[str, Any]:
        store = _get_store()
        tasks = store.list_tasks(project_id, status=status or None)
        return {"status": "ok", "tasks": [t.to_dict() for t in tasks], "count": len(tasks)}


# ---- Milestone Tools -------------------------------------------------------

@register
class MilestoneCreateTool:
    tool_id = "milestone_create"
    name = "Create Milestone"
    description = "Add a milestone checkpoint to a project."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "project_id": {"type": "string", "description": "Project ID"},
                "name": {"type": "string", "description": "Milestone name"},
            },
            "required": ["project_id", "name"],
        }

    def execute(self, project_id: str, name: str) -> Dict[str, Any]:
        store = _get_store()
        milestone = Milestone(project_id=project_id, name=name)
        store.create_milestone(milestone)
        return {"status": "ok", "milestone": milestone.to_dict()}
