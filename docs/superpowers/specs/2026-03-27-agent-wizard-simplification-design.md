# Agent Wizard Simplification + Smart Defaults + Tool Wiring

**Date:** 2026-03-27
**Status:** Approved
**Scope:** Sub-project A — wizard UX, template defaults, system prompts, tool wiring, recommended model endpoint

## Problem

The current agent creation wizard has 12+ fields across 3 steps, requires users to understand memory extraction strategies and retrieval backends, and doesn't wire the selected tools to the executor (`tools=[]`). The result: agents are hard to create and can't use the tools users selected.

## Goals

1. Simplify wizard to 2 steps (template → name + instruction)
2. Smart defaults from templates (tools, model, schedule, retrieval)
3. Collapse Advanced settings with sensible defaults
4. Wire tools from config to executor (fix `tools=[]` gap)
5. Rich system prompt templates with tool documentation
6. Backend endpoint for hardware-appropriate model recommendation

## Non-Goals

- OAuth credential flows (Sub-project B)
- Tab population — Tasks, Memory, Logs (Sub-project C)
- New agent types or templates beyond the existing 3 + Custom

---

## Architecture

### 1. Wizard Flow

**Step 1: Template Selection**

A 2x2 grid of template cards:
- Research Monitor (icon: 🔬)
- Inbox Triager (icon: 📥)
- Code Reviewer (icon: 🔍)
- Custom Agent (icon: ⚙️)

Each card shows: name, 1-line description, tool tags. Clicking a card advances to Step 2.

**Step 2: Configuration**

Two required fields at top:
- **Agent Name** — text input
- **What should this agent do?** — textarea for user instruction

Three pre-filled fields below (editable):
- **Intelligence** — dropdown, pre-selected to backend-recommended model, shows "(recommended)" tag
- **Schedule** — pre-filled from template (e.g. "Every day at 9:00 AM" for Research Monitor), editable dropdown for manual/cron/interval
- **Tools** — shown as purple tags, auto-selected from template, clickable to add/remove

Collapsed `<details>` section for Advanced Settings:
- Memory Extraction
- Observation Compression
- Retrieval Strategy
- Task Decomposition
- Max Turns
- Temperature
- Budget
- Learning Policy

**Launch button** at the bottom — no Step 3 review page.

**Custom Agent variation:** Same layout but model defaults to recommended, schedule defaults to manual, tools default to empty (user adds from Advanced or from the tools tag area), and all Advanced settings use universal defaults.

### 2. Template Defaults

Each template TOML defines all fields. Universal defaults (for Custom Agent and any unset template field) are:

| Field | Universal Default |
|-------|-------------------|
| Memory Extraction | `structured_json` |
| Observation Compression | `summarize` |
| Retrieval Strategy | `sqlite` (BM25/FTS5) |
| Task Decomposition | `hierarchical` |
| Max Turns | `25` |
| Temperature | `0.3` |
| Budget | Unlimited |
| Learning Policy | None |

Template-specific overrides:

**research_monitor.toml:**
| Field | Value |
|-------|-------|
| schedule_type | `cron` |
| schedule_value | `0 9 * * *` |
| tools | `web_search`, `http_request`, `file_read`, `file_write`, `memory_store`, `memory_retrieve`, `think` |
| temperature | `0.3` |
| task_decomposition | `phased` |

**inbox_triager.toml:**
| Field | Value |
|-------|-------|
| schedule_type | `interval` |
| schedule_value | `1800` |
| tools | `channel_send`, `channel_list`, `memory_store`, `memory_retrieve`, `think`, `web_search`, `file_write` |
| max_turns | `20` |
| retrieval_strategy | `sqlite` |
| task_decomposition | `phased` |

**code_reviewer.toml:**
| Field | Value |
|-------|-------|
| schedule_type | `interval` |
| schedule_value | `3600` |
| tools | `file_read`, `file_write`, `shell_exec`, `git_status`, `git_diff`, `git_commit`, `git_log`, `apply_patch`, `code_interpreter`, `memory_store`, `memory_retrieve`, `think` |
| temperature | `0.1` |
| memory_extraction | `scratchpad` |
| retrieval_strategy | `sqlite` |
| task_decomposition | `monolithic` |

### 3. System Prompt Templates

Each template includes a rich system prompt that documents available tools, workflow steps, and quality standards. The user's instruction is inserted at `{instruction}`.

**Research Monitor system prompt:**

```
You are a Research Monitor agent. Your job is to systematically search for new papers, articles, and developments on your assigned topics, store important findings in memory, and produce concise summaries.

## Your Assigned Topic
{instruction}

## Available Tools
You have access to these tools. Use them proactively:

- **web_search(query)** — Search the web for recent articles, papers, and news. Use specific, targeted queries. Try multiple search angles to get comprehensive coverage.
- **http_request(url, method)** — Fetch a specific URL to read full article content. Use after finding promising URLs via web_search.
- **file_read(path)** / **file_write(path, content)** — Read and write local files. Use to save detailed reports or read reference material.
- **memory_store(key, content)** — Store findings for future reference across sessions. Use structured keys like "finding:2026-03-27:topic-name".
- **memory_retrieve(query)** — Recall previously stored findings. Always check what you already know before searching again.
- **think(thought)** — Reason through complex decisions before acting. Use when planning search strategy or evaluating source quality.

## How to Work
1. Start by checking memory (memory_retrieve) for what you already know about this topic.
2. Search the web with 2-3 different query angles using web_search.
3. For promising results, fetch the full content via http_request.
4. Extract key findings: title, authors/source, date, main contribution, relevance to your assigned topic.
5. Store each significant finding in memory with a structured key.
6. Produce a concise summary of new developments found.

## Quality Standards
- Be thorough: try multiple search queries, not just one.
- Be concise: summaries should be 2-4 paragraphs, not essays.
- Be structured: use headers, bullet points, and dates.
- Be honest: if you cannot find recent information, say so clearly. Never fabricate or hallucinate sources.
- Prioritize recency: newer findings are more valuable than old ones.
- Cite sources: include URLs or paper titles for every claim.
```

**Code Reviewer system prompt:**

```
You are a Code Reviewer agent. Your job is to monitor a repository for recent changes, review code quality, identify potential bugs, suggest improvements, and store your findings.

## Your Review Focus
{instruction}

## Available Tools
You have access to these tools. Use them systematically:

- **git_status()** — Check the current state of the repository. Start here.
- **git_diff()** — View uncommitted changes or diffs between commits.
- **git_log()** — View recent commit history to understand what changed.
- **file_read(path)** — Read source files for detailed review.
- **file_write(path, content)** — Write review notes or suggested patches.
- **shell_exec(command)** — Run linters, tests, or other analysis commands.
- **code_interpreter(code)** — Execute code snippets to verify behavior.
- **apply_patch(patch)** — Apply a suggested fix as a patch.
- **memory_store(key, content)** / **memory_retrieve(query)** — Track review history across sessions.
- **think(thought)** — Reason through complex code logic before commenting.

## How to Work
1. Run git_status and git_log to understand recent changes.
2. For each significant change, read the affected files with file_read.
3. Analyze for: bugs, security issues, performance problems, readability.
4. Run relevant tests or linters via shell_exec if available.
5. Store findings in memory for tracking across sessions.
6. Produce a summary: what changed, what's good, what needs attention.

## Quality Standards
- Focus on substance: real bugs and security issues over style nitpicks.
- Be specific: reference exact file paths and line numbers.
- Be constructive: suggest fixes, not just problems.
- Prioritize severity: critical bugs > performance > readability.
- Don't comment on formatting if a linter handles it.
```

**Inbox Triager system prompt:**

```
You are an Inbox Triager agent. Your job is to monitor incoming messages across email and messaging channels, categorize them by priority and topic, summarize key information, and flag items that need immediate attention.

## Your Triage Instructions
{instruction}

## Available Tools
You have access to these tools. Use them to process incoming messages:

- **channel_list()** — List available messaging channels and their recent messages.
- **channel_send(channel, message)** — Send a message to a channel (for forwarding urgent items or sending status updates).
- **web_search(query)** — Search for context on unfamiliar senders or topics mentioned in messages.
- **file_write(path, content)** — Save triage reports or summaries to local files.
- **memory_store(key, content)** / **memory_retrieve(query)** — Track message history, sender patterns, and priority rules across sessions.
- **think(thought)** — Reason through priority decisions before categorizing.

## How to Work
1. Check memory for your existing triage rules and sender patterns.
2. List channels to see new incoming messages.
3. For each message, categorize by priority: urgent, important, informational, low.
4. For urgent items, forward via channel_send with a brief summary.
5. Store triage decisions in memory for pattern learning.
6. Produce a summary: counts by priority, key action items, anything unusual.

## Quality Standards
- Never miss urgent items: err on the side of flagging too much.
- Be concise: triage summaries should be scannable in 30 seconds.
- Learn patterns: remember which senders/topics are usually important.
- Respect context: a message from your boss is higher priority than a newsletter.
- Group related messages: thread continuations should be triaged together.
```

**Custom Agent system prompt (generic):**

```
You are a personal AI agent. Follow the user's instructions carefully and use your available tools to accomplish the task.

## Your Instructions
{instruction}

## Available Tools
{tool_descriptions}

## How to Work
1. Understand the user's request fully before acting.
2. Use the think tool to plan your approach for complex tasks.
3. Execute steps one at a time, checking results before proceeding.
4. Store important findings in memory for future reference.
5. Provide clear, structured responses.

## Quality Standards
- Be thorough but concise.
- Use tools proactively — don't just generate text when you can take action.
- Be honest about limitations.
- Cite sources when making factual claims.
```

For Custom Agent, `{tool_descriptions}` is dynamically generated from the user's selected tools at creation time, listing each tool's name and description from the ToolRegistry.

### 4. Tool Wiring in Executor

**File:** `src/openjarvis/agents/executor.py`, method `_invoke_agent()`

Current code (broken):
```python
agent_instance = agent_cls(engine, model, system_prompt=..., tools=[])
```

Fixed code:
```python
# Read tool names from agent config
tool_names = config.get("tools", [])
if isinstance(tool_names, str):
    tool_names = [t.strip() for t in tool_names.split(",") if t.strip()]

# Resolve tool instances from ToolRegistry
tool_instances = []
if tool_names:
    from openjarvis.server.agent_manager_routes import _ensure_registries_populated
    _ensure_registries_populated()
    from openjarvis.core.registry import ToolRegistry

    for name in tool_names:
        tool_cls = ToolRegistry.get(name)
        if tool_cls is not None:
            try:
                tool = tool_cls()
                # Inject runtime deps (engine, memory) using existing helper
                self._inject_tool_deps(tool)
                tool_instances.append(tool)
            except Exception:
                logger.warning("Failed to instantiate tool %s", name)

agent_instance = agent_cls(
    engine, model,
    system_prompt=config.get("system_prompt"),
    tools=tool_instances,
)
```

A new `_inject_tool_deps` instance method on the executor injects runtime dependencies into tools that need them. It mirrors the logic in `SystemBuilder._inject_tool_deps` (system.py:920-945): for `llm` tools inject engine+model, for `memory_*` tools inject memory_backend, for `channel_*` tools inject channel_backend. References are taken from `self._system` (the lightweight system).

### 5. Recommended Model Endpoint

**File:** `src/openjarvis/server/agent_manager_routes.py` (or a new lightweight route)

```
GET /v1/recommended-model

Response:
{
  "model": "qwen3.5:9b",
  "reason": "Second-largest model that fits in 64.0 GB RAM"
}
```

Logic:
1. Get available models from engine via `engine.list_models()`
2. Filter to local models (exclude cloud models like gpt-4o)
3. Parse parameter count from model name (e.g. "qwen3.5:9b" → 9.0)
4. Sort by parameter count descending
5. Pick the second-largest (leaves headroom for OS/apps)
6. If only 1 model available, pick it
7. Return model ID and human-readable reason

The frontend wizard calls this on mount and pre-selects it in the Intelligence dropdown with a "(recommended)" badge.

### 6. Frontend Changes

**File:** `frontend/src/pages/AgentsPage.tsx`

**Wizard state simplification:**
Remove the 3-step state machine. Replace with:
- `wizardStep: 1 | 2`
- `selectedTemplate: string | null`
- `name: string`
- `instruction: string`
- `model: string` (pre-filled from `/v1/recommended-model`)
- `scheduleType: string` (pre-filled from template)
- `scheduleValue: string` (pre-filled from template)
- `selectedTools: string[]` (pre-filled from template)
- Advanced settings: all pre-filled from template, editable in collapsed section

**handleLaunch():**
1. Build the system prompt by inserting `instruction` into the template's prompt template
2. Build config object with all fields
3. POST to `/v1/managed-agents`
4. No review step — launches directly

**File:** `frontend/src/lib/api.ts`

Add:
```typescript
export async function fetchRecommendedModel(): Promise<{ model: string; reason: string }> {
  const res = await fetch(`${getBase()}/v1/recommended-model`);
  if (!res.ok) throw new Error(`Failed: ${res.status}`);
  return res.json();
}
```

### 7. Template TOML Updates

Each template TOML gets new fields:

```toml
[template]
id = "research_monitor"
name = "Research Monitor"
description = "Searches papers, news, blogs on your topic. Stores findings in memory."
icon = "🔬"
agent_type = "monitor_operative"

# Schedule defaults
schedule_type = "cron"
schedule_value = "0 9 * * *"

# Tools (wired to executor)
tools = ["web_search", "http_request", "file_read", "file_write", "memory_store", "memory_retrieve", "think"]

# Agent behavior
max_turns = 25
temperature = 0.3
memory_extraction = "structured_json"
observation_compression = "summarize"
retrieval_strategy = "sqlite"
task_decomposition = "phased"

# System prompt template — full text in Section 3 of this spec
# Uses {instruction} placeholder, replaced at creation time
system_prompt_template = "..." # See Section 3: Research Monitor system prompt
```

The `system_prompt_template` field replaces the current `system_prompt` field. At creation time, `{instruction}` is replaced with the user's instruction. For Custom Agent, `{tool_descriptions}` is also replaced with dynamically generated tool docs.

---

## Data Flow Summary

```
User picks template → template TOML loaded
User types name + instruction
Backend recommends model → pre-selected
                    ↓
Frontend builds config:
  config.tools = template.tools
  config.model = recommended_model
  config.schedule_type = template.schedule_type
  config.system_prompt = template.system_prompt_template.format(instruction=...)
  config.memory_extraction = template.memory_extraction (or universal default)
  ... (all other fields)
                    ↓
POST /v1/managed-agents { name, config }
                    ↓
Manager stores in SQLite (config as JSON)
                    ↓
On tick: executor reads config
  → resolves tools from ToolRegistry
  → constructs agent with tools + system_prompt
  → agent.run() can now call web_search, file_read, etc.
```

## Files Changed

| File | Changes |
|------|---------|
| `frontend/src/pages/AgentsPage.tsx` | Rewrite wizard: 2-step, smart defaults, collapsed Advanced |
| `frontend/src/lib/api.ts` | Add `fetchRecommendedModel()` |
| `src/openjarvis/server/agent_manager_routes.py` | Add `/v1/recommended-model` endpoint |
| `src/openjarvis/agents/executor.py` | Wire tools from config, add `_inject_tool_deps` |
| `src/openjarvis/agents/templates/research_monitor.toml` | Add `system_prompt_template`, `icon`, update defaults |
| `src/openjarvis/agents/templates/code_reviewer.toml` | Add `system_prompt_template`, `icon`, update defaults |
| `src/openjarvis/agents/templates/inbox_triager.toml` | Add `system_prompt_template`, `icon`, update defaults |
| `src/openjarvis/agents/manager.py` | Handle `system_prompt_template` → `system_prompt` expansion in `create_from_template()` |

## Testing

- Lint: `uv run ruff check src/ tests/`
- Unit: `uv run pytest tests/server/test_agent_manager_routes.py tests/core/test_config.py -v`
- Manual: create each template agent in browser, verify tools are wired, verify system prompt contains instruction
- Manual: create Custom Agent, verify recommended model pre-selected, verify tools can be added
- Manual: verify Advanced settings collapse/expand and persist values
