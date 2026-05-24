"""Jarvis Skills Package — 50+ expert-level capabilities.

Skills are structured knowledge modules that Jarvis can activate
to bring specialized expertise into conversations. Each skill contains
a system prompt fragment, trigger keywords, tool requirements, and metadata.
"""

from openjarvis.skills_expert.manager import SkillManager
from openjarvis.skills_expert.types import Skill, SkillCategory, SkillLevel

__all__ = ["SkillManager", "Skill", "SkillCategory", "SkillLevel"]
