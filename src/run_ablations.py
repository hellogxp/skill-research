"""
Additional ablation experiments for the paper:
1. Decomposition quality ablation (constrained decomposition)
2. Top-k sensitivity analysis  
3. Difficulty-level breakdown
"""

import sys
import json
import logging
import time
import numpy as np
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, "/mnt/workspace/skill-routing/src")

from pipeline.pipeline import (
    TaskDecomposer,
    SkillRetriever,
    CompatibilityScorer,
    DAGPlanner,
    CompositionalSkillRouter,
    PipelineResult,
    SubTaskPrediction,
    load_skill_pool,
    load_benchmark,
    evaluate,
    RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_constrained_decomp():
    """Ablation: Use LLM decomposition but constrain to GT number of steps.
    This isolates the effect of decomposition count vs description quality."""
    experiment_name = "ablation_constrained_decomp"
    logger.info(f"\nAblation: {experiment_name}")

    skills = load_skill_pool()
    benchmark = load_benchmark()

    # Load the full pipeline predictions (Qwen + meta)
    pred_file = RESULTS_DIR / "full_pipeline_metadata_v3.json"
    with open(pred_file) as f:
        full_preds = json.load(f)["predictions"]
    pred_map = {p["query_id"]: p for p in full_preds}

    retriever = SkillRetriever(use_body=False, top_k=10)
    retriever.build_index(skills)
    compatibility = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compatibility)
    planner.set_skill_map(skills)

    results = []
    for qdata in benchmark:
        start = time.time()
        gt_n = len(qdata["subtasks"])
        pred = pred_map.get(qdata["query_id"])
        
        if pred:
            # Take first gt_n subtask descriptions from LLM decomposition
            all_subtasks = pred["decomposed_subtasks"]
            subtask_descs = all_subtasks[:gt_n]
            # Pad if needed
            while len(subtask_descs) < gt_n:
                subtask_descs.append(qdata["query"])
        else:
            subtask_descs = [qdata["query"]] * gt_n

        candidates_per_step = retriever.retrieve_batch(subtask_descs)
        predictions, edges = planner.plan(subtask_descs, candidates_per_step)

        latency = (time.time() - start) * 1000
        results.append(PipelineResult(
            query_id=qdata["query_id"],
            query=qdata["query"],
            decomposed_subtasks=subtask_descs,
            predictions=predictions,
            predicted_edges=edges,
            latency_ms=latency,
        ))

    metrics = evaluate(results, benchmark, skill_pool=skills)
    logger.info(f"Results for {experiment_name}:")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v:.4f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{experiment_name}.json", "w") as f:
        json.dump({
            "experiment": experiment_name,
            "config": {"method": "constrained_decomposition", "note": "LLM subtasks truncated to GT count"},
            "metrics": metrics,
            "predictions": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False, default=str)

    return metrics


def run_difficulty_breakdown():
    """Break down results by query difficulty (easy/medium/hard)."""
    logger.info("\n=== Difficulty Breakdown ===")

    skills = load_skill_pool()
    benchmark = load_benchmark()

    # Group by difficulty
    difficulty_groups = {}
    for q in benchmark:
        diff = q.get("difficulty", "unknown")
        if diff not in difficulty_groups:
            difficulty_groups[diff] = []
        difficulty_groups[diff].append(q)

    logger.info(f"Difficulty distribution: { {k: len(v) for k, v in difficulty_groups.items()} }")

    # For each experiment, break down metrics by difficulty
    experiments = [
        "baseline_single_skill_meta",
        "baseline_oracle_decomp_meta",
        "full_pipeline_metadata_v3",
        "full_pipeline_body_v3",
        "decomposer_llama_31_8b_instruct",
        "decomposer_mistral_7b_instruct_v03",
    ]

    all_breakdowns = {}
    for exp_name in experiments:
        fpath = RESULTS_DIR / f"{exp_name}.json"
        if not fpath.exists():
            continue
        with open(fpath) as f:
            data = json.load(f)
        pred_map = {p["query_id"]: p for p in data["predictions"]}

        exp_breakdown = {}
        for diff, queries in difficulty_groups.items():
            # Filter predictions for this difficulty
            diff_preds = []
            diff_gts = []
            for q in queries:
                pred = pred_map.get(q["query_id"])
                if pred:
                    diff_preds.append(PipelineResult(
                        query_id=pred["query_id"],
                        query=pred["query"],
                        decomposed_subtasks=pred["decomposed_subtasks"],
                        predictions=[SubTaskPrediction(**p) for p in pred["predictions"]],
                        predicted_edges=pred.get("predicted_edges", []),
                        latency_ms=pred.get("latency_ms", 0),
                    ))
                    diff_gts.append(q)

            if diff_preds:
                metrics = evaluate(diff_preds, diff_gts, skill_pool=skills)
                exp_breakdown[diff] = metrics
                logger.info(f"  {exp_name} [{diff}] (n={len(diff_preds)}): "
                           f"R@1={metrics['skill_recall_at_1']:.4f} "
                           f"CatR@1={metrics['cat_recall_at_1']:.4f} "
                           f"CatR@10={metrics['cat_recall_at_10']:.4f}")
        
        all_breakdowns[exp_name] = exp_breakdown

    with open(RESULTS_DIR / "difficulty_breakdown.json", "w") as f:
        json.dump(all_breakdowns, f, indent=2)
    logger.info(f"Difficulty breakdown saved.")

    return all_breakdowns


def run_topk_analysis():
    """Analyze sensitivity to top-k retrieval parameter."""
    logger.info("\n=== Top-K Sensitivity Analysis ===")

    skills = load_skill_pool()
    benchmark = load_benchmark()
    skill_map = {s.skill_id: s for s in skills}

    # Load oracle predictions to test different k values
    retriever = SkillRetriever(use_body=False, top_k=50)  # Use large k for analysis
    retriever.build_index(skills)

    results_by_k = {}
    for k in [1, 3, 5, 10, 20, 50]:
        results = []
        for qdata in benchmark:
            gt_subtasks = qdata["subtasks"]
            subtask_descs = [st["description"] for st in gt_subtasks]

            candidates_per_step = retriever.retrieve_batch(subtask_descs, top_k=k)

            predictions = []
            for step_idx in range(len(gt_subtasks)):
                cands = candidates_per_step[step_idx] if step_idx < len(candidates_per_step) else []
                predictions.append(SubTaskPrediction(
                    step_index=step_idx,
                    description=subtask_descs[step_idx],
                    candidate_skill_ids=[sid for sid, _ in cands],
                    candidate_scores=[sc for _, sc in cands],
                    selected_skill_id=cands[0][0] if cands else "",
                    selected_skill_name=skill_map[cands[0][0]].name if cands else "",
                ))

            results.append(PipelineResult(
                query_id=qdata["query_id"],
                query=qdata["query"],
                decomposed_subtasks=subtask_descs,
                predictions=predictions,
                predicted_edges=[],
                latency_ms=0,
            ))

        metrics = evaluate(results, benchmark, skill_pool=skills)
        results_by_k[k] = metrics
        logger.info(f"  k={k}: R@1={metrics['skill_recall_at_1']:.4f} "
                    f"CatR@1={metrics['cat_recall_at_1']:.4f} "
                    f"R@k={metrics.get(f'skill_recall_at_{min(k,10)}', metrics.get('skill_recall_at_10', 0)):.4f}")

    with open(RESULTS_DIR / "topk_analysis.json", "w") as f:
        json.dump({str(k): v for k, v in results_by_k.items()}, f, indent=2)
    logger.info(f"Top-K analysis saved.")

    return results_by_k


def main():
    logger.info("=" * 70)
    logger.info("ABLATION EXPERIMENTS")
    logger.info("=" * 70)

    # 1. Constrained decomposition
    constrained_metrics = run_constrained_decomp()

    # 2. Difficulty breakdown
    difficulty_results = run_difficulty_breakdown()

    # 3. Top-K analysis
    topk_results = run_topk_analysis()

    logger.info("\n" + "=" * 70)
    logger.info("ALL ABLATIONS COMPLETE")
    logger.info("=" * 70)


if __name__ == "__main__":
    main()
