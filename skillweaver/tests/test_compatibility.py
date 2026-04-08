"""Tests for core/compatibility.py."""

from __future__ import annotations

from skillweaver.core.compatibility import CompatibilityScorer
from skillweaver.core.models import IOSchema, ParamSchema, ParamType, Skill


def _make_skill(
    name: str,
    description: str = "",
    categories: list[str] | None = None,
    tags: list[str] | None = None,
    input_types: list[ParamType] | None = None,
    output_types: list[ParamType] | None = None,
) -> Skill:
    inputs = [ParamSchema(name=f"in_{i}", param_type=t) for i, t in enumerate(input_types or [])]
    outputs = [ParamSchema(name=f"out_{i}", param_type=t) for i, t in enumerate(output_types or [])]
    return Skill(
        skill_id=f"test_{name}",
        name=name,
        description=description,
        categories=categories or [],
        tags=tags or [],
        io_schema=IOSchema(inputs=inputs, outputs=outputs),
    )


class TestCompatibilityScorer:
    def setup_method(self):
        self.scorer = CompatibilityScorer()

    def test_identical_skills(self):
        a = _make_skill("fetch", "Fetch data from API", categories=["data"])
        score = self.scorer.score(a, a)
        assert 0.0 <= score <= 1.0

    def test_producer_consumer_pattern(self):
        """A tool that 'generates' output chaining into one that 'analyzes' input."""
        producer = _make_skill(
            "data-generator",
            "Generate synthetic test data",
            categories=["data"],
            tags=["generate"],
            output_types=[ParamType.OBJECT],
        )
        consumer = _make_skill(
            "data-analyzer",
            "Analyze and summarize data",
            categories=["data"],
            tags=["analyze"],
            input_types=[ParamType.OBJECT],
        )
        score = self.scorer.score(producer, consumer)
        # Should score higher than unrelated pair
        assert score > 0.5

    def test_unrelated_skills_lower_score(self):
        a = _make_skill(
            "image-render",
            "Render 3D images",
            categories=["graphics"],
            tags=["3d", "render"],
        )
        b = _make_skill(
            "sql-query",
            "Execute SQL database queries",
            categories=["database"],
            tags=["sql", "query"],
        )
        score = self.scorer.score(a, b)
        # Should be lower than related pair
        assert score < 0.7

    def test_io_type_match(self):
        """Skills with matching I/O types score higher."""
        a = _make_skill(
            "fetch",
            "Fetch JSON data",
            output_types=[ParamType.STRING],
        )
        b_match = _make_skill(
            "parse",
            "Parse string data",
            input_types=[ParamType.STRING],
        )
        b_mismatch = _make_skill(
            "resize",
            "Resize image",
            input_types=[ParamType.IMAGE],
        )
        score_match = self.scorer._io_score(a, b_match)
        score_mismatch = self.scorer._io_score(a, b_mismatch)
        assert score_match > score_mismatch

    def test_category_overlap(self):
        a = _make_skill("a", categories=["web", "data"])
        b_overlap = _make_skill("b", categories=["data", "ml"])
        b_no_overlap = _make_skill("c", categories=["graphics"])
        assert self.scorer._category_score(a, b_overlap) > self.scorer._category_score(a, b_no_overlap)

    def test_tag_overlap(self):
        a = _make_skill("a", tags=["scraping", "html", "web"])
        b = _make_skill("b", tags=["html", "parsing"])
        score = self.scorer._tag_score(a, b)
        assert score > 0.0

    def test_score_chain(self):
        skills = [
            _make_skill("fetch", "Fetch web page", output_types=[ParamType.STRING]),
            _make_skill("parse", "Parse HTML content", input_types=[ParamType.STRING], output_types=[ParamType.OBJECT]),
            _make_skill("store", "Store parsed data", input_types=[ParamType.OBJECT]),
        ]
        chain_score = self.scorer.score_chain(skills)
        assert 0.0 <= chain_score <= 1.0

    def test_score_chain_single(self):
        s = _make_skill("solo", "A solo skill")
        assert self.scorer.score_chain([s]) == 1.0

    def test_unknown_io_returns_neutral(self):
        """When I/O schema is unknown, score should be neutral (0.5)."""
        a = _make_skill("a")
        b = _make_skill("b")
        assert self.scorer._io_score(a, b) == 0.5
