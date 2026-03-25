# Design: Init Model Onboarding & Privacy Environment Scanner

**Date:** 2026-03-24
**Status:** Draft
**Author:** Jon Saad-Falcon + Claude

## Problem Statement

Two issues reported by a user (Ali Shahkar) after setting up OpenJarvis on macOS with llama.cpp:

1. **`jarvis init` sets a default model with no way to download it.** The config is written with a recommended model, but there's no download prompt, no validation that it's available, and `jarvis doctor` immediately warns it can't be found. On Apple Silicon with MLX, the bug is worse: `recommend_model()` returns an empty string because no Qwen3.5 model lists MLX as a supported engine.

2. **No environment privacy auditing.** OpenJarvis positions itself as privacy-first local AI, but `jarvis init` doesn't verify the local environment is actually private. Cloud sync agents, MDM profiles, disk encryption status, and network exposure can all undermine the privacy guarantee without the user knowing.

## Solution Overview

### Issue 1: Interactive Model Download in `jarvis init`

**Bug fix:** Add `"mlx"` to `supported_engines` for Qwen3.5 models (3b, 4b, 8b, 14b) in the model catalog.

**Feature:** After writing the config and displaying the recommended model, `jarvis init` prompts:

```
  Recommended model: qwen3.5:8b (~4.4 GB)
  Download now? [y/n]:
```

Download logic is engine-specific:
- **Ollama:** Reuse existing `model pull` code (HTTP stream to `POST /api/pull`).
- **llama.cpp:** Shell out to `huggingface-cli download` with GGUF filename from catalog metadata.
- **MLX:** Shell out to `huggingface-cli download` for pre-quantized MLX repo from catalog metadata.
- **vLLM/SGLang:** Inform the user the model downloads automatically on first serve.
- **LM Studio/Exo/Nexa:** Show manual download instructions (these have their own UIs).

**Empty model fallback:** If `recommend_model()` returns `""`, display:

```
  ! Not enough memory to run any local model.
  Consider a cloud engine or a machine with more RAM.
```

### Issue 2: Privacy Environment Scanner

**New CLI command:** `jarvis scan` performs a full environment privacy audit.

**Init hook:** At the end of `jarvis init`, run a lightweight subset (disk encryption + cloud sync overlap with `~/.openjarvis/`) and show a compact summary pointing to `jarvis scan` for the full audit.

## Detailed Design

### Model Catalog Changes

Add `"mlx"` to `supported_engines` and download metadata for Qwen3.5 models in `src/openjarvis/intelligence/model_catalog.py`.

**Important:** The catalog has TWO Qwen3.5 sections. The first (lines ~42-121) contains the original entries (`qwen3.5:3b`, `qwen3.5:8b`, `qwen3.5:14b`, `qwen3.5:35b`, etc. with `context_length=131072`). The second (lines ~219-274) contains newer entries (`qwen3.5:4b`, `qwen3.5:35b-a3b`, etc. with `context_length=262144`). Both sections' models are candidates for `recommend_model()`. MLX must be added to entries in BOTH sections.

Models getting MLX support added to `supported_engines`:

| model_id | Section | Current context_length | Add MLX |
|----------|---------|----------------------|---------|
| `qwen3.5:3b` | First | 131072 | Yes |
| `qwen3.5:4b` | Second | 262144 | Yes |
| `qwen3.5:8b` | First | 131072 | Yes |
| `qwen3.5:14b` | First | 131072 | Yes |

Larger models (35b+) are excluded because MLX quantized weights aren't widely available and would exceed typical Apple Silicon memory.

Download metadata to add to each model's `metadata` dict:

| model_id | `gguf_file` | `mlx_repo` |
|----------|-------------|------------|
| `qwen3.5:3b` | `qwen3.5-3b-q4_k_m.gguf` | `mlx-community/Qwen3.5-3B-4bit` |
| `qwen3.5:4b` | `qwen3.5-4b-q4_k_m.gguf` | `mlx-community/Qwen3.5-4B-4bit` |
| `qwen3.5:8b` | `qwen3.5-8b-q4_k_m.gguf` | `mlx-community/Qwen3.5-8B-4bit` |
| `qwen3.5:14b` | `qwen3.5-14b-q4_k_m.gguf` | `mlx-community/Qwen3.5-14B-4bit` |

Example updated entry:

```python
ModelSpec(
    model_id="qwen3.5:8b",
    name="Qwen3.5 8B",
    parameter_count_b=8.0,
    active_parameter_count_b=1.0,
    context_length=131072,
    supported_engines=("ollama", "vllm", "llamacpp", "sglang", "mlx"),  # added mlx
    provider="alibaba",
    metadata={
        "architecture": "moe",
        "hf_repo": "Qwen/Qwen3.5-8B",
        "gguf_file": "qwen3.5-8b-q4_k_m.gguf",
        "mlx_repo": "mlx-community/Qwen3.5-8B-4bit",
    },
)
```

### Init Command Changes (`src/openjarvis/cli/init_cmd.py`)

After the config is written and the "Getting Started" panel is shown, add:

1. **Size estimate display:** Compute `parameter_count_b * 0.5 * 1.1` and display alongside the model name. Note: this is an estimate based on Q4_K_M quantization. Actual download size may differ slightly by engine/format. The prompt labels it as "~X GB estimated".

2. **Download prompt:** `click.confirm(f"Download {model} (~{size:.1f} GB estimated) now?", default=True)`. A new `--no-download` flag on the `init` command skips this prompt (for CI/automated environments).

3. **Engine-specific download functions:**
   - `_download_ollama(model, host, console)` — calls a new shared helper `ollama_pull(host, model_name, console) -> bool` extracted from `cli/model.py`. Both the `model pull` CLI command and `init_cmd.py` import this helper, avoiding duplication.
   - `_download_llamacpp(model, spec, console)` — `subprocess.run(["huggingface-cli", "download", repo, gguf_file, "--local-dir", cache_dir])`. If `huggingface-cli` is not found (`FileNotFoundError`), prints: `"Install huggingface-cli: pip install huggingface_hub"` and shows the manual download URL as fallback.
   - `_download_mlx(model, spec, console)` — `subprocess.run(["huggingface-cli", "download", mlx_repo, "--local-dir", cache_dir])`. Same `FileNotFoundError` handling as llama.cpp.
   - `_download_auto(model, engine, console)` — print info message that the model auto-downloads on first serve (vLLM, SGLang).
   - `_download_manual(model, engine, console)` — print engine-specific manual instructions (LM Studio, Exo, Nexa).

4. **Empty model fallback:** Check `if not model:` and print the "not enough memory" warning before the next-steps panel.

5. **Privacy hook:** After download (or skip), call `_quick_privacy_check()` that runs disk encryption + cloud sync checks and prints a compact summary.

6. **Next-steps coverage:** Add entries to `_next_steps_text()` for `exo` and `nexa` engines so the Ollama fallback is eliminated.

### `jarvis model pull` Enhancement (`src/openjarvis/cli/model.py`)

**Refactor:** Extract the Ollama streaming pull logic (currently lines 165-196) into a reusable function:

```python
def ollama_pull(host: str, model_name: str, console: Console) -> bool:
    """Pull a model via Ollama API. Returns True on success."""
```

The existing `pull` Click command becomes a thin wrapper around this function.

**Extend** the `pull` command to support engines beyond Ollama:
- Add an `--engine` flag (optional, defaults to configured engine).
- Look up the model in `BUILTIN_MODELS` or `ModelRegistry` to get metadata.
- Dispatch to engine-specific download based on the engine flag.
- Fallback to Ollama pull if no engine specified and model is in Ollama format (name:tag).
- llama.cpp and MLX paths use `huggingface-cli download` with metadata from the catalog, with `FileNotFoundError` handling.

### Privacy Scanner (`src/openjarvis/cli/scan_cmd.py` — new file)

#### Data model

```python
@dataclass
class ScanResult:
    name: str           # e.g. "FileVault"
    status: str         # "ok" | "warn" | "fail" | "skip"
    message: str        # Human-readable explanation
    platform: str       # "darwin" | "linux" | "all"
```

#### `PrivacyScanner` class

Contains a list of check methods. Each check:
- Is decorated or tagged with the platform it applies to.
- Calls a subprocess and parses the output.
- Returns a `ScanResult`.
- Never raises — catches all exceptions and returns `status="skip"` with the error.

#### macOS checks

| Check | Implementation | Status mapping |
|-------|---------------|----------------|
| `check_filevault()` | `subprocess.run(["fdesetup", "status"])`, parse "FileVault is On/Off" | On = ok, Off = fail |
| `check_mdm()` | `subprocess.run(["profiles", "status", "-type", "enrollment"])`, parse for "MDM enrollment" | Not enrolled = ok, enrolled = warn |
| `check_icloud_sync()` | Read `defaults read MobileMeAccounts` for Desktop/Documents sync; check if `~/.openjarvis/` resolves to a path under `~/Library/Mobile Documents/`. Note: `defaults read` output format varies across macOS versions — parsing should be lenient and return `skip` on unexpected output rather than raising. | Not syncing = ok, syncing = warn |
| `check_cloud_sync_agents()` | Check for Dropbox, OneDrive, Google Drive processes via `pgrep`; check if their known sync dirs overlap with `~/.openjarvis/` | No overlap = ok, overlap = warn |
| `check_network_exposure()` | `lsof -iTCP -sTCP:LISTEN -nP`, filter for known engine ports, check bind address | 127.0.0.1 = ok, 0.0.0.0 = warn |
| `check_screen_recording()` | `pgrep` for TeamViewer, AnyDesk, ScreenConnect, vnc | Not found = ok, found = warn |

#### Linux checks

| Check | Implementation | Status mapping |
|-------|---------------|----------------|
| `check_luks()` | `lsblk -o NAME,TYPE,FSTYPE -J`, look for `crypto_LUKS` on root device | Found = ok, not found = fail |
| `check_cloud_sync_agents()` | `pgrep` for rclone, dropbox, insync, onedriver | Not found = ok, found = warn |
| `check_network_exposure()` | `ss -tlnp` or `lsof`, same port-check logic | 127.0.0.1 = ok, 0.0.0.0 = warn |
| `check_remote_access()` | `pgrep` for xrdp, x11vnc, vncserver, AnyDesk | Not found = ok, found = warn |

#### CLI command

```
@click.command()
def scan():
    """Audit your environment for privacy and security risks."""
```

Output format:
```
  Privacy & Environment Audit
  ────────────────────────────
  ✓ FileVault: enabled
  ✓ Network: inference ports bound to localhost only
  ! iCloud Drive: Desktop & Documents sync is active
  ✗ MDM: enterprise management profile detected

  1 warning, 1 issue found.
```

Symbols: `✓` for ok, `!` for warn, `✗` for fail. Skipped checks are hidden.

#### Init integration

A function `_quick_privacy_check()` in `init_cmd.py` that:
1. Instantiates `PrivacyScanner`.
2. Runs only disk encryption and cloud sync overlap checks.
3. Prints a compact 2-3 line summary.
4. Always prints `Run 'jarvis scan' for a full environment audit.`

### File changes summary

| File | Type | Description |
|------|------|-------------|
| `src/openjarvis/intelligence/model_catalog.py` | Edit | Add MLX to supported_engines, add gguf_file/mlx_repo metadata |
| `src/openjarvis/core/config.py` | Edit | Add `estimated_download_gb(spec: ModelSpec) -> float` helper (computes `parameter_count_b * 0.5 * 1.1`) |
| `src/openjarvis/cli/init_cmd.py` | Edit | Add download prompt, engine-specific downloaders, empty-model fallback, privacy hook |
| `src/openjarvis/cli/model.py` | Edit | Extend `pull` for llama.cpp and MLX engines |
| `src/openjarvis/cli/scan_cmd.py` | New | `PrivacyScanner` class, check functions, `jarvis scan` command |
| `src/openjarvis/cli/__init__.py` | Edit | Register `scan` command |

## Testing

### Issue 1 — Model onboarding

| Test | File | What it verifies |
|------|------|-----------------|
| MLX model recommendation | `tests/core/test_recommend_model.py` | Apple Silicon 8/16/32/64GB returns valid model with MLX engine (8GB should get `qwen3.5:4b`, 16GB should get `qwen3.5:14b`) |
| Empty model fallback message | `tests/cli/test_init_guidance.py` | `recommend_model` returning `""` shows "not enough memory" |
| Download prompt shown | `tests/cli/test_init_guidance.py` | Init output includes download prompt when model recommended |
| Engine-specific download dispatch | `tests/cli/test_init_guidance.py` | Ollama triggers pull, llamacpp shows HF download, vllm shows auto-download |
| `model pull` multi-engine | `tests/cli/test_model_pull.py` | llama.cpp and MLX pull paths work (mocked subprocess) |

### Issue 2 — Privacy scanner

| Test | File | What it verifies |
|------|------|-----------------|
| FileVault check | `tests/cli/test_scan.py` | Parses `fdesetup status` for on/off |
| MDM check | `tests/cli/test_scan.py` | Parses `profiles status` for enrollment |
| iCloud sync detection | `tests/cli/test_scan.py` | Detects overlap with `~/.openjarvis/` |
| LUKS check | `tests/cli/test_scan.py` | Parses `lsblk` for crypto_LUKS |
| Network exposure | `tests/cli/test_scan.py` | Parses `lsof`/`ss` for 0.0.0.0 binds |
| Platform filtering | `tests/cli/test_scan.py` | macOS checks return skip on Linux, vice versa |
| Init privacy hook | `tests/cli/test_init_guidance.py` | Init output includes privacy summary |

All tests mock subprocess calls via `monkeypatch`. No real system state required.

## Out of Scope

- Windows support (future work).
- Post-download inference validation (trying a test query).
- Rust implementation of scanner checks.
- DNS leak detection (complex, unreliable heuristics).
- Automatic remediation (e.g., moving `~/.openjarvis/` out of iCloud).
