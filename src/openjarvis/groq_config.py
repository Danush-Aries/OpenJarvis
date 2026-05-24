"""Groq API key configuration — single source of truth.

Update GROQ_API_KEY below with your key from:
  https://console.groq.com/keys

Free models available (no credits needed for rate-limited tiers):
  - gemma3-12b-it              (fast, great quality)
  - gemma3-4b-it               (smallest, fastest)
  - llama-3.3-70b-versatile    (best quality, free tier)
  - llama-3.1-8b-instant       (fast, good quality)
  - llama-3.2-3b-preview       (smallest Llama)
  - mixtral-8x7b-32768         (Mixtral, 32K context)
  - deepseek-r1-distill-llama-70b (reasoning model)
  - qwen-2.5-32b               (Qwen 2.5 32B)
  - qwen-2.5-coder-32b         (Code-optimized Qwen)

All components read from this file automatically via env var.
"""

# ── Set your Groq API key here ─────────────────────────────────────────────
import os
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "")

# ── Groq API base URL (do not change) ──────────────────────────────────────
GROQ_BASE_URL = "https://api.groq.com/openai/v1"

# ── Default free model ─────────────────────────────────────────────────────
GROQ_DEFAULT_MODEL = "gemma3-12b-it"

# ── Model catalog ──────────────────────────────────────────────────────────
# (model_id, context_length, is_free)
FREE_GROQ_MODELS = [
    ("gemma3-12b-it", 32768, True),
    ("gemma3-4b-it", 32768, True),
    ("gemma3-1b-it", 32768, True),
    ("llama-3.3-70b-versatile", 131072, True),
    ("llama-3.1-8b-instant", 131072, True),
    ("llama-3.2-3b-preview", 131072, True),
    ("llama-3.2-1b-preview", 131072, True),
    ("llama-3.3-70b-specdec", 131072, True),
    ("mixtral-8x7b-32768", 32768, True),
    ("deepseek-r1-distill-llama-70b", 65536, True),
    ("qwen-2.5-32b", 131072, True),
    ("qwen-2.5-coder-32b", 131072, True),
    ("qwen-2.5-14b-instruct", 131072, True),
    ("distil-whisper-large-v3-en", 448, True),  # Audio only
]

# Paid models (requires billing)
PAID_GROQ_MODELS = [
    ("llama-3.3-70b-instruct", 131072, False),
    ("llama-guard-3-8b", 8192, False),
    ("llama-3.1-70b-instruct", 131072, False),
    ("llama-3.1-405b-reasoning", 16384, False),
]

# Default context length for models not in our catalog
DEFAULT_CONTEXT_LENGTH = 32768
