"""
Run ONLY the full pipeline experiments (Phase 2 + 3) for v3.
Baselines are already completed. This uses transformers (not vLLM).
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
    evaluate,
    RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main():
    all_results = {}

    # Load baseline results for final summary
    for baseline in [
        "baseline_single_skill_meta",
        "baseline_single_skill_body",
        "baseline_oracle_decomp_meta",
        "baseline_oracle_decomp_body",
    ]:
        fpath = RESULTS_DIR / f"{baseline}.json"
        if fpath.exists():
            with open(fpath) as f:
                data = json.load(f)
                all_results[baseline] = data["metrics"]
                logger.info(f"Loaded existing baseline: {baseline}")

    # ============================================================
    # Phase 2: Full pipeline (metadata-only vs body-aware)
    # ============================================================
    logger.info("=" * 70)
    logger.info("EXPERIMENT GROUP 1: Retrieval Signal Comparison (Qwen2.5-7B)")
    logger.info("=" * 70)

    all_results["full_metadata"] = run_experiment(
        experiment_name="full_pipeline_metadata_v3",
        use_body=False,
        llm_name="Qwen2.5-7B-Instruct",
        use_vllm=False,
        batch_size=32,
    )

    all_results["full_body"] = run_experiment(
        experiment_name="full_pipeline_body_v3",
        use_body=True,
        llm_name="Qwen2.5-7B-Instruct",
        use_vllm=False,
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
            use_vllm=False,
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
