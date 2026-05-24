"""Research Agent -- Specialized agent for web research and information gathering.

This agent is optimized for research tasks including:
- Gathering information from the web
- Fact-checking and verification
- Comprehensive topic research
- Summarizing complex information
- Finding recent developments and trends
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

RESEARCH_AGENT_SYSTEM_PROMPT = """\
You are Jarvis, an expert research assistant with access to current web information. You excel at:
- Finding accurate, up-to-date information from the web
- Conducting comprehensive research on complex topics
- Fact-checking and verifying information from multiple sources
- Summarizing large amounts of information concisely
- Identifying trends, patterns, and insights in data
- Providing well-sourced answers with proper attribution

When working on research tasks:
1. Start by understanding the research question or topic
2. Break down complex questions into specific search queries
3. Gather information from multiple reliable sources
4. Cross-reference information to verify accuracy
5. Synthesize findings into a coherent, well-structured answer
6. Cite your sources properly and indicate confidence levels
7. Note any limitations or conflicting information found

You have access to research tools including:
- Web search for finding current information
- Browser automation for interacting with websites and extracting content
- File read/write for saving and organizing research materials
- Various knowledge and analysis tools

Always strive for accuracy, completeness, and proper source attribution in your research.

{skill_examples}{tool_descriptions}
"""

# Few-shot examples for research tasks
RESEARCH_FEW_SHOT_EXAMPLES = [
    {
        "input": "What are the latest developments in quantum computing as of 2024?",
        "output": """Thought: I need to search for recent developments in quantum computing from 2024. I'll use specific keywords to find the most recent and relevant information.
Action: web_search
Action Input: {"query": "quantum computing breakthroughs 2024 latest developments", "max_results": 10}
Observation: Search results show several 2024 developments including IBM's 1,121-qubit Condor chip, Google's quantum error correction progress, and various quantum advantage demonstrations.

Thought: Let me get more specific details about some of these developments to provide a comprehensive answer.
Action: web_search
Action Input: {"query": "IBM Condor 1121 qubit quantum processor 2024 details", "max_results": 5}
Observation: Results show IBM unveiled the Condor chip in 2023, with 2024 focusing on error correction and software development. More recent 2024 developments include quantum networking advances and error mitigation techniques.

Thought: Now I'll search for other major 2024 developments to give a well-rounded view.
Action: web_search
Action Input: {"query": "2024 quantum error correction breakthroughs fault tolerance", "max_results": 5}
Observation: Shows progress in surface code error correction, logical qubit demonstrations, and various error mitigation strategies from companies like Quantinuum, Intel, and academic labs.

Thought: I have enough information to provide a comprehensive answer about 2024 quantum computing developments.
Final Answer: In 2024, quantum computing saw several significant developments:

1. **Quantum Hardware Advances**: While IBM's 1,121-qubit Condor chip was unveiled in late 2023, 2024 focused on improving qubit quality, connectivity, and control systems. Companies like Quantinuum and IonQ demonstrated advances in trapped-ion qubits with higher fidelity operations.

2. **Error Correction Progress**: Major strides were made in quantum error correction, including:
   - First demonstrations of logical qubits with error rates below physical qubit levels
   - Advances in surface code implementation and decoding algorithms
   - Various error mitigation techniques showing promise for near-term quantum advantage

3. **Quantum Networking and Communication**: 
   - Progress in quantum repeaters and quantum memory storage
   - Demonstrations of quantum entanglement over increasing distances
   - Development of quantum internet protocols

4. **Software and Algorithms**:
   - Improved quantum machine learning algorithms
   - Better optimization techniques for quantum approximate optimization algorithm (QAOA)
   - Advances in quantum simulation for chemistry and materials science

5. **Industry and Investment**:
   - Continued growth in quantum computing investment
   - More companies entering the quantum space
   - Development of quantum-specific talent pipelines

The field is moving from pure physics experiments toward engineering-focused development, with increasing emphasis on practical error correction and scalable architectures.
""",
    },
    {
        "input": "Explain the concept of machine learning overfitting and how to prevent it",
        "output": """Thought: This is a conceptual question about machine learning that I can answer based on established knowledge, but I'll verify some details with a quick search to ensure accuracy.
Action: web_search
Action Input: {"query": "machine learning overfitting prevention techniques regularization", "max_results": 5}
Observation: Results confirm the standard definition and techniques, mentioning regularization, cross-validation, early stopping, and data augmentation.

Thought: Now I'll provide a comprehensive explanation based on my knowledge and verified information.
Final Answer: **Overfitting in Machine Learning**

Overfitting occurs when a machine learning model learns the training data too well, including its noise and outliers, resulting in poor performance on new, unseen data. The model essentially memorizes the training examples rather than learning generalizable patterns.

**Signs of Overfitting:**
- High accuracy on training data but low accuracy on validation/test data
- Model complexity that doesn't generalize
- Performance gap between training and validation sets that widens over time

**Causes:**
- Model too complex relative to amount of training data
- Insufficient training data
- Noisy or unrepresentative training data
- Training for too many epochs (in neural networks)

**Prevention Techniques:**

1. **Cross-Validation**: Use techniques like k-fold cross-validation to get more reliable estimates of model performance

2. **Regularization**: Add penalty terms to the loss function to discourage complex models:
   - L1 (Lasso): Encourages sparsity
   - L2 (Ridge): Penalizes large weights
   - Dropout: Randomly deactivates neurons during training (neural networks)

3. **Early Stopping**: Monitor validation performance and stop training when it starts to degrade

4. **Data Augmentation**: Artificially increase training data size by creating modified versions of existing data (especially effective for images)

5. **Feature Selection**: Use only the most relevant features to reduce model complexity

6. **Ensemble Methods**: Combine multiple models to reduce variance (e.g., Random Forest, Gradient Boosting)

7. **Simpler Models**: Start with simpler models and increase complexity only when needed

8. **More Training Data**: When possible, gather more representative training data

The key is finding the right balance between model complexity and generalization ability - a model should be complex enough to capture underlying patterns but simple enough to generalize to new data.
""",
    },
]


@AgentRegistry.register("research_agent")
class ResearchAgent(ToolUsingAgent):
    """Specialized agent for web research and information gathering."""

    agent_id = "research_agent"
    _default_temperature = 0.3  # Balanced temperature for factual yet engaging research
    _default_max_tokens = 3072
    _default_max_turns = 12

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
        # Combine default research tools with any provided tools
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
            skill_few_shot_examples=skill_few_shot_examples or RESEARCH_FEW_SHOT_EXAMPLES,
        )

    def _get_default_tools(self) -> List[BaseTool]:
        """Get the default set of tools for research tasks."""
        from openjarvis.tools.web_search import WebSearchTool
        from openjarvis.tools.browser import BrowserNavigateTool, BrowserClickTool, BrowserTypeTool
        from openjarvis.tools.file_read import FileReadTool
        from openjarvis.tools.file_write import FileWriteTool
        
        return [
            WebSearchTool(),
            BrowserNavigateTool(),
            BrowserClickTool(),
            BrowserTypeTool(),
            FileReadTool(),
            FileWriteTool(),
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
            load_system_prompt_override("research_agent") or RESEARCH_AGENT_SYSTEM_PROMPT
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
        for ex in load_few_shot_exemplars("research_agent"):
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
                id=f"research_{turns}",
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


__all__ = ["ResearchAgent", "RESEARCH_AGENT_SYSTEM_PROMPT"]