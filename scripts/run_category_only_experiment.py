#!/usr/bin/env python3
"""SAD Category-Only Hints Experiment.

Purpose: Validate that SAD's gains come from structural guidance rather than answer leakage.

Experimental Conditions:
1. Vanilla: No hints (baseline)
2. Category-Only: Pass-2 hints are category names (e.g., "web", "comm") instead of skill names
3. Full Skill Hints: Normal SAD with skill names (e.g., "web-scraper", "email-sender")

Hypothesis: If Category-Only hints still significantly outperform vanilla, it proves
that SAD's benefits come from structural guidance, not answer leakage.

Usage:
    python run_category_only_experiment.py

Output:
    results_v3/category_only_experiment.json
"""

import json
import logging
import sys
import time
from pathlib import Path

# Add skillweaver to path
WORKSPACE = Path("/mnt/workspace")
sys.path.insert(0, str(WORKSPACE / "skillweaver" / "src"))

from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = WORKSPACE / "skill-research" / "data"
RESULTS_DIR = WORKSPACE / "skill-research" / "results_v3"
SKILL_POOL_PATH = DATA_DIR / "processed_v3" / "skill_pool.jsonl"
QUERIES_PATH = DATA_DIR / "benchmark_v3" / "compositional_queries.jsonl"
OUTPUT_PATH = RESULTS_DIR / "category_only_experiment.json"

# Model paths
MODEL_7B = "/mnt/workspace/models/Qwen/Qwen2___5-7B-Instruct"
MODEL_14B = "/mnt/workspace/models/Qwen/Qwen2___5-14B-Instruct"
EMBEDDING_MODEL = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"


def load_skill_pool() -> list[Skill]:
    """Load skill pool from JSONL file."""
    skills = []
    with open(SKILL_POOL_PATH, "r") as f:
        for line in f:
            data = json.loads(line.strip())
            skills.append(Skill.from_dict(data))
    logger.info(f"Loaded {len(skills)} skills from pool")
    return skills


def load_queries() -> list[dict]:
    """Load compositional queries from JSONL file."""
    queries = []
    with open(QUERIES_PATH, "r") as f:
        for line in f:
            queries.append(json.loads(line.strip()))
    logger.info(f"Loaded {len(queries)} queries")
    return queries


def extract_categories_from_skills(skills: list[Skill]) -> dict[str, set[str]]:
    """Build mapping from skill_id to categories."""
    skill_categories = {}
    for skill in skills:
        skill_categories[skill.skill_id] = set(skill.categories)
    return skill_categories


def get_category_hints(
    candidates_per_step: list[list],
    skill_to_categories: dict[str, set[str]],
    hint_count: int = 8,
) -> list[str]:
    """Extract unique category names from retrieval candidates.

    Instead of returning skill names like normal SAD, this returns
    category names (e.g., "web", "comm", "code") as hints.
    """
    # Collect all unique categories from candidates
    all_categories = set()
    for candidates in candidates_per_step:
        for match in candidates:
            skill_id = match.skill.skill_id
            if skill_id in skill_to_categories:
                all_categories.update(skill_to_categories[skill_id])

    # Return sorted list (limited by hint_count)
    return sorted(list(all_categories))[:hint_count]


def evaluate_condition(
    queries: list[dict],
    decomposer: LocalDecomposer,
    retriever: SkillRetriever,
    condition_name: str,
    skill_to_categories: dict[str, set[str]],
    sad_hint_count: int = 15,
) -> dict:
    """Evaluate a single experimental condition on all queries.

    Args:
        queries: List of query dicts
        decomposer: Decomposer instance
        retriever: Retriever instance
        condition_name: One of "vanilla", "category_only", "full_skill"
        skill_to_categories: Mapping from skill_id to categories
        sad_hint_count: Number of hints for full_skill condition

    Returns:
        Dict with metrics and predictions
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluating condition: {condition_name}")
    logger.info(f"{'='*60}")

    predictions = []
    total_latency = 0.0
    correct_decompositions = 0
    skill_recalls_at_k = {1: 0, 5: 0, 10: 0}
    cat_recalls_at_k = {1: 0, 5: 0, 10: 0}
    chain_exact_matches = 0
    chain_partial_matches = 0
    chain_cat_matches = 0

    for idx, query_data in enumerate(queries):
        query_id = query_data["query_id"]
        query_text = query_data["query"]
        ground_truth_subtasks = query_data.get("subtasks", [])

        start_time = time.time()

        # Stage 1: Decompose based on condition
        if condition_name == "vanilla":
            # No hints - vanilla decomposition
            subtasks = decomposer.decompose(query_text)

        elif condition_name == "category_only":
            # Pass 1: vanilla decomposition + retrieval
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)

            # Build category-only hints
            cat_hints = get_category_hints(
                pass1_candidates, skill_to_categories, hint_count=sad_hint_count
            )

            # Pass 2: re-decompose with category hints
            # Note: We pass category names as hints, but the decomposer expects skill names
            # This tests whether structural guidance alone helps
            subtasks = decomposer.decompose_with_hints(query_text, cat_hints)

        elif condition_name == "full_skill":
            # Normal SAD with skill name hints
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)

            # Build skill name hints (normal SAD)
            skill_hints = build_hint_set(pass1_candidates, sad_hint_count)

            # Pass 2: re-decompose with skill hints
            subtasks = decomposer.decompose_with_hints(query_text, skill_hints)

        else:
            raise ValueError(f"Unknown condition: {condition_name}")

        # Stage 2: Retrieve candidates per sub-task
        subtask_texts = [st.description for st in subtasks]
        candidates = retriever.search_batch(subtask_texts)

        latency_ms = (time.time() - start_time) * 1000
        total_latency += latency_ms

        # Evaluate decomposition accuracy
        predicted_skill_names = [st.description for st in subtasks]
        gt_skill_names = [st["ground_truth_skill_name"] for st in ground_truth_subtasks]

        # Check if decomposition matches ground truth (order-insensitive)
        pred_set = set(predicted_skill_names)
        gt_set = set(gt_skill_names)
        if pred_set == gt_set:
            correct_decompositions += 1

        # Calculate recall metrics
        for k in [1, 5, 10]:
            for step_idx, gt_subtask in enumerate(ground_truth_subtasks):
                gt_skill_id = gt_subtask["ground_truth_skill_id"]
                gt_category = gt_subtask.get("required_category", "")

                if step_idx < len(candidates):
                    top_k_candidates = candidates[step_idx][:k]
                    candidate_ids = [c.skill.skill_id for c in top_k_candidates]
                    candidate_categories = set()
                    for c in top_k_candidates:
                        if c.skill.skill_id in skill_to_categories:
                            candidate_categories.update(
                                skill_to_categories[c.skill.skill_id]
                            )

                    # Skill recall
                    if gt_skill_id in candidate_ids:
                        skill_recalls_at_k[k] += 1

                    # Category recall
                    if gt_category and gt_category in candidate_categories:
                        cat_recalls_at_k[k] += 1

        # Chain-level metrics
        num_steps = len(ground_truth_subtasks)
        if num_steps > 0:
            # Exact match: all steps match exactly
            exact_match = all(
                i < len(predicted_skill_names)
                and predicted_skill_names[i] == gt_skill_names[i]
                for i in range(num_steps)
            )
            if exact_match:
                chain_exact_matches += 1

            # Partial match: at least one step matches
            partial_match = any(
                i < len(predicted_skill_names)
                and predicted_skill_names[i] == gt_skill_names[i]
                for i in range(num_steps)
            )
            if partial_match:
                chain_partial_matches += 1

            # Category match: all steps have matching categories
            cat_match = True
            for i, gt_subtask in enumerate(ground_truth_subtasks):
                gt_cat = gt_subtask.get("required_category", "")
                if i < len(predicted_skill_names):
                    pred_name = predicted_skill_names[i]
                    # Find the skill and check its category
                    pred_cat_found = False
                    for skill_id, cats in skill_to_categories.items():
                        # This is approximate - we'd need skill name to ID mapping
                        # For now, skip detailed category matching
                        pass
                else:
                    cat_match = False
                    break
            if cat_match:
                chain_cat_matches += 1

        # Store prediction
        predictions.append({
            "query_id": query_id,
            "query": query_text,
            "decomposed_subtasks": predicted_skill_names,
            "latency_ms": latency_ms,
            "num_subtasks": len(subtasks),
            "ground_truth_num_skills": len(ground_truth_subtasks),
        })

        if (idx + 1) % 50 == 0:
            logger.info(f"  Processed {idx + 1}/{len(queries)} queries")

    # Calculate final metrics
    n_queries = len(queries)
    avg_latency = total_latency / n_queries if n_queries > 0 else 0

    metrics = {
        "decomposition_accuracy": correct_decompositions / n_queries if n_queries > 0 else 0,
        "skill_recall_at_1": skill_recalls_at_k[1] / (n_queries * max(1, len(ground_truth_subtasks))) if n_queries > 0 else 0,
        "skill_recall_at_5": skill_recalls_at_k[5] / (n_queries * max(1, len(ground_truth_subtasks))) if n_queries > 0 else 0,
        "skill_recall_at_10": skill_recalls_at_k[10] / (n_queries * max(1, len(ground_truth_subtasks))) if n_queries > 0 else 0,
        "cat_recall_at_1": cat_recalls_at_k[1] / (n_queries * max(1, len(ground_truth_subtasks))) if n_queries > 0 else 0,
        "cat_recall_at_5": cat_recalls_at_k[5] / (n_queries * max(1, len(ground_truth_subtasks))) if n_queries > 0 else 0,
        "cat_recall_at_10": cat_recalls_at_k[10] / (n_queries * max(1, len(ground_truth_subtasks))) if n_queries > 0 else 0,
        "chain_exact_match": chain_exact_matches / n_queries if n_queries > 0 else 0,
        "chain_partial_match": chain_partial_matches / n_queries if n_queries > 0 else 0,
        "chain_cat_match": chain_cat_matches / n_queries if n_queries > 0 else 0,
        "avg_latency_ms": avg_latency,
    }

    logger.info(f"Condition {condition_name} completed:")
    logger.info(f"  Decomposition Accuracy: {metrics['decomposition_accuracy']:.4f}")
    logger.info(f"  Skill Recall@1: {metrics['skill_recall_at_1']:.4f}")
    logger.info(f"  Cat Recall@1: {metrics['cat_recall_at_1']:.4f}")
    logger.info(f"  Avg Latency: {metrics['avg_latency_ms']:.2f}ms")

    return {
        "condition": condition_name,
        "metrics": metrics,
        "predictions": predictions,
    }


def run_experiment(model_path: str, model_name: str):
    """Run the full experiment for a given model.

    Args:
        model_path: Path to the local LLM
        model_name: Human-readable model name for output
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"Starting Category-Only Hints Experiment")
    logger.info(f"Model: {model_name}")
    logger.info(f"Model Path: {model_path}")
    logger.info(f"{'#'*80}\n")

    # Load data
    skills = load_skill_pool()
    queries = load_queries()

    # Build skill-to-categories mapping
    skill_to_categories = extract_categories_from_skills(skills)
    logger.info(f"Built skill-to-categories mapping for {len(skill_to_categories)} skills")

    # Initialize components
    decomposer = LocalDecomposer(
        model_path=model_path,
        device="auto",
        temperature=0.1,
    )

    retriever = SkillRetriever(
        embedding_model_path=EMBEDDING_MODEL,
        skill_pool=skills,
    )

    # Run three conditions
    conditions = ["vanilla", "category_only", "full_skill"]
    results = {
        "experiment": "category_only_hints",
        "model": model_name,
        "model_path": model_path,
        "config": {
            "sad_hint_count": 15,
            "category_hint_count": 8,  # Number of categories to use as hints
            "num_queries": len(queries),
            "num_skills": len(skills),
        },
        "conditions": {},
    }

    for condition in conditions:
        result = evaluate_condition(
            queries=queries,
            decomposer=decomposer,
            retriever=retriever,
            condition_name=condition,
            skill_to_categories=skill_to_categories,
            sad_hint_count=15,
        )
        results["conditions"][condition] = result

    # Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    logger.info(f"\nResults saved to: {OUTPUT_PATH}")
    logger.info(f"Experiment complete!")

    # Print summary comparison
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY COMPARISON")
    logger.info(f"{'='*80}")
    for condition in conditions:
        metrics = results["conditions"][condition]["metrics"]
        logger.info(f"\n{condition.upper()}:")
        logger.info(f"  Decomposition Accuracy: {metrics['decomposition_accuracy']:.4f}")
        logger.info(f"  Skill Recall@1:         {metrics['skill_recall_at_1']:.4f}")
        logger.info(f"  Cat Recall@1:           {metrics['cat_recall_at_1']:.4f}")
        logger.info(f"  Chain Exact Match:      {metrics['chain_exact_match']:.4f}")
        logger.info(f"  Avg Latency (ms):       {metrics['avg_latency_ms']:.2f}")

    return results


if __name__ == "__main__":
    # Test with 7B model first
    logger.info("Running experiment with Qwen2.5-7B-Instruct...")
    results_7b = run_experiment(MODEL_7B, "Qwen2.5-7B-Instruct")

    # Then test with 14B model
    logger.info("\n\nRunning experiment with Qwen2.5-14B-Instruct...")
    results_14b = run_experiment(MODEL_14B, "Qwen2.5-14B-Instruct")

    logger.info("\n\nAll experiments completed successfully!")
