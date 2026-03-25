# Init Model Onboarding & Privacy Scanner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the broken model recommendation for MLX users, add interactive model download to `jarvis init`, and create a `jarvis scan` privacy environment audit command.

**Architecture:** Two independent features sharing only the init command integration point. Feature 1 modifies the model catalog and init flow. Feature 2 creates a new `PrivacyScanner` class with platform-specific checks exposed via `jarvis scan` CLI command and a lightweight hook in init.

**Tech Stack:** Python 3.10+, Click (CLI), Rich (terminal UI), httpx (Ollama API), subprocess (system checks)

**Spec:** `docs/development/specs/2026-03-24-init-onboarding-and-privacy-scanner-design.md`

---

### Task 1: Fix MLX support in model catalog

**Files:**
- Modify: `src/openjarvis/intelligence/model_catalog.py:42-54` (qwen3.5:3b)
- Modify: `src/openjarvis/intelligence/model_catalog.py:55-67` (qwen3.5:8b)
- Modify: `src/openjarvis/intelligence/model_catalog.py:68-80` (qwen3.5:14b)
- Modify: `src/openjarvis/intelligence/model_catalog.py:219-232` (qwen3.5:4b)
- Test: `tests/core/test_recommend_model.py`

- [ ] **Step 1: Write failing tests for MLX model recommendation**

Add a new test class to `tests/core/test_recommend_model.py`:

```python
class TestRecommendModelMlx:
    """Apple Silicon (MLX) model recommendation."""

    def test_apple_silicon_8gb_mlx(self) -> None:
        hw = HardwareInfo(
            platform="darwin",
            ram_gb=8.0,
            gpu=GpuInfo(vendor="apple", name="Apple M1", vram_gb=8.0, count=1),
        )
        result = recommend_model(hw, "mlx")
        # available = 8 * 0.9 = 7.2 GB
        # 8B * 0.5 * 1.1 = 4.4 → fits, but check 14B first: 7.7 → too big
        # 4B * 0.5 * 1.1 = 2.2 → fits, but 8B also fits → pick 8B
        assert result == "qwen3.5:8b"

    def test_apple_silicon_16gb_mlx(self) -> None:
        hw = HardwareInfo(
            platform="darwin",
            ram_gb=16.0,
            gpu=GpuInfo(vendor="apple", name="Apple M2", vram_gb=16.0, count=1),
        )
        result = recommend_model(hw, "mlx")
        # available = 16 * 0.9 = 14.4 GB
        # 14B * 0.5 * 1.1 = 7.7 → fits
        assert result == "qwen3.5:14b"

    def test_apple_silicon_32gb_mlx(self) -> None:
        hw = HardwareInfo(
            platform="darwin",
            ram_gb=32.0,
            gpu=GpuInfo(vendor="apple", name="Apple M2 Pro", vram_gb=32.0, count=1),
        )
        result = recommend_model(hw, "mlx")
        # available = 32 * 0.9 = 28.8 GB
        # 14B * 0.5 * 1.1 = 7.7 → fits (14b is the largest with mlx support)
        assert result == "qwen3.5:14b"

    def test_apple_silicon_64gb_mlx(self) -> None:
        hw = HardwareInfo(
            platform="darwin",
            ram_gb=64.0,
            gpu=GpuInfo(vendor="apple", name="Apple M2 Max", vram_gb=64.0, count=1),
        )
        result = recommend_model(hw, "mlx")
        # available = 64 * 0.9 = 57.6 GB — but 14b is the largest MLX model
        assert result == "qwen3.5:14b"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/core/test_recommend_model.py::TestRecommendModelMlx -v`
Expected: FAIL — all 4 tests fail because no Qwen3.5 model has `"mlx"` in `supported_engines`.

- [ ] **Step 3: Add MLX to supported_engines and download metadata**

In `src/openjarvis/intelligence/model_catalog.py`, update the four Qwen3.5 model entries:

For `qwen3.5:3b` (line 48): change `supported_engines` from `("ollama", "vllm", "llamacpp", "sglang")` to `("ollama", "vllm", "llamacpp", "sglang", "mlx")`. Add `"gguf_file": "qwen3.5-3b-q4_k_m.gguf"` and `"mlx_repo": "mlx-community/Qwen3.5-3B-4bit"` to metadata.

For `qwen3.5:8b` (line 61): change `supported_engines` from `("ollama", "vllm", "llamacpp", "sglang")` to `("ollama", "vllm", "llamacpp", "sglang", "mlx")`. Add `"gguf_file": "qwen3.5-8b-q4_k_m.gguf"` and `"mlx_repo": "mlx-community/Qwen3.5-8B-4bit"` to metadata.

For `qwen3.5:14b` (line 74): change `supported_engines` from `("ollama", "vllm", "llamacpp", "sglang")` to `("ollama", "vllm", "llamacpp", "sglang", "mlx")`. Add `"gguf_file": "qwen3.5-14b-q4_k_m.gguf"` and `"mlx_repo": "mlx-community/Qwen3.5-14B-4bit"` to metadata.

For `qwen3.5:4b` (line 226): change `supported_engines` from `("ollama", "vllm", "sglang", "llamacpp")` to `("ollama", "vllm", "sglang", "llamacpp", "mlx")`. Add `"gguf_file": "qwen3.5-4b-q4_k_m.gguf"` and `"mlx_repo": "mlx-community/Qwen3.5-4B-4bit"` to metadata.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/core/test_recommend_model.py -v`
Expected: ALL 15 tests pass (11 existing + 4 new).

- [ ] **Step 5: Add `estimated_download_gb` helper to config.py**

In `src/openjarvis/core/config.py`, after the `recommend_model` function (after line 248), add:

```python
def estimated_download_gb(parameter_count_b: float) -> float:
    """Estimate download size in GB for Q4_K_M quantized model."""
    return parameter_count_b * 0.5 * 1.1
```

- [ ] **Step 6: Commit**

```bash
git add src/openjarvis/intelligence/model_catalog.py src/openjarvis/core/config.py tests/core/test_recommend_model.py
git commit -m "fix: add MLX engine support to Qwen3.5 model catalog entries

Fixes recommend_model() returning empty string on Apple Silicon
when MLX is the recommended engine. Also adds gguf_file and
mlx_repo download metadata, and estimated_download_gb helper."
```

---

### Task 2: Extract Ollama pull helper and extend `jarvis model pull`

**Files:**
- Modify: `src/openjarvis/cli/model.py:152-197`
- Test: `tests/cli/test_model_pull.py` (new)

- [ ] **Step 1: Write failing tests for multi-engine pull**

Create `tests/cli/test_model_pull.py`:

```python
"""Tests for ``jarvis model pull`` multi-engine support."""

from __future__ import annotations

from unittest import mock

import pytest
from click.testing import CliRunner
from rich.console import Console

from openjarvis.cli.model import ollama_pull


class TestOllamaPull:
    """Test the extracted ollama_pull helper."""

    def test_ollama_pull_success(self) -> None:
        import io
        console = Console(file=io.StringIO())
        mock_lines = [
            '{"status": "pulling manifest"}',
            '{"status": "downloading", "total": 100, "completed": 100}',
            '{"status": "success"}',
        ]
        mock_resp = mock.MagicMock()
        mock_resp.raise_for_status = mock.MagicMock()
        mock_resp.iter_lines.return_value = iter(mock_lines)
        mock_resp.__enter__ = mock.MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = mock.MagicMock(return_value=False)

        with mock.patch("httpx.stream", return_value=mock_resp):
            result = ollama_pull("http://localhost:11434", "qwen3.5:3b", console)
        assert result is True

    def test_ollama_pull_connect_error(self) -> None:
        import io
        import httpx

        console = Console(file=io.StringIO())
        with mock.patch("httpx.stream", side_effect=httpx.ConnectError("refused")):
            result = ollama_pull("http://localhost:11434", "qwen3.5:3b", console)
        assert result is False


class TestPullCliMultiEngine:
    """Test the pull CLI command dispatches to correct engine."""

    def test_pull_llamacpp_uses_huggingface_cli(self) -> None:
        from openjarvis.cli import cli

        runner = CliRunner()
        with (
            mock.patch("openjarvis.cli.model.load_config") as mock_cfg,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_cfg.return_value.engine.default = "llamacpp"
            mock_cfg.return_value.engine.ollama_host = None
            mock_run.return_value = mock.MagicMock(returncode=0)

            result = runner.invoke(
                cli, ["model", "pull", "qwen3.5:8b", "--engine", "llamacpp"]
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "huggingface-cli" in call_args
        assert "qwen3.5-8b-q4_k_m.gguf" in call_args

    def test_pull_mlx_uses_huggingface_cli(self) -> None:
        from openjarvis.cli import cli

        runner = CliRunner()
        with (
            mock.patch("openjarvis.cli.model.load_config") as mock_cfg,
            mock.patch("subprocess.run") as mock_run,
        ):
            mock_cfg.return_value.engine.default = "mlx"
            mock_cfg.return_value.engine.ollama_host = None
            mock_run.return_value = mock.MagicMock(returncode=0)

            result = runner.invoke(
                cli, ["model", "pull", "qwen3.5:8b", "--engine", "mlx"]
            )

        assert result.exit_code == 0
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert "huggingface-cli" in call_args
        assert "mlx-community/Qwen3.5-8B-4bit" in call_args

    def test_pull_llamacpp_huggingface_cli_not_found(self) -> None:
        from openjarvis.cli import cli

        runner = CliRunner()
        with (
            mock.patch("openjarvis.cli.model.load_config") as mock_cfg,
            mock.patch("subprocess.run", side_effect=FileNotFoundError),
        ):
            mock_cfg.return_value.engine.default = "llamacpp"
            mock_cfg.return_value.engine.ollama_host = None

            result = runner.invoke(
                cli, ["model", "pull", "qwen3.5:8b", "--engine", "llamacpp"]
            )

        assert result.exit_code != 0
        assert "huggingface_hub" in result.output or "pip install" in result.output
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_model_pull.py -v`
Expected: FAIL — `ollama_pull` function doesn't exist yet, `--engine` flag not recognized.

- [ ] **Step 3: Refactor model.py — extract ollama_pull and add multi-engine support**

In `src/openjarvis/cli/model.py`:

1. Add `import subprocess` at the top.
2. Add `from openjarvis.intelligence.model_catalog import BUILTIN_MODELS` at the top.
3. Extract the Ollama pull logic into a standalone function:

```python
def ollama_pull(host: str, model_name: str, console: Console) -> bool:
    """Pull a model via Ollama API. Returns True on success."""
    console.print(f"Pulling [cyan]{model_name}[/cyan] via Ollama...")
    try:
        with httpx.stream(
            "POST",
            f"{host}/api/pull",
            json={"name": model_name, "stream": True},
            timeout=600.0,
        ) as resp:
            resp.raise_for_status()
            import json

            for line in resp.iter_lines():
                if not line.strip():
                    continue
                try:
                    data = json.loads(line)
                except Exception:
                    continue
                status = data.get("status", "")
                if "total" in data and "completed" in data:
                    total = data["total"]
                    done = data["completed"]
                    pct = int(done / total * 100) if total else 0
                    console.print(f"  {status}: {pct}%", end="\r")
                elif status:
                    console.print(f"  {status}")
        console.print(f"\n[green]Successfully pulled {model_name}[/green]")
        return True
    except httpx.ConnectError:
        console.print("[red]Cannot connect to Ollama.[/red] Is it running?")
        return False
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Ollama error:[/red] {exc.response.status_code}")
        return False
```

4. Add helper to find model spec:

```python
def find_model_spec(model_name: str):
    """Look up a model in the builtin catalog. Returns None if not found."""
    for spec in BUILTIN_MODELS:
        if spec.model_id == model_name:
            return spec
    return None
```

5. Add HuggingFace download helper:

```python
def hf_download(repo: str, filename: str | None, console: Console) -> bool:
    """Download from HuggingFace via huggingface-cli. Returns True on success."""
    cmd = ["huggingface-cli", "download", repo]
    if filename:
        cmd.append(filename)
    try:
        result = subprocess.run(cmd, check=True)
        console.print(f"[green]Download complete.[/green]")
        return True
    except FileNotFoundError:
        console.print(
            "[red]huggingface-cli not found.[/red]\n"
            "Install it: [cyan]pip install huggingface_hub[/cyan]\n"
            f"Or download manually: https://huggingface.co/{repo}"
        )
        return False
    except subprocess.CalledProcessError:
        console.print(f"[red]Download failed.[/red]")
        return False
```

6. Replace the existing `pull` command with a multi-engine version:

```python
@model.command()
@click.argument("model_name")
@click.option("--engine", default=None, help="Engine to download for (ollama, llamacpp, mlx).")
def pull(model_name: str, engine: str | None) -> None:
    """Download a model."""
    console = Console()
    config = load_config()

    engine = engine or config.engine.default or "ollama"

    if engine == "ollama":
        host = (
            config.engine.ollama_host
            or os.environ.get("OLLAMA_HOST")
            or "http://localhost:11434"
        ).rstrip("/")
        if not ollama_pull(host, model_name, console):
            sys.exit(1)
    elif engine in ("llamacpp", "mlx"):
        spec = find_model_spec(model_name)
        if not spec:
            console.print(f"[red]Model not in catalog:[/red] {model_name}")
            sys.exit(1)
        if engine == "llamacpp":
            repo = spec.metadata.get("hf_repo", "")
            gguf = spec.metadata.get("gguf_file", "")
            if not repo or not gguf:
                console.print(f"[red]No GGUF download info for {model_name}[/red]")
                sys.exit(1)
            console.print(f"Downloading [cyan]{gguf}[/cyan] from {repo}...")
            if not hf_download(repo, gguf, console):
                sys.exit(1)
        else:  # mlx
            mlx_repo = spec.metadata.get("mlx_repo", "")
            if not mlx_repo:
                console.print(f"[red]No MLX repo info for {model_name}[/red]")
                sys.exit(1)
            console.print(f"Downloading [cyan]{mlx_repo}[/cyan]...")
            if not hf_download(mlx_repo, None, console):
                sys.exit(1)
    elif engine in ("vllm", "sglang"):
        console.print(
            f"[cyan]{model_name}[/cyan] will download automatically when "
            f"{engine} starts serving it."
        )
    else:
        console.print(
            f"Manual download required for engine [cyan]{engine}[/cyan].\n"
            f"Check the engine documentation for instructions."
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_model_pull.py -v`
Expected: ALL tests pass.

- [ ] **Step 5: Run existing tests to verify no regressions**

Run: `uv run pytest tests/core/test_recommend_model.py tests/cli/test_init_guidance.py -v`
Expected: ALL pass.

- [ ] **Step 6: Commit**

```bash
git add src/openjarvis/cli/model.py tests/cli/test_model_pull.py
git commit -m "feat: extract ollama_pull helper and add multi-engine model pull

Refactors model pull into reusable ollama_pull() function. Adds
--engine flag to support llamacpp (GGUF) and mlx (HuggingFace)
downloads via huggingface-cli, with FileNotFoundError handling."
```

---

### Task 3: Add interactive download and empty-model fallback to `jarvis init`

**Files:**
- Modify: `src/openjarvis/cli/init_cmd.py:139-299`
- Test: `tests/cli/test_init_guidance.py`

- [ ] **Step 1: Write failing tests for download prompt and empty-model fallback**

Add to `tests/cli/test_init_guidance.py`:

```python
class TestInitDownloadPrompt:
    """Interactive download prompt during init."""

    def test_init_shows_download_prompt(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".openjarvis"
        config_path = config_dir / "config.toml"
        with (
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
        ):
            result = CliRunner().invoke(
                cli, ["init", "--engine", "ollama"], input="n\n"
            )
        assert result.exit_code == 0
        assert "Download" in result.output and "now?" in result.output

    def test_init_no_download_flag_skips_prompt(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".openjarvis"
        config_path = config_dir / "config.toml"
        with (
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
        ):
            result = CliRunner().invoke(
                cli, ["init", "--engine", "ollama", "--no-download"]
            )
        assert result.exit_code == 0
        assert "Download" not in result.output or "now?" not in result.output


class TestInitEmptyModelFallback:
    """Empty model recommendation shows helpful message."""

    def test_init_no_model_shows_warning(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".openjarvis"
        config_path = config_dir / "config.toml"
        with (
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
            mock.patch(
                "openjarvis.cli.init_cmd.recommend_model", return_value=""
            ),
        ):
            result = CliRunner().invoke(cli, ["init", "--engine", "llamacpp"])
        assert result.exit_code == 0
        assert "Not enough memory" in result.output or "not enough memory" in result.output


class TestNextStepsExoNexa:
    """Exo and Nexa have their own next-steps text."""

    def test_next_steps_exo(self) -> None:
        text = _next_steps_text("exo")
        assert "exo" in text.lower()
        assert "jarvis ask" in text
        # Should NOT fall back to Ollama instructions
        assert "ollama" not in text.lower()

    def test_next_steps_nexa(self) -> None:
        text = _next_steps_text("nexa")
        assert "nexa" in text.lower()
        assert "jarvis ask" in text
        assert "ollama" not in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_init_guidance.py::TestInitDownloadPrompt tests/cli/test_init_guidance.py::TestInitEmptyModelFallback tests/cli/test_init_guidance.py::TestNextStepsExoNexa -v`
Expected: FAIL — no `--no-download` flag, no "Not enough memory" message, no exo/nexa next-steps.

- [ ] **Step 3: Update init_cmd.py**

In `src/openjarvis/cli/init_cmd.py`:

1. Add imports at the top:

```python
from openjarvis.cli.model import ollama_pull, find_model_spec, hf_download
from openjarvis.core.config import estimated_download_gb
```

2. Add `exo` and `nexa` entries to `_next_steps_text()` dict (before the closing `}`):

```python
        "exo": (
            "Next steps:\n"
            "\n"
            "  1. Install and start Exo:\n"
            "     pip install exo\n"
            "     exo\n"
            "\n"
            "  2. Try it out:\n"
            "     jarvis ask \"Hello\"\n"
            "\n"
            "  Run `jarvis doctor` to verify your setup."
        ),
        "nexa": (
            "Next steps:\n"
            "\n"
            "  1. Install and start Nexa:\n"
            "     pip install nexaai\n"
            "     nexa server\n"
            "\n"
            "  2. Try it out:\n"
            "     jarvis ask \"Hello\"\n"
            "\n"
            "  Run `jarvis doctor` to verify your setup."
        ),
```

3. Add `--no-download` flag to the `@click.command()` decorator chain (after `--engine`):

```python
@click.option(
    "--no-download",
    is_flag=True,
    default=False,
    help="Skip the model download prompt.",
)
```

4. Update the `init()` function signature to accept `no_download: bool = False`.

5. Replace the block at lines 287-298 (the model recommendation + next-steps panel) with:

```python
    selected_engine = engine or recommend_engine(hw)
    model = recommend_model(hw, selected_engine)

    if not model:
        console.print(
            "\n  [yellow]! Not enough memory to run any local model.[/yellow]\n"
            "  Consider a cloud engine or a machine with more RAM."
        )
    else:
        spec = find_model_spec(model)
        size_gb = estimated_download_gb(spec.parameter_count_b) if spec else 0
        console.print(f"\n  [bold]Recommended model:[/bold] {model} (~{size_gb:.1f} GB estimated)")

        if not no_download and spec:
            if click.confirm(f"  Download {model} (~{size_gb:.1f} GB estimated) now?", default=True):
                _do_download(selected_engine, model, spec, console)

    console.print()
    console.print(
        Panel(
            _next_steps_text(selected_engine, model),
            title="Getting Started",
            border_style="cyan",
        )
    )
```

6. Add the `_do_download` helper function:

```python
def _do_download(engine: str, model: str, spec, console: Console) -> None:
    """Dispatch model download based on engine type."""
    import os

    if engine == "ollama":
        host = os.environ.get("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
        ollama_pull(host, model, console)
    elif engine == "llamacpp":
        repo = spec.metadata.get("hf_repo", "")
        gguf = spec.metadata.get("gguf_file", "")
        if repo and gguf:
            console.print(f"  Downloading [cyan]{gguf}[/cyan] from {repo}...")
            hf_download(repo, gguf, console)
        else:
            console.print(f"  [yellow]No GGUF download info for {model}[/yellow]")
    elif engine == "mlx":
        mlx_repo = spec.metadata.get("mlx_repo", "")
        if mlx_repo:
            console.print(f"  Downloading [cyan]{mlx_repo}[/cyan]...")
            hf_download(mlx_repo, None, console)
        else:
            console.print(f"  [yellow]No MLX repo info for {model}[/yellow]")
    elif engine in ("vllm", "sglang"):
        console.print(
            f"  [cyan]{model}[/cyan] will download automatically when "
            f"{engine} starts serving it."
        )
    else:
        console.print(
            f"  Download {model} through the {engine} interface."
        )
```

- [ ] **Step 4: Update existing init tests to add `--no-download`**

The download prompt breaks existing tests because `click.confirm` will try to download a model. Update all existing init CLI tests in `tests/cli/test_init_guidance.py` to add `"--no-download"` to their invocation args:

- `test_init_shows_next_steps`: change `["init", "--engine", "llamacpp"]` to `["init", "--engine", "llamacpp", "--no-download"]`
- `test_init_output_shows_toml_sections_literally`: same change
- `test_init_generates_minimal_by_default`: change `["init", "--engine", "ollama"]` to `["init", "--engine", "ollama", "--no-download"]`
- `test_init_full_generates_verbose_config`: change `["init", "--full", "--engine", "ollama"]` to `["init", "--full", "--engine", "ollama", "--no-download"]`

- [ ] **Step 5: Add download dispatch tests**

Add to `tests/cli/test_init_guidance.py`:

```python
class TestInitDownloadDispatch:
    """Verify download dispatches correctly for each engine."""

    def test_init_ollama_download_calls_ollama_pull(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".openjarvis"
        config_path = config_dir / "config.toml"
        with (
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
            mock.patch("openjarvis.cli.init_cmd.ollama_pull", return_value=True) as mock_pull,
        ):
            result = CliRunner().invoke(
                cli, ["init", "--engine", "ollama"], input="y\n"
            )
        assert result.exit_code == 0
        mock_pull.assert_called_once()

    def test_init_vllm_shows_auto_download_message(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".openjarvis"
        config_path = config_dir / "config.toml"
        with (
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
        ):
            result = CliRunner().invoke(
                cli, ["init", "--engine", "vllm"], input="y\n"
            )
        assert result.exit_code == 0
        assert "automatically" in result.output
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_init_guidance.py -v`
Expected: ALL tests pass (10 existing + 7 new).

- [ ] **Step 7: Lint**

Run: `uv run ruff check src/openjarvis/cli/init_cmd.py --fix`
Expected: Clean or auto-fixed.

- [ ] **Step 8: Commit**

```bash
git add src/openjarvis/cli/init_cmd.py tests/cli/test_init_guidance.py
git commit -m "feat: add interactive model download and empty-model fallback to init

Prompts user to download recommended model during jarvis init.
Adds --no-download flag for CI. Shows helpful message when no
model fits available memory. Adds exo/nexa next-steps text."
```

---

### Task 4: Create privacy scanner — ScanResult and check functions

**Files:**
- Create: `src/openjarvis/cli/scan_cmd.py`
- Test: `tests/cli/test_scan.py` (new)

- [ ] **Step 1: Write failing tests for individual scanner checks**

Create `tests/cli/test_scan.py`:

```python
"""Tests for ``jarvis scan`` privacy environment audit."""

from __future__ import annotations

import subprocess
import sys
from unittest import mock

import pytest

from openjarvis.cli.scan_cmd import PrivacyScanner, ScanResult


class TestScanResultDataclass:
    def test_scan_result_fields(self) -> None:
        r = ScanResult(name="Test", status="ok", message="All good", platform="all")
        assert r.name == "Test"
        assert r.status == "ok"
        assert r.message == "All good"
        assert r.platform == "all"


class TestFileVault:
    def test_filevault_enabled(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout="FileVault is On.", returncode=0
            )
            result = scanner.check_filevault()
        assert result.status == "ok"
        assert "enabled" in result.message.lower()

    def test_filevault_disabled(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout="FileVault is Off.", returncode=0
            )
            result = scanner.check_filevault()
        assert result.status == "fail"

    def test_filevault_command_not_found(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run", side_effect=FileNotFoundError):
            result = scanner.check_filevault()
        assert result.status == "skip"


class TestMDM:
    def test_mdm_not_enrolled(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout="This machine is not enrolled", returncode=0
            )
            result = scanner.check_mdm()
        assert result.status == "ok"

    def test_mdm_enrolled(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout="Enrolled via DEP: Yes\nMDM server: example.com",
                returncode=0,
            )
            result = scanner.check_mdm()
        assert result.status == "warn"


class TestCloudSync:
    def test_no_cloud_sync_agents(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            # pgrep returns exit code 1 when no match
            mock_run.return_value = mock.MagicMock(stdout="", returncode=1)
            result = scanner.check_cloud_sync_agents()
        assert result.status == "ok"

    def test_dropbox_running(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            def side_effect(cmd, **kwargs):
                m = mock.MagicMock()
                # Match on the process name in the pgrep pattern
                if any("Dropbox" in str(c) for c in cmd):
                    m.stdout = "12345"
                    m.returncode = 0
                else:
                    m.stdout = ""
                    m.returncode = 1
                return m
            mock_run.side_effect = side_effect
            result = scanner.check_cloud_sync_agents()
        assert result.status == "warn"
        assert "dropbox" in result.message.lower()


class TestNetworkExposure:
    def test_no_exposed_ports(self) -> None:
        scanner = PrivacyScanner()
        lsof_output = (
            "COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
            "ollama  12345 user    5u  IPv4 0x1234      0t0  TCP 127.0.0.1:11434 (LISTEN)\n"
        )
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout=lsof_output, returncode=0
            )
            result = scanner.check_network_exposure()
        assert result.status == "ok"

    def test_exposed_port(self) -> None:
        scanner = PrivacyScanner()
        lsof_output = (
            "COMMAND   PID USER   FD   TYPE DEVICE SIZE/OFF NODE NAME\n"
            "ollama  12345 user    5u  IPv4 0x1234      0t0  TCP *:11434 (LISTEN)\n"
        )
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout=lsof_output, returncode=0
            )
            result = scanner.check_network_exposure()
        assert result.status == "warn"
        assert "11434" in result.message


class TestLUKS:
    def test_luks_encrypted(self) -> None:
        scanner = PrivacyScanner()
        lsblk_json = '{"blockdevices": [{"name": "sda", "type": "disk", "fstype": null, "children": [{"name": "sda1", "type": "part", "fstype": "crypto_LUKS"}]}]}'
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout=lsblk_json, returncode=0
            )
            result = scanner.check_luks()
        assert result.status == "ok"

    def test_luks_not_encrypted(self) -> None:
        scanner = PrivacyScanner()
        lsblk_json = '{"blockdevices": [{"name": "sda", "type": "disk", "fstype": null, "children": [{"name": "sda1", "type": "part", "fstype": "ext4"}]}]}'
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(
                stdout=lsblk_json, returncode=0
            )
            result = scanner.check_luks()
        assert result.status == "fail"


class TestScreenRecording:
    def test_no_screen_recording(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value = mock.MagicMock(stdout="", returncode=1)
            result = scanner.check_screen_recording()
        assert result.status == "ok"

    def test_teamviewer_running(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch("subprocess.run") as mock_run:
            def side_effect(cmd, **kwargs):
                m = mock.MagicMock()
                if any("TeamViewer" in str(c) for c in cmd):
                    m.stdout = "12345"
                    m.returncode = 0
                else:
                    m.stdout = ""
                    m.returncode = 1
                return m
            mock_run.side_effect = side_effect
            result = scanner.check_screen_recording()
        assert result.status == "warn"


class TestPlatformFiltering:
    def test_run_all_returns_only_current_platform(self) -> None:
        scanner = PrivacyScanner()
        with mock.patch.object(scanner, "_get_all_checks") as mock_checks:
            mock_checks.return_value = [
                lambda: ScanResult("Test1", "ok", "ok", "darwin"),
                lambda: ScanResult("Test2", "ok", "ok", "linux"),
                lambda: ScanResult("Test3", "ok", "ok", "all"),
            ]
            results = scanner.run_all()
        current = sys.platform
        for r in results:
            assert r.platform in (current, "all")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/cli/test_scan.py -v`
Expected: FAIL — `scan_cmd` module doesn't exist.

- [ ] **Step 3: Implement PrivacyScanner class**

Create `src/openjarvis/cli/scan_cmd.py`:

```python
"""``jarvis scan`` — privacy and environment audit."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List

import click
from rich.console import Console


@dataclass(slots=True)
class ScanResult:
    """Result of a single privacy check."""

    name: str
    status: str  # "ok" | "warn" | "fail" | "skip"
    message: str
    platform: str  # "darwin" | "linux" | "all"


# Engine ports to check for network exposure
_ENGINE_PORTS = {
    11434: "Ollama",
    8080: "llama.cpp / MLX",
    8000: "vLLM",
    30000: "SGLang",
    1234: "LM Studio",
    52415: "Exo",
    18181: "Nexa",
}

# Cloud sync process names to check
_CLOUD_SYNC_PROCESSES = ["Dropbox", "OneDrive", "Google Drive", "iCloudDrive"]

# Screen recording / remote access process names
_SCREEN_RECORDING_PROCESSES_MACOS = [
    "TeamViewer", "AnyDesk", "ScreenConnect", "VNC",
]
_REMOTE_ACCESS_PROCESSES_LINUX = [
    "xrdp", "x11vnc", "vncserver", "AnyDesk", "TeamViewer",
]


class PrivacyScanner:
    """Run platform-specific privacy and environment checks."""

    def _run(self, cmd: list[str], **kwargs) -> subprocess.CompletedProcess:
        """Run a subprocess, capturing stdout as text."""
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=10, **kwargs
        )

    # ------------------------------------------------------------------
    # macOS checks
    # ------------------------------------------------------------------

    def check_filevault(self) -> ScanResult:
        """Check macOS FileVault disk encryption status."""
        try:
            proc = self._run(["fdesetup", "status"])
            if "On" in proc.stdout:
                return ScanResult("FileVault", "ok", "FileVault enabled", "darwin")
            return ScanResult(
                "FileVault", "fail",
                "FileVault is disabled — disk is not encrypted", "darwin"
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ScanResult("FileVault", "skip", "fdesetup not available", "darwin")

    def check_mdm(self) -> ScanResult:
        """Check for MDM / enterprise management enrollment."""
        try:
            proc = self._run(["profiles", "status", "-type", "enrollment"])
            output = proc.stdout + proc.stderr
            if "MDM" in output or "Enrolled" in output:
                return ScanResult(
                    "MDM", "warn",
                    "Enterprise management profile detected — this device may be monitored",
                    "darwin",
                )
            return ScanResult("MDM", "ok", "No MDM enrollment detected", "darwin")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ScanResult("MDM", "skip", "profiles command not available", "darwin")

    def check_icloud_sync(self) -> ScanResult:
        """Check if ~/.openjarvis/ could be synced by iCloud Drive."""
        try:
            oj_path = Path.home() / ".openjarvis"
            # Check if the path is under iCloud's mobile documents
            mobile_docs = Path.home() / "Library" / "Mobile Documents"
            try:
                resolved = oj_path.resolve()
                if str(resolved).startswith(str(mobile_docs)):
                    return ScanResult(
                        "iCloud Drive", "warn",
                        "~/.openjarvis/ is inside iCloud Drive sync path",
                        "darwin",
                    )
            except OSError:
                pass

            # Check if Desktop & Documents sync is enabled
            proc = self._run(
                ["defaults", "read", "com.apple.bird", "optimize-storage"]
            )
            # Also check the broader MobileMeAccounts for sync status
            proc2 = self._run(
                ["defaults", "read", "MobileMeAccounts"]
            )
            output = proc.stdout + proc2.stdout
            if "MOBILE_DOCUMENTS" in output or "Desktop" in output:
                return ScanResult(
                    "iCloud Drive", "warn",
                    "iCloud Desktop & Documents sync may be active — "
                    "~/.openjarvis/ could be synced to Apple servers",
                    "darwin",
                )
            return ScanResult(
                "iCloud Drive", "ok",
                "No iCloud sync overlap detected", "darwin"
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ScanResult(
                "iCloud Drive", "skip",
                "Could not determine iCloud sync status", "darwin"
            )
        except Exception:
            return ScanResult(
                "iCloud Drive", "skip",
                "Could not determine iCloud sync status", "darwin"
            )

    # ------------------------------------------------------------------
    # Linux checks
    # ------------------------------------------------------------------

    def check_luks(self) -> ScanResult:
        """Check for LUKS disk encryption on Linux."""
        try:
            proc = self._run(["lsblk", "-o", "NAME,TYPE,FSTYPE", "-J"])
            data = json.loads(proc.stdout)

            def _has_luks(devices: list) -> bool:
                for dev in devices:
                    if dev.get("fstype") == "crypto_LUKS":
                        return True
                    if _has_luks(dev.get("children", [])):
                        return True
                return False

            if _has_luks(data.get("blockdevices", [])):
                return ScanResult(
                    "Disk Encryption", "ok",
                    "LUKS encryption detected", "linux"
                )
            return ScanResult(
                "Disk Encryption", "fail",
                "No LUKS encryption detected — disk may not be encrypted",
                "linux",
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ScanResult(
                "Disk Encryption", "skip",
                "lsblk not available", "linux"
            )
        except (json.JSONDecodeError, KeyError):
            return ScanResult(
                "Disk Encryption", "skip",
                "Could not parse lsblk output", "linux"
            )

    def check_remote_access(self) -> ScanResult:
        """Check for remote access tools on Linux."""
        return self._check_processes(
            _REMOTE_ACCESS_PROCESSES_LINUX,
            "Remote Access",
            "Remote access tool detected",
            "linux",
        )

    # ------------------------------------------------------------------
    # Cross-platform checks
    # ------------------------------------------------------------------

    def check_cloud_sync_agents(self) -> ScanResult:
        """Check for running cloud sync agents."""
        platform = "darwin" if sys.platform == "darwin" else "linux"
        return self._check_processes(
            _CLOUD_SYNC_PROCESSES,
            "Cloud Sync",
            "Cloud sync agent detected",
            platform,
        )

    def check_network_exposure(self) -> ScanResult:
        """Check if inference engine ports are bound to 0.0.0.0."""
        platform = "darwin" if sys.platform == "darwin" else "linux"
        try:
            if sys.platform == "darwin":
                proc = self._run(["lsof", "-iTCP", "-sTCP:LISTEN", "-nP"])
            else:
                proc = self._run(["ss", "-tlnp"])

            exposed = []
            for line in proc.stdout.splitlines():
                for port, engine_name in _ENGINE_PORTS.items():
                    port_str = str(port)
                    if port_str in line and ("*:" + port_str in line or "0.0.0.0:" + port_str in line):
                        exposed.append(f"{engine_name} (port {port})")

            if exposed:
                return ScanResult(
                    "Network Exposure", "warn",
                    f"Inference ports exposed to network: {', '.join(exposed)}",
                    platform,
                )
            return ScanResult(
                "Network Exposure", "ok",
                "Inference ports bound to localhost only", platform
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return ScanResult(
                "Network Exposure", "skip",
                "Could not check listening ports", platform
            )

    def check_screen_recording(self) -> ScanResult:
        """Check for screen recording / remote desktop tools (macOS)."""
        return self._check_processes(
            _SCREEN_RECORDING_PROCESSES_MACOS,
            "Screen Recording",
            "Screen recording or remote access tool detected",
            "darwin",
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _check_processes(
        self,
        process_names: list[str],
        check_name: str,
        warn_message: str,
        platform: str,
    ) -> ScanResult:
        """Check if any of the named processes are running."""
        found = []
        for name in process_names:
            try:
                proc = self._run(["pgrep", "-i", name])
                if proc.returncode == 0 and proc.stdout.strip():
                    found.append(name)
            except (FileNotFoundError, subprocess.TimeoutExpired):
                continue
        if found:
            return ScanResult(
                check_name, "warn",
                f"{warn_message}: {', '.join(found)}", platform
            )
        return ScanResult(
            check_name, "ok",
            f"No {check_name.lower()} detected", platform
        )

    def _get_all_checks(self) -> List[Callable[[], ScanResult]]:
        """Return all check methods."""
        return [
            self.check_filevault,
            self.check_mdm,
            self.check_icloud_sync,
            self.check_luks,
            self.check_cloud_sync_agents,
            self.check_network_exposure,
            self.check_screen_recording,
            self.check_remote_access,
        ]

    def run_all(self) -> list[ScanResult]:
        """Run all checks, filtering to current platform."""
        results = []
        for check in self._get_all_checks():
            result = check()
            if result.platform in (sys.platform, "all"):
                if result.status != "skip":
                    results.append(result)
        return results

    def run_quick(self) -> list[ScanResult]:
        """Run only critical checks (for init hook)."""
        checks = [self.check_filevault, self.check_luks, self.check_icloud_sync,
                   self.check_cloud_sync_agents]
        results = []
        for check in checks:
            result = check()
            if result.platform in (sys.platform, "all"):
                if result.status != "skip":
                    results.append(result)
        return results


# ------------------------------------------------------------------
# CLI command
# ------------------------------------------------------------------

_STATUS_SYMBOLS = {"ok": "\u2713", "warn": "!", "fail": "\u2717"}


@click.command()
def scan() -> None:
    """Audit your environment for privacy and security risks."""
    console = Console()
    scanner = PrivacyScanner()
    results = scanner.run_all()

    console.print()
    console.print("  [bold]Privacy & Environment Audit[/bold]")
    console.print("  " + "\u2500" * 28)

    warns = 0
    fails = 0
    for r in results:
        symbol = _STATUS_SYMBOLS.get(r.status, "?")
        if r.status == "ok":
            console.print(f"  [green]{symbol}[/green] {r.name}: {r.message}")
        elif r.status == "warn":
            console.print(f"  [yellow]{symbol}[/yellow] {r.name}: {r.message}")
            warns += 1
        elif r.status == "fail":
            console.print(f"  [red]{symbol}[/red] {r.name}: {r.message}")
            fails += 1

    console.print()
    if warns == 0 and fails == 0:
        console.print("  [green]No issues found.[/green]")
    else:
        parts = []
        if warns:
            parts.append(f"{warns} warning{'s' if warns != 1 else ''}")
        if fails:
            parts.append(f"{fails} issue{'s' if fails != 1 else ''}")
        console.print(f"  {', '.join(parts)} found.")
    console.print()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/cli/test_scan.py -v`
Expected: ALL tests pass.

- [ ] **Step 5: Lint**

Run: `uv run ruff check src/openjarvis/cli/scan_cmd.py --fix`
Expected: Clean or auto-fixed.

- [ ] **Step 6: Commit**

```bash
git add src/openjarvis/cli/scan_cmd.py tests/cli/test_scan.py
git commit -m "feat: add privacy environment scanner with platform-specific checks

New PrivacyScanner class with checks for disk encryption (FileVault/LUKS),
MDM profiles, cloud sync agents, network exposure, and screen recording.
Supports macOS and Linux with graceful skip on missing tools."
```

---

### Task 5: Register `jarvis scan` and integrate privacy hook into init

**Files:**
- Modify: `src/openjarvis/cli/__init__.py:34` (add import)
- Modify: `src/openjarvis/cli/__init__.py:89` (register command)
- Modify: `src/openjarvis/cli/init_cmd.py` (add privacy hook)
- Test: `tests/cli/test_init_guidance.py`

- [ ] **Step 1: Write failing test for init privacy hook**

Add to `tests/cli/test_init_guidance.py`:

```python
class TestInitPrivacyHook:
    """Init shows a lightweight privacy summary."""

    def test_init_shows_privacy_summary(self, tmp_path: Path) -> None:
        config_dir = tmp_path / ".openjarvis"
        config_path = config_dir / "config.toml"
        with (
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_DIR", config_dir),
            mock.patch("openjarvis.cli.init_cmd.DEFAULT_CONFIG_PATH", config_path),
            mock.patch("openjarvis.cli.init_cmd.PrivacyScanner") as MockScanner,
        ):
            from openjarvis.cli.scan_cmd import ScanResult
            instance = MockScanner.return_value
            instance.run_quick.return_value = [
                ScanResult("FileVault", "ok", "FileVault enabled", "darwin"),
            ]
            result = CliRunner().invoke(
                cli, ["init", "--engine", "llamacpp", "--no-download"]
            )
        assert result.exit_code == 0
        assert "jarvis scan" in result.output
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/cli/test_init_guidance.py::TestInitPrivacyHook -v`
Expected: FAIL — no `PrivacyScanner` import in init_cmd, no privacy output.

- [ ] **Step 3: Update all existing init tests to mock PrivacyScanner**

After adding the privacy hook to init, all existing init CLI tests will call real system commands (`fdesetup`, `pgrep`, etc.). Add `mock.patch("openjarvis.cli.init_cmd.PrivacyScanner")` to every existing init CLI test's context manager block in `tests/cli/test_init_guidance.py`. This includes:

- `test_init_shows_next_steps`
- `test_init_output_shows_toml_sections_literally`
- `test_init_generates_minimal_by_default`
- `test_init_full_generates_verbose_config`
- `test_init_shows_download_prompt`
- `test_init_no_download_flag_skips_prompt`
- `test_init_no_model_shows_warning`
- `test_init_ollama_download_calls_ollama_pull`
- `test_init_vllm_shows_auto_download_message`

For each, add inside the `with (...)` block:
```python
mock.patch("openjarvis.cli.init_cmd.PrivacyScanner"),
```

- [ ] **Step 4: Register scan command and add init privacy hook**

In `src/openjarvis/cli/__init__.py`, add after line 33:

```python
from openjarvis.cli.scan_cmd import scan
```

After line 89 (the last `cli.add_command` call), add:

```python
cli.add_command(scan, "scan")
```

In `src/openjarvis/cli/init_cmd.py`, add import:

```python
from openjarvis.cli.scan_cmd import PrivacyScanner
```

Add `_quick_privacy_check` function:

```python
def _quick_privacy_check(console: Console) -> None:
    """Run critical privacy checks and print compact summary."""
    scanner = PrivacyScanner()
    results = scanner.run_quick()

    if results:
        console.print("  [bold]Privacy check:[/bold]")
        for r in results:
            if r.status == "ok":
                console.print(f"  [green]\u2713[/green] {r.message}")
            elif r.status == "warn":
                console.print(f"  [yellow]![/yellow] {r.message}")
            elif r.status == "fail":
                console.print(f"  [red]\u2717[/red] {r.message}")

    console.print()
    console.print("  Run [cyan]jarvis scan[/cyan] for a full environment audit.")
```

Call `_quick_privacy_check(console)` at the end of the `init()` function, just before the final "Getting Started" panel.

- [ ] **Step 4: Run all tests to verify everything passes**

Run: `uv run pytest tests/cli/test_init_guidance.py tests/cli/test_scan.py tests/core/test_recommend_model.py tests/cli/test_model_pull.py -v`
Expected: ALL tests pass.

- [ ] **Step 5: Lint all changed files**

Run: `uv run ruff check src/openjarvis/cli/ --fix`
Expected: Clean.

- [ ] **Step 6: Commit**

```bash
git add src/openjarvis/cli/__init__.py src/openjarvis/cli/init_cmd.py tests/cli/test_init_guidance.py
git commit -m "feat: register jarvis scan command and add init privacy hook

Registers the new scan command in the CLI. Adds a lightweight
privacy check at the end of jarvis init that runs disk encryption
and cloud sync checks, with pointer to jarvis scan for full audit."
```

---

### Task 6: Final integration test and cleanup

**Files:**
- All modified files from tasks 1-5

- [ ] **Step 1: Run full test suite for all touched modules**

Run: `uv run pytest tests/core/test_recommend_model.py tests/cli/test_init_guidance.py tests/cli/test_model_pull.py tests/cli/test_scan.py -v`
Expected: ALL pass.

- [ ] **Step 2: Run linter on all source files**

Run: `uv run ruff check src/openjarvis/cli/ src/openjarvis/intelligence/model_catalog.py src/openjarvis/core/config.py`
Expected: Clean.

- [ ] **Step 3: Verify the MLX bug is fixed**

Run: `uv run python3 -c "from openjarvis.core.config import HardwareInfo, GpuInfo, recommend_model; hw = HardwareInfo(platform='darwin', ram_gb=16.0, gpu=GpuInfo(vendor='apple', name='Apple M1', vram_gb=16.0, count=1)); print(f'MLX model: {recommend_model(hw, \"mlx\")}')"`
Expected output: `MLX model: qwen3.5:14b`

- [ ] **Step 4: Verify the CLI scan command is registered**

Run: `uv run jarvis scan --help`
Expected: Shows help text for the scan command.

- [ ] **Step 5: Commit if any cleanup was needed**

Only if changes were made during cleanup. Otherwise skip.
