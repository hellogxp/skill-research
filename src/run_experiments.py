"""
Run all experiments for the Compositional Skill Routing paper (v3).

Uses v3 benchmark with proper skill curation and category-level evaluation.

Experiments:
1. Baselines (single-skill, oracle decomposition)
2. Retrieval signal comparison (metadata-only vs body-aware)
3. LLM decomposer comparison (Qwen, Llama, Mistral)
"""

import sys
import json
import logging
import time
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, "/mnt/workspace/skill-routing/src")

from pipeline.pipeline import (
    run_experiment,
    load_skill_pool,
    load_benchmark,
    SkillRetriever,
    CompatibilityScorer,
    DAGPlanner,
    PipelineResult,
    SubTaskPrediction,
    evaluate,
    RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def run_baseline_single_skill(use_body: bool = False):
    """Baseline: No decomposition, retrieve skills directly for the full query."""
    experiment_name = f"baseline_single_skill_{'body' if use_body else 'meta'}"
    logger.info(f"\nBaseline: {experiment_name}")

    skills = load_skill_pool()
    benchmark = load_benchmark()

    retriever = SkillRetriever(use_body=use_body, top_k=10)
    retriever.build_index(skills)
    skill_map = {s.skill_id: s for s in skills}

    results = []
    for qdata in benchmark:
        start = time.time()
        candidates = retriever.retrieve(qdata["query"])

        gt_subtasks = qdata["subtasks"]
        predictions = []

        for step_idx in range(len(gt_subtasks)):
            predictions.append(SubTaskPrediction(
                step_index=step_idx,
                description=qdata["query"],
                candidate_skill_ids=[sid for sid, _ in candidates],
                candidate_scores=[sc for _, sc in candidates],
                selected_skill_id=candidates[0][0] if candidates else "",
                selected_skill_name=skill_map[candidates[0][0]].name if candidates else "",
            ))

        latency = (time.time() - start) * 1000
        results.append(PipelineResult(
            query_id=qdata["query_id"],
            query=qdata["query"],
            decomposed_subtasks=[qdata["query"]] * len(gt_subtasks),
            predictions=predictions,
            predicted_edges=[],
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
            "config": {"use_body": use_body, "method": "single_skill_retrieval"},
            "metrics": metrics,
            "predictions": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False, default=str)

    return metrics


def run_baseline_oracle_decomp(use_body: bool = False):
    """Baseline: Oracle decomposition (use GT subtask descriptions), then retrieve."""
    experiment_name = f"baseline_oracle_decomp_{'body' if use_body else 'meta'}"
    logger.info(f"\nBaseline: {experiment_name}")

    skills = load_skill_pool()
    benchmark = load_benchmark()

    retriever = SkillRetriever(use_body=use_body, top_k=10)
    retriever.build_index(skills)
    compatibility = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compatibility)
    planner.set_skill_map(skills)

    results = []
    for qdata in benchmark:
        start = time.time()
        gt_subtasks = qdata["subtasks"]
        subtask_descs = [st["description"] for st in gt_subtasks]

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
            "config": {"use_body": use_body, "method": "oracle_decomposition"},
            "metrics": metrics,
            "predictions": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False, default=str)

    return metrics


def main():
    all_results = {}

    # ============================================================
    # Phase 0: Build v3 benchmark if not exists
    # ============================================================
    benchmark_path = Path("/mnt/workspace/skill-routing/data/benchmark_v3/compositional_queries.jsonl")
    if not benchmark_path.exists():
        logger.info("Building v3 benchmark...")
        sys.path.insert(0, "/mnt/workspace/skill-routing/src/collection")
        from build_benchmark_v3 import main as build_benchmark
        build_benchmark()
        logger.info("v3 benchmark built!")

    # ============================================================
    # Phase 1: Baselines (no LLM needed, fast)
    # ============================================================
    logger.info("=" * 70)
    logger.info("BASELINES")
    logger.info("=" * 70)

    all_results["single_skill_meta"] = run_baseline_single_skill(use_body=False)
    all_results["single_skill_body"] = run_baseline_single_skill(use_body=True)
    all_results["oracle_decomp_meta"] = run_baseline_oracle_decomp(use_body=False)
    all_results["oracle_decomp_body"] = run_baseline_oracle_decomp(use_body=True)

    # ============================================================
    # Phase 2: Full pipeline (metadata-only vs body-aware)
    # ============================================================
    logger.info("=" * 70)
    logger.info("EXPERIMENT GROUP 1: Retrieval Signal Comparison")
    logger.info("=" * 70)

    all_results["full_metadata"] = run_experiment(
        experiment_name="full_pipeline_metadata_v3",
        use_body=False,
        llm_name="Qwen2.5-7B-Instruct",
        batch_size=32,
    )

    all_results["full_body"] = run_experiment(
        experiment_name="full_pipeline_body_v3",
        use_body=True,
        llm_name="Qwen2.5-7B-Instruct",
        batch_size=32,
    )

    # ============================================================
    # Phase 3: Different LLM decomposers
    # ============================================================
    logger.info("=" * 70)
    logger.info("EXPERIMENT GROUP 2: LLM Decomposer Comparison")
    logger.info("=" * 70)

    for llm in ["Llama-3.1-8B-Instruct", "Mistral-7B-Instruct-v0.3"]:
        safe_name = llm.lower().replace(".", "").replace("-", "_")
        all_results[f"decomposer_{safe_name}"] = run_experiment(
            experiment_name=f"decomposer_{safe_name}",
            use_body=False,
            llm_name=llm,
            batch_size=32,
        )

    # ============================================================
    # Summary
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY OF ALL EXPERIMENTS")
    logger.info("=" * 70)

    header = (
        f"{'Experiment':<35} {'DecompAcc':>9} {'R@1':>7} {'R@5':>7} {'R@10':>7} "
        f"{'CatR@1':>7} {'CatR@5':>7} {'CatR@10':>8} {'Chain_E':>8} {'Latency':>10}"
    )
    logger.info(header)
    logger.info("-" * 115)
    for name, metrics in all_results.items():
        logger.info(
            f"{name:<35} "
            f"{metrics.get('decomposition_accuracy', 0):>8.4f} "
            f"{metrics.get('skill_recall_at_1', 0):>6.4f} "
            f"{metrics.get('skill_recall_at_5', 0):>6.4f} "
            f"{metrics.get('skill_recall_at_10', 0):>6.4f} "
            f"{metrics.get('cat_recall_at_1', 0):>6.4f} "
            f"{metrics.get('cat_recall_at_5', 0):>6.4f} "
            f"{metrics.get('cat_recall_at_10', 0):>7.4f} "
            f"{metrics.get('chain_exact_match', 0):>7.4f} "
            f"{metrics.get('avg_latency_ms', 0):>8.1f}ms"
        )

    # Save summary
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "experiment_summary.json", "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info(f"\nSummary saved to {RESULTS_DIR / 'experiment_summary.json'}")


if __name__ == "__main__":
    main()
