"""NVIDIA API key configuration — single source of truth.

Update NVIDIA_API_KEY below with your key from:
  https://build.nvidia.com → click any free model → "Get API Key"

Free models available (no credits needed):
  - meta/llama-3.1-8b-instruct          (fast, recommended)
  - meta/llama-3.2-3b-instruct          (smallest, fastest)
  - meta/llama-3.3-70b-instruct         (best quality, free)
  - mistralai/mistral-7b-instruct-v0.3  (Mistral 7B)
  - google/gemma-2-9b-it                (Gemma 2 9B)
  - google/gemma-3-4b-it                (Gemma 3 4B)
  - google/gemma-3-12b-it               (Gemma 3 12B)
  - google/gemma-3-27b-it               (Gemma 3 27B)
  - deepseek-ai/deepseek-r1             (DeepSeek R1 reasoning)
  - deepseek-ai/deepseek-v3             (DeepSeek V3)
  - deepseek-ai/deepseek-v4-flash       (DeepSeek V4 Flash)
  - qwen/qwen2.5-72b-instruct           (Qwen 2.5 72B)
  - qwen/qwen2.5-coder-32b-instruct     (Qwen Coder 32B)
  - qwen/qwen3-8b-instruct              (Qwen3 8B)
  - qwen/qwen3-30b-instruct             (Qwen3 30B)
  - qwen/qwen3-235b-a22b                (Qwen3 235B MoE)
  - qwen/qwen3.5-122b-a10b              (Qwen3.5 122B MoE)
  - microsoft/phi-3-mini-4k-instruct    (Phi-3 Mini)
  - microsoft/phi-3-medium-128k-instruct (Phi-3 Medium)

All components (voice, dashboard, API) read from this file automatically.
"""

# ── Replace with your key from build.nvidia.com ──────────────────────────────
import os
NVIDIA_API_KEY = os.environ.get("NVIDIA_API_KEY", "")

# ── NVIDIA NIM base URL (do not change) ───────────────────────────────────────
NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

# ── Default free model ────────────────────────────────────────────────────────
NVIDIA_DEFAULT_MODEL = "meta/llama-3.1-8b-instruct"

# ── Model aliases for convenience ─────────────────────────────────────────────
MODEL_ALIASES = {
    "llama-fast": "meta/llama-3.1-8b-instruct",
    "llama-best": "meta/llama-3.3-70b-instruct",
    "qwen-fast": "qwen/qwen2.5-72b-instruct",
    "qwen-best": "qwen/qwen3.5-122b-a10b",
    "deepseek-reason": "deepseek-ai/deepseek-r1",
    "deepseek-flash": "deepseek-ai/deepseek-v4-flash",
    "gemma-fast": "google/gemma-3-4b-it",
    "gemma-best": "google/gemma-3-27b-it",
}
