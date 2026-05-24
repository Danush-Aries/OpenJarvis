"""Data models for the project management system."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _now() -> float:
    return time.time()


@dataclass(slots=True)
class Project:
    """A long-running project with goals, tasks, and milestones."""

    id: str = field(default_factory=_new_id)
    name: str = ""
    description: str = ""
    status: str = "planning"  # planning | active | paused | completed | cancelled
    goals: List[str] = field(default_factory=list)
    tags: List[str] = field(default_factory=list)
    priority: int = 0  # higher = more important
    deadline: Optional[float] = None
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["deadline"] = int(d["deadline"]) if d["deadline"] else None
        d["created_at"] = int(d["created_at"])
        d["updated_at"] = int(d["updated_at"])
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Project:
        return cls(
            id=data.get("id", _new_id()),
            name=data.get("name", ""),
            description=data.get("description", ""),
            status=data.get("status", "planning"),
            goals=json.loads(data["goals"]) if isinstance(data.get("goals"), str) else data.get("goals", []),
            tags=json.loads(data["tags"]) if isinstance(data.get("tags"), str) else data.get("tags", []),
            priority=data.get("priority", 0),
            deadline=data.get("deadline"),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )


@dataclass(slots=True)
class Task:
    """A single unit of work within a project."""

    id: str = field(default_factory=_new_id)
    project_id: str = ""
    title: str = ""
    description: str = ""
    status: str = "todo"  # todo | in_progress | review | done | blocked | cancelled
    priority: int = 0
    depends_on: List[str] = field(default_factory=list)  # task IDs this depends on
    assignee: str = ""
    estimated_hours: float = 0.0
    actual_hours: float = 0.0
    created_at: float = field(default_factory=_now)
    updated_at: float = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["created_at"] = int(d["created_at"])
        d["updated_at"] = int(d["updated_at"])
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Task:
        return cls(
            id=data.get("id", _new_id()),
            project_id=data.get("project_id", ""),
            title=data.get("title", ""),
            description=data.get("description", ""),
            status=data.get("status", "todo"),
            priority=data.get("priority", 0),
            depends_on=json.loads(data["depends_on"]) if isinstance(data.get("depends_on"), str) else data.get("depends_on", []),
            assignee=data.get("assignee", ""),
            estimated_hours=float(data.get("estimated_hours", 0)),
            actual_hours=float(data.get("actual_hours", 0)),
            created_at=data.get("created_at", _now()),
            updated_at=data.get("updated_at", _now()),
        )


@dataclass(slots=True)
class Milestone:
    """A named checkpoint within a project."""

    id: str = field(default_factory=_new_id)
    project_id: str = ""
    name: str = ""
    completed: bool = False
    created_at: float = field(default_factory=_now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "completed": self.completed,
            "created_at": int(self.created_at),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> Milestone:
        return cls(
            id=data.get("id", _new_id()),
            project_id=data.get("project_id", ""),
            name=data.get("name", ""),
            completed=bool(data.get("completed", False)),
            created_at=data.get("created_at", _now()),
        )
