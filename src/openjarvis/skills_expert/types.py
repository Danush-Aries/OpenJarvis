"""Skill data types — the core model for Jarvis's skills system.

Each Skill is a structured knowledge module containing:
- A system prompt fragment that enhances Jarvis's responses
- Trigger keywords for automatic activation
- Tool requirements for capability matching
- Metadata for browsing and discovery
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class SkillLevel(Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class SkillCategory(Enum):
    WEB_DEV = "web-development"
    BACKEND = "backend-api"
    DEVOPS = "devops-infrastructure"
    AI_ML = "ai-machine-learning"
    SECURITY = "security"
    DATA = "data-analytics"
    FRONTEND = "frontend-ui"
    CREATIVE = "creative-design"
    PRODUCTIVITY = "productivity-tools"
    MOBILE = "mobile-cross-platform"
    SPECIALIZED = "specialized"
    SYSTEM = "system-admin"
    FINANCE = "finance-business"
    COMMUNICATION = "communication"
    SCIENCE = "science-engineering"


@dataclass
class Skill:
    """A single skill — structured knowledge module for Jarvis"""

    id: str
    """Unique snake_case identifier (e.g. 'react-nextjs', 'docker-patterns')."""

    name: str
    """Human-readable display name (e.g. 'React & Next.js Patterns')."""

    description: str
    """One-line summary of what this skill provides."""

    category: SkillCategory
    """Primary functional category."""

    subcategory: str = ""
    """Optional sub-category for finer grouping."""

    level: SkillLevel = SkillLevel.INTERMEDIATE
    """Typical expertise level required."""

    prompt: str = ""
    """System prompt fragment injected when this skill is active.
    
    This is the core of the skill — instructions, patterns, and knowledge
    that Jarvis uses when responding in this domain.
    """

    trigger_keywords: List[str] = field(default_factory=list)
    """Keywords that should auto-activate this skill."""

    tool_requirements: List[str] = field(default_factory=list)
    """Tool IDs that this skill typically requires (e.g. ['web_search', 'file_read'])."""

    dependencies: List[str] = field(default_factory=list)
    """Other skill IDs that should be active alongside this one."""

    examples: List[str] = field(default_factory=list)
    """Example prompts that activate this skill."""

    def to_dict(self) -> Dict:
        """Serialize to a plain dict for API responses."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "subcategory": self.subcategory,
            "level": self.level.value,
            "trigger_keywords": self.trigger_keywords,
            "tool_requirements": self.tool_requirements,
            "dependencies": self.dependencies,
            "examples": self.examples[:3] if self.examples else [],
        }

    def to_prompt_block(self) -> str:
        """Format this skill as a system prompt injection block."""
        if not self.prompt:
            return ""
        header = f"=== SKILL: {self.name} ==="
        return f"\n\n{header}\n{self.prompt}\n"
