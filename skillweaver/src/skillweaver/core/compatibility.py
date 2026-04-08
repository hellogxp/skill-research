"""Compatibility scoring between skills.

Determines how well two skills chain together (output of A → input of B).
Used by the Planner to prefer coherent skill chains over random pairings.

Scoring dimensions:
  1. I/O type overlap   — outputs of A match inputs of B
  2. Category overlap    — shared domain categories
  3. Tag similarity      — shared semantic tags
  4. Keyword heuristic   — output-producing A → input-consuming B patterns
"""

from __future__ import annotations

import logging

from skillweaver.core.models import ParamType, Skill

logger = logging.getLogger(__name__)

# Keyword sets for output-producing vs input-consuming patterns
_OUTPUT_KEYWORDS = frozenset([
    "generate", "create", "produce", "output", "export", "write",
    "build", "render", "convert", "transform", "extract", "compile",
    "translate", "synthesize", "encode", "fetch", "download", "scrape",
])
_INPUT_KEYWORDS = frozenset([
    "read", "parse", "process", "analyze", "import", "consume",
    "load", "ingest", "decode", "validate", "evaluate", "summarize",
    "classify", "index", "upload", "deploy", "send", "publish",
])

# Type compatibility rules: which output types can flow into which input types
_TYPE_COMPAT: dict[ParamType, set[ParamType]] = {
    ParamType.STRING:  {ParamType.STRING, ParamType.ANY},
    ParamType.INTEGER: {ParamType.INTEGER, ParamType.NUMBER, ParamType.STRING, ParamType.ANY},
    ParamType.NUMBER:  {ParamType.NUMBER, ParamType.STRING, ParamType.ANY},
    ParamType.BOOLEAN: {ParamType.BOOLEAN, ParamType.STRING, ParamType.ANY},
    ParamType.ARRAY:   {ParamType.ARRAY, ParamType.ANY},
    ParamType.OBJECT:  {ParamType.OBJECT, ParamType.ANY},
    ParamType.FILE:    {ParamType.FILE, ParamType.STRING, ParamType.ANY},
    ParamType.IMAGE:   {ParamType.IMAGE, ParamType.FILE, ParamType.ANY},
    ParamType.ANY:     {t for t in ParamType},
}


class CompatibilityScorer:
    """Scores how well skill_a's output chains into skill_b's input."""

    def __init__(
        self,
        w_io: float = 0.4,
        w_category: float = 0.2,
        w_tag: float = 0.2,
        w_keyword: float = 0.2,
    ):
        self.w_io = w_io
        self.w_category = w_category
        self.w_tag = w_tag
        self.w_keyword = w_keyword

    def score(self, skill_a: Skill, skill_b: Skill) -> float:
        """Return a compatibility score in [0, 1]."""
        io = self._io_score(skill_a, skill_b)
        cat = self._category_score(skill_a, skill_b)
        tag = self._tag_score(skill_a, skill_b)
        kw = self._keyword_score(skill_a, skill_b)
        return (
            self.w_io * io
            + self.w_category * cat
            + self.w_tag * tag
            + self.w_keyword * kw
        )

    # -- Dimension scorers ------------------------------------------------

    @staticmethod
    def _io_score(a: Skill, b: Skill) -> float:
        """Score based on I/O type compatibility.

        If A has known outputs and B has known inputs, check how many of
        A's output types can satisfy B's input types.
        """
        a_out = a.io_schema.output_types
        b_in = b.io_schema.input_types

        if not a_out or not b_in:
            return 0.5  # unknown — neutral

        matched = 0
        for out_t in a_out:
            compat_set = _TYPE_COMPAT.get(out_t, {ParamType.ANY})
            if compat_set & b_in:
                matched += 1

        return min(matched / max(len(b_in), 1), 1.0)

    @staticmethod
    def _category_score(a: Skill, b: Skill) -> float:
        """Jaccard-like overlap of categories."""
        if not a.categories or not b.categories:
            return 0.5  # neutral
        sa = set(c.lower() for c in a.categories)
        sb = set(c.lower() for c in b.categories)
        union = sa | sb
        if not union:
            return 0.5
        return len(sa & sb) / len(union)

    @staticmethod
    def _tag_score(a: Skill, b: Skill) -> float:
        """Jaccard-like overlap of tags."""
        if not a.tags or not b.tags:
            return 0.5
        sa = set(t.lower() for t in a.tags)
        sb = set(t.lower() for t in b.tags)
        union = sa | sb
        if not union:
            return 0.5
        return len(sa & sb) / len(union)

    @staticmethod
    def _keyword_score(a: Skill, b: Skill) -> float:
        """Heuristic: does A 'produce' and B 'consume'?"""
        a_text = f"{a.name} {a.description}".lower()
        b_text = f"{b.name} {b.description}".lower()

        a_produces = any(k in a_text for k in _OUTPUT_KEYWORDS)
        b_consumes = any(k in b_text for k in _INPUT_KEYWORDS)

        if a_produces and b_consumes:
            return 1.0
        if a_produces or b_consumes:
            return 0.6
        return 0.3  # no strong signal

    # -- Batch -----------------------------------------------------------

    def score_chain(self, skills: list[Skill]) -> float:
        """Average pairwise compatibility of a skill chain."""
        if len(skills) < 2:
            return 1.0
        total = sum(
            self.score(skills[i], skills[i + 1])
            for i in range(len(skills) - 1)
        )
        return total / (len(skills) - 1)
