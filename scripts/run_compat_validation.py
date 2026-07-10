#!/usr/bin/env python3
"""Experiment 4: Compatibility Scorer Validation.

Addresses reviewer wkod: "A small set of human-annotated compatibility labels
would already make Eq. 4 much more credible."

Validates the CompatibilityScorer (Eq. 4) by:
  1. Sampling ground-truth compatible pairs (adjacent skills in benchmark chains)
  2. Sampling random pairs (negative examples)
  3. Scoring each pair with the CompatibilityScorer
  4. Using Qwen2.5-7B-Instruct as an LLM judge (binary: compatible / not compatible)
  5. Computing AUC, Spearman correlation, precision/recall

Usage:
    cd /mnt/workspace/skill-research
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=skillweaver/src \
        python3 scripts/run_compat_validation.py
"""
import json
import logging
import os
import random
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faiss_shim as _faiss_shim
sys.modules["faiss"] = _faiss_shim

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "results_v4"
MODEL_PATH = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
N_POSITIVE = 200
N_NEGATIVE = 200
RANDOM_SEED = 42

COMPAT_JUDGE_PROMPT = """You are an expert at evaluating whether two software tools/skills can be chained together in a pipeline.

Skill A (output producer): {skill_a_name}
  Description: {skill_a_desc}
  Categories: {skill_a_cats}

Skill B (input consumer): {skill_b_name}
  Description: {skill_b_desc}
  Categories: {skill_b_cats}

Question: Can the output of Skill A naturally serve as input to Skill B? In other words, would a user typically chain A then B in a workflow?

Answer with ONLY "YES" or "NO" and a brief reason (one sentence).

Answer:"""


def load_data():
    from skillweaver.core.models import Skill

    skills = []
    with open(DATA_DIR / "processed_v3" / "skill_pool.jsonl") as f:
        for line in f:
            if line.strip():
                skills.append(Skill.from_dict(json.loads(line.strip())))

    queries = []
    with open(DATA_DIR / "benchmark_v3" / "compositional_queries.jsonl") as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line.strip()))

    logger.info(f"Loaded {len(skills)} skills, {len(queries)} queries")
    return skills, queries


def sample_pairs(skills, queries):
    """Sample positive (ground-truth chain) and negative (random) pairs."""
    random.seed(RANDOM_SEED)
    skill_by_id = {s.skill_id: s for s in skills}

    # Positive pairs: adjacent skills in ground-truth chains
    positive_pairs = []
    for q in queries:
        subtasks = q.get("subtasks", [])
        for i in range(len(subtasks) - 1):
            a_id = subtasks[i].get("ground_truth_skill_id", "")
            b_id = subtasks[i + 1].get("ground_truth_skill_id", "")
            if a_id in skill_by_id and b_id in skill_by_id:
                positive_pairs.append((skill_by_id[a_id], skill_by_id[b_id]))

    # Deduplicate and sample
    seen = set()
    unique_positive = []
    for a, b in positive_pairs:
        key = (a.skill_id, b.skill_id)
        if key not in seen:
            seen.add(key)
            unique_positive.append((a, b))
    random.shuffle(unique_positive)
    sampled_positive = unique_positive[:N_POSITIVE]
    logger.info(f"Sampled {len(sampled_positive)} positive pairs from {len(unique_positive)} unique ground-truth pairs")

    # Negative pairs: random skills
    negative_pairs = []
    while len(negative_pairs) < N_NEGATIVE:
        a, b = random.sample(skills, 2)
        key = (a.skill_id, b.skill_id)
        if key not in seen:
            seen.add(key)
            negative_pairs.append((a, b))
    logger.info(f"Sampled {len(negative_pairs)} negative (random) pairs")

    return sampled_positive, negative_pairs


def score_pairs(positive_pairs, negative_pairs):
    """Score all pairs with the CompatibilityScorer."""
    from skillweaver.core.compatibility import CompatibilityScorer

    scorer = CompatibilityScorer()
    results = []

    for label, pairs in [("positive", positive_pairs), ("negative", negative_pairs)]:
        for a, b in pairs:
            score = scorer.score(a, b)
            results.append({
                "skill_a": a.name,
                "skill_a_desc": a.description[:100],
                "skill_b": b.name,
                "skill_b_desc": b.description[:100],
                "label": 1 if label == "positive" else 0,
                "compat_score": round(score, 4),
            })

    return results


def llm_judge_pairs(decomposer, all_pairs):
    """Use Qwen2.5-7B-Instruct to judge each pair."""
    from skillweaver.core.models import Skill
    llm_labels = []

    for i, pair in enumerate(all_pairs):
        prompt = COMPAT_JUDGE_PROMPT.format(
            skill_a_name=pair["skill_a"],
            skill_a_desc=pair["skill_a_desc"],
            skill_a_cats=",".join([]),  # not stored in pair
            skill_b_name=pair["skill_b"],
            skill_b_desc=pair["skill_b_desc"],
            skill_b_cats=",".join([]),
        )

        messages = [
            {"role": "system", "content": "You are a helpful assistant that evaluates tool compatibility."},
            {"role": "user", "content": prompt},
        ]
        text = decomposer._generate(messages)
        llm_yes = "yes" in text.lower()[:20]
        llm_labels.append(int(llm_yes))

        if (i + 1) % 50 == 0:
            logger.info(f"  LLM judged {i+1}/{len(all_pairs)} pairs")

    return llm_labels


def compute_metrics(results, llm_labels):
    """Compute AUC, Spearman, precision/recall."""
    from scipy.stats import spearmanr, pearsonr
    from sklearn.metrics import roc_auc_score, precision_recall_curve, average_precision_score

    gt_labels = np.array([r["label"] for r in results])
    compat_scores = np.array([r["compat_score"] for r in results])
    llm_labels = np.array(llm_labels)

    # AUC: compatibility scorer's ability to distinguish positive vs negative
    auc_scorer = roc_auc_score(gt_labels, compat_scores)
    auc_llm = roc_auc_score(gt_labels, llm_labels)

    # Correlation between scorer and LLM
    spearman, sp_p = spearmanr(compat_scores, llm_labels)
    pearson, pe_p = pearsonr(compat_scores, llm_labels)

    # Agreement between scorer and LLM
    scorer_pred = (compat_scores > 0.5).astype(int)
    agreement = np.mean(scorer_pred == llm_labels)

    # Precision/Recall at threshold 0.5
    tp = np.sum((scorer_pred == 1) & (gt_labels == 1))
    fp = np.sum((scorer_pred == 1) & (gt_labels == 0))
    fn = np.sum((scorer_pred == 0) & (gt_labels == 1))
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0

    # Average precision
    ap_scorer = average_precision_score(gt_labels, compat_scores)
    ap_llm = average_precision_score(gt_labels, llm_labels)

    return {
        "n_pairs": len(results),
        "n_positive": int(np.sum(gt_labels)),
        "n_negative": int(np.sum(1 - gt_labels)),
        "auc_scorer": round(auc_scorer, 4),
        "auc_llm": round(auc_llm, 4),
        "spearman_scorer_llm": round(spearman, 4),
        "spearman_p": round(sp_p, 6),
        "pearson_scorer_llm": round(pearson, 4),
        "agreement_scorer_llm": round(agreement, 4),
        "precision_at_0.5": round(prec, 4),
        "recall_at_0.5": round(rec, 4),
        "f1_at_0.5": round(f1, 4),
        "avg_score_positive": round(float(np.mean(compat_scores[gt_labels == 1])), 4),
        "avg_score_negative": round(float(np.mean(compat_scores[gt_labels == 0])), 4),
        "ap_scorer": round(ap_scorer, 4),
        "ap_llm": round(ap_llm, 4),
    }


def main():
    from skillweaver.core.decomposer import LocalDecomposer

    skills, queries = load_data()
    positive, negative = sample_pairs(skills, queries)

    # Score with compatibility scorer
    logger.info("Scoring pairs with CompatibilityScorer...")
    results = score_pairs(positive, negative)

    # LLM judge
    logger.info("Loading Qwen2.5-7B-Instruct for LLM judgment...")
    decomposer = LocalDecomposer(model_path=MODEL_PATH, temperature=0.1)

    logger.info(f"LLM judging {len(results)} pairs...")
    t0 = time.time()
    llm_labels = llm_judge_pairs(decomposer, results)
    elapsed = time.time() - t0
    logger.info(f"LLM judging complete in {elapsed:.0f}s")

    # Compute metrics
    metrics = compute_metrics(results, llm_labels)

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = {
        "metrics": metrics,
        "pairs": [{**r, "llm_label": int(l)} for r, l in zip(results, llm_labels)],
    }
    with open(OUTPUT_DIR / "compat_validation.json", "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    logger.info(f"Saved to {OUTPUT_DIR / 'compat_validation.json'}")

    # Print summary
    print("\n" + "=" * 60)
    print("COMPATIBILITY SCORER VALIDATION (Eq. 4)")
    print("=" * 60)
    print(f"  Pairs: {metrics['n_pairs']} ({metrics['n_positive']} pos + {metrics['n_negative']} neg)")
    print(f"  AUC (scorer):        {metrics['auc_scorer']:.3f}")
    print(f"  AUC (LLM judge):     {metrics['auc_llm']:.3f}")
    print(f"  Spearman (scorer-LLM): {metrics['spearman_scorer_llm']:.3f} (p={metrics['spearman_p']})")
    print(f"  Pearson (scorer-LLM):  {metrics['pearson_scorer_llm']:.3f}")
    print(f"  Agreement (scorer-LLM): {metrics['agreement_scorer_llm']:.3f}")
    print(f"  Avg score (positive):  {metrics['avg_score_positive']:.3f}")
    print(f"  Avg score (negative):  {metrics['avg_score_negative']:.3f}")
    print(f"  P/R/F1 @0.5:  {metrics['precision_at_0.5']:.3f} / {metrics['recall_at_0.5']:.3f} / {metrics['f1_at_0.5']:.3f}")
    print(f"  AP (scorer):  {metrics['ap_scorer']:.3f} | AP (LLM): {metrics['ap_llm']:.3f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
