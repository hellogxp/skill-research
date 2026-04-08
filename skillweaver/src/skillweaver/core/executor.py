"""Plan executor — runs a Plan's steps, respecting the DAG order.

Supports both synchronous (for CLI/testing) and async (for server/proxy)
execution modes.  Handles parallel groups by running independent steps
concurrently.

Note: SkillWeaver does NOT execute tools directly (that's the agent's job).
The executor prepares the invocation context — which tool, what arguments,
in what order.  It generates an execution trace for observability.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable

from skillweaver.core.models import Plan, PlanStep

logger = logging.getLogger(__name__)


class StepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StepResult:
    """Result of executing one plan step."""
    step_index: int
    status: StepStatus
    tool_name: str = ""
    duration_ms: float = 0.0
    output: Any = None
    error: str = ""


@dataclass
class ExecutionTrace:
    """Full trace of a plan execution."""
    plan_query: str
    step_results: list[StepResult] = field(default_factory=list)
    total_duration_ms: float = 0.0
    parallel_groups_used: int = 0

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.step_results if r.status == StepStatus.COMPLETED)

    @property
    def fail_count(self) -> int:
        return sum(1 for r in self.step_results if r.status == StepStatus.FAILED)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.plan_query,
            "total_duration_ms": round(self.total_duration_ms, 1),
            "parallel_groups_used": self.parallel_groups_used,
            "steps": [
                {
                    "step": r.step_index,
                    "tool": r.tool_name,
                    "status": r.status.value,
                    "duration_ms": round(r.duration_ms, 1),
                    "error": r.error or None,
                }
                for r in self.step_results
            ],
            "success": self.success_count,
            "failed": self.fail_count,
        }


# Type for the tool execution callback
ToolCallback = Callable[[str, dict[str, Any]], Any]
AsyncToolCallback = Callable[[str, dict[str, Any]], Any]  # coroutine


class PlanExecutor:
    """Executes a Plan, respecting DAG dependencies and parallel groups.

    The executor doesn't call tools directly — it uses a callback function
    that the caller provides.  This makes it work with any backend:
    MCP proxy, direct API calls, mock for testing, etc.
    """

    def __init__(self, tool_callback: AsyncToolCallback | None = None):
        self._callback = tool_callback

    async def execute(
        self,
        plan: Plan,
        tool_callback: AsyncToolCallback | None = None,
    ) -> ExecutionTrace:
        """Execute a plan asynchronously with parallel group support."""
        callback = tool_callback or self._callback
        start = time.time()

        # Group steps by parallel_group
        groups: dict[int, list[PlanStep]] = defaultdict(list)
        for step in plan.steps:
            group = step.parallel_group if step.parallel_group is not None else step.step_index
            groups[group].append(step)

        trace = ExecutionTrace(
            plan_query=plan.query,
            parallel_groups_used=len(groups),
        )
        results_by_step: dict[int, StepResult] = {}

        # Execute groups in order
        for group_id in sorted(groups.keys()):
            group_steps = groups[group_id]

            if callback:
                # Run all steps in this group concurrently
                tasks = [
                    self._execute_step(step, callback)
                    for step in group_steps
                ]
                group_results = await asyncio.gather(*tasks, return_exceptions=True)

                for step, result in zip(group_steps, group_results):
                    if isinstance(result, Exception):
                        sr = StepResult(
                            step_index=step.step_index,
                            status=StepStatus.FAILED,
                            tool_name=step.selected_skill.name if step.selected_skill else "",
                            error=str(result),
                        )
                    else:
                        sr = result
                    results_by_step[step.step_index] = sr
            else:
                # No callback — create dry-run results
                for step in group_steps:
                    sr = StepResult(
                        step_index=step.step_index,
                        status=StepStatus.COMPLETED if step.selected_skill else StepStatus.SKIPPED,
                        tool_name=step.selected_skill.name if step.selected_skill else "",
                    )
                    results_by_step[step.step_index] = sr

        # Assemble trace in step order
        for i in range(len(plan.steps)):
            trace.step_results.append(
                results_by_step.get(i, StepResult(step_index=i, status=StepStatus.SKIPPED))
            )

        trace.total_duration_ms = (time.time() - start) * 1000
        return trace

    async def _execute_step(
        self,
        step: PlanStep,
        callback: AsyncToolCallback,
    ) -> StepResult:
        """Execute a single plan step."""
        if not step.selected_skill:
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.SKIPPED,
            )

        tool_name = step.selected_skill.name
        start = time.time()

        try:
            # The callback is responsible for actual tool invocation
            output = await callback(tool_name, {"subtask": step.subtask})
            duration = (time.time() - start) * 1000
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.COMPLETED,
                tool_name=tool_name,
                duration_ms=duration,
                output=output,
            )
        except Exception as e:
            duration = (time.time() - start) * 1000
            logger.error("Step %d failed: %s", step.step_index, e)
            return StepResult(
                step_index=step.step_index,
                status=StepStatus.FAILED,
                tool_name=tool_name,
                duration_ms=duration,
                error=str(e),
            )

    def execute_sync(self, plan: Plan) -> ExecutionTrace:
        """Synchronous dry-run execution (no tool callback)."""
        return asyncio.get_event_loop().run_until_complete(self.execute(plan))
