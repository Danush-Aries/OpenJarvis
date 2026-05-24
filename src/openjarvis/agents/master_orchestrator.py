"""Master Orchestrator Agent -- Routes requests to specialized sub-agents.

This agent analyzes incoming requests and routes them to the most appropriate
specialized agent based on the content and intent of the request.
"""

from __future__ import annotations

import re
from typing import Any, Optional

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

MASTER_ORCHESTRATOR_SYSTEM_PROMPT = """\
You are Jarvis, the master AI assistant that coordinates specialized sub-agents. Your role is to:
1. Analyze user requests to determine their intent and domain
2. Route requests to the most appropriate specialized agent:
   - Coding Agent: For software development, programming, debugging, code-related tasks
   - Research Agent: For information gathering, web research, fact-checking, learning topics
   - Task Agent: For system administration, automation, file management, command execution
3. Provide clear routing decisions and explanations
4. Handle simple conversational requests directly when appropriate

When analyzing requests:
- Coding requests typically contain: code, programming, debug, fix, implement, function, class, algorithm, API, database, etc.
- Research requests typically contain: what is, explain, tell me about, research, find, search, learn, understand, compare, latest, news, etc.
- Task requests typically contain: run, execute, create, delete, move, copy, launch, open, close, start, stop, install, configure, system, file, folder, etc.

For simple greetings, thanks, or casual conversation, respond directly as Jarvis.

Always explain your routing decision briefly before delegating to a sub-agent.

{skill_examples}{tool_descriptions}
"""

# Few-shot examples for orchestration
ORCHESTRATOR_FEW_SHOT_EXAMPLES = [
    {
        "input": "Hello Jarvis, how are you today?",
        "output": """Thought: This is a simple greeting and casual conversation. I should respond directly as Jarvis without delegating to a specialized agent.
Final Answer: I'm functioning optimally, sir. All systems are online and ready to assist you with any tasks you may have. How may I be of service today?
""",
    },
    {
        "input": "Can you create a Python script that sorts a list of dictionaries by a specific key?",
        "output": """Thought: This request is asking for code creation - specifically a Python script that sorts dictionaries. This clearly falls under software development, so I should route this to the Coding Agent.
Final Answer: I'll route this request to the Coding Agent, as it involves creating a Python script for sorting dictionaries, which is a software development task.
""",
    },
    {
        "input": "What are the latest developments in artificial intelligence this month?",
        "output": """Thought: This request is asking for information about recent developments in AI. This involves gathering current information from the web, which is a research task. I should route this to the Research Agent.
Final Answer: I'll route this request to the Research Agent, as it involves gathering recent information about AI developments, which requires web research and information synthesis.
""",
    },
    {
        "input": "Please clean up my desktop by organizing all files into appropriate folders",
        "output": """Thought: This request is asking for file organization and system cleanup. This involves managing files and directories on the system, which is a system administration task. I should route this to the Task Agent.
Final Answer: I'll route this request to the Task Agent, as it involves organizing files and cleaning up the desktop, which requires system task execution and file management.
""",
    },
]


@AgentRegistry.register("master_orchestrator")
class MasterOrchestratorAgent(ToolUsingAgent):
    """Master orchestrator that routes requests to specialized sub-agents."""

    agent_id = "master_orchestrator"
    _default_temperature = 0.2  # Low temperature for consistent routing decisions
    _default_max_tokens = 1024
    _default_max_turns = 3  # Few turns needed for routing decision

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
        # The orchestrator doesn't need many tools - mainly for simple responses
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
            skill_few_shot_examples=skill_few_shot_examples or ORCHESTRATOR_FEW_SHOT_EXAMPLES,
        )

    def _get_default_tools(self) -> List[BaseTool]:
        """Get the default set of tools for the orchestrator."""
        from openjarvis.tools.file_read import FileReadTool
        from openjarvis.tools.file_write import FileWriteTool
        
        return [
            FileReadTool(),
            FileWriteTool(),
        ]

    def _analyze_request_intent(self, input_text: str) -> str:
        """Analyze the request to determine the appropriate agent."""
        input_lower = input_text.lower().strip()
        
        # Simple conversational patterns
        conversational_patterns = [
            r'^(hi|hello|hey|good\s+(morning|afternoon|evening)|how\s+are\s+you|what\'s\s+up)',
            r'(thanks?|thank\s+you|appreciate it)',
            r'(bye|goodbye|see\s+you)',
            r'^(who\s+are\s+you|what\s+can\s+you\s+do)',
        ]
        
        for pattern in conversational_patterns:
            if re.search(pattern, input_lower):
                return "conversational"
        
        # Coding-related patterns
        coding_patterns = [
            r'\b(code|program|script|function|class|method|variable|algorithm)\b',
            r'\b(debug|fix|error|bug|issue|problem)\b',
            r'\b(implement|create|build|develop|write)\b.*\b(code|program|script|app|application)\b',
            r'\b(python|javascript|java|c\+\+|ruby|php|swift|kotlin|go|rust)\b',
            r'\b(api|database|sql|query|html|css|frontend|backend|fullstack)\b',
            r'\b(test|testing|unit\s+test|integration\s+test)\b',
            r'\b(refactor|optimize|improve|enhance)\b.*\b(code|performance)\b',
            r'\b(framework|library|package|module|dependency)\b',
        ]
        
        # Research-related patterns
        research_patterns = [
            r'\b(what\s+is|what\s+are|explain|tell\s+me\s+about|describe)\b',
            r'\b(research|study|investigate|explore|learn|understand)\b',
            r'\b(find|search|look\s+up|look\s+for)\b.*\b(information|data|facts|details)\b',
            r'\b(latest|recent|current|news|update|development|trend)\b',
            r'\b(compare|difference|versus|vs|better|best|worst)\b',
            r'\b(how\s+to|how\s+do|how\s+can)\b',
            r'\b(why\s+is|why\s+are|why\s+does)\b',
            r'\b(who\s+is|who\s+are|when\s+is|where\s+is)\b',
            r'\b(define|definition|meaning|concept)\b',
        ]
        
        # Task-related patterns
        task_patterns = [
            r'\b(run|execute|launch|start|stop|kill|terminate)\b',
            r'\b(create|make|build|delete|remove|copy|move|rename)\b.*\b(file|folder|directory|app|application)\b',
            r'\b(open|close|launch|quit)\b.*\b(app|application|program|window)\b',
            r'\b(install|setup|configure|update|upgrade)\b',
            r'\b(system|computer|machine|device|hardware|software)\b',
            r'\b(file|folder|directory|document|desktop|downloads)\b',
            r'\b(backup|sync|share|transfer|upload|download)\b',
            r'\b(process|service|daemon|service)\b',
            r'\b(volume|brightness|screen|display|audio|sound)\b',
            r'\b(clean|organize|tidy|arrange|sort)\b.*\b(file|folder|desktop|disk)\b',
            r'\b(list|show|display|view)\b.*\b(file|folder|process|service|app)\b',
        ]
        
        # Count matches for each category
        coding_score = sum(1 for pattern in coding_patterns if re.search(pattern, input_lower))
        research_score = sum(1 for pattern in research_patterns if re.search(pattern, input_lower))
        task_score = sum(1 for pattern in task_patterns if re.search(pattern, input_lower))
        
        # Determine the highest scoring category
        if coding_score >= research_score and coding_score >= task_score:
            return "coding"
        elif research_score >= coding_score and research_score >= task_score:
            return "research"
        elif task_score >= coding_score and task_score >= research_score:
            return "task"
        else:
            # Default to research for unclear cases
            return "research"

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

        # Analyze the request to determine routing
        intent = self._analyze_request_intent(input)
        
        # Handle conversational requests directly
        if intent == "conversational":
            # Build a simple response for conversational input
            system_prompt = load_system_prompt_override("master_orchestrator") or MASTER_ORCHESTRATOR_SYSTEM_PROMPT
            tool_desc = build_tool_descriptions(self._tools)
            
            try:
                system_prompt = system_prompt.format(
                    tool_descriptions=tool_desc,
                    skill_examples="",
                )
            except KeyError:
                system_prompt = system_prompt.format(tool_descriptions=tool_desc)
            
            messages = self._build_messages(input, context, system_prompt=system_prompt)
            
            # Inject few-shot exemplars
            for ex in load_few_shot_exemplars("master_orchestrator"):
                if ex.get("input") and ex.get("output"):
                    messages.insert(-1, Message(role=Role.USER, content=ex["input"]))
                    messages.insert(-1, Message(role=Role.ASSISTANT, content=ex["output"]))
            
            result = self._generate(messages)
            content = result.get("content", "")
            
            self._emit_turn_end(turns=1)
            msg_dicts = [_message_to_dict(m) for m in messages]
            return AgentResult(
                content=content,
                tool_results=[],
                turns=1,
                metadata={"messages": msg_dicts},
            )
        
        # For non-conversational requests, provide routing explanation and delegate
        routing_explanations = {
            "coding": "I'll route this to the Coding Agent, as it involves software development or programming tasks.",
            "research": "I'll route this to the Research Agent, as it involves gathering information or researching a topic.",
            "task": "I'll route this to the Task Agent, as it involves system administration or task execution."
        }
        
        explanation = routing_explanations.get(intent, "I'll route this to the Research Agent for information gathering.")
        
        # Build system prompt with routing explanation
        system_prompt = load_system_prompt_override("master_orchestrator") or MASTER_ORCHESTRATOR_SYSTEM_PROMPT
        tool_desc = build_tool_descriptions(self._tools)
        
        try:
            system_prompt = system_prompt.format(
                tool_descriptions=tool_desc,
                skill_examples="",
            )
        except KeyError:
            system_prompt = system_prompt.format(tool_descriptions=tool_desc)
        
        # Add the routing explanation to the system prompt
        enhanced_system_prompt = f"{system_prompt}\n\n{explanation}"
        
        messages = self._build_messages(input, context, system_prompt=enhanced_system_prompt)
        
        # Inject few-shot exemplars
        for ex in load_few_shot_exemplars("master_orchestrator"):
            if ex.get("input") and ex.get("output"):
                messages.insert(-1, Message(role=Role.USER, content=ex["input"]))
                messages.insert(-1, Message(role=Role.ASSISTANT, content=ex["output"]))
        
        result = self._generate(messages)
        content = result.get("content", "")
        
        self._emit_turn_end(turns=1)
        msg_dicts = [_message_to_dict(m) for m in messages]
        return AgentResult(
            content=content,
            tool_results=[],
            turns=1,
            metadata={"messages": msg_dicts, "routed_to": intent},
        )


__all__ = ["MasterOrchestratorAgent", "MASTER_ORCHESTRATOR_SYSTEM_PROMPT"]