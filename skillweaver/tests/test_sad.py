"""Tests for Skill-Aware Decomposition (SAD) two-pass feedback loop.

Covers:
- build_hint_set utility
- decompose_with_hints on BaseDecomposer subclasses
- Pipeline integration with sad=True
- Mock-based OpenAI SAD prompt verification
"""

from __future__ import annotations

from skillweaver.core.decomposer import (
    SAD_USER_TEMPLATE,
    BaseDecomposer,
    RuleBasedDecomposer,
)
from skillweaver.core.models import Plan, Skill, SkillFormat, SkillMatch, SubTask
from skillweaver.core.pipeline import build_hint_set


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_skill(name: str, desc: str = "", cat: str = "general") -> Skill:
    return Skill(
        skill_id=f"id-{name}",
        name=name,
        description=desc or f"A skill called {name}",
        categories=[cat],
        tags=[cat],
        source_format=SkillFormat.GENERIC,
    )


def _make_match(name: str, score: float) -> SkillMatch:
    return SkillMatch(skill=_make_skill(name), score=score)


def _make_skills(n: int = 10) -> list[Skill]:
    categories = ["web", "data", "ai", "file", "comm"]
    return [
        Skill(
            skill_id=f"skill-{i}",
            name=f"test-skill-{i}",
            description=f"A test skill for {categories[i % len(categories)]} operations number {i}",
            categories=[categories[i % len(categories)]],
            tags=[categories[i % len(categories)], f"tag-{i}"],
            source_format=SkillFormat.GENERIC,
        )
        for i in range(n)
    ]


# ---------------------------------------------------------------------------
# build_hint_set
# ---------------------------------------------------------------------------
class TestBuildHintSet:
    def test_basic_ranking(self):
        candidates = [
            [_make_match("alpha", 0.9), _make_match("beta", 0.7)],
            [_make_match("gamma", 0.8), _make_match("alpha", 0.6)],
        ]
        hints = build_hint_set(candidates, hint_count=3)
        assert hints == ["alpha", "gamma", "beta"]

    def test_deduplication(self):
        candidates = [
            [_make_match("skill-a", 0.9), _make_match("skill-b", 0.5)],
            [_make_match("skill-a", 0.8), _make_match("skill-c", 0.6)],
        ]
        hints = build_hint_set(candidates, hint_count=10)
        assert len(hints) == 3
        assert hints[0] == "skill-a"  # best score 0.9

    def test_hint_count_limit(self):
        candidates = [
            [_make_match(f"s{i}", 1.0 - i * 0.1) for i in range(10)]
        ]
        hints = build_hint_set(candidates, hint_count=3)
        assert len(hints) == 3
        assert hints == ["s0", "s1", "s2"]

    def test_empty_candidates(self):
        hints = build_hint_set([], hint_count=5)
        assert hints == []

    def test_empty_inner_candidates(self):
        hints = build_hint_set([[], []], hint_count=5)
        assert hints == []

    def test_best_score_kept_across_steps(self):
        candidates = [
            [_make_match("x", 0.3)],
            [_make_match("x", 0.9)],
        ]
        hints = build_hint_set(candidates, hint_count=5)
        assert hints == ["x"]


# ---------------------------------------------------------------------------
# decompose_with_hints
# ---------------------------------------------------------------------------
class TestDecomposeWithHints:
    def test_rule_based_ignores_hints(self):
        d = RuleBasedDecomposer()
        result_vanilla = d.decompose("scrape website, and then analyze data")
        result_hints = d.decompose_with_hints(
            "scrape website, and then analyze data",
            ["web-scraper", "data-analyzer"],
        )
        assert len(result_vanilla) == len(result_hints)
        for a, b in zip(result_vanilla, result_hints):
            assert a.description == b.description

    def test_base_decomposer_default_fallback(self):
        class MinimalDecomposer(BaseDecomposer):
            def decompose(self, query: str) -> list[SubTask]:
                return [SubTask(step_index=0, description=query)]

        d = MinimalDecomposer()
        result = d.decompose_with_hints("test query", ["hint1", "hint2"])
        assert len(result) == 1
        assert result[0].description == "test query"


# ---------------------------------------------------------------------------
# SAD prompt template
# ---------------------------------------------------------------------------
class TestSADPromptTemplate:
    def test_template_includes_hints(self):
        rendered = SAD_USER_TEMPLATE.format(
            query="scrape and analyze",
            hint_list="web-scraper, data-analyzer, chart-gen",
        )
        assert "web-scraper, data-analyzer, chart-gen" in rendered
        assert "scrape and analyze" in rendered
        assert "Available skills that may be relevant:" in rendered

    def test_template_with_empty_hints(self):
        rendered = SAD_USER_TEMPLATE.format(query="test", hint_list="")
        assert "Available skills that may be relevant: " in rendered


# ---------------------------------------------------------------------------
# Pipeline SAD integration
# ---------------------------------------------------------------------------
class TestPipelineSAD:
    def test_sad_pipeline_produces_plan(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(20)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(
            decomposer, retriever, sad=True, sad_hint_count=5
        )
        result = pipeline.plan("scrape website, and then analyze data")

        assert isinstance(result, Plan)
        assert len(result.steps) >= 2
        for step in result.steps:
            assert step.selected_skill is not None

    def test_sad_disabled_by_default(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(10)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(decomposer, retriever)
        assert pipeline.sad is False

    def test_sad_with_dag_planner(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(15)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        pipeline = SkillWeaverPipeline(
            decomposer, retriever, use_dag=True, sad=True, sad_hint_count=10,
        )
        result = pipeline.plan("fetch data, then process it, and send notification")

        assert isinstance(result, Plan)
        assert len(result.steps) >= 2

    def test_sad_calls_decompose_with_hints(self):
        """Verify the pipeline calls decompose_with_hints during SAD pass 2."""
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(10)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        # Spy on decompose_with_hints
        original_dwh = decomposer.decompose_with_hints
        call_log = []

        def spy_dwh(query, hints):
            call_log.append({"query": query, "hints": hints})
            return original_dwh(query, hints)

        decomposer.decompose_with_hints = spy_dwh

        pipeline = SkillWeaverPipeline(
            decomposer, retriever, sad=True, sad_hint_count=5,
        )
        pipeline.plan("scrape website, and then analyze data")

        assert len(call_log) == 1
        assert call_log[0]["query"] == "scrape website, and then analyze data"
        assert isinstance(call_log[0]["hints"], list)
        assert len(call_log[0]["hints"]) <= 5

    def test_sad_hint_count_respected(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(30)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=10)
        retriever.build_index(skills)

        call_log = []
        original_dwh = decomposer.decompose_with_hints

        def spy_dwh(query, hints):
            call_log.append(hints)
            return original_dwh(query, hints)

        decomposer.decompose_with_hints = spy_dwh

        pipeline = SkillWeaverPipeline(
            decomposer, retriever, sad=True, sad_hint_count=3,
        )
        pipeline.plan("scrape website, parse data, send email")

        assert len(call_log) == 1
        assert len(call_log[0]) == 3

    def test_no_sad_does_not_call_decompose_with_hints(self):
        from skillweaver.core.pipeline import SkillWeaverPipeline
        from skillweaver.core.retriever import SkillRetriever

        skills = _make_skills(10)
        decomposer = RuleBasedDecomposer()
        retriever = SkillRetriever(top_k=5)
        retriever.build_index(skills)

        call_log = []

        def spy_dwh(query, hints):
            call_log.append(True)
            return decomposer.decompose(query)

        decomposer.decompose_with_hints = spy_dwh

        pipeline = SkillWeaverPipeline(decomposer, retriever, sad=False)
        pipeline.plan("scrape website")

        assert len(call_log) == 0
