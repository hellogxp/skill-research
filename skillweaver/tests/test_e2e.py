"""End-to-end smoke test: init → index → search → plan (with SAD).

Verifies the full user journey works without errors.
Uses the bundled test-skills/ directory and rule-based decomposer (no LLM needed).
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Path to bundled test skills
TEST_SKILLS_DIR = Path(__file__).resolve().parent.parent / "test-skills"


@pytest.fixture
def tmp_store(tmp_path):
    """Create a temporary store directory."""
    store_dir = tmp_path / ".skillweaver"
    store_dir.mkdir()
    return store_dir


class TestEndToEnd:
    """Full pipeline smoke test."""

    def test_index_and_search(self, tmp_store):
        """Index test skills and search for one."""
        from skillweaver.adapters.skill_md import scan_directory
        from skillweaver.core.retriever import SkillRetriever
        from skillweaver.index.store import IndexStore

        store = IndexStore(store_dir=tmp_store)
        skills = scan_directory(TEST_SKILLS_DIR)
        assert len(skills) >= 3, f"Expected >=3 test skills, got {len(skills)}"

        store.save_skills(skills)
        loaded = store.load_skills()
        assert len(loaded) == len(skills)

        retriever = SkillRetriever(top_k=5)
        retriever.build_index(loaded)

        results = retriever.search("parse PDF documents")
        assert len(results) > 0
        assert results[0].score > 0

    def test_plan_vanilla(self, tmp_store):
        """Plan a workflow without SAD."""
        from skillweaver.adapters.skill_md import scan_directory
        from skillweaver.core.decomposer import RuleBasedDecomposer
        from skillweaver.core.models import Plan
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = scan_directory(TEST_SKILLS_DIR)
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)
        decomposer = RuleBasedDecomposer()

        pipeline = SkillWeaverPipeline(decomposer, retriever)
        plan = pipeline.plan("scrape a website, then generate a chart")

        assert isinstance(plan, Plan)
        assert plan.num_steps >= 2
        assert plan.avg_confidence > 0

    def test_plan_with_sad(self, tmp_store):
        """Plan a workflow with SAD enabled."""
        from skillweaver.adapters.skill_md import scan_directory
        from skillweaver.core.decomposer import RuleBasedDecomposer
        from skillweaver.core.models import Plan
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = scan_directory(TEST_SKILLS_DIR)
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)
        decomposer = RuleBasedDecomposer()

        pipeline = SkillWeaverPipeline(
            decomposer, retriever, sad=True, sad_hint_count=5,
        )
        plan = pipeline.plan("scrape a website, then generate a chart")

        assert isinstance(plan, Plan)
        assert plan.num_steps >= 2

    def test_plan_with_dag(self, tmp_store):
        """Plan with DAG planner."""
        from skillweaver.adapters.skill_md import scan_directory
        from skillweaver.core.decomposer import RuleBasedDecomposer
        from skillweaver.core.models import Plan
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = scan_directory(TEST_SKILLS_DIR)
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)
        decomposer = RuleBasedDecomposer()

        pipeline = SkillWeaverPipeline(
            decomposer, retriever, use_dag=True, sad=True, sad_hint_count=5,
        )
        plan = pipeline.plan(
            "fetch data from API, then parse CSV, and send notification"
        )

        assert isinstance(plan, Plan)
        assert plan.num_steps >= 2
        assert len(plan.edges) >= 1

    def test_sdk_client(self, tmp_store):
        """Test the SDK client end-to-end."""
        from skillweaver.config.settings import load_settings, reset_settings_cache
        from skillweaver.sdk.client import SkillWeaverClient

        reset_settings_cache()
        settings = load_settings(overrides={
            "store_dir": str(tmp_store),
            "decomposer_backend": "rule",
        }, use_cache=False)

        client = SkillWeaverClient(settings=settings)
        added = client.load_skills_from_directory(str(TEST_SKILLS_DIR))
        assert added >= 3

        results = client.search("web scraping")
        assert len(results) > 0

        plan = client.plan("scrape website, then analyze data", backend="rule")
        assert plan.num_steps >= 2

    def test_plan_to_json(self, tmp_store):
        """Verify plan serialization."""
        import json

        from skillweaver.adapters.skill_md import scan_directory
        from skillweaver.core.decomposer import RuleBasedDecomposer
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = scan_directory(TEST_SKILLS_DIR)
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(RuleBasedDecomposer(), retriever, sad=True)
        plan = pipeline.plan("parse PDF, then convert to markdown")

        data = json.loads(plan.to_json())
        assert "query" in data
        assert "steps" in data
        assert len(data["steps"]) >= 1
