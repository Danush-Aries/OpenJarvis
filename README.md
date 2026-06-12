<div align="center">
  <img alt="OpenJarvis" src="assets/OpenJarvis_Horizontal_Logo.png" width="400">

  <p><i>Personal AI, On Personal Devices.</i></p>

  <p>
    <a href="https://scalingintelligence.stanford.edu/blogs/openjarvis/"><img src="https://img.shields.io/badge/project-OpenJarvis-blue" alt="Project"></a>
    <a href="https://open-jarvis.github.io/OpenJarvis/"><img src="https://img.shields.io/badge/docs-mkdocs-blue" alt="Docs"></a>
    <img src="https://img.shields.io/badge/python-%3E%3D3.10-blue" alt="Python 3.10+">
    <img src="https://img.shields.io/badge/license-MIT-green" alt="MIT License">
    <a href="https://discord.gg/YZZRxCAhmm"><img src="https://img.shields.io/badge/discord-join-7289da?logo=discord&logoColor=white" alt="Discord"></a>
    <a href="https://x.com/OpenJarvisAI"><img src="https://img.shields.io/badge/X-@OpenJarvisAI-black?logo=x&logoColor=white" alt="X / Twitter"></a>
  </p>
</div>

---

**OpenJarvis** is a local-first personal AI agent framework developed at Stanford. It runs LLM-powered agents on your own hardware using [Ollama](https://ollama.com/) or cloud APIs, with a FastAPI backend, an optional Tauri desktop app, a Rust extension for high-performance memory indexing, and a rich CLI with eight built-in agents covering tasks from morning briefings to deep research and code assistance.

---

## What It Does

OpenJarvis gives you a personal AI that runs on your machine, not someone else's server. It is built around three ideas:

- **Local-first inference** — routes requests to the best engine available on your hardware (Ollama, MLX on Apple Silicon, vLLM on NVIDIA, llama.cpp CPU-only) and falls back to cloud APIs only when needed.
- **Persistent memory and identity** — the Soul system gives every agent episodic, semantic, and procedural memory that survives across sessions and evolves over time.
- **Learning loop** — traces from real use are fed back into DSPy / GEPA / SFT optimizers to continuously improve prompts and model weights on your data.

## Features

- **Eight built-in agents** — morning digest, deep research, code assistant, autonomous monitor, orchestrator, ReAct loop, OpenHands CodeAct, and simple chat.
- **Soul system** — tiered memory (episodic / semantic / procedural), knowledge graph, emotional state model, and dream-cycle consolidation.
- **Multi-engine routing** — Ollama, MLX, vLLM, SGLang, llama.cpp, LM Studio, Exo, Nexa, Apple Foundation Models, Lemonade (AMD), and cloud providers (OpenAI, Anthropic, Google).
- **Composable tools** — web search, file I/O, shell exec, git, code interpreter, HTTP requests, browser automation (Playwright), calculator, REPL, finance data, and more.
- **Channels** — Telegram, Discord, Slack, WhatsApp, Signal, email, IRC, Mattermost, Matrix, and more.
- **Scheduler** — cron-based task runner for recurring agents.
- **FastAPI server** — REST and SSE streaming endpoints for chat, soul, projects, voice, and knowledge graph.
- **Rust extension** — high-performance memory indexing and security scanning (optional; degrades gracefully when not built).
- **Skills** — install and share agent skills from Hermes, OpenClaw, or any GitHub repo.
- **Security** — input/output scanning, PII redaction, SSRF protection, rate limiting, and a signed Merkle audit log.

## Installation

### Quick install (macOS / Linux)

```bash
curl -fsSL https://raw.githubusercontent.com/open-jarvis/OpenJarvis/main/scripts/install/install.sh | bash
jarvis
```

The installer sets up `uv`, a Python virtual environment, Ollama, and a starter model. Takes about three minutes on a typical connection.

> If `openjarvis.ai` SSL fails (issue #337), use the GitHub mirror URL above — same script, no dependency on the custom domain.

### Manual install

**Requirements:** Python 3.10+, [uv](https://docs.astral.sh/uv/) (recommended) or pip.

```bash
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis

# With uv (recommended):
uv sync
source .venv/bin/activate    # or: prefix every command with `uv run`

# With pip:
pip install -r requirements.txt
pip install -e .
```

Install optional extras to unlock additional features:

```bash
# Server (FastAPI + uvicorn)
uv sync --extra server

# Cloud LLM providers
uv sync --extra inference-cloud

# Memory with FAISS vector search
uv sync --extra memory-faiss

# Playwright browser automation
uv sync --extra browser

# Full dev environment
uv sync --extra dev
```

### Build the Rust extension (optional)

The Rust extension accelerates memory indexing and security scanning. Without it the Python fallbacks are used automatically.

```bash
pip install maturin
cd rust && maturin develop --release
```

### Windows

Native Windows is not supported. Use **WSL2** (recommended) or download the desktop binary from the [Releases page](https://github.com/open-jarvis/OpenJarvis/releases).

```powershell
# One-time WSL2 setup (admin PowerShell):
wsl --install -d Ubuntu-24.04
```

Then follow the Linux install steps inside the Ubuntu shell.

## Quick Start

```bash
# Interactive chat
jarvis

# Ask a single question
jarvis ask "What is the capital of France?"

# Start the API server
jarvis serve

# Generate a morning digest
jarvis digest --fresh

# Index documents into memory
jarvis memory index ./docs/
```

### Starter presets

Switch to a pre-configured use case in one command:

```bash
jarvis init --preset morning-digest-mac    # spoken daily briefing (macOS)
jarvis init --preset deep-research         # multi-hop research with citations
jarvis init --preset code-assistant        # code execution + file I/O
jarvis init --preset chat-simple           # lightweight conversation
```

## Usage Examples

### Python SDK

```python
from openjarvis import Jarvis

# Simple question
with Jarvis() as j:
    answer = j.ask("Summarize the key points of quantum computing.")
    print(answer)

# Specify engine and model explicitly
j = Jarvis(engine_key="ollama", model="qwen3.5:9b")
result = j.ask_full("Explain backpropagation", max_tokens=512)
print(result["content"])
j.close()

# Streaming tokens
import asyncio

async def stream_example():
    async with Jarvis() as j:
        async for token in j.ask_stream("Write a haiku about the ocean"):
            print(token, end="", flush=True)

asyncio.run(stream_example())

# Memory indexing and search
with Jarvis() as j:
    j.memory.index("./my_notes/")
    hits = j.memory.search("meeting notes from last week", top_k=5)
    for hit in hits:
        print(hit["content"], hit["score"])
```

### CLI

```bash
# Ask with web search enabled
jarvis ask "Latest developments in fusion energy" --tools web_search

# Run an agent with multiple tools
jarvis ask "Read README.md, then write a test for the main function" \
    --agent orchestrator \
    --tools file_read,code_interpreter,file_write

# Deep research mode (multi-hop, cited)
jarvis ask "Impact of LLM scaling laws on hardware roadmaps" --research

# Soul memory commands
jarvis soul show              # current soul state
jarvis soul remember "I prefer concise explanations"
jarvis soul recall "user preferences"
jarvis soul reflect           # run a dream/consolidation cycle
```

### API Server

```bash
# Start the server
uvicorn app:app --host 0.0.0.0 --port 9099

# or
jarvis serve --port 9099
```

```bash
# Chat endpoint
curl -X POST http://localhost:9099/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello, what can you do?"}'

# Streaming chat
curl -X POST http://localhost:9099/v1/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a short story", "session_id": "demo"}'

# Health check
curl http://localhost:9099/health
```

### Built-in Agents

| Agent | Mode | Description |
|-------|------|-------------|
| `morning_digest` | Scheduled | Spoken briefing from email, calendar, health, and news with TTS audio |
| `deep_research` | On-demand | Multi-hop research with citations across web and local docs |
| `monitor_operative` | Continuous | Long-horizon monitoring with memory compression and retrieval |
| `orchestrator` | On-demand | Multi-turn reasoning with automatic tool selection |
| `native_react` | On-demand | ReAct (Thought-Action-Observation) loop |
| `operative` | Continuous | Persistent autonomous agent with state management |
| `native_openhands` | On-demand | CodeAct — generates and executes Python code |
| `simple` | On-demand | Single-turn chat, no tools |

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.10+ |
| API framework | FastAPI + uvicorn + Pydantic v2 |
| CLI | Click |
| Local inference | Ollama, MLX, vLLM, SGLang, llama.cpp, LM Studio, Exo, Nexa, Apple FM, Lemonade |
| Cloud inference | OpenAI, Anthropic, Google Gemini, LiteLLM |
| Memory | SQLite (default), FAISS, ColBERT, BM25 |
| Performance extension | Rust (via PyO3 / maturin) |
| Desktop app | Tauri v2 (Rust + React) |
| Package manager | uv / hatchling |
| Learning | DSPy, GEPA, SFT (PyTorch + transformers) |
| Security | Rust-accelerated scanners, Merkle audit log |

## Configuration

OpenJarvis reads `~/.openjarvis/config.toml`. Generate a starter file with:

```bash
jarvis init
```

Key settings:

```toml
[engine]
default = "ollama"          # ollama | mlx | vllm | sglang | llamacpp | cloud

[intelligence]
default_model = "qwen3.5:9b"

[agent]
default_agent = "simple"
max_turns = 10

[server]
host = "127.0.0.1"
port = 8000
```

See `jarvis config --help` and the [full config reference](https://open-jarvis.github.io/OpenJarvis/) for all options.

## Rust Extension

The Rust extension (`rust/`) provides:

- High-throughput memory index operations (BM25, embedding search)
- Zero-copy JSON parsing for engine responses
- Security scanning (prompt injection, PII, secret detection)
- Optimisation result persistence (SQLite)

Build it once with `maturin develop --release`. Without it, `RUST_AVAILABLE` is `False` and Python fallbacks handle all operations transparently.

## Contributing

```bash
git clone https://github.com/open-jarvis/OpenJarvis.git
cd OpenJarvis
uv sync --extra dev
uv run pre-commit install
uv run pytest tests/ -v
```

Browse the [Roadmap](https://open-jarvis.github.io/OpenJarvis/development/roadmap/) for areas where help is wanted. Comment **"take"** on any GitHub issue to be auto-assigned.

See [CONTRIBUTING.md](CONTRIBUTING.md) for incentives, guidelines, and the PR process.

## Community

- **Docs:** [open-jarvis.github.io/OpenJarvis](https://open-jarvis.github.io/OpenJarvis/)
- **Discord:** [discord.gg/YZZRxCAhmm](https://discord.gg/YZZRxCAhmm)
- **X / Twitter:** [@OpenJarvisAI](https://x.com/OpenJarvisAI)
- **GitHub:** [github.com/open-jarvis/OpenJarvis](https://github.com/open-jarvis/OpenJarvis)

## About

OpenJarvis is part of [Intelligence Per Watt](https://www.intelligence-per-watt.ai/), a research initiative studying the intelligence efficiency of AI systems. The project is developed at [Hazy Research](https://hazyresearch.stanford.edu/) and the [Scaling Intelligence Lab](https://scalingintelligence.stanford.edu/) at [Stanford SAIL](https://ai.stanford.edu/).

## Citation

```bibtex
@misc{saadfalcon2026openjarvispersonalaipersonal,
      title={OpenJarvis: Personal AI, On Personal Devices},
      author={Jon Saad-Falcon and Avanika Narayan and Robby Manihani and Tanvir Bhathal
              and Herumb Shandilya and Hakki Orhun Akengin and Gabriel Bo and Andrew Park
              and Matthew Hart and Caia Costello and Chuan Li and Christopher Re
              and Azalia Mirhoseini},
      year={2026},
      eprint={2605.17172},
      archivePrefix={arXiv},
      primaryClass={cs.LG},
      url={https://arxiv.org/abs/2605.17172},
}
```

## License

[MIT](LICENSE)
