# Eval Grid Search — 4× A100 Runbook

Complete guide for running the OpenJarvis evaluation grid search across **5 models × 4 engines × 5 agents × 15 benchmarks** on a 4× NVIDIA A100 (80 GB) node.

## Grid Dimensions

| Dimension | Values |
|-----------|--------|
| **Models** | GPT-OSS-120B, Qwen3.5-122B-FP8, Qwen3.5-397B-GGUF, Kimi-K2.5-GGUF, GLM-5-GGUF |
| **Engines** | vLLM, SGLang, llama.cpp, Ollama |
| **Agents** | simple, orchestrator, native_react, native_openhands, rlm |
| **Benchmarks** | supergpqa, gpqa, mmlu-pro, math500, natural-reasoning, hle, simpleqa, wildchat, ipw, gaia, frames, swebench, swefficiency, terminalbench, terminalbench-native |
| **Samples** | 5 per benchmark |

**Total: 750 experiment cells** (each model only runs on its compatible engines).

| Model | Compatible Engines |
|-------|--------------------|
| openai/gpt-oss-120b | vllm, sglang |
| Qwen/Qwen3.5-122B-A10B-FP8 | vllm, sglang |
| unsloth/Qwen3.5-397B-A17B-GGUF | llamacpp, ollama |
| unsloth/Kimi-K2.5-GGUF | llamacpp, ollama |
| unsloth/GLM-5-GGUF | llamacpp, ollama |

---

## Phase 1: Environment Setup

```bash
# Clone and install
cd ~/gabebo  # or wherever your workspace lives
git clone <repo-url> OpenJarvis && cd OpenJarvis
uv sync --extra dev

# Install eval dependencies
uv pip install openai datasets huggingface-hub terminal-bench

# Load API keys (needed for LLM judge — gpt-5-mini)
source .env

# Log in to HuggingFace (needed for gated datasets)
huggingface-cli login
```

> **SGLang note:** SGLang requires Python ≤ 3.12 (FlashInfer/outlines_core fail on 3.13).
> If your base env is Python 3.13, create a separate conda env:
> ```bash
> conda create -n sglang python=3.11 -y && conda activate sglang
> pip install "sglang[all]"
> ```

---

## Phase 2: Download Models

```bash
# HuggingFace weights (vLLM / SGLang)
hf download openai/gpt-oss-120b --local-dir ~/models/gpt-oss-120b
hf download Qwen/Qwen3.5-122B-A10B-FP8 --local-dir ~/models/Qwen3.5-122B-A10B-FP8

# GGUF quantizations (llama.cpp / Ollama)
# Qwen3.5-397B — UD-Q4_K_XL fits in 4× A100 (~214 GB)
hf download unsloth/Qwen3.5-397B-A17B-GGUF \
  --include "Q4_K_M/*.gguf" \
  --local-dir ~/models/Qwen3.5-397B-A17B-GGUF

# Kimi-K2.5 — UD-IQ2_XXS to fit (~240 GB usable)
hf download unsloth/Kimi-K2.5-GGUF \
  --include "UD-IQ2_XXS/*.gguf" \
  --local-dir ~/models/Kimi-K2.5-GGUF

# GLM-5 — UD-IQ2_XXS to fit
hf download unsloth/GLM-5-GGUF \
  --include "UD-IQ2_XXS/*.gguf" \
  --local-dir ~/models/GLM-5-GGUF
```

### Verify downloads

```bash
# HuggingFace weights — check for config.json and safetensors shards
ls ~/models/gpt-oss-120b/config.json
ls ~/models/Qwen3.5-122B-A10B-FP8/config.json

# GGUF files — check they exist and aren't zero-byte
find ~/models/Qwen3.5-397B-A17B-GGUF -name "*.gguf" -exec ls -lh {} \;
find ~/models/Kimi-K2.5-GGUF -name "*.gguf" -exec ls -lh {} \;
find ~/models/GLM-5-GGUF -name "*.gguf" -exec ls -lh {} \;
```

---

## Phase 3: Run the Grid (One Model at a Time)

Serve a model, run all agents/benchmarks for it, then kill the server and swap.

### 3A. GPT-OSS-120B via vLLM

```bash
# Terminal 1: Start vLLM server
vllm serve openai/gpt-oss-120b \
  --tensor-parallel-size 2 \
  --port 8000 \
  --max-model-len 8192
```

```bash
# Terminal 2: Wait for "Uvicorn running" then run grid
cd OpenJarvis && source .env
uv run python scripts/run_grid_search.py \
  --model "gpt-oss" --engine vllm -n 5
# When done, Ctrl-C the vLLM server
```

### 3B. GPT-OSS-120B via SGLang

```bash
# Terminal 1: Start SGLang server
python -m sglang.launch_server \
  --model-path openai/gpt-oss-120b \
  --tp 2 \
  --port 30000
```

```bash
# Terminal 2: Run grid
uv run python scripts/run_grid_search.py \
  --model "gpt-oss" --engine sglang --resume -n 5
# Kill server when done
```

### 3C. Qwen3.5-122B-FP8 via vLLM

```bash
# Terminal 1
vllm serve Qwen/Qwen3.5-122B-A10B-FP8 \
  --tensor-parallel-size 2 \
  --port 8000 \
  --max-model-len 8192 \
  --quantization fp8
```

```bash
# Terminal 2
uv run python scripts/run_grid_search.py \
  --model "Qwen3.5-122B" --engine vllm --resume -n 5
```

### 3D. Qwen3.5-122B-FP8 via SGLang

```bash
# Terminal 1
python -m sglang.launch_server \
  --model-path Qwen/Qwen3.5-122B-A10B-FP8 \
  --tp 2 \
  --port 30000 \
  --quantization fp8
```

```bash
# Terminal 2
uv run python scripts/run_grid_search.py \
  --model "Qwen3.5-122B" --engine sglang --resume -n 5
```

### 3E. Qwen3.5-397B GGUF via llama.cpp

```bash
# Terminal 1: Start llama.cpp server with all 4 GPUs
./llama.cpp/build/bin/llama-server \
  -m ~/models/Qwen3.5-397B-A17B-GGUF/Q4_K_M/Qwen3.5-397B-A17B-Q4_K_M-00001-of-00005.gguf \
  --n-gpu-layers 99 \
  --tensor-split 1,1,1,1 \
  --port 8080 \
  --ctx-size 8192
```

```bash
# Terminal 2
uv run python scripts/run_grid_search.py \
  --model "Qwen3.5-397B" --engine llamacpp --resume -n 5
```

### 3F. Qwen3.5-397B GGUF via Ollama

```bash
# Create an Ollama modelfile
cat > /tmp/Qwen3.5-397B.Modelfile << 'EOF'
FROM ~/models/Qwen3.5-397B-A17B-GGUF/Q4_K_M/Qwen3.5-397B-A17B-Q4_K_M-00001-of-00005.gguf
EOF

# Import into Ollama
ollama create qwen3.5-397b -f /tmp/Qwen3.5-397B.Modelfile

# Ollama serves automatically on port 11434
uv run python scripts/run_grid_search.py \
  --model "Qwen3.5-397B" --engine ollama --resume -n 5

# Unload when done
ollama stop qwen3.5-397b
```

### 3G. Kimi-K2.5 GGUF via llama.cpp

```bash
# Terminal 1
./llama.cpp/build/bin/llama-server \
  -m ~/models/Kimi-K2.5-GGUF/UD-IQ2_XXS/Kimi-K2.5-UD-IQ2_XXS-00001-of-00005.gguf \
  --n-gpu-layers 99 \
  --tensor-split 1,1,1,1 \
  --port 8080 \
  --ctx-size 8192
```

```bash
# Terminal 2
uv run python scripts/run_grid_search.py \
  --model "Kimi-K2.5" --engine llamacpp --resume -n 5
```

### 3H. Kimi-K2.5 GGUF via Ollama

```bash
cat > /tmp/Kimi-K2.5.Modelfile << 'EOF'
FROM ~/models/Kimi-K2.5-GGUF/UD-IQ2_XXS/Kimi-K2.5-UD-IQ2_XXS-00001-of-00005.gguf
EOF

ollama create kimi-k2.5 -f /tmp/Kimi-K2.5.Modelfile

uv run python scripts/run_grid_search.py \
  --model "Kimi-K2.5" --engine ollama --resume -n 5

ollama stop kimi-k2.5
```

### 3I. GLM-5 GGUF via llama.cpp

```bash
# Terminal 1
./llama.cpp/build/bin/llama-server \
  -m ~/models/GLM-5-GGUF/UD-IQ2_XXS/GLM-5-UD-IQ2_XXS-00001-of-00005.gguf \
  --n-gpu-layers 99 \
  --tensor-split 1,1,1,1 \
  --port 8080 \
  --ctx-size 8192
```

```bash
# Terminal 2
uv run python scripts/run_grid_search.py \
  --model "GLM-5" --engine llamacpp --resume -n 5
```

### 3J. GLM-5 GGUF via Ollama

```bash
cat > /tmp/GLM-5.Modelfile << 'EOF'
FROM ~/models/GLM-5-GGUF/UD-IQ2_XXS/GLM-5-UD-IQ2_XXS-00001-of-00005.gguf
EOF

ollama create glm-5 -f /tmp/GLM-5.Modelfile

uv run python scripts/run_grid_search.py \
  --model "GLM-5" --engine ollama --resume -n 5

ollama stop glm-5
```

---

## Phase 4: Recover Failed Runs

If some runs fail (missing packages, engine not reachable, etc.), fix the issue, then:

```bash
# Delete error summaries so --resume retries them
find results/grid-search -name "*.summary.json" \
  -exec grep -l '"error"' {} \; -delete

# Re-run with --resume (only retries deleted/missing summaries)
uv run python scripts/run_grid_search.py --resume -n 5
```

### Common Failures and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `No inference engine available` | `openai` package missing (LLM judge can't init) | `uv pip install openai` |
| `No module named 'datasets'` | Missing HF datasets package | `uv pip install datasets` |
| `terminal-bench package required` | Missing terminal-bench | `uv pip install terminal-bench` |
| `Dataset doesn't exist on the Hub` | Gated dataset or HF auth needed | `huggingface-cli login`, accept terms on HF website |
| `IPW data directory not found` | IPW uses local data, not HuggingFace | Place files in `src/openjarvis/evals/data/ipw/` |
| `natural-reasoning` 0 samples | Field name mismatch in dataset loader | Patch `src/openjarvis/evals/datasets/natural_reasoning.py` |

---

## Phase 5: Analyze Results

```bash
# Preview what ran
uv run python scripts/run_grid_search.py --dry-run --resume

# Consolidated results (appended after each run)
cat results/grid-search/grid-results.jsonl

# Per-run summaries
find results/grid-search -name "*.summary.json" | head -20
cat results/grid-search/openai-gpt-oss-120b/vllm/simple/supergpqa.summary.json

# Count completed vs failed
echo "Completed:" && find results/grid-search -name "*.summary.json" \
  -exec grep -L '"error"' {} \; | wc -l
echo "Failed:" && find results/grid-search -name "*.summary.json" \
  -exec grep -l '"error"' {} \; | wc -l
```

---

## Useful Flags

```bash
# Preview the full matrix without running
uv run python scripts/run_grid_search.py --dry-run

# Filter to a single model + engine
uv run python scripts/run_grid_search.py --model "gpt-oss" --engine vllm -n 5

# Filter to a single agent or benchmark
uv run python scripts/run_grid_search.py --agent native_react --benchmark supergpqa -n 5

# Increase sample count
uv run python scripts/run_grid_search.py -n 50

# Verbose logging
uv run python scripts/run_grid_search.py -v --resume -n 5
```

---

## GPU Assignment Tips

Use `CUDA_VISIBLE_DEVICES` to pin servers to specific GPUs:

```bash
# Run vLLM on GPUs 0,1 and llama.cpp on GPUs 2,3 simultaneously
CUDA_VISIBLE_DEVICES=0,1 vllm serve openai/gpt-oss-120b --tensor-parallel-size 2 --port 8000
CUDA_VISIBLE_DEVICES=2,3 ./llama.cpp/build/bin/llama-server -m model.gguf --n-gpu-layers 99 --port 8080
```

This lets you run two model servers in parallel on different GPU pairs.
