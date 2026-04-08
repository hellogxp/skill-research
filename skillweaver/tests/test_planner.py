"""Tests for the planner integration with the new CompatibilityScorer."""

from skillweaver.core.models import (
    IOSchema,
    ParamSchema,
    ParamType,
    Skill,
    SkillMatch,
    SubTask,
)
from skillweaver.core.planner import Planner


def _skill(name, desc="", **kwargs):
    return Skill(skill_id=f"t_{name}", name=name, description=desc, **kwargs)


class TestPlanner:
    def test_single_step(self):
        planner = Planner()
        s = _skill("fetch", "Fetch data")
        result = planner.plan(
            query="fetch something",
            subtasks=[SubTask(step_index=0, description="fetch data")],
            candidates_per_step=[[SkillMatch(skill=s, score=0.9)]],
        )
        assert result.num_steps == 1
        assert result.steps[0].selected_skill.name == "fetch"

    def test_multi_step_uses_compatibility(self):
        planner = Planner(alpha=0.5)
        s1 = _skill(
            "generator",
            "Generate data output",
            io_schema=IOSchema(
                outputs=[ParamSchema(name="data", param_type=ParamType.STRING)]
            ),
        )
        s2_good = _skill(
            "parser",
            "Parse string input data",
            categories=["data"],
            io_schema=IOSchema(
                inputs=[ParamSchema(name="text", param_type=ParamType.STRING)]
            ),
        )
        s2_bad = _skill(
            "renderer",
            "Render 3D graphics",
            categories=["graphics"],
            io_schema=IOSchema(
                inputs=[ParamSchema(name="model", param_type=ParamType.FILE)]
            ),
        )

        result = planner.plan(
            query="generate then parse",
            subtasks=[
                SubTask(step_index=0, description="generate data"),
                SubTask(step_index=1, description="parse the result"),
            ],
            candidates_per_step=[
                [SkillMatch(skill=s1, score=0.9)],
                [SkillMatch(skill=s2_good, score=0.7), SkillMatch(skill=s2_bad, score=0.75)],
            ],
        )
        assert result.num_steps == 2
        # s2_good should be selected despite lower retrieval score,
        # because it has better compatibility with s1
        assert result.steps[1].selected_skill.name == "parser"

    def test_empty_candidates(self):
        planner = Planner()
        result = planner.plan(
            query="do something",
            subtasks=[SubTask(step_index=0, description="step1")],
            candidates_per_step=[[]],
        )
        assert result.steps[0].selected_skill is None
        assert result.steps[0].confidence == 0.0

    def test_edges_sequential(self):
        planner = Planner()
        s = _skill("s", "skill")
        result = planner.plan(
            query="multi",
            subtasks=[
                SubTask(step_index=0, description="a"),
                SubTask(step_index=1, description="b"),
                SubTask(step_index=2, description="c"),
            ],
            candidates_per_step=[
                [SkillMatch(skill=s, score=0.8)],
                [SkillMatch(skill=s, score=0.8)],
                [SkillMatch(skill=s, score=0.8)],
            ],
        )
        assert result.edges == [(0, 1), (1, 2)]
