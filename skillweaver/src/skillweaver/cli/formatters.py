"""Rich-based DAG visualization for the CLI.

Renders execution plans as visual DAGs in the terminal,
showing parallel groups, dependencies, and confidence scores.
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from skillweaver.core.executor import ExecutionTrace, StepStatus
from skillweaver.core.models import Plan


def render_plan_dag(plan: Plan, console: Console | None = None) -> None:
    """Render a Plan as a visual DAG in the terminal."""
    con = console or Console()

    # Group steps by parallel_group
    groups: dict[int, list[int]] = {}
    for step in plan.steps:
        g = step.parallel_group if step.parallel_group is not None else step.step_index
        groups.setdefault(g, []).append(step.step_index)

    # Build the visualization
    lines = []
    lines.append(f"[bold]Query:[/] {plan.query}\n")

    sorted_groups = sorted(groups.keys())
    for gi, group_id in enumerate(sorted_groups):
        step_indices = groups[group_id]
        is_parallel = len(step_indices) > 1

        if is_parallel:
            lines.append(f"[bold yellow]  Group {group_id}[/] [dim](parallel)[/]")

        for idx in step_indices:
            step = plan.steps[idx]
            skill_name = step.selected_skill.name if step.selected_skill else "???"
            conf = step.confidence

            # Confidence color
            if conf >= 0.7:
                conf_color = "green"
            elif conf >= 0.5:
                conf_color = "yellow"
            else:
                conf_color = "red"

            prefix = "    " if is_parallel else "  "
            parallel_mark = "[dim]||[/] " if is_parallel else ""

            lines.append(
                f"{prefix}{parallel_mark}"
                f"[bold]Step {idx + 1}[/]: "
                f"[cyan]\\[{skill_name}][/]  "
                f"[{conf_color}]{conf:.2f}[/]"
            )
            lines.append(f"{prefix}       {step.subtask}")

        # Draw edge to next group
        if gi < len(sorted_groups) - 1:
            lines.append("        [dim]│[/]")
            lines.append("        [dim]▼[/]")

    # Footer stats
    lines.append("")
    lines.append(
        f"[bold]Steps:[/] {plan.num_steps}  "
        f"[bold]Edges:[/] {len(plan.edges)}  "
        f"[bold]Parallel groups:[/] {len(groups)}  "
        f"[bold]Avg confidence:[/] {plan.avg_confidence:.2f}"
    )

    con.print(Panel("\n".join(lines), title="Execution Plan (DAG)", border_style="green"))


def render_execution_trace(trace: ExecutionTrace, console: Console | None = None) -> None:
    """Render an execution trace as a summary table."""
    con = console or Console()

    table = Table(title="Execution Trace")
    table.add_column("Step", style="bold", width=5)
    table.add_column("Tool", style="cyan", min_width=20)
    table.add_column("Status", min_width=10)
    table.add_column("Duration", justify="right", width=10)
    table.add_column("Error", style="dim", max_width=40)

    status_styles = {
        StepStatus.COMPLETED: "[green]OK[/]",
        StepStatus.FAILED: "[red]FAIL[/]",
        StepStatus.SKIPPED: "[dim]SKIP[/]",
        StepStatus.RUNNING: "[yellow]RUN[/]",
        StepStatus.PENDING: "[dim]...[/]",
    }

    for r in trace.step_results:
        table.add_row(
            str(r.step_index + 1),
            r.tool_name or "-",
            status_styles.get(r.status, str(r.status)),
            f"{r.duration_ms:.0f}ms" if r.duration_ms > 0 else "-",
            r.error[:40] if r.error else "",
        )

    con.print(table)
    con.print(
        f"\n[bold]Total:[/] {trace.total_duration_ms:.0f}ms  "
        f"[green]{trace.success_count} OK[/]  "
        f"[red]{trace.fail_count} failed[/]  "
        f"[dim]{len(trace.step_results) - trace.success_count - trace.fail_count} skipped[/]"
    )


def render_plan_ascii(plan: Plan) -> str:
    """Render a Plan as plain ASCII art (for non-terminal output)."""
    groups: dict[int, list[int]] = {}
    for step in plan.steps:
        g = step.parallel_group if step.parallel_group is not None else step.step_index
        groups.setdefault(g, []).append(step.step_index)

    lines = [f"Query: {plan.query}", ""]
    sorted_groups = sorted(groups.keys())

    for gi, group_id in enumerate(sorted_groups):
        step_indices = groups[group_id]
        is_parallel = len(step_indices) > 1

        for idx in step_indices:
            step = plan.steps[idx]
            skill_name = step.selected_skill.name if step.selected_skill else "???"
            par = " ||" if is_parallel else ""
            lines.append(f"  [{idx + 1}]{par} {skill_name} ({step.confidence:.2f}) - {step.subtask}")

        if gi < len(sorted_groups) - 1:
            lines.append("       |")
            lines.append("       v")

    lines.append("")
    lines.append(f"Steps: {plan.num_steps}, Edges: {len(plan.edges)}, Avg conf: {plan.avg_confidence:.2f}")
    return "\n".join(lines)
