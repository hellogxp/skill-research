"""Integration tests for the full pipeline: decompose -> retrieve -> compose."""

from __future__ import annotations

from pathlib import Path

import pytest

from skillweaver.core.decomposer import RuleBasedDecomposer
from skillweaver.core.models import Plan, Skill, SkillFormat


def _make_skills(n: int = 10) -> list[Skill]:
    """Create a set of test skills."""
    categories = ["web", "data", "ai", "file", "comm"]
    skills = []
    for i in range(n):
        cat = categories[i % len(categories)]
        skills.append(Skill(
            skill_id=f"skill-{i}",
            name=f"test-skill-{i}",
            description=f"A test skill for {cat} operations number {i}",
            categories=[cat],
            tags=[cat, f"tag-{i}"],
            source_format=SkillFormat.GENERIC,
        ))
    return skills


class TestPipelineIntegration:
    """Tests the full decompose -> retrieve -> compose pipeline."""

    def test_single_task_pipeline(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(10)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(decomposer, retriever)
        result = pipeline.plan("do a web operation")

        assert isinstance(result, Plan)
        assert len(result.steps) >= 1
        assert result.steps[0].selected_skill is not None

    def test_multi_task_pipeline(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(20)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(decomposer, retriever)
        result = pipeline.plan("scrape website, and then analyze data")

        assert isinstance(result, Plan)
        assert len(result.steps) >= 2
        for step in result.steps:
            assert step.selected_skill is not None
            assert step.confidence > 0

    def test_dag_pipeline(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(15)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(decomposer, retriever, use_dag=True)
        result = pipeline.plan("fetch data, then process it, and send notification")

        assert isinstance(result, Plan)
        assert len(result.steps) >= 2

    def test_pipeline_with_demo_skills(self):
        """Test with actual demo skills if they exist."""
        from skillweaver.adapters.skill_md import scan_directory
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        demo_dir = Path(__file__).parent.parent / "demo-skills"
        if not demo_dir.exists():
            pytest.skip("demo-skills directory not found")

        skills = scan_directory(demo_dir)
        assert len(skills) >= 10, f"Expected 10+ skills, got {len(skills)}"

        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(decomposer, retriever)

        # Single skill query
        result = pipeline.plan("scrape a website")
        assert len(result.steps) >= 1
        assert result.steps[0].selected_skill is not None

        # Multi-skill query
        result = pipeline.plan("scrape website, parse the data, and send to Slack")
        assert len(result.steps) >= 2
