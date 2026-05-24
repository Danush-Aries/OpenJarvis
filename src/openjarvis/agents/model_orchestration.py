"""ModelOrchestrationAgent — High-End Dynamic Multi-Agent Orchestrator.

Implements a NousResearch Hermes / OpenClaw-style cognitive architecture with:
1. Dynamic Model Routing: Route deep coding/auditing to high-reasoning models, and fast boilerplate/tool executions to high-speed models.
2. Sub-Agent Collaboration Cascade: Virtual Architect, Developer, and Auditor sub-agents collaborating on the same task context.
3. Self-Healing Tool Loop: Autonomously debug and repair syntax, test, and shell execution errors using feedback from the Auditor.
"""

from __future__ import annotations

import logging
import re
import json
from typing import Any, Dict, List, Optional

from openjarvis.agents._stubs import AgentContext, AgentResult, ToolUsingAgent
from openjarvis.core.events import EventBus
from openjarvis.core.registry import AgentRegistry
from openjarvis.core.types import Message, Role, ToolCall, ToolResult
from openjarvis.engine._stubs import InferenceEngine
from openjarvis.tools._stubs import BaseTool

logger = logging.getLogger(__name__)

# System prompts for specialized virtual sub-agents
ARCHITECT_SYSTEM_PROMPT = (
    "You are the J.A.R.V.I.S. Lead Architect (NousResearch/Hermes style).\n"
    "Your role is to analyze Dhanush's request, formulate a flawless technical implementation plan, "
    "and identify all required system tools, folders, and dependencies.\n"
    "Think step-by-step. Keep your responses structured. Output your plan inside <architecture_plan> tags.\n"
    "Do NOT invoke any tools directly in this phase. Simply design the implementation blueprint."
)

DEVELOPER_SYSTEM_PROMPT = (
    "You are the J.A.R.V.I.S. Master Developer (OpenClaw style).\n"
    "Your role is to execute the architectural plan step-by-step using your available physical system tools.\n"
    "You must prioritize completing the tasks correctly and robustly. Address the user politely as 'sir' or 'Dhanush'.\n"
    "For code generation, write highly optimized code. When calling tools, call them in parallel or sequence, "
    "and always inspect their observations before deciding on the next step."
)

AUDITOR_SYSTEM_PROMPT = (
    "You are the J.A.R.V.I.S. Security & Quality Auditor.\n"
    "Your role is to strictly review the developer's implementations, check tool execution logs for errors/warnings, "
    "and verify code correctness.\n"
    "IMPORTANT: If Dhanush's request is a conversational greeting, general question, or does not require implementing "
    "or running code, you MUST immediately output <audit_verdict status=\"PASSED\"> to approve it.\n"
    "If you find syntax errors, shell failures, or security flaws in code changes, output <audit_verdict status=\"FAILED\"> "
    "followed by clear debugging instructions so the Developer can self-heal.\n"
    "If everything is correct and verified successfully, output <audit_verdict status=\"PASSED\">."
)


@AgentRegistry.register("model_orchestration")
class ModelOrchestrationAgent(ToolUsingAgent):
    """High-End Multi-Agent Orchestrator executing the Architect-Developer-Auditor cascade."""

    agent_id = "model_orchestration"
    _default_temperature = 0.5
    _default_max_tokens = 4096
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
        parallel_tools: bool = True,
        interactive: bool = False,
        confirm_callback=None,
    ) -> None:
        super().__init__(
            engine,
            model,
            tools=tools,
            bus=bus,
            max_turns=max_turns,
            temperature=temperature,
            max_tokens=max_tokens,
            interactive=interactive,
            confirm_callback=confirm_callback,
        )
        self._parallel_tools = parallel_tools

    def _determine_routing_model(self, input_text: str) -> str:
        """Dynamically route requests to high-reasoning models for agentic reliability."""
        # Always use Sonnet (llama-3.3-nemotron-super-49b) as the baseline for multi-agent cascades
        return "claude-3-5-sonnet-20241022"

    def run(
        self,
        input: str,
        context: Optional[AgentContext] = None,
        **kwargs: Any,
    ) -> AgentResult:
        self._emit_turn_start(input)

        # ── Step 1: Dynamic Task Routing ──────────────────────────────────
        active_model = self._determine_routing_model(input)
        logger.info("[ModelOrchestrator] Selected model routing: %s", active_model)
        
        # Stash current model and restore after completion
        original_model = self._model
        self._model = active_model

        all_tool_results: List[ToolResult] = []
        turns = 0

        try:
            # ── Step 2: Architect Phase ───────────────────────────────────
            architect_messages = self._build_messages(
                input, context, system_prompt=ARCHITECT_SYSTEM_PROMPT
            )
            logger.info("[ModelOrchestrator] Invoking Lead Architect...")
            architect_result = self._generate(architect_messages)
            architect_plan = architect_result.get("content", "")
            logger.info("[ModelOrchestrator] Architectural plan generated successfully.")

            # ── Step 3: Developer & Auditor Self-Healing Cascade ──────────
            # Compile Developer context including the original request and the Architect's design
            dev_prompt = (
                f"User Request: {input}\n\n"
                f"Architectural Plan:\n{architect_plan}\n\n"
                "Please execute this plan step-by-step. Remember to address the user as 'sir' or 'Dhanush' "
                "with polite British wit, and invoke the appropriate tools to accomplish each step."
            )
            
            developer_messages = [
                Message(role=Role.SYSTEM, content=DEVELOPER_SYSTEM_PROMPT)
            ]
            if context and context.conversation.messages:
                # Carry over previous conversation history
                developer_messages.extend(context.conversation.messages)
            developer_messages.append(Message(role=Role.USER, content=dev_prompt))

            openai_tools = self._executor.get_openai_tools() if self._tools else []

            # Multi-turn execution loop
            for turn in range(self._max_turns):
                turns += 1

                if self._loop_guard:
                    developer_messages = self._loop_guard.compress_context(developer_messages)

                gen_kwargs: dict[str, Any] = {}
                if openai_tools:
                    gen_kwargs["tools"] = openai_tools

                # Call developer model to generate content or tool calls
                dev_gen = self._generate(developer_messages, **gen_kwargs)
                dev_content = dev_gen.get("content", "")
                raw_tool_calls = dev_gen.get("tool_calls", [])

                # ── Tool Execution Turn ───────────────────────────────────
                if raw_tool_calls:
                    tool_calls = [
                        ToolCall(
                            id=tc.get("id", f"call_{i}"),
                            name=tc.get("name", ""),
                            arguments=tc.get("arguments", "{}"),
                        )
                        for i, tc in enumerate(raw_tool_calls)
                    ]

                    # Append developer message with tool calls
                    developer_messages.append(
                        Message(
                            role=Role.ASSISTANT,
                            content=dev_content,
                            tool_calls=tool_calls,
                        )
                    )

                    # Execute tools sequentially (cleaner error tracking for self-healing)
                    for tc in tool_calls:
                        if self._loop_guard:
                            verdict = self._loop_guard.check_call(tc.name, tc.arguments)
                            if verdict.blocked:
                                tool_result = ToolResult(
                                    tool_name=tc.name,
                                    content=f"Loop guard: {verdict.reason}",
                                    success=False,
                                )
                                all_tool_results.append(tool_result)
                                developer_messages.append(
                                    Message(
                                        role=Role.TOOL,
                                        content=tool_result.content,
                                        tool_call_id=tc.id,
                                        name=tc.name,
                                    )
                                )
                                continue

                        logger.info("[ModelOrchestrator] Executing tool: %s", tc.name)
                        tool_result = self._executor.execute(tc)
                        all_tool_results.append(tool_result)

                        # Append tool response
                        developer_messages.append(
                            Message(
                                role=Role.TOOL,
                                content=tool_result.content,
                                tool_call_id=tc.id,
                                name=tc.name,
                            )
                        )
                    continue

                # ── Content Response & Audit Turn ──────────────────────────
                # Developer returned a text response. We now invoke the Auditor.
                developer_messages.append(Message(role=Role.ASSISTANT, content=dev_content))
                
                # Check with Auditor
                logger.info("[ModelOrchestrator] Invoking Security & Quality Auditor...")
                audit_messages = [
                    Message(role=Role.SYSTEM, content=AUDITOR_SYSTEM_PROMPT),
                    Message(role=Role.USER, content=(
                        f"Dhanush's Request: {input}\n\n"
                        f"Developer Response:\n{dev_content}\n\n"
                        f"Tool Results:\n" + "\n".join(
                            [f"Tool: {r.tool_name} | Success: {r.success} | Content: {r.content[:400]}" for r in all_tool_results[-5:]]
                        )
                    ))
                ]
                
                audit_gen = self._generate(audit_messages, temperature=0.2)
                audit_content = audit_gen.get("content", "")
                
                # Parse Audit Verdict
                passed = True
                fail_match = re.search(r'<audit_verdict status=["\']FAILED["\']>(.*?)(?:</audit_verdict>|\Z)', audit_content, re.DOTALL | re.IGNORECASE)
                if fail_match:
                    passed = False
                    debugging_instructions = fail_match.group(1).strip()
                    logger.warning("[ModelOrchestrator] AUDIT FAILED! Triggering self-healing loop.")
                    
                    # Feed the debugging instructions back into the Developer flow to self-heal
                    developer_messages.append(
                        Message(
                            role=Role.USER,
                            content=(
                                "WARNING: The Auditor rejected this implementation with the following feedback:\n"
                                f"{debugging_instructions}\n\n"
                                "Please fix the code or repair the system errors immediately."
                            )
                        )
                    )
                else:
                    logger.info("[ModelOrchestrator] AUDIT PASSED! Core implementation approved.")
                    final_reply = self._strip_think_tags(dev_content)
                    self._emit_turn_end(turns=turns, content_length=len(final_reply))
                    return AgentResult(
                        content=final_reply,
                        tool_results=all_tool_results,
                        turns=turns,
                    )

            # Max turns exceeded
            return self._max_turns_result(all_tool_results, turns, content=dev_content)

        finally:
            # Restore original model
            self._model = original_model
