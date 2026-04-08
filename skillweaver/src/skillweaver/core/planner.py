"""Compatibility-aware DAG planner.

Selects the best skill per step considering both retrieval score
and inter-skill compatibility.  Adapted from the paper's DAGPlanner.

The planner now delegates compatibility scoring to the dedicated
CompatibilityScorer, which considers I/O type matching, category overlap,
tag similarity, and keyword heuristics.
"""

from __future__ import annotations

import logging

from skillweaver.core.compatibility import CompatibilityScorer
from skillweaver.core.models import Plan, PlanStep, Skill, SkillMatch, SubTask

logger = logging.getLogger(__name__)


class Planner:
    """Plans skill execution by selecting the best skill chain."""

    def __init__(
        self,
        alpha: float = 0.7,
        scorer: CompatibilityScorer | None = None,
    ):
        """
        Args:
            alpha: Weight for retrieval score vs compatibility.
                   1.0 = pure retrieval, 0.0 = pure compatibility.
            scorer: Compatibility scorer instance.  Uses default if None.
        """
        self.alpha = alpha
        self.scorer = scorer or CompatibilityScorer()

    def plan(
        self,
        query: str,
        subtasks: list[SubTask],
        candidates_per_step: list[list[SkillMatch]],
    ) -> Plan:
        """Create an execution plan from decomposed subtasks and candidates."""
        steps: list[PlanStep] = []
        prev_skill: Skill | None = None

        for i, subtask in enumerate(subtasks):
            candidates = candidates_per_step[i] if i < len(candidates_per_step) else []

            best_score = -1.0
            best_match: SkillMatch | None = None

            for match in candidates:
                total = match.score
                if prev_skill is not None:
                    compat = self.scorer.score(prev_skill, match.skill)
                    match.compatibility_score = compat
                    total = self.alpha * match.score + (1 - self.alpha) * compat

                if total > best_score:
                    best_score = total
                    best_match = match

            step = PlanStep(
                step_index=i,
                subtask=subtask.description,
                selected_skill=best_match.skill if best_match else None,
                candidates=candidates,
                confidence=best_score if best_score > 0 else 0.0,
            )
            steps.append(step)
            if best_match:
                prev_skill = best_match.skill

        # Sequential edges (parallel grouping will be added in Phase 3)
        edges = [(i, i + 1) for i in range(len(steps) - 1)]

        return Plan(query=query, steps=steps, edges=edges)
