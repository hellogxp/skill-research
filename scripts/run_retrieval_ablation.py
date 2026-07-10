#!/usr/bin/env python3
"""Experiment 2+3: Retrieval Ablation — Metadata vs Body-Aware + Encoder Baselines.

Addresses reviewer weaknesses:
  - 7t4E: "unclear if the skill retrieval is metadata-only, or body-aware"
  - usWc: "retrieval only uses a lightweight encoder without comprehensive model comparison"

Uses the SAD-decomposed subtask texts saved by run_compose_eval.py (no LLM needed).

Usage:
    cd /mnt/workspace/skill-research
    PYTHONPATH=skillweaver/src python3 scripts/run_retrieval_ablation.py
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

# --- FAISS shim ---
sys.path.insert(0, str(Path(__file__).resolve().parent))
import faiss_shim as _faiss_shim
sys.modules["faiss"] = _faiss_shim

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "results_v4"

# Encoder configs: (name, display_label)
ENCODER_CONFIGS = [
    ("sentence-transformers/all-MiniLM-L6-v2", "MiniLM-L6-v2"),
    ("BAAI/bge-base-en-v1.5", "BGE-base-v1.5"),
    ("intfloat/e5-small-v2", "E5-small-v2"),
]

USE_BODY_CONFIGS = [False, True]

TOP_K = 10


def load_data():
    from skillweaver.core.models import Skill

    skill_path = DATA_DIR / "processed_v3" / "skill_pool.jsonl"
    query_path = DATA_DIR / "benchmark_v3" / "compositional_queries.jsonl"

    skills = []
    with open(skill_path) as f:
        for line in f:
            if line.strip():
                skills.append(Skill.from_dict(json.loads(line.strip())))

    queries = []
    with open(query_path) as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line.strip()))

    # Check body availability
    n_with_body = sum(1 for s in skills if s.body and len(s.body.strip()) > 10)
    logger.info(f"Loaded {len(skills)} skills ({n_with_body} with body text), {len(queries)} queries")
    return skills, queries


def load_sad_subtask_texts():
    """Load SAD-decomposed subtask texts from compose eval output."""
    path = OUTPUT_DIR / "sad_subtask_texts.json"
    if not path.exists():
        logger.error(f"SAD subtask texts not found at {path}. Run run_compose_eval.py first.")
        sys.exit(1)

    with open(path) as f:
        items = json.load(f)

    # Group by query_id
    by_query = {}
    for item in items:
        qid = item["query_id"]
        if qid not in by_query:
            by_query[qid] = []
        by_query[qid].append(item["subtask_text"])

    logger.info(f"Loaded SAD subtask texts for {len(by_query)} queries")
    return by_query


def run_experiment():
    from skillweaver.core.retriever import SkillRetriever

    skills, queries = load_data()
    sad_texts = load_sad_subtask_texts()

    skill_id_to_cat = {}
    for s in skills:
        if s.categories:
            skill_id_to_cat[s.skill_id] = s.categories[0]

    all_results = []

    for encoder_name, encoder_label in ENCODER_CONFIGS:
        for use_body in USE_BODY_CONFIGS:
            config_name = f"{encoder_label} | body={'Y' if use_body else 'N'}"
            logger.info(f"\n{'='*50}\n  Config: {config_name}\n{'='*50}")

            try:
                retriever = SkillRetriever(
                    encoder_name=encoder_name,
                    use_body=use_body,
                    top_k=TOP_K,
                )
                retriever.build_index(skills)
            except Exception as e:
                logger.error(f"Failed to build retriever for {config_name}: {e}")
                all_results.append({
                    "config": config_name,
                    "encoder": encoder_name,
                    "use_body": use_body,
                    "error": str(e),
                })
                continue

            per_query = []
            t0 = time.time()

            for qi, q in enumerate(queries):
                qid = q.get("query_id", str(qi))
                gt_subtasks = q.get("subtasks", [])
                gt_categories = [
                    skill_id_to_cat.get(st.get("ground_truth_skill_id", ""),
                                         st.get("required_category", ""))
                    for st in gt_subtasks
                ]

                subtask_texts = sad_texts.get(qid, [st["description"] for st in gt_subtasks])
                if not subtask_texts:
                    continue

                cands = retriever.search_batch(subtask_texts)

                # CatR@1, @5, @10
                catr1, catr5, catr10 = 0, 0, 0
                for i, gc in enumerate(gt_categories):
                    if i < len(cands) and cands[i]:
                        cats_at_k = []
                        for m in cands[i][:TOP_K]:
                            if m.skill.categories:
                                cats_at_k.append(m.skill.categories)
                            else:
                                cats_at_k.append([])
                        if cats_at_k and gc in cats_at_k[0]:
                            catr1 += 1
                        if any(gc in c for c in cats_at_k[:5]):
                            catr5 += 1
                        if any(gc in c for c in cats_at_k[:10]):
                            catr10 += 1

                n_gt = len(gt_categories) if gt_categories else 1
                per_query.append({
                    "query_id": qid,
                    "catr1": catr1 / n_gt,
                    "catr5": catr5 / n_gt,
                    "catr10": catr10 / n_gt,
                })

            elapsed = time.time() - t0
            avg_catr1 = np.mean([p["catr1"] for p in per_query])
            avg_catr5 = np.mean([p["catr5"] for p in per_query])
            avg_catr10 = np.mean([p["catr10"] for p in per_query])

            logger.info(f"  {config_name}: CatR@1={avg_catr1:.3f}, CatR@5={avg_catr5:.3f}, CatR@10={avg_catr10:.3f} ({elapsed:.0f}s)")

            all_results.append({
                "config": config_name,
                "encoder": encoder_name,
                "encoder_label": encoder_label,
                "use_body": use_body,
                "n_queries": len(per_query),
                "catr1": round(avg_catr1, 4),
                "catr5": round(avg_catr5, 4),
                "catr10": round(avg_catr10, 4),
                "per_query": per_query,
            })

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "retrieval_ablation.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved to {out_path}")

    print_summary(all_results)


def print_summary(results):
    print("\n" + "=" * 70)
    print("RETRIEVAL ABLATION SUMMARY")
    print("=" * 70)
    print(f"{'Config':<35} {'CatR@1':>8} {'CatR@5':>8} {'CatR@10':>8}")
    print("-" * 70)
    for r in results:
        if "error" in r:
            print(f"  {r['config']:<33} {'ERROR':>8}")
        else:
            print(f"  {r['config']:<33} {r['catr1']:>8.3f} {r['catr5']:>8.3f} {r['catr10']:>8.3f}")
    print("=" * 70)

    # Metadata vs body comparison (same encoder)
    print("\n  Metadata vs Body-Aware (per encoder):")
    for enc_label in set(r.get("encoder_label", "") for r in results if "error" not in r):
        meta = [r for r in results if r.get("encoder_label") == enc_label and not r["use_body"]]
        body = [r for r in results if r.get("encoder_label") == enc_label and r["use_body"]]
        if meta and body:
            m, b = meta[0], body[0]
            delta1 = b["catr1"] - m["catr1"]
            print(f"    {enc_label}: Meta={m['catr1']:.3f} vs Body={b['catr1']:.3f} (delta={delta1:+.3f})")

    # Encoder comparison (metadata-only)
    print("\n  Encoder Comparison (metadata-only):")
    for r in results:
        if "error" not in r and not r["use_body"]:
            print(f"    {r['encoder_label']}: CatR@1={r['catr1']:.3f}, CatR@5={r['catr5']:.3f}, CatR@10={r['catr10']:.3f}")


if __name__ == "__main__":
    run_experiment()
