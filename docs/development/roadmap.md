# Roadmap

OpenJarvis uses **GitHub Projects** boards organized by domain to plan and
track work. Each board has quarterly columns so contributors can see what's
coming and where help is needed.

---

## How We Plan

- Work is organized into domain-specific project boards (see below)
- Each board uses quarterly columns: **Backlog → Q2 2026 → Q3 2026 → Q4 2026 → Future**
- Issues are labeled by difficulty (`good-first-issue`, `help-wanted`) and type (`type:bug`, `type:feature`, `type:perf`, `type:docs`, `type:eval`)
- Domain labels (`domain:agents`, `domain:engine`, `domain:tools`, etc.) connect issues to the right board

Want to contribute? Check the boards below, pick an issue labeled `good-first-issue` or `help-wanted`, and comment **"take"** to claim it.

---

## Active Project Boards

| Board | Scope | Link |
|---|---|---|
| **Agents & Tools** | Agent types, tool implementations, MCP | *TBD — boards will be linked once created on GitHub* |
| **Engine & Inference** | Engine backends, streaming, performance | *TBD* |
| **Learning & Routing** | GRPO, trace-driven policies, rewards | *TBD* |
| **Evals & Benchmarks** | Datasets, scorers, benchmark infra | *TBD* |
| **Frontend & Desktop** | Tauri app, dashboard, leaderboard | *TBD* |
| **Rust Port** | PyO3 bindings, crate parity | *TBD* |

---

## Current Focus Areas

These are the areas where active development is happening and contributions are most impactful:

- **GRPO training from trace data** — moving router policies beyond heuristics using reinforcement learning from execution traces
- **Multi-model orchestration pipelines** — coordinating multiple models within a single query (e.g., small model for classification, large model for generation)
- **Energy-aware routing** — using power consumption data from telemetry to optimize for energy efficiency alongside latency and quality
- **Plugin ecosystem** — community-contributed engines, tools, and agents distributed as Python packages
- **Federated memory** — memory backends that synchronize across devices

---

## How to Get Involved

1. Browse the [project boards](#active-project-boards) for issues that interest you
2. Look for `good-first-issue` and `help-wanted` labels
3. Read the [Contributing Guide](../../CONTRIBUTING.md) for the full process
4. Comment **"take"** on an issue to claim it

---

<details>
<summary><strong>Version History</strong></summary>

| Version | Phase | Status | Delivers |
|---|---|---|---|
| **v0.1** | Phase 0 -- Scaffolding | :material-check-circle:{ .green } Complete | Project scaffolding, registry system (`RegistryBase[T]`), core types (`Message`, `ModelSpec`, `Conversation`, `ToolResult`), configuration loader with hardware detection, Click CLI skeleton |
| **v0.2** | Phase 1 -- Intelligence + Inference | :material-check-circle:{ .green } Complete | Intelligence primitive (model catalog, heuristic router), inference engines (Ollama, vLLM, llama.cpp), engine discovery and health probing, `jarvis ask` command working end-to-end |
| **v0.3** | Phase 2 -- Memory | :material-check-circle:{ .green } Complete | Memory backends (SQLite/FTS5, FAISS, ColBERTv2, BM25, Hybrid/RRF), document chunking and ingestion pipeline, context injection with source attribution, `jarvis memory` commands |
| **v0.4** | Phase 3 -- Agents + Tools + Server | :material-check-circle:{ .green } Complete | Agent system (SimpleAgent, OrchestratorAgent), tool system (Calculator, Think, Retrieval, LLM, FileRead), ToolExecutor dispatch engine, OpenAI-compatible API server (`jarvis serve`) |
| **v0.5** | Phase 4 -- Learning + Telemetry | :material-check-circle:{ .green } Complete | Learning system (HeuristicRouter policy, TraceDrivenPolicy, GRPO stub), reward functions, telemetry aggregation (per-model/engine stats, export), `--router` CLI flag, `jarvis telemetry` commands |
| **v1.0** | Phase 5 -- SDK + Production | :material-check-circle:{ .green } Complete | Python SDK (`Jarvis` class, `MemoryHandle`), multi-platform channel system (Telegram, Discord, Slack, WhatsApp, etc.), benchmarking framework (latency, throughput), Docker deployment (CPU + GPU), MkDocs documentation site |
| **v1.1** | Phase 6 -- Traces + Learning | :material-check-circle:{ .green } Complete | Trace system (`TraceStore`, `TraceCollector`, `TraceAnalyzer`), trace-driven learning, MCP integration layer |
| **v1.5** | Phase 10 -- Agent Restructuring | :material-check-circle:{ .green } Complete | BaseAgent helpers, ToolUsingAgent intermediate base, NativeReActAgent, NativeOpenHandsAgent, RLMAgent, OpenHandsAgent (SDK), `accepts_tools` introspection, backward-compat shims, CustomAgent removed |

</details>
