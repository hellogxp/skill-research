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
from rich.panel import Panel
from rich.table import Table

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
    from pathlib import Path

    from skillweaver.index.store import IndexStore

    store = IndexStore()
    store.ensure_dir()

    # Auto-install bundled demo skills if no skills indexed yet
    existing = store.load_skills()
    demo_count = 0
    if not existing:
        demo_dir = Path(__file__).resolve().parent.parent.parent.parent / "test-skills"
        if demo_dir.is_dir():
            from skillweaver.adapters.skill_md import scan_directory

            demo_skills = scan_directory(demo_dir)
            if demo_skills:
                store.save_skills(demo_skills)
                demo_count = len(demo_skills)
                console.print(f"  Installed {demo_count} demo skills from bundled examples.")

    next_steps = (
        "Next steps:\n"
        "  1. Index your skills:  [cyan]skillweaver index ./path/to/skills[/]\n"
        "  2. Search for skills:  [cyan]skillweaver search \"your query\"[/]\n"
        "  3. Plan a workflow:    [cyan]skillweaver plan \"your task\" --sad[/]"
    )
    if demo_count:
        next_steps = (
            f"  {demo_count} demo skills installed — try them now:\n"
            "  [cyan]skillweaver search \"parse PDF\"[/]\n"
            "  [cyan]skillweaver plan \"scrape website, analyze data, generate chart\" --sad[/]\n\n"
            "To index your own skills:\n"
            "  [cyan]skillweaver index ./path/to/skills[/]"
        )

    console.print(Panel.fit(
        "[bold green]SkillWeaver initialized![/]\n\n"
        f"Store directory: {store.store_dir}\n\n"
        + next_steps,
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

    from skillweaver.adapters.mcp import parse_mcp_config
    from skillweaver.adapters.skill_md import scan_directory
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
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.index.store import IndexStore

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
@click.option("--backend", "-b", default="rule", help="LLM backend: ollama, openai, local, rule")
@click.option("--model", "-m", default=None, help="Model name for decomposition")
@click.option("--top-k", "-k", default=10, help="Candidates per step")
@click.option("--dag", is_flag=True, help="Use advanced DAG planner (detects parallelism)")
@click.option("--sad", is_flag=True, help="Enable SAD (two-pass feedback loop)")
@click.option("--sad-hints", default=15, help="Hint count for SAD (default: 15)")
def plan(
    query: str, backend: str, model: str | None,
    top_k: int, dag: bool, sad: bool, sad_hints: int,
):
    """Decompose a complex task and compose a skill execution plan."""
    from skillweaver.core.decomposer import create_decomposer
    from skillweaver.core.pipeline import SkillWeaverPipeline
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.index.store import IndexStore

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

    pipeline = SkillWeaverPipeline(
        decomposer, retriever,
        use_dag=dag, sad=sad, sad_hint_count=sad_hints,
    )

    # Run pipeline
    console.print(f"[dim]Planning: \"{query}\"...[/]\n")

    try:
        result = pipeline.plan(query)
    except Exception as e:
        console.print(f"[red]Planning failed: {e}[/]")
        sys.exit(1)

    # Display plan with new DAG visualizer
    from skillweaver.cli.formatters import render_plan_dag
    render_plan_dag(result, console)


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


# ============================================================
# skillweaver proxy
# ============================================================
@cli.command()
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), default=None,
              help="Path to MCP config file (auto-detects Claude/Cursor config if omitted)")
@click.option("--max-tools", default=20, help="Max tools to expose to the agent")
@click.option("--token-budget", default=8000, help="Max token budget for tool descriptions")
def proxy(config_path: str | None, max_tools: int, token_budget: int):
    """Start SkillWeaver as an MCP proxy gateway.

    Sits between your AI agent and real MCP servers.
    Intercepts tools/list to return smart-filtered subset.
    Routes tools/call to the correct upstream server.

    \b
    Usage in Claude Desktop config:
        "skillweaver": {
            "command": "skillweaver",
            "args": ["proxy"]
        }
    """
    import asyncio
    from pathlib import Path as P

    from skillweaver.mcp.proxy import McpProxy, load_proxy_configs

    cfg_path = P(config_path) if config_path else None
    configs = load_proxy_configs(cfg_path)

    if not configs:
        console.print("[red]No MCP server configs found.[/]")
        console.print(
            "[dim]Looked for: .skillweaver.json, Claude Desktop config, Cursor config.\n"
            "Provide one with --config or create .skillweaver.json[/]"
        )
        sys.exit(1)

    console.print(
        f"[green]SkillWeaver Proxy[/] — {len(configs)} upstream servers, "
        f"max_tools={max_tools}, token_budget={token_budget}"
    )

    proxy_server = McpProxy(
        server_configs=configs,
        max_tools=max_tools,
        token_budget=token_budget,
    )

    async def _run():
        results = await proxy_server.start()
        total = sum(results.values())
        for name, count in results.items():
            console.print(f"  [cyan]{name}[/]: {count} tools")
        console.print(f"\n[green]Ready[/] — {total} tools indexed, serving on stdio\n")
        await proxy_server.serve_stdio()

    try:
        asyncio.run(_run())
    except KeyboardInterrupt:
        pass


# ============================================================
# skillweaver benchmark
# ============================================================
@cli.command()
@click.argument("query")
@click.option("--top-k", "-k", default=20, help="Number of tools to test with")
def benchmark(query: str, top_k: int):
    """Benchmark tool selection accuracy with/without SkillWeaver filtering.

    Shows the before/after comparison: how many tools the agent sees
    and estimated context window savings.
    """
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.index.store import IndexStore

    store = IndexStore()
    skills = store.load_skills()

    if not skills:
        console.print("[red]No skills indexed.[/]")
        sys.exit(1)

    # Calculate "before" metrics
    total_tokens_before = sum(s.estimated_tokens() for s in skills)

    # Build retriever and filter
    retriever = SkillRetriever(top_k=top_k)
    if store.has_index():
        retriever.load_index(store.index_dir, skills)
    else:
        retriever.build_index(skills)

    results = retriever.search(query, top_k=top_k)
    total_tokens_after = sum(m.skill.estimated_tokens() for m in results)

    # Display comparison
    table = Table(title=f"Benchmark: \"{query}\"")
    table.add_column("Metric", style="bold")
    table.add_column("Without SkillWeaver", justify="right", style="red")
    table.add_column("With SkillWeaver", justify="right", style="green")
    table.add_column("Savings", justify="right", style="cyan")

    table.add_row(
        "Tools exposed",
        str(len(skills)),
        str(len(results)),
        f"-{len(skills) - len(results)} ({(1 - len(results)/max(len(skills),1))*100:.0f}%)",
    )
    saved = total_tokens_before - total_tokens_after
    pct = (1 - total_tokens_after / max(total_tokens_before, 1)) * 100
    table.add_row(
        "Est. tokens",
        f"{total_tokens_before:,}",
        f"{total_tokens_after:,}",
        f"-{saved:,} ({pct:.0f}%)",
    )

    if results:
        avg_score = sum(m.score for m in results) / len(results)
        top_score = results[0].score
        table.add_row("Top match score", "N/A", f"{top_score:.3f}", "")
        table.add_row("Avg match score", "N/A", f"{avg_score:.3f}", "")

    console.print(table)

    # Show top matches
    console.print(f"\n[bold]Top {min(5, len(results))} selected tools:[/]")
    for i, m in enumerate(results[:5], 1):
        console.print(f"  {i}. [{m.score:.2f}] {m.skill.name}: {m.skill.description[:60]}")


# ============================================================
# skillweaver serve
# ============================================================
@cli.command()
@click.option("--host", default="0.0.0.0", help="Bind address")
@click.option("--port", "-p", default=8740, help="Port number")
@click.option("--reload", "do_reload", is_flag=True, help="Auto-reload on code changes")
def serve(host: str, port: int, do_reload: bool):
    """Start the SkillWeaver HTTP API server."""
    try:
        import uvicorn
    except ImportError:
        console.print("[red]uvicorn is required. Install with: pip install skillweaver\\[server][/]")
        sys.exit(1)

    console.print(
        f"[green]SkillWeaver API Server[/] starting on [cyan]http://{host}:{port}[/]\n"
        f"  Docs: http://{host}:{port}/docs\n"
    )

    uvicorn.run(
        "skillweaver.server.app:create_app",
        host=host,
        port=port,
        reload=do_reload,
        factory=True,
        log_level="info",
    )


# ============================================================
# skillweaver hub
# ============================================================
@cli.group()
def hub():
    """Manage community skill packs."""
    pass


@hub.command("list")
def hub_list():
    """List available skill packs."""
    from skillweaver.hub.client import HubClient

    client = HubClient()
    packs = client.list_packs()

    if not packs:
        console.print("[yellow]No packs found.[/]")
        console.print("[dim]Publish one with: skillweaver hub publish --name my-pack ./skills[/]")
        return

    table = Table(title="Skill Packs")
    table.add_column("Name", style="cyan")
    table.add_column("Version")
    table.add_column("Skills", justify="right")
    table.add_column("Author")
    table.add_column("Source", style="dim")

    for p in packs:
        table.add_row(
            p["name"], p.get("version", "?"),
            str(p.get("skill_count", 0)),
            p.get("author", ""),
            p.get("source", ""),
        )
    console.print(table)


@hub.command("install")
@click.argument("pack_name")
def hub_install(pack_name: str):
    """Install a skill pack and add to index."""
    from skillweaver.hub.client import HubClient
    from skillweaver.index.store import IndexStore

    client = HubClient()
    pack = client.install(pack_name)

    if not pack:
        console.print(f"[red]Pack '{pack_name}' not found.[/]")
        sys.exit(1)

    store = IndexStore()
    existing = store.load_skills()
    existing_ids = {s.skill_id for s in existing}
    new = [s for s in pack.skills if s.skill_id not in existing_ids]
    all_skills = existing + new
    store.save_skills(all_skills)

    console.print(
        f"[green]Installed pack '{pack.name}' v{pack.version}[/]\n"
        f"  Added {len(new)} skills ({len(pack.skills) - len(new)} duplicates skipped)\n"
        f"  Total skills: {len(all_skills)}"
    )


@hub.command("publish")
@click.argument("path", type=click.Path(exists=True))
@click.option("--name", "-n", required=True, help="Pack name")
@click.option("--version", "-V", default="1.0.0", help="Pack version")
@click.option("--author", "-a", default="", help="Author name")
@click.option("--description", "-d", default="", help="Pack description")
def hub_publish(path: str, name: str, version: str, author: str, description: str):
    """Publish skills from a directory as a skill pack."""
    from pathlib import Path as P

    from skillweaver.hub.client import HubClient
    from skillweaver.hub.publish import create_pack_from_directory

    pack = create_pack_from_directory(
        P(path), name=name, version=version,
        author=author, description=description,
    )

    if not pack.skills:
        console.print("[yellow]No skills found in directory.[/]")
        return

    client = HubClient()
    out = client.publish(pack)
    console.print(
        f"[green]Published pack '{name}' v{version}[/]\n"
        f"  Skills: {len(pack.skills)}\n"
        f"  Saved: {out}"
    )


if __name__ == "__main__":
    cli()
