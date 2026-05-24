"""Skill Manager — activates, deactivates, and injects skills into conversations.

The SkillManager is the central registry and lifecycle manager for Jarvis's
53 skills. It handles:
- Loading skills from the registry
- Activating/deactivating skills per conversation
- Injecting skill prompts into the system prompt
- Auto-activating skills based on trigger keywords
- Querying and searching the skill database
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from openjarvis.skills_expert.index import (
    get_all_skills,
    get_skill,
    get_skills_by_category,
    search_skills,
    count_skills,
    get_registry_stats,
)
from openjarvis.skills_expert.types import Skill, SkillCategory

logger = logging.getLogger(__name__)


class SkillManager:
    """Manages skill lifecycle per conversation session."""

    def __init__(self) -> None:
        self._active_skills: Dict[str, Skill] = {}
        logger.info("SkillManager initialized with %d skills available", count_skills())

    # ------------------------------------------------------------------
    # Activation / Deactivation
    # ------------------------------------------------------------------

    def activate(self, skill_id: str) -> Dict[str, Any]:
        """Activate a skill by ID.

        Returns:
            Dict with status, skill info, and any errors.
        """
        skill = get_skill(skill_id)
        if skill is None:
            return {"status": "error", "message": f"Skill '{skill_id}' not found"}

        if skill_id in self._active_skills:
            return {"status": "already_active", "skill": skill.to_dict()}

        self._active_skills[skill_id] = skill

        # Auto-activate dependencies
        deps_activated = []
        for dep_id in skill.dependencies:
            if dep_id not in self._active_skills:
                dep = get_skill(dep_id)
                if dep:
                    self._active_skills[dep_id] = dep
                    deps_activated.append(dep.name)

        logger.info("Skill activated: %s (%s)", skill.name, skill.category.value)
        return {
            "status": "activated",
            "skill": skill.to_dict(),
            "dependencies_activated": deps_activated,
        }

    def deactivate(self, skill_id: str) -> Dict[str, Any]:
        """Deactivate a skill by ID."""
        skill = self._active_skills.pop(skill_id, None)
        if skill is None:
            return {"status": "error", "message": f"Skill '{skill_id}' is not active"}
        logger.info("Skill deactivated: %s", skill.name)
        return {"status": "deactivated", "skill": skill.to_dict()}

    def deactivate_all(self) -> Dict[str, Any]:
        """Deactivate all active skills."""
        count = len(self._active_skills)
        names = [s.name for s in self._active_skills.values()]
        self._active_skills.clear()
        logger.info("Deactivated %d skills", count)
        return {"status": "deactivated", "count": count, "skills": names}

    def list_active(self) -> List[Dict[str, Any]]:
        """Return all currently active skills."""
        return [s.to_dict() for s in self._active_skills.values()]

    def is_active(self, skill_id: str) -> bool:
        """Check if a skill is currently active."""
        return skill_id in self._active_skills

    # ------------------------------------------------------------------
    # Query / Search
    # ------------------------------------------------------------------

    def search(self, query: str) -> List[Dict[str, Any]]:
        """Search skills by keyword."""
        results = search_skills(query)
        return [s.to_dict() for s in results]

    def get_by_category(self, category: str) -> List[Dict[str, Any]]:
        """Get all skills in a category."""
        try:
            cat = SkillCategory(category)
            return [s.to_dict() for s in get_skills_by_category(cat)]
        except ValueError:
            return []

    def get_all(self) -> List[Dict[str, Any]]:
        """Get all available skills."""
        return [s.to_dict() for s in get_all_skills()]

    def get_status(self) -> Dict[str, Any]:
        """Get full status of the skill manager."""
        active = self.list_active()
        stats = get_registry_stats()
        return {
            "active_count": len(active),
            "total_available": stats["total"],
            "active_skills": [s["name"] for s in active],
            "registry": stats,
        }

    # ------------------------------------------------------------------
    # Auto-activation
    # ------------------------------------------------------------------

    def auto_activate(self, message: str) -> List[Dict[str, Any]]:
        """Auto-activate skills based on trigger keywords in a message.

        Scans the user message for trigger keywords and activates matching
        skills that aren't already active.

        Returns:
            List of activation results for newly activated skills.
        """
        msg_lower = message.lower()
        activated = []

        for skill in get_all_skills():
            if skill.id in self._active_skills:
                continue  # already active

            # Check trigger keywords
            for kw in skill.trigger_keywords:
                if kw.lower() in msg_lower:
                    result = self.activate(skill.id)
                    if result["status"] == "activated":
                        activated.append(result)
                        logger.debug("Auto-activated skill '%s' from keyword '%s'",
                                    skill.name, kw)
                    break  # one match per skill is enough

        return activated

    # ------------------------------------------------------------------
    # System Prompt Injection
    # ------------------------------------------------------------------

    def build_prompt_section(self) -> str:
        """Build the skills section for the system prompt.

        Returns a formatted string containing prompt blocks from all
        active skills, to be injected into the Jarvis system prompt.
        """
        if not self._active_skills:
            return ""

        parts = ["\n\n=== ACTIVE SKILLS ==="]
        parts.append(f"Active skills ({len(self._active_skills)}): "
                     f"{', '.join(s.name for s in self._active_skills.values())}")
        parts.append("")

        for skill in self._active_skills.values():
            block = skill.to_prompt_block()
            if block:
                parts.append(block)

        return "\n".join(parts)
