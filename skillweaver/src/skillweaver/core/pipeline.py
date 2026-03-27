"""Complete Decompose-Retrieve-Compose pipeline.

This is the main orchestration module that ties together the decomposer,
retriever, and planner into a single compositional skill routing pipeline.
"""

from __future__ import annotations

import logging
import time

from skillweaver.core.decomposer import BaseDecomposer
from skillweaver.core.models import Plan, Skill
from skillweaver.core.planner import Planner
from skillweaver.core.retriever import SkillRetriever

logger = logging.getLogger(__name__)


class SkillWeaverPipeline:
    """The complete SkillWeaver pipeline: Decompose -> Retrieve -> Compose."""

    def __init__(
        self,
        decomposer: BaseDecomposer,
        retriever: SkillRetriever,
        planner: Planner | None = None,
    ):
        self.decomposer = decomposer
        self.retriever = retriever
        self.planner = planner or Planner()

    def plan(self, query: str) -> Plan:
        """Run the full pipeline on a single query.

        Args:
            query: A natural language task description.

        Returns:
            A Plan with decomposed steps, selected skills, and execution DAG.
        """
        start = time.time()

        # Stage 1: Decompose
        subtasks = self.decomposer.decompose(query)
        logger.info(f"Decomposed into {len(subtasks)} sub-tasks")

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
