"""``jarvis soul`` — manage the AI's persistent soul (identity, memory, persona).

Subcommands:
  init     Create or reset a soul
  status   Show current soul state
  reflect  Run a dream/reflection cycle
  list     List all available souls
  recall   Search soul memories
  forget   Clear soul memories
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout
from rich.text import Text


@click.group(help="Manage the AI's persistent soul (identity, memory, persona).")
def soul() -> None:
    """Manage the soul — the agent's persistent identity."""


@soul.command()
@click.argument("name", default="default")
@click.option("--openness", default=0.7, type=float, help="Openness trait (0-1)")
@click.option("--conscientiousness", default=0.8, type=float, help="Conscientiousness trait (0-1)")
@click.option("--extraversion", default=0.5, type=float, help="Extraversion trait (0-1)")
@click.option("--agreeableness", default=0.7, type=float, help="Agreeableness trait (0-1)")
@click.option("--force", is_flag=True, help="Overwrite existing soul")
def init(
    name: str,
    openness: float,
    conscientiousness: float,
    extraversion: float,
    agreeableness: float,
    force: bool,
) -> None:
    """Initialize or reset a soul identity."""
    from openjarvis.soul import Soul
    from openjarvis.soul.storage import DEFAULT_BASE_DIR

    console = Console(stderr=True)
    soul_dir = (DEFAULT_BASE_DIR / name / "soul.json")

    if soul_dir.exists() and not force:
        console.print(
            f"[yellow]Soul '{name}' already exists.[/yellow]\n"
            f"  Use [bold]--force[/bold] to overwrite, or [bold]jarvis soul status[/bold] to view."
        )
        return

    traits = {
        "openness": max(0.0, min(1.0, openness)),
        "conscientiousness": max(0.0, min(1.0, conscientiousness)),
        "extraversion": max(0.0, min(1.0, extraversion)),
        "agreeableness": max(0.0, min(1.0, agreeableness)),
    }

    soul = Soul.load_or_create(name, traits=traits)
    soul.close()  # Flush write buffer to disk before process exits
    console.print(f"[green]Created[/green] soul: [bold]{name}[/bold]")
    console.print(f"  Traits: {json.dumps(traits)}")
    console.print(f"  Location: {soul_dir.parent}")


@soul.command()
@click.argument("name", default="default")
def status(name: str) -> None:
    """Show current soul state — identity, memory stats, persona."""
    from openjarvis.soul import Soul
    from openjarvis.soul.storage import DEFAULT_BASE_DIR

    console = Console()
    soul_dir = (DEFAULT_BASE_DIR / name / "soul.json")

    if not soul_dir.exists():
        console.print(f"[red]Soul '{name}' not found.[/red] Run [bold]jarvis soul init {name}[/bold]")
        return

    soul = Soul.load_or_create(name)
    summary = soul.state_summary()

    # Identity panel
    identity = summary.get("identity", {})
    traits_text = "\n".join(
        f"  {t}: {'█' * int(v * 10)}{'░' * (10 - int(v * 10))} ({v:.1%})"
        for t, v in identity.get("traits", {}).items()
    )
    stats = identity.get("stats", {})
    stats_text = (
        f"Interactions: {stats.get('interactions', 0)}\n"
        f"Memories stored: {stats.get('memories_stored', 0)}\n"
        f"Dreams dreamt: {stats.get('dreams_dreamed', 0)}\n"
        f"Sessions: {stats.get('sessions', 0)}"
    )

    layout = Layout()
    layout.split_column(
        Layout(Panel(f"[bold cyan]{identity.get('name', name)}[/bold cyan]\n"
                     f"Mood: {identity.get('mood', 'neutral')}",
                     title="Identity")),
        Layout(Panel(traits_text, title="Traits")),
        Layout(Panel(stats_text, title="Statistics")),
    )

    # Memory stats
    mem_stats = summary.get("memory_stats", {})
    mem_table = Table(title="Memory")
    mem_table.add_column("Type", style="cyan")
    mem_table.add_column("Count", justify="right")
    for key in ("episodic", "semantic", "procedural", "total"):
        mem_table.add_row(key.capitalize(), str(mem_stats.get(key, 0)))

    # Persona summary
    persona = summary.get("persona", {})
    expertise = persona.get("expertise", {})
    quirks = persona.get("quirks", [])

    console.print(layout)
    console.print(mem_table)

    if expertise:
        exp_text = "\n".join(f"  • {d}: {c:.0%}" for d, c in sorted(expertise.items(), key=lambda x: x[1], reverse=True))
        console.print(Panel(exp_text, title="Expertise"))
    else:
        console.print("[dim]No expertise developed yet.[/dim]")

    if quirks:
        console.print(Panel("\n".join(f"  • {q}" for q in quirks), title="Quirks"))

    # Dreams summary
    dreams = summary.get("dreams", {})
    console.print(f"[dim]Dream cycles: {dreams.get('dreams_count', 0)} | "
                  f"Insights: {dreams.get('insights_count', 0)}[/dim]")


@soul.command()
@click.argument("name", default="default")
def reflect(name: str) -> None:
    """Run a dream/reflection cycle to consolidate memories."""
    from openjarvis.soul import Soul
    from openjarvis.soul.storage import DEFAULT_BASE_DIR

    console = Console(stderr=True)
    soul_dir = (DEFAULT_BASE_DIR / name / "soul.json")

    if not soul_dir.exists():
        console.print(f"[red]Soul '{name}' not found.[/red] Run [bold]jarvis soul init {name}[/bold]")
        return

    soul = Soul.load_or_create(name)

    with console.status("[cyan]Dreaming...[/cyan]"):
        result = soul.reflect()
    soul.close()  # Flush write buffer to disk before process exits

    insights = result.get("insights", [])
    if not insights:
        console.print("[yellow]Dream cycle produced no new insights.[/yellow]")
        console.print("  (Need more memories — interact with the AI first or seed some.)")
        return

    console.print(f"[green]Dream cycle complete![/green] {len(insights)} insights:")
    for ins in insights:
        insight_type = ins.get("type", "general")
        content = str(ins.get("insight", ""))
        style = {
            "pattern": "cyan",
            "expertise_discovery": "green",
            "style_adjustment": "yellow",
            "quirk_discovery": "magenta",
        }.get(insight_type, "white")
        console.print(f"  [{style}]•[/] [{style}]{content}[/{style}]")


@soul.command()
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def list_souls(as_json: bool) -> None:
    """List all available souls."""
    from openjarvis.soul import Soul
    from openjarvis.soul.storage import DEFAULT_BASE_DIR

    console = Console()
    souls = Soul.list_souls()
    if as_json:
        console.print(json.dumps(souls, indent=2))
        return

    if not souls:
        console.print("[yellow]No souls found.[/yellow]")
        console.print(f"  Looked in: {DEFAULT_BASE_DIR}")
        console.print("  Run [bold]jarvis soul init <name>[/bold] to create one.")
        return

    table = Table(title="Available Souls")
    table.add_column("Name", style="cyan")
    table.add_column("Path")

    for sname in souls:
        spath = DEFAULT_BASE_DIR / sname / "soul.json"
        table.add_row(sname, str(spath))

    console.print(table)


@soul.command()
@click.option("--soul-name", "-s", "soul_name", default="default", help="Soul name to search")
@click.argument("query")
@click.option("--limit", "-n", default=10, type=int, help="Max results")
def recall(soul_name: str, query: str, limit: int) -> None:
    """Search soul memories."""
    from openjarvis.soul import Soul as _Soul
    from openjarvis.soul.storage import DEFAULT_BASE_DIR

    console = Console()
    soul_path = (DEFAULT_BASE_DIR / soul_name / "soul.json")

    if not soul_path.exists():
        console.print(f"[red]Soul '{soul_name}' not found.[/red]")
        return

    agent_soul = _Soul.load_or_create(soul_name)
    results = agent_soul.recall(query, limit=limit)

    if not results:
        console.print(f"[yellow]No memories matching '{query}'.[/yellow]")
        return

    table = Table(title=f"Memories matching: {query}")
    table.add_column("Type", style="cyan")
    table.add_column("Content")
    table.add_column("Score", justify="right")

    for r in results:
        content = r.get("content", "")[:100]
        if len(r.get("content", "")) > 100:
            content += "..."
        table.add_row(
            r.get("memory_type", "?"),
            content,
            f"{r.get('score', 0):.3f}",
        )

    console.print(table)


@soul.command()
@click.argument("name", default="default")
@click.option("--force", is_flag=True, help="Skip confirmation")
def forget(name: str, force: bool) -> None:
    """Reset a soul's memories and persona evolution."""
    import shutil
    from openjarvis.soul.storage import DEFAULT_BASE_DIR

    console = Console(stderr=True)
    soul_dir = DEFAULT_BASE_DIR / name

    if not (soul_dir / "soul.json").exists():
        console.print(f"[red]Soul '{name}' not found.[/red]")
        return

    if not force:
        click.confirm(
            f"Reset soul '{name}'? This will delete all memories and persona evolution.",
            abort=True,
        )

    shutil.rmtree(str(soul_dir))
    console.print(f"[green]Reset[/green] soul: [bold]{name}[/bold]")


__all__ = ["soul"]
