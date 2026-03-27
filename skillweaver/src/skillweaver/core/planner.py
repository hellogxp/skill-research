"""Compatibility-aware DAG planner.

Selects the best skill per step considering both retrieval score
and inter-skill compatibility. Adapted from the paper's DAGPlanner.
"""

from __future__ import annotations

import logging

import numpy as np

from skillweaver.core.models import Plan, PlanStep, Skill, SkillMatch, SubTask

logger = logging.getLogger(__name__)


class Planner:
    """Plans skill execution by selecting the best skill chain."""

    def __init__(self, alpha: float = 0.7):
        """
        Args:
            alpha: Weight for retrieval score vs compatibility.
                   1.0 = pure retrieval, 0.0 = pure compatibility.
        """
        self.alpha = alpha

    def _compatibility(self, skill_a: Skill, skill_b: Skill) -> float:
        """Score compatibility between two consecutive skills."""
        score = 0.5  # base

        # Category overlap bonus
        if skill_a.categories and skill_b.categories:
            overlap = len(set(skill_a.categories) & set(skill_b.categories))
            score += 0.1 * min(overlap, 2)

        # I/O pattern heuristic
        a_text = f"{skill_a.name} {skill_a.description}".lower()
        b_text = f"{skill_b.name} {skill_b.description}".lower()
        output_kw = ["generate", "create", "produce", "output", "export", "write", "build"]
        input_kw = ["read", "parse", "process", "analyze", "import", "consume", "load"]
        if any(k in a_text for k in output_kw) and any(k in b_text for k in input_kw):
            score += 0.15

        return min(score, 1.0)

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
                    compat = self._compatibility(prev_skill, match.skill)
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

        # Sequential edges
        edges = [(i, i + 1) for i in range(len(steps) - 1)]

        return Plan(query=query, steps=steps, edges=edges)
