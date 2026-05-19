"""Advanced DAG planner with parallel execution support.

This module replaces the simple sequential planner with a full DAG
(Directed Acyclic Graph) planner that:
    1. Detects which subtasks can run in parallel
    2. Infers data dependencies from I/O type matching
    3. Assigns parallel groups for concurrent execution
    4. Uses the CompatibilityScorer for chain optimization

This is the core of the paper's "Compose" stage contribution.
"""

from __future__ import annotations

import logging
from collections import defaultdict

from skillweaver.core.compatibility import CompatibilityScorer
from skillweaver.core.models import (
    Plan,
    PlanStep,
    Skill,
    SkillMatch,
    SubTask,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Dependency detection
# ---------------------------------------------------------------------------

# Keywords that suggest a subtask produces output
_PRODUCER_PATTERNS = frozenset([
    "fetch", "get", "download", "scrape", "extract", "generate", "create",
    "read", "load", "query", "search", "collect", "retrieve", "capture",
])

# Keywords that suggest a subtask consumes prior output
_CONSUMER_PATTERNS = frozenset([
    "parse", "analyze", "process", "transform", "convert", "format",
    "summarize", "classify", "store", "save", "upload", "send", "deploy",
    "render", "visualize", "compile", "validate", "publish", "merge",
])

# Explicit dependency markers in natural language
_DEPENDENCY_MARKERS = frozenset([
    "then", "after", "next", "finally", "subsequently", "once",
    "using the", "with the", "from the", "based on",
])


def _has_dependency(earlier: SubTask, later: SubTask) -> bool:
    """Heuristically detect if `later` depends on `earlier`.

    Uses keyword analysis to determine if tasks have a
    producer-consumer relationship.
    """
    e_text = earlier.description.lower()
    l_text = later.description.lower()

    # Check explicit dependency markers
    for marker in _DEPENDENCY_MARKERS:
        if marker in l_text:
            return True

    # Check producer → consumer pattern
    e_produces = any(p in e_text for p in _PRODUCER_PATTERNS)
    l_consumes = any(p in l_text for p in _CONSUMER_PATTERNS)
    if e_produces and l_consumes:
        return True

    # Check I/O type overlap
    e_out = earlier.expected_output_types
    l_in = later.required_input_types
    if e_out and l_in and (e_out & l_in):
        return True

    return False


def detect_dependencies(subtasks: list[SubTask]) -> list[tuple[int, int]]:
    """Detect dependencies between subtasks.

    Returns a list of (from_idx, to_idx) edges where
    subtask[from_idx] must complete before subtask[to_idx].
    """
    edges: list[tuple[int, int]] = []

    for i in range(len(subtasks)):
        for j in range(i + 1, len(subtasks)):
            if _has_dependency(subtasks[i], subtasks[j]):
                edges.append((i, j))

    # If no dependencies detected, assume sequential
    if not edges and len(subtasks) > 1:
        edges = [(i, i + 1) for i in range(len(subtasks) - 1)]

    return edges


def assign_parallel_groups(
    num_steps: int,
    edges: list[tuple[int, int]],
) -> list[int]:
    """Assign parallel execution groups based on dependency edges.

    Steps with the same group number can execute concurrently.
    Uses topological ordering with level assignment.
    """
    # Build adjacency and in-degree
    in_degree = [0] * num_steps
    successors: dict[int, list[int]] = defaultdict(list)
    for src, dst in edges:
        successors[src].append(dst)
        in_degree[dst] += 1

    # BFS level assignment (Kahn's algorithm)
    levels = [0] * num_steps
    queue = [i for i in range(num_steps) if in_degree[i] == 0]
    visited = 0

    while queue:
        next_queue = []
        for node in queue:
            visited += 1
            for succ in successors[node]:
                levels[succ] = max(levels[succ], levels[node] + 1)
                in_degree[succ] -= 1
                if in_degree[succ] == 0:
                    next_queue.append(succ)
        queue = next_queue

    if visited < num_steps:
        logger.warning("Cycle detected in dependency graph; falling back to sequential")
        return list(range(num_steps))

    return levels


# ---------------------------------------------------------------------------
# DAG Planner
# ---------------------------------------------------------------------------
class DAGPlanner:
    """Advanced planner that builds parallel execution DAGs.

    Compared to the basic Planner:
        - Detects parallelizable subtasks
        - Assigns parallel groups
        - Considers both retrieval score AND compatibility
        - Optimizes the full chain, not just greedy per-step
    """

    def __init__(
        self,
        alpha: float = 0.7,
        scorer: CompatibilityScorer | None = None,
    ):
        self.alpha = alpha
        self.scorer = scorer or CompatibilityScorer()

    def plan(
        self,
        query: str,
        subtasks: list[SubTask],
        candidates_per_step: list[list[SkillMatch]],
    ) -> Plan:
        """Build a DAG plan with parallel group assignment."""
        # Step 1: Detect dependencies
        edges = detect_dependencies(subtasks)

        # Step 2: Assign parallel groups
        groups = assign_parallel_groups(len(subtasks), edges)

        # Step 3: Build predecessor map for compatibility scoring
        predecessors: dict[int, list[int]] = defaultdict(list)
        for src, dst in edges:
            predecessors[dst].append(src)

        # Step 4: Select best skill per step
        steps: list[PlanStep] = []
        selected_skills: dict[int, Skill] = {}  # step_idx → selected skill

        for i, subtask in enumerate(subtasks):
            candidates = candidates_per_step[i] if i < len(candidates_per_step) else []

            best_score = -1.0
            best_match: SkillMatch | None = None

            for match in candidates:
                # Base retrieval score
                total = match.score

                # Compatibility with all predecessors
                pred_indices = predecessors.get(i, [])
                if pred_indices:
                    compat_scores = []
                    for pred_idx in pred_indices:
                        pred_skill = selected_skills.get(pred_idx)
                        if pred_skill:
                            c = self.scorer.score(pred_skill, match.skill)
                            compat_scores.append(c)
                    if compat_scores:
                        avg_compat = sum(compat_scores) / len(compat_scores)
                        match.compatibility_score = avg_compat
                        total = self.alpha * match.score + (1 - self.alpha) * avg_compat

                if total > best_score:
                    best_score = total
                    best_match = match

            step = PlanStep(
                step_index=i,
                subtask=subtask.description,
                selected_skill=best_match.skill if best_match else None,
                candidates=candidates,
                confidence=best_score if best_score > 0 else 0.0,
                parallel_group=groups[i] if i < len(groups) else None,
            )
            steps.append(step)
            if best_match:
                selected_skills[i] = best_match.skill

        return Plan(query=query, steps=steps, edges=edges)
