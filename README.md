# OpenJarvis

**A personal AI that runs on your machine, not someone else's server.**

<!-- hero: 1600x600 screenshot of the OpenJarvis CLI running the morning-briefing agent -->

![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)
![Ollama](https://img.shields.io/badge/local-Ollama-000000?logo=ollama&logoColor=white)
![MLX](https://img.shields.io/badge/Apple-MLX-000000?logo=apple&logoColor=white)
![vLLM](https://img.shields.io/badge/NVIDIA-vLLM-76B900?logo=nvidia&logoColor=white)
![License](https://img.shields.io/badge/License-MIT-yellow)

OpenJarvis is a local-first personal AI agent framework. It routes requests to whichever inference engine your hardware supports (Ollama, MLX on Apple Silicon, vLLM on NVIDIA, llama.cpp on CPU), ships eight built-in agents (briefings, research, code, etc.), and keeps every interaction in a persistent memory graph so agents remember across sessions.

---

## Why this exists

Personal-AI SaaS has an obvious problem: your calendar, notes, code, and voice all leave your machine to make it work. OpenJarvis flips that — it runs the model on your box, keeps memory on your box, and only calls cloud APIs when you explicitly opt in. The result is an assistant that's actually yours.

---

## Try it in 60 seconds

```bash
git clone https://github.com/Danush-Aries/OpenJarvis
cd OpenJarvis
pip install -e .

# Point at a local model
export OJ_MODEL=ollama/llama3.1

openjarvis agent morning-brief
```

No local model? Set `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` and it falls through to cloud.

---

## How it works

```
+-- Router ---------------------------------+
|  detects: Ollama / MLX / vLLM / llama.cpp |
|  cloud fallback: Anthropic / OpenAI       |
+---------------------|---------------------+
                      v
+-- Soul (persistent memory) ---------------+
|  episodic  (conversation history)         |
|  semantic  (fact store, vector-indexed)   |
|  procedural (learned workflows)           |
+---------------------|---------------------+
                      v
+-- Agents ---------------------------------+
|  morning-brief    · research               |
|  code             · shell                  |
|  desktop          · voice                  |
|  planner          · self-improver          |
+-------------------------------------------+
                      v
+-- Learning loop --------------------------+
|  traces -> DSPy / GEPA / SFT              |
|  prompts + weights improve over time      |
+-------------------------------------------+
```

Optional Tauri desktop app and a Rust extension for high-performance memory indexing.

---

## Screenshots

<!-- screenshot: cli-briefing.png -->
<!-- screenshot: soul-memory.png -->
<!-- screenshot: agent-picker.png -->

---

## Stack

| Layer | Tech |
|---|---|
| Inference router | Ollama / MLX / vLLM / llama.cpp / cloud |
| Memory | vector store + episodic log ("Soul") |
| Backend | FastAPI |
| Desktop | Tauri (optional) |
| Native ext | Rust (memory indexing) |
| Optimizers | DSPy, GEPA, SFT |

---

## More from Danush

Part of a broader stack of AI + security tooling:

- [jarvis](https://github.com/Danush-Aries/jarvis) — portable multi-provider AI assistant (voice/web/CLI)
- [breachintel](https://github.com/Danush-Aries/breachintel) — OSINT breach intelligence aggregator
- [cve-advisor](https://github.com/Danush-Aries/cve-advisor) — AI-powered CVE triage and patch recommendation
- [llm-fragility-lab](https://github.com/Danush-Aries/llm-fragility-lab) — adversarial testing lab for LLM robustness
- [network-intrusion-analyzer](https://github.com/Danush-Aries/network-intrusion-analyzer) — Suricata + Claude AI intrusion triage
- [autonomous-coding-agent](https://github.com/Danush-Aries/autonomous-coding-agent) — two-agent autonomous coding system

Built by [Dhanush](https://github.com/Danush-Aries) — AI engineering + cybersecurity.

## License

MIT.
