"""Complete Decompose-Retrieve-Compose pipeline.

This is the main orchestration module that ties together the decomposer,
retriever, and planner into a single compositional skill routing pipeline.
Supports both the basic sequential Planner and the advanced DAGPlanner.
Implements SAD (Skill-Aware Decomposition) two-pass feedback loop.
"""

from __future__ import annotations

import logging
import time

from skillweaver.core.decomposer import BaseDecomposer
from skillweaver.core.models import Plan, SkillMatch
from skillweaver.core.planner import Planner
from skillweaver.core.retriever import SkillRetriever

logger = logging.getLogger(__name__)

# Default number of skill-name hints for SAD Pass 2
DEFAULT_SAD_HINT_COUNT = 15


def build_hint_set(
    candidates_per_step: list[list[SkillMatch]],
    hint_count: int = DEFAULT_SAD_HINT_COUNT,
) -> list[str]:
    """Build the hint set H from Pass-1 retrieval results.

    Collects unique skill names from the union of all candidate lists,
    ordered by their best retrieval score, and returns the top-H names.
    """
    # Track best score per skill name for ranking
    best_score: dict[str, float] = {}
    for candidates in candidates_per_step:
        for match in candidates:
            name = match.skill.name
            if name not in best_score or match.score > best_score[name]:
                best_score[name] = match.score

    # Sort by score descending, take top-H
    ranked = sorted(best_score.items(), key=lambda x: x[1], reverse=True)
    return [name for name, _ in ranked[:hint_count]]


class SkillWeaverPipeline:
    """The complete SkillWeaver pipeline: Decompose -> Retrieve -> Compose.

    When ``sad=True``, the pipeline implements the two-pass Skill-Aware
    Decomposition feedback loop described in Algorithm 1 of the paper:
        Pass 1 (vanilla)  -> Retrieve -> Build hints
        Pass 2 (SAD)      -> Retrieve -> Compose
    """

    def __init__(
        self,
        decomposer: BaseDecomposer,
        retriever: SkillRetriever,
        planner: Planner | None = None,
        use_dag: bool = False,
        sad: bool = False,
        sad_hint_count: int = DEFAULT_SAD_HINT_COUNT,
    ):
        self.decomposer = decomposer
        self.retriever = retriever
        self.use_dag = use_dag
        self.sad = sad
        self.sad_hint_count = sad_hint_count

        if use_dag:
            from skillweaver.core.dag_planner import DAGPlanner
            self.planner = planner or DAGPlanner()
        else:
            self.planner = planner or Planner()

    def plan(self, query: str) -> Plan:
        """Run the full pipeline on a single query.

        Args:
            query: A natural language task description.

        Returns:
            A Plan with decomposed steps, selected skills, and execution DAG.
        """
        start = time.time()

        # Stage 1: Decompose (vanilla)
        subtasks = self.decomposer.decompose(query)
        logger.info(f"Decomposed into {len(subtasks)} sub-tasks")

        if self.sad:
            # --- SAD feedback loop (Algorithm 1) ---
            # Retrieve candidates for Pass-1 sub-tasks
            pass1_texts = [st.description for st in subtasks]
            pass1_candidates = self.retriever.search_batch(pass1_texts)
            logger.info("SAD Pass 1: retrieved candidates for hint construction")

            # Build hint set H
            hints = build_hint_set(pass1_candidates, self.sad_hint_count)
            hint_preview = ", ".join(hints[:5])
            if len(hints) > 5:
                hint_preview += "..."
            logger.info(f"SAD hints ({len(hints)}): {hint_preview}")

            # Pass 2: Re-decompose with skill hints
            subtasks = self.decomposer.decompose_with_hints(query, hints)
            logger.info(f"SAD Pass 2: re-decomposed into {len(subtasks)} sub-tasks")

        # Stage 2: Retrieve candidates per sub-task
        subtask_texts = [st.description for st in subtasks]
        candidates = self.retriever.search_batch(subtask_texts)
        logger.info(f"Retrieved candidates for {len(subtask_texts)} sub-tasks")

        # Stage 3: Plan (select + compose)
        plan = self.planner.plan(query, subtasks, candidates)

        elapsed = (time.time() - start) * 1000
        logger.info(f"Plan complete in {elapsed:.0f}ms (confidence={plan.avg_confidence:.2f})")

        return plan

    def search(self, query: str, top_k: int = 10) -> list:
        """Simple single-query skill search (no decomposition)."""
        return self.retriever.search(query, top_k=top_k)
