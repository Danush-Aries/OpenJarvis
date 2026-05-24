"""Learning tools — extract patterns from conversations and create reusable skills."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline registry
# ---------------------------------------------------------------------------
_TOOLS: Dict[str, Any] = {}


def register(cls: Any) -> Any:
    _TOOLS[cls.__name__] = cls
    return cls


def get_tools() -> List[Any]:
    return list(_TOOLS.values())


# ---------------------------------------------------------------------------
# Pattern Analysis
# ---------------------------------------------------------------------------

@register
class AnalyzeConversationPatternsTool:
    """Analyze conversation history to identify recurring patterns, commands, and topics."""

    tool_id = "analyze_patterns"
    name = "Analyze Conversation Patterns"
    description = "Scan conversation history and extract recurring request patterns, command usage frequencies, and topic clusters for skill discovery."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "max_messages": {
                    "type": "integer",
                    "description": "Number of recent messages to analyze",
                    "default": 100,
                },
                "pattern_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["command", "topic", "entity", "tool_usage"]},
                    "description": "Types of patterns to extract",
                    "default": ["command", "topic", "tool_usage"],
                },
            },
        }

    def execute(self, max_messages: int = 100, pattern_types: Optional[List[str]] = None) -> Dict[str, Any]:
        if pattern_types is None:
            pattern_types = ["command", "topic", "tool_usage"]

        # Try loading recent session logs
        messages = self._load_recent_messages(max_messages)
        if not messages:
            return {"status": "ok", "message": "No conversation history available to analyze", "patterns": []}

        patterns = []
        if "command" in pattern_types:
            patterns.extend(self._extract_command_patterns(messages))
        if "topic" in pattern_types:
            patterns.extend(self._extract_topic_patterns(messages))
        if "tool_usage" in pattern_types:
            patterns.extend(self._extract_tool_usage_patterns(messages))

        return {
            "status": "ok",
            "messages_analyzed": len(messages),
            "patterns_found": len(patterns),
            "patterns": patterns,
        }

    def _load_recent_messages(self, max_messages: int) -> List[Dict[str, Any]]:
        """Load recent conversation messages from the session store."""
        try:
            from openjarvis.sessions.session import SessionStore
            import time
            store = SessionStore()
            cutoff = time.time() - 86400 * 7  # last 7 days
            sessions = store.list_sessions(limit=5)
            messages = []
            for sess in sessions:
                try:
                    history = store.get_session_history(sess.id)
                    for msg in history[-max_messages:]:
                        messages.append({
                            "role": msg.get("role", ""),
                            "content": msg.get("content", ""),
                            "timestamp": msg.get("timestamp", 0),
                        })
                except Exception:
                    continue
            return messages[-max_messages:]
        except ImportError:
            logger.warning("SessionStore not available")
            return []
        except Exception as e:
            logger.warning("Failed to load messages: %s", e)
            return []

    def _extract_command_patterns(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract recurring command patterns from user messages."""
        patterns = []
        command_counts: Dict[str, int] = {}

        for msg in messages:
            if msg.get("role") != "user":
                continue
            content = msg.get("content", "")
            # Detect common command patterns
            commands = re.findall(
                r"\b(create|update|delete|find|search|analyze|summarize|translate|"
                r"generate|write|read|list|show|run|execute|deploy|build|test|"
                r"fix|debug|optimize|refactor|review|check|monitor|schedule|send)\b",
                content.lower(),
            )
            for cmd in commands:
                command_counts[cmd] = command_counts.get(cmd, 0) + 1

        for cmd, count in sorted(command_counts.items(), key=lambda x: -x[1]):
            if count >= 3:
                patterns.append({
                    "type": "command",
                    "pattern": cmd,
                    "frequency": count,
                    "suggest_skill": count >= 5,
                })
        return patterns

    def _extract_topic_patterns(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract recurring topic clusters."""
        all_text = " ".join(
            m.get("content", "") for m in messages if m.get("role") in ("user", "assistant")
        )
        topics: Dict[str, int] = {}
        # Simple topic extraction via noun phrase detection
        topic_patterns = re.findall(
            r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+){1,3})\b", all_text
        )
        for tp in topic_patterns:
            topics[tp] = topics.get(tp, 0) + 1

        return [
            {"type": "topic", "pattern": topic, "frequency": count}
            for topic, count in sorted(topics.items(), key=lambda x: -x[1])
            if count >= 2
        ]

    def _extract_tool_usage_patterns(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract recurring tool usage sequences."""
        patterns = []
        tool_mentions: Dict[str, int] = {}
        for msg in messages:
            if msg.get("role") != "assistant":
                continue
            content = msg.get("content", "")
            tools = re.findall(r"`(\w+)`|\[(\w+)\]", content)
            for t in tools:
                name = t[0] or t[1]
                if name:
                    tool_mentions[name] = tool_mentions.get(name, 0) + 1

        for tool, count in sorted(tool_mentions.items(), key=lambda x: -x[1]):
            if count >= 3:
                patterns.append({
                    "type": "tool_usage",
                    "pattern": tool,
                    "frequency": count,
                })
        return patterns


# ---------------------------------------------------------------------------
# Skill Creation
# ---------------------------------------------------------------------------

@register
class CreateSkillFromPatternTool:
    """Create a reusable skill definition from discovered usage patterns."""

    tool_id = "create_skill_from_pattern"
    name = "Create Skill From Pattern"
    description = "Generate a TOML skill file from a discovered pattern, locking in reusable behavior as a persistent skill."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Skill name (lowercase, hyphen-separated)",
                },
                "description": {
                    "type": "string",
                    "description": "Short description of what this skill does",
                },
                "trigger_pattern": {
                    "type": "string",
                    "description": "Keywords or patterns that should trigger this skill",
                },
                "instructions": {
                    "type": "string",
                    "description": "Step-by-step instructions for the skill",
                },
                "example_prompt": {
                    "type": "string",
                    "description": "Optional example prompt that triggers this skill",
                },
            },
            "required": ["name", "description", "trigger_pattern", "instructions"],
        }

    def execute(self, name: str, description: str, trigger_pattern: str,
                instructions: str, example_prompt: str = "") -> Dict[str, Any]:
        skill_dir = self._get_skills_dir()
        skill_path = skill_dir / f"{name}.toml"

        if skill_path.exists():
            return {"status": "error", "message": f"Skill '{name}' already exists at {skill_path}"}

        # Build TOML content
        toml_parts = [
            f'[skill]',
            f'name = "{name}"',
            f'description = """{description}"""',
            f'trigger_pattern = """{trigger_pattern}"""',
            "",
            "[executor]",
            'type = "prompt"',
            "",
            "[executor.prompt]",
            f'instructions = """\\',
        ]

        # Split instructions into lines for TOML
        for line in instructions.strip().split("\n"):
            toml_parts.append(line)

        toml_parts.append('"""')
        toml_parts.append("")

        if example_prompt:
            toml_parts.append(f'example_prompt = """{example_prompt}"""')

        toml_content = "\n".join(toml_parts)

        skill_dir.mkdir(parents=True, exist_ok=True)
        skill_path.write_text(toml_content, encoding="utf-8")

        return {
            "status": "ok",
            "skill_name": name,
            "skill_path": str(skill_path),
            "message": f"Skill '{name}' created. It will be loaded on next restart.",
        }

    def _get_skills_dir(self):
        from pathlib import Path
        return Path.home() / ".config" / "openjarvis" / "skills"


# ---------------------------------------------------------------------------
# Learning Status
# ---------------------------------------------------------------------------

@register
class LearningStatusTool:
    """Report the current state of learning and discovered patterns."""

    tool_id = "learning_status"
    name = "Learning Status"
    description = "Show current learning state: patterns discovered, skills created, and active learning configuration."

    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "include_patterns": {
                    "type": "boolean",
                    "description": "Whether to include detailed pattern list",
                    "default": False,
                },
            },
        }

    def execute(self, include_patterns: bool = False) -> Dict[str, Any]:
        try:
            from openjarvis.sessions.session import SessionStore
            store = SessionStore()
            session_count = len(store.list_sessions(limit=100))
        except Exception:
            session_count = 0

        skills_dir = self._get_skills_dir()
        existing_skills = list(skills_dir.glob("*.toml")) if skills_dir.exists() else []

        result = {
            "status": "ok",
            "sessions_available": session_count,
            "skills_created": len(existing_skills),
            "skills": [s.stem for s in existing_skills],
            "learning_enabled": True,
        }

        if include_patterns:
            tool = AnalyzeConversationPatternsTool()
            patterns = tool.execute(max_messages=50)
            result["patterns"] = patterns.get("patterns", [])

        return result

    def _get_skills_dir(self):
        from pathlib import Path
        return Path.home() / ".config" / "openjarvis" / "skills"
