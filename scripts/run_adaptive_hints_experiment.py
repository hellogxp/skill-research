#!/usr/bin/env python3
"""Adaptive Hint Selection Experiment for SkillWeaver.

Purpose: Address hint dilution problem in hard queries (4-5 skills) where 
standard SAD with fixed H=15 hints suffers from category starvation.

Experimental Conditions:
1. Vanilla: No hints (baseline)
2. Standard SAD: Fixed H=15 hints (current approach)
3. Category-Stratified: Sample hints proportionally from each detected category
4. Complexity-Adaptive H: Dynamic H based on predicted query complexity
   - Easy (2 skills): H=10
   - Medium (3 skills): H=15
   - Hard (4-5 skills): H=25
5. Combined: Complexity-Adaptive H + Category-Stratified

Hypothesis: Adaptive strategies will significantly improve performance on hard queries
by ensuring better category coverage and reducing hint dilution.

Usage:
    python run_adaptive_hints_experiment.py

Output:
    results_v3/adaptive_hints_experiment.json
"""

import json
import logging
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

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
OUTPUT_PATH = RESULTS_DIR / "adaptive_hints_experiment.json"

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


def extract_skill_categories(skills: list[Skill]) -> dict[str, set[str]]:
    """Build mapping from skill_id to categories."""
    skill_categories = {}
    for skill in skills:
        skill_categories[skill.skill_id] = set(skill.categories)
    return skill_categories


def predict_query_complexity(query_text: str, decomposer: LocalDecomposer) -> int:
    """Predict the number of skills needed for a query.
    
    Uses vanilla decomposition to estimate complexity.
    Returns estimated number of subtasks (skills).
    """
    subtasks = decomposer.decompose(query_text)
    return len(subtasks)


def get_category_stratified_hints(
    candidates_per_step: list[list],
    skill_to_categories: dict[str, set[str]],
    total_hint_count: int = 15,
) -> list[str]:
    """Category-Stratified Sampling: sample hints proportionally from each category.
    
    Instead of taking top-H globally, we:
    1. Detect all unique categories in retrieval results
    2. Allocate hints proportionally to each category
    3. Select top skills within each category
    
    This ensures better category coverage for multi-category queries.
    """
    # Collect candidates by category
    category_candidates: dict[str, list] = defaultdict(list)
    
    for candidates in candidates_per_step:
        for match in candidates:
            skill_id = match.skill.skill_id
            if skill_id in skill_to_categories:
                for cat in skill_to_categories[skill_id]:
                    category_candidates[cat].append(match)
    
    if not category_candidates:
        # Fallback to standard hint selection
        return build_hint_set(candidates_per_step, total_hint_count)
    
    # Sort candidates within each category by score
    for cat in category_candidates:
        category_candidates[cat].sort(key=lambda m: m.score, reverse=True)
    
    # Allocate hints proportionally
    num_categories = len(category_candidates)
    base_allocation = total_hint_count // num_categories
    remainder = total_hint_count % num_categories
    
    hints = []
    sorted_cats = sorted(category_candidates.keys())
    
    for i, cat in enumerate(sorted_cats):
        # Allocate base + 1 for first 'remainder' categories
        cat_allocation = base_allocation + (1 if i < remainder else 0)
        cat_matches = category_candidates[cat][:cat_allocation]
        
        # Add unique skill names from this category
        for match in cat_matches:
            skill_name = match.skill.name
            if skill_name not in hints:
                hints.append(skill_name)
    
    # If we have fewer hints than requested, fill from remaining candidates
    if len(hints) < total_hint_count:
        all_candidates = []
        for candidates in candidates_per_step:
            all_candidates.extend(candidates)
        all_candidates.sort(key=lambda m: m.score, reverse=True)
        
        for match in all_candidates:
            skill_name = match.skill.name
            if skill_name not in hints:
                hints.append(skill_name)
            if len(hints) >= total_hint_count:
                break
    
    return hints[:total_hint_count]


def determine_adaptive_h_count(predicted_complexity: int) -> int:
    """Complexity-Adaptive H: determine hint count based on predicted complexity.
    
    Strategy:
    - Easy queries (2 skills): H=10
    - Medium queries (3 skills): H=15
    - Hard queries (4-5 skills): H=25
    """
    if predicted_complexity <= 2:
        return 10
    elif predicted_complexity == 3:
        return 15
    else:  # 4 or more
        return 25


def evaluate_condition(
    queries: list[dict],
    decomposer: LocalDecomposer,
    retriever: SkillRetriever,
    condition_name: str,
    skill_to_categories: dict[str, set[str]],
    standard_hint_count: int = 15,
) -> dict:
    """Evaluate a single experimental condition on all queries.
    
    Args:
        queries: List of query dicts
        decomposer: Decomposer instance
        retriever: Retriever instance
        condition_name: One of "vanilla", "standard_sad", "category_stratified", 
                       "complexity_adaptive", "combined"
        skill_to_categories: Mapping from skill_id to categories
        standard_hint_count: Base hint count for standard SAD
    
    Returns:
        Dict with metrics and predictions
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluating condition: {condition_name}")
    logger.info(f"{'='*60}")
    
    predictions = []
    total_latency = 0.0
    difficulty_metrics = defaultdict(lambda: {
        'count': 0,
        'correct_decompositions': 0,
        'skill_recalls': {1: 0, 5: 0, 10: 0},
        'chain_exact_matches': 0,
        'chain_partial_matches': 0,
        'total_latency': 0.0,
    })
    
    for idx, query_data in enumerate(queries):
        query_id = query_data["query_id"]
        query_text = query_data["query"]
        difficulty = query_data.get("difficulty", "unknown")
        ground_truth_subtasks = query_data.get("subtasks", [])
        gt_num_skills = query_data.get("num_skills", len(ground_truth_subtasks))
        
        start_time = time.time()
        
        # Stage 1: Decompose based on condition
        if condition_name == "vanilla":
            # No hints - vanilla decomposition
            subtasks = decomposer.decompose(query_text)
            
        elif condition_name == "standard_sad":
            # Standard SAD with fixed H=15
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)
            
            hints = build_hint_set(pass1_candidates, standard_hint_count)
            subtasks = decomposer.decompose_with_hints(query_text, hints)
            
        elif condition_name == "category_stratified":
            # Category-Stratified Sampling
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)
            
            hints = get_category_stratified_hints(
                pass1_candidates, skill_to_categories, total_hint_count=standard_hint_count
            )
            subtasks = decomposer.decompose_with_hints(query_text, hints)
            
        elif condition_name == "complexity_adaptive":
            # Complexity-Adaptive H
            predicted_complexity = predict_query_complexity(query_text, decomposer)
            adaptive_h = determine_adaptive_h_count(predicted_complexity)
            
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)
            
            hints = build_hint_set(pass1_candidates, adaptive_h)
            subtasks = decomposer.decompose_with_hints(query_text, hints)
            
        elif condition_name == "combined":
            # Combined: Complexity-Adaptive H + Category-Stratified
            predicted_complexity = predict_query_complexity(query_text, decomposer)
            adaptive_h = determine_adaptive_h_count(predicted_complexity)
            
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)
            
            hints = get_category_stratified_hints(
                pass1_candidates, skill_to_categories, total_hint_count=adaptive_h
            )
            subtasks = decomposer.decompose_with_hints(query_text, hints)
            
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
        is_correct = pred_set == gt_set
        
        # Calculate recall metrics
        recalls_at_k = {1: 0, 5: 0, 10: 0}
        for k in [1, 5, 10]:
            for step_idx, gt_subtask in enumerate(ground_truth_subtasks):
                gt_skill_id = gt_subtask["ground_truth_skill_id"]
                
                if step_idx < len(candidates):
                    top_k_candidates = candidates[step_idx][:k]
                    candidate_ids = [c.skill.skill_id for c in top_k_candidates]
                    
                    if gt_skill_id in candidate_ids:
                        recalls_at_k[k] += 1
        
        # Chain-level metrics
        num_steps = len(ground_truth_subtasks)
        exact_match = False
        partial_match = False
        
        if num_steps > 0:
            # Exact match: all steps match exactly
            exact_match = all(
                i < len(predicted_skill_names)
                and predicted_skill_names[i] == gt_skill_names[i]
                for i in range(num_steps)
            )
            
            # Partial match: at least one step matches
            partial_match = any(
                i < len(predicted_skill_names)
                and predicted_skill_names[i] == gt_skill_names[i]
                for i in range(num_steps)
            )
        
        # Store prediction
        predictions.append({
            "query_id": query_id,
            "query": query_text,
            "difficulty": difficulty,
            "predicted_subtasks": predicted_skill_names,
            "ground_truth_subtasks": gt_skill_names,
            "latency_ms": latency_ms,
            "num_predicted_skills": len(subtasks),
            "num_ground_truth_skills": gt_num_skills,
            "is_correct_decomposition": is_correct,
            "recall_at_1": recalls_at_k[1] / max(1, num_steps),
            "recall_at_5": recalls_at_k[5] / max(1, num_steps),
            "recall_at_10": recalls_at_k[10] / max(1, num_steps),
            "chain_exact_match": exact_match,
            "chain_partial_match": partial_match,
        })
        
        # Accumulate difficulty-specific metrics
        dm = difficulty_metrics[difficulty]
        dm['count'] += 1
        if is_correct:
            dm['correct_decompositions'] += 1
        for k in [1, 5, 10]:
            dm['skill_recalls'][k] += recalls_at_k[k]
        if exact_match:
            dm['chain_exact_matches'] += 1
        if partial_match:
            dm['chain_partial_matches'] += 1
        dm['total_latency'] += latency_ms
        
        if (idx + 1) % 50 == 0:
            logger.info(f"  Processed {idx + 1}/{len(queries)} queries")
    
    # Calculate final metrics (overall and by difficulty)
    n_queries = len(queries)
    avg_latency = total_latency / n_queries if n_queries > 0 else 0
    
    overall_metrics = {
        "decomposition_accuracy": sum(
            dm['correct_decompositions'] for dm in difficulty_metrics.values()
        ) / n_queries if n_queries > 0 else 0,
        "skill_recall_at_1": sum(
            dm['skill_recalls'][1] for dm in difficulty_metrics.values()
        ) / (n_queries * 3) if n_queries > 0 else 0,  # Approximate avg steps
        "skill_recall_at_5": sum(
            dm['skill_recalls'][5] for dm in difficulty_metrics.values()
        ) / (n_queries * 3) if n_queries > 0 else 0,
        "skill_recall_at_10": sum(
            dm['skill_recalls'][10] for dm in difficulty_metrics.values()
        ) / (n_queries * 3) if n_queries > 0 else 0,
        "chain_exact_match": sum(
            dm['chain_exact_matches'] for dm in difficulty_metrics.values()
        ) / n_queries if n_queries > 0 else 0,
        "chain_partial_match": sum(
            dm['chain_partial_matches'] for dm in difficulty_metrics.values()
        ) / n_queries if n_queries > 0 else 0,
        "avg_latency_ms": avg_latency,
    }
    
    # Per-difficulty metrics
    difficulty_results = {}
    for diff in ["easy", "medium", "hard"]:
        if diff in difficulty_metrics:
            dm = difficulty_metrics[diff]
            n = dm['count']
            if n > 0:
                difficulty_results[diff] = {
                    "count": n,
                    "decomposition_accuracy": dm['correct_decompositions'] / n,
                    "skill_recall_at_1": dm['skill_recalls'][1] / (n * 3),
                    "skill_recall_at_5": dm['skill_recalls'][5] / (n * 3),
                    "skill_recall_at_10": dm['skill_recalls'][10] / (n * 3),
                    "chain_exact_match": dm['chain_exact_matches'] / n,
                    "chain_partial_match": dm['chain_partial_matches'] / n,
                    "avg_latency_ms": dm['total_latency'] / n,
                }
    
    logger.info(f"Condition {condition_name} completed:")
    logger.info(f"  Overall Decomposition Accuracy: {overall_metrics['decomposition_accuracy']:.4f}")
    logger.info(f"  Overall Skill Recall@1: {overall_metrics['skill_recall_at_1']:.4f}")
    logger.info(f"  Overall Chain Exact Match: {overall_metrics['chain_exact_match']:.4f}")
    logger.info(f"  Avg Latency: {overall_metrics['avg_latency_ms']:.2f}ms")
    
    if "hard" in difficulty_results:
        hr = difficulty_results["hard"]
        logger.info(f"  HARD Queries Only:")
        logger.info(f"    Decomposition Accuracy: {hr['decomposition_accuracy']:.4f}")
        logger.info(f"    Skill Recall@1: {hr['skill_recall_at_1']:.4f}")
        logger.info(f"    Chain Exact Match: {hr['chain_exact_match']:.4f}")
    
    return {
        "condition": condition_name,
        "metrics": overall_metrics,
        "difficulty_breakdown": difficulty_results,
        "predictions": predictions,
    }


def run_experiment(model_path: str, model_name: str):
    """Run the full adaptive hints experiment for a given model.
    
    Args:
        model_path: Path to the local LLM
        model_name: Human-readable model name for output
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"Starting Adaptive Hint Selection Experiment")
    logger.info(f"Model: {model_name}")
    logger.info(f"Model Path: {model_path}")
    logger.info(f"{'#'*80}\n")
    
    # Load data
    skills = load_skill_pool()
    queries = load_queries()
    
    # Build skill-to-categories mapping
    skill_to_categories = extract_skill_categories(skills)
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
    
    # Run five conditions
    conditions = [
        "vanilla",
        "standard_sad",
        "category_stratified",
        "complexity_adaptive",
        "combined",
    ]
    
    results = {
        "experiment": "adaptive_hint_selection",
        "model": model_name,
        "model_path": model_path,
        "config": {
            "standard_hint_count": 15,
            "complexity_adaptive_thresholds": {
                "easy_2_skills": 10,
                "medium_3_skills": 15,
                "hard_4_5_skills": 25,
            },
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
            standard_hint_count=15,
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
        diff_breakdown = results["conditions"][condition].get("difficulty_breakdown", {})
        
        logger.info(f"\n{condition.upper().replace('_', ' ')}:")
        logger.info(f"  Overall Decomposition Accuracy: {metrics['decomposition_accuracy']:.4f}")
        logger.info(f"  Overall Skill Recall@1:         {metrics['skill_recall_at_1']:.4f}")
        logger.info(f"  Overall Chain Exact Match:      {metrics['chain_exact_match']:.4f}")
        logger.info(f"  Avg Latency (ms):               {metrics['avg_latency_ms']:.2f}")
        
        if "hard" in diff_breakdown:
            hr = diff_breakdown["hard"]
            logger.info(f"  HARD Queries ({hr['count']} samples):")
            logger.info(f"    Decomposition Accuracy:     {hr['decomposition_accuracy']:.4f}")
            logger.info(f"    Skill Recall@1:             {hr['skill_recall_at_1']:.4f}")
            logger.info(f"    Chain Exact Match:          {hr['chain_exact_match']:.4f}")
    
    return results


if __name__ == "__main__":
    # Test with 7B model first
    logger.info("Running experiment with Qwen2.5-7B-Instruct...")
    results_7b = run_experiment(MODEL_7B, "Qwen2.5-7B-Instruct")
    
    # Then test with 14B model
    logger.info("\n\nRunning experiment with Qwen2.5-14B-Instruct...")
    results_14b = run_experiment(MODEL_14B, "Qwen2.5-14B-Instruct")
    
    logger.info("\n\nAll experiments completed successfully!")
