"""Coding Agent -- Specialized agent for software development tasks.

This agent is optimized for coding tasks including:
- Writing, debugging, and refactoring code
- Running tests and build commands
- File manipulation and project navigation
- Using development tools and frameworks
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

CODING_AGENT_SYSTEM_PROMPT = """\
You are Jarvis, an expert software engineering assistant. You excel at:
- Writing clean, efficient, and well-documented code in multiple languages
- Debugging complex issues and providing clear explanations
- Refactoring code to improve readability and performance
- Running tests, builds, and development workflows
- Navigating and understanding codebases
- Suggesting architectural improvements and best practices

When working on coding tasks:
1. First understand the problem or requirement clearly
2. Examine existing code if relevant to understand patterns and conventions
3. Write clean, modular code following best practices
4. Test your solutions thoroughly
5. Provide clear explanations of your approach and any trade-offs

You have access to development tools including:
- Code interpreter for running Python code
- File read/write tools for examining and modifying files
- Shell execution for running commands, tests, and build processes
- Web search for finding documentation and examples
- Various development and debugging tools

Always strive for production-quality code and provide actionable feedback.

{skill_examples}{tool_descriptions}
"""

# Few-shot examples for coding tasks
CODING_FEW_SHOT_EXAMPLES = [
    {
        "input": "Create a Python function that calculates the factorial of a number",
        "output": """Thought: I need to create a Python function that calculates factorial. I'll use recursion for a clean solution, but also mention the iterative alternative.
Action: file_write
Action Input: {"path": "factorial.py", "content": "def factorial(n: int) -> int:\n    \"\"\"Calculate the factorial of a non-negative integer.\n    \n    Args:\n        n: Non-negative integer\n        \n    Returns:\n        Factorial of n\n        \n    Raises:\n        ValueError: If n is negative\n    \"\"\"\n    if n < 0:\n        raise ValueError(\"Factorial is not defined for negative numbers\")\n    if n == 0 or n == 1:\n        return 1\n    return n * factorial(n - 1)\n\n# Alternative iterative implementation\n# def factorial_iterative(n: int) -> int:\n#     if n < 0:\n#         raise ValueError(\"Factorial is not defined for negative numbers\")\n#     result = 1\n#     for i in range(2, n + 1):\n#         result *= i\n#     return result", "mode": "write"}
Observation: Successfully wrote to factorial.py
Thought: Now I should test the function to make sure it works correctly.
Action: code_interpreter
Action Input: {"code": "from factorial import factorial\n\n# Test cases\ntest_cases = [0, 1, 5, 10]\nfor n in test_cases:\n    result = factorial(n)\n    print(f\"factorial({n}) = {result}\")\n\n# Test error case\ntry:\n    factorial(-1)\nexcept ValueError as e:\n    print(f\"Error for negative input: {e}\")"}
Observation: === STDOUT ===
factorial(0) = 1
factorial(1) = 1
factorial(5) = 120
factorial(10) = 3628800
Error for negative input: Factorial is not defined for negative numbers

Thought: The function works correctly! I'll provide the final answer with the code and explanation.
Final Answer: I've created a factorial.py file with a recursive factorial function that includes proper error handling, documentation, and test cases. The function correctly calculates factorials for non-negative integers and raises a ValueError for negative inputs. I've also included test cases that verify the function works for inputs 0, 1, 5, and 10, and properly handles the error case.
""",
    },
    {
        "input": "Explain the difference between == and === in JavaScript",
        "output": """Thought: This is a conceptual question about JavaScript equality operators. I need to explain the difference between == (loose equality) and === (strict equality).
Action: web_search
Action Input: {"query": "JavaScript == vs === difference loose vs strict equality"}
Observation: Search results show that == compares values after type coercion, while === compares both value and type without conversion.

Thought: Now I have enough information to provide a comprehensive explanation.
Final Answer: In JavaScript, == and === are both equality operators but they work differently:

== (Loose Equality):
- Compares values after performing type coercion (conversion)
- Converts operands to the same type before comparison
- Examples: 5 == "5" is true (string "5" converted to number), 0 == false is true (false converted to 0), null == undefined is true

=== (Strict Equality):
- Compares both value and type without conversion
- Returns true only if both operands are of the same type and have the same value
- Examples: 5 === "5" is false (different types), 5 === 5 is true (same type and value), null === undefined is false (different types)

Best practice: Always use === (and !==) for comparisons unless you specifically need type coercion, as it leads to more predictable and bug-free code.
""",
    },
]


@AgentRegistry.register("coding_agent")
class CodingAgent(ToolUsingAgent):
    """Specialized agent for software development tasks."""

    agent_id = "coding_agent"
    _default_temperature = 0.2  # Lower temperature for more focused, deterministic coding
    _default_max_tokens = 2048
    _default_max_turns = 15

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
        # Combine default coding tools with any provided tools
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
            skill_few_shot_examples=skill_few_shot_examples or CODING_FEW_SHOT_EXAMPLES,
        )

    def _get_default_tools(self) -> List[BaseTool]:
        """Get the default set of tools for coding tasks."""
        from openjarvis.tools.code_interpreter import CodeInterpreterTool
        from openjarvis.tools.file_read import FileReadTool
        from openjarvis.tools.file_write import FileWriteTool
        from openjarvis.tools.shell_exec import ShellExecTool
        from openjarvis.tools.web_search import WebSearchTool
        
        return [
            CodeInterpreterTool(),
            FileReadTool(),
            FileWriteTool(),
            ShellExecTool(),
            WebSearchTool(),
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
            load_system_prompt_override("coding_agent") or CODING_AGENT_SYSTEM_PROMPT
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
        for ex in load_few_shot_exemplars("coding_agent"):
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
                id=f"coding_{turns}",
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


__all__ = ["CodingAgent", "CODING_AGENT_SYSTEM_PROMPT"]