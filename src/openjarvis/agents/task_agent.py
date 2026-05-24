"""Task Agent -- Specialized agent for system tasks and automation.

This agent is optimized for task execution including:
- Running system commands and scripts
- Managing files and directories
- Controlling applications and system settings
- Automating repetitive tasks
- Managing processes and services
"""

from __future__ import annotations

import os
import re
from typing import Any, List, Optional

from openjarvis.agents._stubs import AgentContext, AgentResult, ToolUsingAgent
from openjarvis.agents.prompt_loader import (
    load_few_shot_exemplars,
    load_system_prompt_override,
)
from openjarvis.core.events import EventBus
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Message, Role, ToolCall, ToolResult, _message_to_dict
from openjarvis.engine._stubs import InferenceEngine
from openjarvis.tools._stubs import BaseTool, build_tool_descriptions

TASK_AGENT_SYSTEM_PROMPT = """\
You are Jarvis, an expert system administration and automation assistant. You excel at:
- Executing system commands and shell scripts safely and efficiently
- Managing files, directories, and storage systems
- Controlling applications, services, and system processes
- Automating repetitive tasks and workflows
- Monitoring system performance and resource usage
- Troubleshooting system issues and providing solutions

When working on task execution:
1. First understand the task requirements and constraints
2. Plan the safest and most efficient approach
3. Execute commands with proper validation and error handling
4. Verify results and provide clear feedback
5. Clean up any temporary resources when appropriate
6. Document what was done for future reference

You have access to system tools including:
- Shell execution for running commands and scripts
- File read/write for managing files and configurations
- Application launcher for opening and controlling desktop apps
- System controller for managing macOS-specific features
- Process and service management tools

Always prioritize safety, clarity, and effectiveness in your system interactions.
Never execute destructive commands without explicit confirmation.
Provide clear explanations of what actions were taken and why.

{skill_examples}{tool_descriptions}
"""

# Few-shot examples for task execution
TASK_FEW_SHOT_EXAMPLES = [
    {
        "input": "Create a backup of my Documents folder to a timestamped folder",
        "output": """Thought: I need to create a backup of the Documents folder with a timestamp. I'll use the date command to generate a timestamp and then use cp or rsync to copy the folder.
Action: shell_exec
Action Input: {"command": "date '+%Y-%m-%d_%H-%M-%s'"}
Observation: === STDOUT ===
2026-05-25_14-30-22

Thought: Now I'll create the backup directory and copy the Documents folder to it.
Action: shell_exec
Action Input: {"command": "mkdir -p ~/Documents_backup_2026-05-25_14-30-22 && cp -r ~/Documents/* ~/Documents_backup_2026-05-25_14-30-22/"}
Observation: === STDOUT ===
(no output)

Thought: Let me verify the backup was created successfully by checking the contents.
Action: shell_exec
Action Input: {"command": "ls -la ~/Documents_backup_2026-05-25_14-30-22 | head -10"}
Observation: === STDOUT ===
total 0
drwxr-xr-x  5 dhanush  staff   160 May 25 14:30 .
drwxr-xr-x  30 dhanush  staff   960 May 25 14:30 ..
drwxr-xr-x  @ dhanush  staff   128 May 24 10:15 Projects
drwxr-xr-x  @ dhanush  staff   128 May 24 10:15 Research
drwxr-xr-x  @ dhanush  staff   128 May 24 10:15 Archives
...

Thought: The backup appears to have been created successfully. I'll provide a summary of what was done.
Final Answer: I've successfully created a backup of your Documents folder. Here's what I did:\n\n1. Generated a timestamp: 2026-05-25_14-30-22\n2. Created a backup directory: ~/Documents_backup_2026-05-25_14-30-22\n3. Copied all contents from ~/Documents to the backup directory\n4. Verified the backup by listing the contents\n\nYour Documents folder has been successfully backed up to ~/Documents_backup_2026-05-25_14-30-22. The backup includes all files and subdirectories from your original Documents folder.
""",
    },
    {
        "input": "Show me the top 5 processes by memory usage on this system",
        "output": """Thought: I need to show the top 5 processes by memory usage. I'll use the ps command with appropriate sorting options.
Action: shell_exec
Action Input: {"command": "ps aux --sort=-%mem | head -6"}
Observation: === STDOUT ===
USER         PID %CPU %MEM    VSZ   RSS TTY      STAT START   TIME COMMAND
dhanush   12345  0.2  15.2  4567890 123456 ?      Ssl  10:30   2:45 /Applications/Google Chrome.app/Contents/MacOS/Google Chrome --flag-switches-begin --flag-switches-end
dhanush   12346  0.1  12.8  3456789 102456 ?      Ssl  10:31   1:20 /Applications/Slack.app/Contents/MacOS/Slack
dhanush   12347  0.5  10.5  2345678  84567 ?      Sl   10:32   3:10 /usr/lib/insyslogd
dhanush   12348  0.0  8.9   1234567  71234 ??     Ss   10:00   0:15 /usr/libexec/syslogd
dhanush   12349  0.3  7.2   987654  57890 ?      S    10:33   0:45 /Applications/Spotify.app/Contents/MacOS/Spotify

Thought: I have the process information. Now I'll format it into a clear, readable response.
Final Answer: Here are the top 5 processes by memory usage on your system:\n\n1. **Google Chrome** (PID: 12345)\n   - Memory Usage: 15.2% (123.456 MB RSS)\n   - CPU Usage: 0.2%\n   - Status: Running\n\n2. **Slack** (PID: 12346)\n   - Memory Usage: 12.8% (102.456 MB RSS)\n   - CPU Usage: 0.1%\n   - Status: Running\n\n3. **insyslogd** (PID: 12347)\n   - Memory Usage: 10.5% (84.567 MB RSS)\n   - CPU Usage: 0.5%\n   - Status: Running\n\n4. **syslogd** (PID: 12348)\n   - Memory Usage: 8.9% (71.234 MB RSS)\n   - CPU Usage: 0.0%\n   - Status: Running\n\n5. **Spotify** (PID: 12349)\n   - Memory Usage: 7.2% (57.890 MB RSS)\n   - CPU Usage: 0.3%\n   - Status: Running\n\nNote: Memory usage is shown as both percentage of total RAM and actual RSS (Resident Set Size) in megabytes.
""",
    },
]


@AgentRegistry.register("task_agent")
class TaskAgent(ToolUsingAgent):
    """Specialized agent for system tasks and automation."""

    agent_id = "task_agent"
    _default_temperature = 0.1  # Very low temperature for precise, reliable task execution
    _default_max_tokens = 2048
    _default_max_turns = 10

    def __init__(
        self,
        engine: InferenceEngine,
        model: str,
        *,
        tools: Optional[List[BaseTool]] = None,
        bus: Optional[EventBus] = None,
        max_turns: Optional[int] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        interactive: bool = False,
        confirm_callback=None,
        skill_few_shot_examples: Optional[List[str]] = None,
    ) -> None:
        # Combine default task tools with any provided tools
        default_tools = self._get_default_tools()
        if tools:
            all_tools = default_tools + tools
        else:
            all_tools = default_tools
            
        super().__init__(
            engine,
            model,
            tools=all_tools,
            bus=bus,
            max_turns=max_turns,
            temperature=temperature,
            max_tokens=max_tokens,
            interactive=interactive,
            confirm_callback=confirm_callback,
            skill_few_shot_examples=skill_few_shot_examples or TASK_FEW_SHOT_EXAMPLES,
        )

    def _get_default_tools(self) -> List[BaseTool]:
        """Get the default set of tools for task execution."""
        from openjarvis.tools.shell_exec import ShellExecTool
        from openjarvis.tools.file_read import FileReadTool
        from openjarvis.tools.file_write import FileWriteTool
        from openjarvis.tools.app_launcher import AppLaunchTool
        from openjarvis.tools.mac_system import MacControllerTool
        from openjarvis.tools.launch_app import LaunchAppTool  # Fixed import
        
        return [
            ShellExecTool(),
            FileReadTool(),
            FileWriteTool(),
            AppLaunchTool(),
            MacControllerTool(),
        ]

    def _parse_response(self, text: str) -> dict:
        """Parse ReAct structured output."""
        result = {"thought": "", "action": "", "action_input": "", "final_answer": ""}

        # Extract Thought
        thought_match = re.search(
            r"Thought:\\s*(.+?)(?=\\nAction:|\\nFinal Answer:|\\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if thought_match:
            result["thought"] = thought_match.group(1).strip()

        # Check for Final Answer
        final_match = re.search(
            r"Final Answer:\\s*(.+)", text, re.DOTALL | re.IGNORECASE
        )
        if final_match:
            result["final_answer"] = final_match.group(1).strip()
            return result

        # Extract Action and Action Input
        action_match = re.search(r"Action:\\s*(.+)", text, re.IGNORECASE)
        if action_match:
            result["action"] = action_match.group(1).strip()

        input_match = re.search(
            r"Action Input:\\s*(.+?)(?=\\n\\n|\\nThought:|\\Z)",
            text,
            re.DOTALL | re.IGNORECASE,
        )
        if input_match:
            result["action_input"] = input_match.group(1).strip()

        return result

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        self._emit_turn_start(input)

        # Build system prompt with rich tool descriptions
        tool_desc = build_tool_descriptions(self._tools)
        # Plan 2B I3: render optimized few-shot skill examples as a section
        # before the tool descriptions. Empty string when not present.
        if self._skill_few_shot_examples:
            skill_examples_block = (
                "## Skill Examples\\n\\n"
                + "\\n\\n".join(self._skill_few_shot_examples)
                + "\\n\\n"
            )
        else:
            skill_examples_block = ""
        # Respect $OPENJARVIS_HOME override for the base template (M2+ work).
        prompt_template = (
            load_system_prompt_override("task_agent") or TASK_AGENT_SYSTEM_PROMPT
        )
        # External overrides may not include the {skill_examples} slot.
        try:
            system_prompt = prompt_template.format(
                tool_descriptions=tool_desc,
                skill_examples=skill_examples_block,
            )
        except KeyError:
            system_prompt = prompt_template.format(tool_descriptions=tool_desc)
            if skill_examples_block:
                system_prompt = system_prompt + "\\n\\n" + skill_examples_block

        messages = self._build_messages(input, context, system_prompt=system_prompt)

        # Inject few-shot exemplars before the user input
        for ex in load_few_shot_exemplars("task_agent"):
            if ex.get("input") and ex.get("output"):
                messages.insert(-1, Message(role=Role.USER, content=ex["input"]))
                messages.insert(-1, Message(role=Role.ASSISTANT, content=ex["output"]))

        all_tool_results: list[ToolResult] = []
        turns = 0
        total_usage: dict[str, int] = {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
        }

        for _turn in range(self._max_turns):
            turns += 1

            if self._loop_guard:
                messages = self._loop_guard.compress_context(messages)

            result = self._generate(messages)
            usage = result.get("usage", {})
            for k in total_usage:
                total_usage[k] += usage.get(k, 0)

            content = result.get("content", "")
            parsed = self._parse_response(content)

            # Final answer?
            if parsed["final_answer"]:
                self._emit_turn_end(turns=turns)
                msg_dicts = [_message_to_dict(m) for m in messages]
                return AgentResult(
                    content=parsed["final_answer"],
                    tool_results=all_tool_results,
                    turns=turns,
                    metadata={**total_usage, "messages": msg_dicts},
                )

            # No action? Treat content as final answer
            if not parsed["action"]:
                self._emit_turn_end(turns=turns)
                msg_dicts = [_message_to_dict(m) for m in messages]
                return AgentResult(
                    content=content,
                    tool_results=all_tool_results,
                    turns=turns,
                    metadata={**total_usage, "messages": msg_dicts},
                )

            # Execute action
            messages.append(Message(role=Role.ASSISTANT, content=content))

            tool_call = ToolCall(
                id=f"task_{turns}",
                name=parsed["action"],
                arguments=parsed["action_input"] or "{}",
            )

            # Loop guard check before execution
            if self._loop_guard:
                verdict = self._loop_guard.check_call(
                    tool_call.name,
                    tool_call.arguments,
                )
                if verdict.blocked:
                    tool_result = ToolResult(
                        tool_name=tool_call.name,
                        content=f"Loop guard: {verdict.reason}",
                        success=False,
                    )
                    all_tool_results.append(tool_result)
                    observation = f"Observation: {tool_result.content}"
                    messages.append(Message(role=Role.USER, content=observation))
                    continue

            tool_result = self._executor.execute(tool_call)
            all_tool_results.append(tool_result)

            observation = f"Observation: {tool_result.content}"
            messages.append(Message(role=Role.USER, content=observation))

        # Max turns exceeded
        msg_dicts = [_message_to_dict(m) for m in messages]
        return self._max_turns_result(
            all_tool_results,
            turns,
            metadata={**total_usage, "messages": msg_dicts},
        )


__all__ = ["TaskAgent", "TASK_AGENT_SYSTEM_PROMPT"]