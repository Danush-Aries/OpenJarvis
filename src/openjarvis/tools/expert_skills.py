"""Expert Skills tool — allows Jarvis to browse, activate, and manage 53 expert system-prompt skills."""

from __future__ import annotations

from typing import Any, Dict
from openjarvis.core.registry import ToolRegistry
from openjarvis.core.types import ToolResult
from openjarvis.tools._stubs import BaseTool, ToolSpec

_MANAGER = None

def _get_manager():
    """Lazy-load the SkillManager singleton from our isolated namespace."""
    global _MANAGER
    if _MANAGER is None:
        from openjarvis.skills_expert.manager import SkillManager
        _MANAGER = SkillManager()
    return _MANAGER


@ToolRegistry.register("expert_skills")
class ExpertSkillsTool(BaseTool):
    """Manage Jarvis's 53 expert-level system-prompt skills across 12 domains."""

    def __init__(self) -> None:
        pass

    @property
    def spec(self) -> ToolSpec:
        return ToolSpec(
            name="expert_skills",
            description=(
                "List, search, activate, or deactivate any of Jarvis's 53 expert-level "
                "system-prompt skills (such as react-nextjs, tailwind-css, python-backend, "
                "prompt-engineering, web-security, database-design, docker, etc.) to inject "
                "deep specialized domain knowledge into the current conversation."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "activate", "deactivate", "status"],
                        "description": "Action to perform: 'list', 'activate', 'deactivate', or 'status'.",
                    },
                    "skill_id": {
                        "type": "string",
                        "description": "The ID of the skill to activate or deactivate (e.g., 'react-nextjs', 'python-backend', 'docker').",
                    },
                    "category": {
                        "type": "string",
                        "description": "Filter by category when listing. Options include: web-development, backend-api, devops-infrastructure, ai-machine-learning, security, data-analytics, frontend-ui, creative-design, productivity-tools, mobile-cross-platform, specialized, system-admin, finance-business, communication, science-engineering.",
                    },
                    "query": {
                        "type": "string",
                        "description": "Search skills by keyword across names, descriptions, and trigger keywords.",
                    },
                    "deactivate_all": {
                        "type": "boolean",
                        "description": "If true and action is 'deactivate', deactivates all active skills.",
                        "default": False,
                    }
                },
                "required": ["action"],
            },
            category="skill",
        )

    def execute(self, **params: Any) -> ToolResult:
        action = params.get("action", "status")
        skill_id = params.get("skill_id", "")
        category = params.get("category", "")
        query = params.get("query", "")
        deactivate_all = params.get("deactivate_all", False)

        mgr = _get_manager()

        if action == "list":
            if query:
                skills = mgr.search(query)
            elif category:
                skills = mgr.get_by_category(category)
            else:
                skills = mgr.get_all()
            
            return ToolResult(
                tool_name="expert_skills",
                success=True,
                content=f"Found {len(skills)} matching expert skills.\n" + "\n".join(
                    f"- {s['id']}: {s['name']} [{s['level']}] - {s['description']}" for s in skills
                ),
                metadata={"skills": skills}
            )

        elif action == "activate":
            if not skill_id:
                return ToolResult(
                    tool_name="expert_skills",
                    success=False,
                    content="A valid skill_id is required to activate a skill."
                )
            result = mgr.activate(skill_id)
            if result.get("status") in ("activated", "already_active"):
                dep_msg = ""
                if result.get("dependencies_activated"):
                    dep_msg = f" (Dependencies activated: {', '.join(result['dependencies_activated'])})"
                return ToolResult(
                    tool_name="expert_skills",
                    success=True,
                    content=f"Successfully activated expert skill '{skill_id}'!{dep_msg}\nJarvis is now equipped with: {result['skill']['description']}.",
                    metadata=result
                )
            else:
                return ToolResult(
                    tool_name="expert_skills",
                    success=False,
                    content=result.get("message", f"Failed to activate skill '{skill_id}'.")
                )

        elif action == "deactivate":
            if deactivate_all:
                result = mgr.deactivate_all()
                return ToolResult(
                    tool_name="expert_skills",
                    success=True,
                    content=f"Deactivated all active skills ({result.get('count', 0)} total).",
                    metadata=result
                )
            if not skill_id:
                return ToolResult(
                    tool_name="expert_skills",
                    success=False,
                    content="A valid skill_id or deactivate_all=True is required to deactivate."
                )
            result = mgr.deactivate(skill_id)
            if result.get("status") == "deactivated":
                return ToolResult(
                    tool_name="expert_skills",
                    success=True,
                    content=f"Successfully deactivated expert skill '{skill_id}'.",
                    metadata=result
                )
            else:
                return ToolResult(
                    tool_name="expert_skills",
                    success=False,
                    content=result.get("message", f"Failed to deactivate skill '{skill_id}'.")
                )

        elif action == "status":
            status = mgr.get_status()
            active_skills_list = ", ".join(status.get("active_skills", [])) or "None"
            return ToolResult(
                tool_name="expert_skills",
                success=True,
                content=(
                    f"Expert Skills Registry Status:\n"
                    f"- Total Available Skills: {status['total_available']}\n"
                    f"- Active Skills: {status['active_count']} ({active_skills_list})"
                ),
                metadata=status
            )

        return ToolResult(
            tool_name="expert_skills",
            success=False,
            content=f"Unknown action: {action}"
        )


__all__ = ["ExpertSkillsTool"]
