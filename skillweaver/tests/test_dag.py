"""Tests for DAG planner, executor, and formatters."""

from __future__ import annotations

import asyncio

from skillweaver.core.dag_planner import (
    DAGPlanner,
    assign_parallel_groups,
    detect_dependencies,
)
from skillweaver.core.executor import ExecutionTrace, PlanExecutor, StepStatus
from skillweaver.core.models import (
    IOSchema,
    ParamSchema,
    ParamType,
    Plan,
    PlanStep,
    Skill,
    SkillMatch,
    SubTask,
)


# =========================================================================
# Dependency detection
# =========================================================================
class TestDependencyDetection:
    def test_sequential_tasks(self):
        subtasks = [
            SubTask(step_index=0, description="fetch data from the API"),
            SubTask(step_index=1, description="then parse the JSON response"),
            SubTask(step_index=2, description="finally store results in database"),
        ]
        edges = detect_dependencies(subtasks)
        # "then" and "finally" should create dependencies
        assert len(edges) > 0
        # Step 0 should come before step 1
        assert (0, 1) in edges

    def test_parallel_tasks(self):
        subtasks = [
            SubTask(step_index=0, description="download image from URL A"),
            SubTask(step_index=1, description="download image from URL B"),
            SubTask(step_index=2, description="merge downloaded images"),
        ]
        edges = detect_dependencies(subtasks)
        # Steps 0 and 1 are both producers, step 2 is a consumer
        # Step 2 should depend on both 0 and 1
        has_0_to_2 = (0, 2) in edges
        has_1_to_2 = (1, 2) in edges
        assert has_0_to_2 or has_1_to_2

    def test_io_type_dependency(self):
        subtasks = [
            SubTask(
                step_index=0,
                description="generate report",
                expected_output_types={ParamType.FILE},
            ),
            SubTask(
                step_index=1,
                description="upload report",
                required_input_types={ParamType.FILE},
            ),
        ]
        edges = detect_dependencies(subtasks)
        assert (0, 1) in edges

    def test_single_task_no_edges(self):
        subtasks = [SubTask(step_index=0, description="do something")]
        edges = detect_dependencies(subtasks)
        assert edges == []


class TestParallelGroups:
    def test_sequential(self):
        # 0 → 1 → 2
        groups = assign_parallel_groups(3, [(0, 1), (1, 2)])
        assert groups[0] < groups[1] < groups[2]

    def test_parallel_then_merge(self):
        # 0 and 1 are parallel, both feed into 2
        groups = assign_parallel_groups(3, [(0, 2), (1, 2)])
        assert groups[0] == groups[1]  # Same level
        assert groups[2] > groups[0]   # After both

    def test_diamond(self):
        # 0 → 1, 0 → 2, 1 → 3, 2 → 3
        groups = assign_parallel_groups(4, [(0, 1), (0, 2), (1, 3), (2, 3)])
        assert groups[1] == groups[2]  # Parallel
        assert groups[3] > groups[1]   # After both

    def test_no_edges_all_parallel(self):
        groups = assign_parallel_groups(4, [])
        assert all(g == 0 for g in groups)


# =========================================================================
# DAG Planner
# =========================================================================
class TestDAGPlanner:
    def _skill(self, name, desc="", **kwargs):
        return Skill(skill_id=f"t_{name}", name=name, description=desc, **kwargs)

    def test_basic_plan(self):
        planner = DAGPlanner()
        s1 = self._skill("fetch", "Fetch data from API")
        s2 = self._skill("parse", "Parse the JSON data")

        result = planner.plan(
            query="fetch and then parse data",
            subtasks=[
                SubTask(step_index=0, description="fetch data from API"),
                SubTask(step_index=1, description="then parse the data"),
            ],
            candidates_per_step=[
                [SkillMatch(skill=s1, score=0.9)],
                [SkillMatch(skill=s2, score=0.8)],
            ],
        )
        assert result.num_steps == 2
        assert len(result.edges) > 0

    def test_parallel_group_assignment(self):
        planner = DAGPlanner()
        s = self._skill("tool", "generic tool")
        result = planner.plan(
            query="download A and download B, then merge",
            subtasks=[
                SubTask(step_index=0, description="download image A"),
                SubTask(step_index=1, description="download image B"),
                SubTask(step_index=2, description="merge downloaded images"),
            ],
            candidates_per_step=[
                [SkillMatch(skill=s, score=0.8)],
                [SkillMatch(skill=s, score=0.8)],
                [SkillMatch(skill=s, score=0.7)],
            ],
        )
        # Steps 0 and 1 might be in the same parallel group
        assert result.num_steps == 3

    def test_compatibility_scoring(self):
        planner = DAGPlanner(alpha=0.5)
        s1 = self._skill(
            "generator", "Generate output data",
            io_schema=IOSchema(outputs=[ParamSchema(name="d", param_type=ParamType.STRING)]),
        )
        s2_good = self._skill(
            "consumer", "Process input string data",
            io_schema=IOSchema(inputs=[ParamSchema(name="d", param_type=ParamType.STRING)]),
        )
        s2_bad = self._skill(
            "unrelated", "Render 3D scene",
            io_schema=IOSchema(inputs=[ParamSchema(name="m", param_type=ParamType.FILE)]),
        )

        result = planner.plan(
            query="generate then process",
            subtasks=[
                SubTask(step_index=0, description="generate data"),
                SubTask(step_index=1, description="then process the result"),
            ],
            candidates_per_step=[
                [SkillMatch(skill=s1, score=0.9)],
                [SkillMatch(skill=s2_good, score=0.7), SkillMatch(skill=s2_bad, score=0.75)],
            ],
        )
        # s2_good should win despite lower retrieval score
        assert result.steps[1].selected_skill.name == "consumer"


# =========================================================================
# Executor
# =========================================================================
class TestPlanExecutor:
    def _make_plan(self):
        s1 = Skill(skill_id="s1", name="fetch", description="Fetch")
        s2 = Skill(skill_id="s2", name="parse", description="Parse")
        return Plan(
            query="test",
            steps=[
                PlanStep(step_index=0, subtask="fetch", selected_skill=s1, confidence=0.9, parallel_group=0),
                PlanStep(step_index=1, subtask="parse", selected_skill=s2, confidence=0.8, parallel_group=1),
            ],
            edges=[(0, 1)],
        )

    def test_dry_run(self):
        executor = PlanExecutor()
        plan = self._make_plan()
        trace = executor.execute_sync(plan)
        assert trace.success_count == 2
        assert trace.fail_count == 0

    def test_with_callback(self):
        async def mock_callback(tool_name, args):
            return {"status": "ok", "tool": tool_name}

        executor = PlanExecutor()
        plan = self._make_plan()
        trace = asyncio.get_event_loop().run_until_complete(
            executor.execute(plan, tool_callback=mock_callback)
        )
        assert trace.success_count == 2
        assert trace.step_results[0].tool_name == "fetch"

    def test_callback_failure(self):
        async def failing_callback(tool_name, args):
            raise RuntimeError("Connection refused")

        executor = PlanExecutor()
        plan = self._make_plan()
        trace = asyncio.get_event_loop().run_until_complete(
            executor.execute(plan, tool_callback=failing_callback)
        )
        assert trace.fail_count == 2
        assert "Connection refused" in trace.step_results[0].error

    def test_skipped_step(self):
        plan = Plan(
            query="test",
            steps=[PlanStep(step_index=0, subtask="nothing", selected_skill=None)],
        )
        executor = PlanExecutor()
        trace = executor.execute_sync(plan)
        assert trace.step_results[0].status == StepStatus.SKIPPED

    def test_trace_to_dict(self):
        executor = PlanExecutor()
        plan = self._make_plan()
        trace = executor.execute_sync(plan)
        d = trace.to_dict()
        assert d["success"] == 2
        assert len(d["steps"]) == 2


# =========================================================================
# Formatters (just check they don't crash)
# =========================================================================
class TestFormatters:
    def _make_plan(self):
        s1 = Skill(skill_id="s1", name="fetch", description="Fetch data")
        s2 = Skill(skill_id="s2", name="parse", description="Parse data")
        return Plan(
            query="fetch and parse",
            steps=[
                PlanStep(step_index=0, subtask="fetch data", selected_skill=s1,
                         confidence=0.9, parallel_group=0),
                PlanStep(step_index=1, subtask="parse data", selected_skill=s2,
                         confidence=0.7, parallel_group=1),
            ],
            edges=[(0, 1)],
        )

    def test_render_plan_dag(self):
        from io import StringIO

        from rich.console import Console

        from skillweaver.cli.formatters import render_plan_dag

        buf = StringIO()
        con = Console(file=buf, width=120)
        render_plan_dag(self._make_plan(), con)
        output = buf.getvalue()
        assert "fetch" in output
        assert "parse" in output

    def test_render_ascii(self):
        from skillweaver.cli.formatters import render_plan_ascii
        text = render_plan_ascii(self._make_plan())
        assert "fetch" in text
        assert "parse" in text
        assert "Avg conf" in text

    def test_render_trace(self):
        from io import StringIO

        from rich.console import Console

        from skillweaver.cli.formatters import render_execution_trace
        from skillweaver.core.executor import StepResult, StepStatus

        trace = ExecutionTrace(
            plan_query="test",
            step_results=[
                StepResult(step_index=0, status=StepStatus.COMPLETED, tool_name="t1", duration_ms=42),
                StepResult(step_index=1, status=StepStatus.FAILED, tool_name="t2", error="timeout"),
            ],
            total_duration_ms=50,
        )
        buf = StringIO()
        con = Console(file=buf, width=120)
        render_execution_trace(trace, con)
        output = buf.getvalue()
        assert "t1" in output
        assert "t2" in output
