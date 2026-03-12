"""``jarvis model`` — model management subcommands."""

from __future__ import annotations

import os
import sys

import click
import httpx
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from openjarvis.core.config import load_config
from openjarvis.core.registry import ModelRegistry
from openjarvis.engine import discover_engines, discover_models
from openjarvis.intelligence import merge_discovered_models, register_builtin_models


@click.group()
def model() -> None:
    """Manage language models."""


@model.command("list")
def list_models() -> None:
    """List available models from running engines."""
    console = Console()
    config = load_config()
    register_builtin_models()

    engines = discover_engines(config)
    if not engines:
        console.print(
            "[yellow]No inference engines detected.[/yellow]\n"
            "Start an engine (e.g. [cyan]ollama serve[/cyan]) and try again."
        )
        return

    all_models = discover_models(engines)
    for ek, model_ids in all_models.items():
        merge_discovered_models(ek, model_ids)

    table = Table(title="Available Models")
    table.add_column("Engine", style="cyan")
    table.add_column("Model", style="green")
    table.add_column("Params", justify="right")
    table.add_column("Active", justify="right")
    table.add_column("Context", justify="right")
    table.add_column("VRAM", justify="right")
    table.add_column("Arch", style="dim")

    for engine_key, model_ids in all_models.items():
        for mid in model_ids:
            try:
                spec = ModelRegistry.get(mid)
                params = f"{spec.parameter_count_b}B" if spec.parameter_count_b else "-"
                active = (
                    f"{spec.active_parameter_count_b}B"
                    if spec.active_parameter_count_b
                    else "-"
                )
                ctx = f"{spec.context_length:,}" if spec.context_length else "-"
                vram = f"{spec.min_vram_gb}GB" if spec.min_vram_gb else "-"
                arch = spec.metadata.get("architecture", "-")
            except KeyError:
                params = "-"
                active = "-"
                ctx = "-"
                vram = "-"
                arch = "-"
            table.add_row(engine_key, mid, params, active, ctx, vram, arch)

    console.print(table)


@model.command()
@click.argument("model_name")
def info(model_name: str) -> None:
    """Show details for a model."""
    console = Console()
    register_builtin_models()

    # Also try discovering from running engines
    config = load_config()
    engines = discover_engines(config)
    all_models = discover_models(engines)
    for ek, model_ids in all_models.items():
        merge_discovered_models(ek, model_ids)

    if not ModelRegistry.contains(model_name):
        console.print(f"[red]Model not found:[/red] {model_name}")
        sys.exit(1)

    spec = ModelRegistry.get(model_name)
    params = f"{spec.parameter_count_b}B" if spec.parameter_count_b else "unknown"
    active = (
        f"{spec.active_parameter_count_b}B"
        if spec.active_parameter_count_b
        else "-"
    )
    ctx_len = f"{spec.context_length:,}" if spec.context_length else "unknown"
    vram = f"{spec.min_vram_gb}GB" if spec.min_vram_gb else "-"
    engines_str = (
        ", ".join(spec.supported_engines) if spec.supported_engines else "-"
    )
    provider = spec.provider or "-"
    api_key = "required" if spec.requires_api_key else "not required"
    lines = [
        f"[bold]Model ID:[/bold]       {spec.model_id}",
        f"[bold]Name:[/bold]           {spec.name}",
        f"[bold]Parameters:[/bold]     {params}",
        f"[bold]Active Params:[/bold]  {active}",
        f"[bold]Context:[/bold]        {ctx_len}",
        f"[bold]Quantization:[/bold]   {spec.quantization.value}",
        f"[bold]Min VRAM:[/bold]       {vram}",
        f"[bold]Engines:[/bold]        {engines_str}",
        f"[bold]Provider:[/bold]       {provider}",
        f"[bold]API Key:[/bold]        {api_key}",
    ]

    # Append metadata fields with well-known labels
    meta_labels = {
        "architecture": "Architecture",
        "hf_repo": "HuggingFace",
        "url": "More Info",
        "teacher": "Teacher Model",
        "quantization": "Quant Format",
        "license": "License",
        "pricing_input": "Price (input)",
        "pricing_output": "Price (output)",
    }
    for key, label in meta_labels.items():
        value = spec.metadata.get(key)
        if value is not None:
            if key.startswith("pricing_"):
                value = f"${value}/M tokens"
            elif key == "hf_repo":
                value = f"https://huggingface.co/{value}"
            pad = " " * max(1, 14 - len(label))
            lines.append(f"[bold]{label}:[/bold]{pad}{value}")

    # Any remaining metadata not covered above
    extra_keys = set(spec.metadata) - set(meta_labels)
    for key in sorted(extra_keys):
        pad = " " * max(1, 14 - len(key))
        lines.append(f"[bold]{key}:[/bold]{pad}{spec.metadata[key]}")

    console.print(Panel("\n".join(lines), title=spec.name, border_style="blue"))


@model.command()
@click.argument("model_name")
def pull(model_name: str) -> None:
    """Download a model (Ollama only)."""
    console = Console()
    config = load_config()
    host = (
        config.engine.ollama_host
        or os.environ.get("OLLAMA_HOST")
        or "http://localhost:11434"
    ).rstrip("/")

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
    except httpx.ConnectError:
        console.print("[red]Cannot connect to Ollama.[/red] Is it running?")
        sys.exit(1)
    except httpx.HTTPStatusError as exc:
        console.print(f"[red]Ollama error:[/red] {exc.response.status_code}")
        sys.exit(1)
