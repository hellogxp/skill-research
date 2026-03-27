"""SkillWeaver CLI - AI Agent skill discovery and workflow orchestration.

Usage:
    skillweaver init          Initialize SkillWeaver configuration
    skillweaver index <path>  Scan and index skills from a directory
    skillweaver search <q>    Search for skills matching a query
    skillweaver plan <q>      Auto-decompose task and compose skill chain
    skillweaver status        Show index status
"""

from __future__ import annotations

import logging
import sys

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

console = Console()

LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.version_option(version="0.1.0", prog_name="skillweaver")
def cli(verbose: bool):
    """SkillWeaver - AI Agent skill discovery and workflow orchestration."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format=LOG_FORMAT)


# ============================================================
# skillweaver init
# ============================================================
@cli.command()
def init():
    """Initialize SkillWeaver configuration and download models."""
    from skillweaver.index.store import IndexStore

    store = IndexStore()
    store.ensure_dir()

    console.print(Panel.fit(
        "[bold green]SkillWeaver initialized![/]\n\n"
        f"Store directory: {store.store_dir}\n\n"
        "Next steps:\n"
        "  1. Index your skills:  [cyan]skillweaver index ./path/to/skills[/]\n"
        "  2. Search for skills:  [cyan]skillweaver search \"your query\"[/]\n"
        "  3. Plan a workflow:    [cyan]skillweaver plan \"your complex task\"[/]",
        title="SkillWeaver",
    ))


# ============================================================
# skillweaver index
# ============================================================
@cli.command()
@click.argument("path", type=click.Path(exists=True))
@click.option("--format", "fmt", type=click.Choice(["auto", "skill_md", "mcp"]), default="auto")
@click.option("--rebuild", is_flag=True, help="Rebuild FAISS index after scanning")
def index(path: str, fmt: str, rebuild: bool):
    """Scan a directory or config file for skills and add to index."""
    from pathlib import Path as P

    from skillweaver.adapters.skill_md import scan_directory
    from skillweaver.adapters.mcp import parse_mcp_config
    from skillweaver.index.store import IndexStore

    target = P(path)
    skills = []

    if fmt == "mcp" or (fmt == "auto" and target.suffix == ".json"):
        skills = parse_mcp_config(target)
    elif fmt == "skill_md" or (fmt == "auto" and target.is_dir()):
        skills = scan_directory(target)
    else:
        console.print(f"[red]Cannot determine format for: {path}[/]")
        sys.exit(1)

    if not skills:
        console.print("[yellow]No skills found.[/]")
        return

    # Merge with existing index
    store = IndexStore()
    existing = store.load_skills()
    existing_ids = {s.skill_id for s in existing}
    new_skills = [s for s in skills if s.skill_id not in existing_ids]
    all_skills = existing + new_skills

    store.save_skills(all_skills)

    console.print(
        f"[green]Indexed {len(new_skills)} new skills[/] "
        f"({len(skills)} scanned, {len(skills) - len(new_skills)} duplicates skipped)\n"
        f"Total skills in index: [bold]{len(all_skills)}[/]"
    )

    if rebuild or not store.has_index():
        _rebuild_faiss_index(store, all_skills)


def _rebuild_faiss_index(store, skills):
    """Rebuild FAISS index from skills."""
    from skillweaver.core.retriever import SkillRetriever

    console.print("[dim]Building search index...[/]")
    retriever = SkillRetriever()
    retriever.build_index(skills)
    retriever.save_index(store.index_dir)
    console.print("[green]Search index built.[/]")


# ============================================================
# skillweaver search
# ============================================================
@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", default=5, help="Number of results")
@click.option("--category", "-c", default=None, help="Filter by category")
def search(query: str, top_k: int, category: str | None):
    """Search for skills matching a natural language query."""
    from skillweaver.index.store import IndexStore
    from skillweaver.core.retriever import SkillRetriever

    store = IndexStore()
    skills = store.load_skills()

    if not skills:
        console.print("[red]No skills indexed. Run 'skillweaver index <path>' first.[/]")
        sys.exit(1)

    # Filter by category if specified
    if category:
        skills = [s for s in skills if category.lower() in [c.lower() for c in s.categories]]
        if not skills:
            console.print(f"[yellow]No skills found in category: {category}[/]")
            return

    retriever = SkillRetriever(top_k=top_k)
    if store.has_index() and not category:
        retriever.load_index(store.index_dir, skills)
    else:
        retriever.build_index(skills)

    results = retriever.search(query, top_k=top_k)

    if not results:
        console.print("[yellow]No matching skills found.[/]")
        return

    table = Table(title=f"Search: \"{query}\"", show_lines=False)
    table.add_column("#", style="dim", width=3)
    table.add_column("Score", justify="right", width=6)
    table.add_column("Skill", style="cyan", min_width=20)
    table.add_column("Description", min_width=40)

    for i, match in enumerate(results, 1):
        score_color = "green" if match.score > 0.7 else "yellow" if match.score > 0.5 else "dim"
        table.add_row(
            str(i),
            f"[{score_color}]{match.score:.2f}[/]",
            match.skill.name,
            match.skill.description[:80],
        )

    console.print(table)


# ============================================================
# skillweaver plan
# ============================================================
@cli.command()
@click.argument("query")
@click.option("--backend", "-b", default="ollama", help="LLM backend: ollama, openai, local")
@click.option("--model", "-m", default=None, help="Model name for decomposition")
@click.option("--top-k", "-k", default=10, help="Candidates per step")
def plan(query: str, backend: str, model: str | None, top_k: int):
    """Decompose a complex task and compose a skill execution plan."""
    from skillweaver.index.store import IndexStore
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.core.decomposer import create_decomposer
    from skillweaver.core.planner import Planner
    from skillweaver.core.pipeline import SkillWeaverPipeline

    store = IndexStore()
    skills = store.load_skills()

    if not skills:
        console.print("[red]No skills indexed. Run 'skillweaver index <path>' first.[/]")
        sys.exit(1)

    # Set up components
    decomposer_kwargs = {}
    if model:
        decomposer_kwargs["model"] = model

    try:
        decomposer = create_decomposer(backend, **decomposer_kwargs)
    except Exception as e:
        console.print(f"[red]Failed to create decomposer ({backend}): {e}[/]")
        console.print("[dim]Tip: Install Ollama and run 'ollama pull qwen2.5:7b-instruct'[/]")
        sys.exit(1)

    retriever = SkillRetriever(top_k=top_k)
    if store.has_index():
        retriever.load_index(store.index_dir, skills)
    else:
        retriever.build_index(skills)

    pipeline = SkillWeaverPipeline(decomposer, retriever, Planner())

    # Run pipeline
    console.print(f"[dim]Planning: \"{query}\"...[/]\n")

    try:
        result = pipeline.plan(query)
    except Exception as e:
        console.print(f"[red]Planning failed: {e}[/]")
        sys.exit(1)

    # Display plan
    _display_plan(result)


def _display_plan(plan):
    """Pretty-print an execution plan."""
    from skillweaver.core.models import Plan

    lines = []
    for step in plan.steps:
        skill_name = step.selected_skill.name if step.selected_skill else "???"
        conf = f"{step.confidence:.2f}" if step.confidence > 0 else "N/A"
        lines.append(
            f"  Step {step.step_index + 1}: "
            f"[cyan]\\[{skill_name}][/] {step.subtask}\n"
            f"          [dim]confidence: {conf}[/]"
        )

    # Dependencies
    dep_str = " -> ".join(f"Step {i + 1}" for i in range(plan.num_steps))

    panel_text = (
        f"[bold]Query:[/] {plan.query}\n\n"
        + "\n".join(lines)
        + f"\n\n[bold]Dependencies:[/] {dep_str}"
        + f"\n[bold]Avg confidence:[/] {plan.avg_confidence:.2f}"
    )

    console.print(Panel(panel_text, title="Execution Plan", border_style="green"))


# ============================================================
# skillweaver status
# ============================================================
@cli.command()
def status():
    """Show index status and statistics."""
    from skillweaver.index.store import IndexStore

    store = IndexStore()
    info = store.status()

    table = Table(title="SkillWeaver Index Status")
    table.add_column("Property", style="bold")
    table.add_column("Value")

    table.add_row("Store directory", info["store_dir"])
    table.add_row("Total skills", str(info["total_skills"]))
    table.add_row("FAISS index", "Yes" if info["has_faiss_index"] else "No")

    for fmt, count in info["format_counts"].items():
        table.add_row(f"  {fmt}", str(count))

    console.print(table)

    if info["total_skills"] == 0:
        console.print("\n[yellow]No skills indexed yet.[/]")
        console.print("Run: [cyan]skillweaver index ./path/to/skills[/]")


if __name__ == "__main__":
    cli()
