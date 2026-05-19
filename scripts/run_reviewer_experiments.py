#!/usr/bin/env python3
"""Reviewer-requested experiments for EMNLP 2026 submission.

Part 1: Cross-model validation with Qwen2.5-14B-Instruct (50 queries)
Part 2: Expanded paraphrase robustness (150 additional queries, total 200)

Usage:
    python run_reviewer_experiments.py

Output:
    results_v4/cross_model_14b.json
    results_v4/paraphrase_expanded.json
"""

import json
import sys
import time
import random
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "/mnt/workspace/skill-research/skillweaver/src")

from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

# Paths
SKILL_POOL = Path("/mnt/workspace/skill-research/data/processed_v3/skill_pool.jsonl")
QUERIES_PATH = Path("/mnt/workspace/skill-research/data/benchmark_v3/compositional_queries.jsonl")
OUTPUT_DIR = Path("/mnt/workspace/skill-research/results_v4")

# Models
MODEL_7B = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
MODEL_14B = "/mnt/workspace/models/Qwen/Qwen2.5-14B-Instruct"
ENCODER = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"

HINT_COUNT = 15
TOP_K = 10
SEED = 42


def load_skills():
    skills = []
    for line in open(SKILL_POOL):
        skills.append(Skill.from_dict(json.loads(line)))
    print(f"Loaded {len(skills)} skills")
    return skills


def evaluate_routing(candidates, ground_truth_categories):
    cat_hits_1 = 0
    cat_hits_10 = 0
    for i, gt_cat in enumerate(ground_truth_categories):
        if i >= len(candidates) or not candidates[i]:
            continue
        if gt_cat in candidates[i][0].skill.categories:
            cat_hits_1 += 1
        for match in candidates[i][:10]:
            if gt_cat in match.skill.categories:
                cat_hits_10 += 1
                break
    num_gt = len(ground_truth_categories)
    return (
        cat_hits_1 / num_gt if num_gt else 0,
        cat_hits_10 / num_gt if num_gt else 0,
    )


def run_cross_model_14b(queries, skills, retriever):
    """Part 1: Run 14B on 50 queries to validate cross-model generalization."""
    print("\n" + "=" * 60)
    print("PART 1: Cross-Model Validation (Qwen2.5-14B, 50 queries)")
    print("=" * 60)

    random.seed(SEED)
    sample = random.sample(queries, min(50, len(queries)))

    print("Loading 14B decomposer...")
    decomposer_14b = LocalDecomposer(model_path=MODEL_14B, temperature=0.1)

    results = {"vanilla": [], "sad": []}

    for qi, q in enumerate(sample):
        gt_categories = [st["required_category"] for st in q["subtasks"]]
        gt_num = q["num_skills"]

        # Vanilla
        subtasks_v = decomposer_14b.decompose(q["query"])
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever.search_batch(texts_v)
        da_v = 1 if len(subtasks_v) == gt_num else 0
        cr1_v, cr10_v = evaluate_routing(cands_v, gt_categories)

        # SAD
        hints = build_hint_set(cands_v, HINT_COUNT)
        subtasks_s = decomposer_14b.decompose_with_hints(q["query"], hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever.search_batch(texts_s)
        da_s = 1 if len(subtasks_s) == gt_num else 0
        cr1_s, cr10_s = evaluate_routing(cands_s, gt_categories)

        results["vanilla"].append({"da": da_v, "cat_r1": cr1_v, "cat_r10": cr10_v})
        results["sad"].append({"da": da_s, "cat_r1": cr1_s, "cat_r10": cr10_s})

        if (qi + 1) % 10 == 0:
            v_da = np.mean([r["da"] for r in results["vanilla"]])
            s_da = np.mean([r["da"] for r in results["sad"]])
            print(f"  [{qi+1}/50] V_DA={v_da:.3f} S_DA={s_da:.3f}")

    # Summary
    summary = {}
    for mode in ["vanilla", "sad"]:
        data = results[mode]
        summary[mode] = {
            "da": round(np.mean([r["da"] for r in data]), 3),
            "cat_r1": round(np.mean([r["cat_r1"] for r in data]), 3),
            "cat_r10": round(np.mean([r["cat_r10"] for r in data]), 3),
        }

    output = {
        "experiment": "cross_model_14b",
        "model": "Qwen2.5-14B-Instruct",
        "n_queries": len(sample),
        "summary": summary,
        "results": results,
    }

    out_path = OUTPUT_DIR / "cross_model_14b.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nPart 1 saved: {out_path}")
    print(f"  Vanilla: DA={summary['vanilla']['da']} CatR@1={summary['vanilla']['cat_r1']}")
    print(f"  SAD:     DA={summary['sad']['da']} CatR@1={summary['sad']['cat_r1']}")
    print(f"  DA gain: {summary['sad']['da'] - summary['vanilla']['da']:+.3f}")

    # Cleanup 14B model from GPU
    del decomposer_14b
    import torch
    torch.cuda.empty_cache()

    return summary


def run_paraphrase_expanded(queries, skills, retriever):
    """Part 2: Expand paraphrase test from 50 to 200 queries."""
    print("\n" + "=" * 60)
    print("PART 2: Expanded Paraphrase Robustness (150 new, 200 total)")
    print("=" * 60)

    # Load existing 50 paraphrased query IDs to avoid overlap
    existing_path = OUTPUT_DIR / "paraphrase_v4.json"
    existing_ids = set()
    if existing_path.exists():
        existing = json.load(open(existing_path))
        paraphrased = existing.get("paraphrased_queries", [])
        if isinstance(paraphrased, list) and paraphrased:
            if isinstance(paraphrased[0], dict):
                existing_ids = {p.get("query_id", "") for p in paraphrased}
            else:
                existing_ids = set(paraphrased[:50])  # fallback
        print(f"  Existing paraphrased queries: {len(existing_ids)}")

    # Select 150 new queries not in existing set
    random.seed(SEED + 1)
    remaining = [q for q in queries if q.get("query_id", f"cq_{queries.index(q):04d}") not in existing_ids]
    if len(remaining) < 150:
        remaining = queries  # fallback: use all
    sample = random.sample(remaining, min(150, len(remaining)))
    print(f"  Selected {len(sample)} new queries for paraphrase expansion")

    # Load 7B for decomposition + paraphrasing
    print("Loading 7B decomposer...")
    decomposer = LocalDecomposer(model_path=MODEL_7B, temperature=0.1)

    # Generate paraphrases using 7B with high temperature
    results_orig = {"vanilla": [], "sad": []}
    results_para = {"vanilla": [], "sad": []}
    paraphrased_queries = []

    for qi, q in enumerate(sample):
        query_text = q["query"]
        gt_categories = [st["required_category"] for st in q["subtasks"]]
        gt_num = q["num_skills"]

        # Generate paraphrase using the model's _generate method
        para_msgs = [
            {"role": "system", "content": "You are a rephrasing assistant. Output ONLY the rephrased query."},
            {"role": "user", "content": f"Rephrase using completely different words while preserving the same intent and all subtasks:\n\n{query_text}"}
        ]
        old_temp = decomposer.temperature
        decomposer.temperature = 0.7
        para_text = decomposer._generate(para_msgs).strip().split("\n")[0]
        decomposer.temperature = old_temp
        paraphrased_queries.append({"original": query_text, "paraphrased": para_text})

        # Evaluate ORIGINAL
        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever.search_batch(texts_v)
        da_v = 1 if len(subtasks_v) == gt_num else 0
        cr1_v, _ = evaluate_routing(cands_v, gt_categories)

        hints = build_hint_set(cands_v, HINT_COUNT)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever.search_batch(texts_s)
        da_s = 1 if len(subtasks_s) == gt_num else 0
        cr1_s, _ = evaluate_routing(cands_s, gt_categories)

        results_orig["vanilla"].append({"da": da_v, "cat_r1": cr1_v})
        results_orig["sad"].append({"da": da_s, "cat_r1": cr1_s})

        # Evaluate PARAPHRASE
        subtasks_pv = decomposer.decompose(para_text)
        texts_pv = [st.description for st in subtasks_pv]
        cands_pv = retriever.search_batch(texts_pv)
        da_pv = 1 if len(subtasks_pv) == gt_num else 0
        cr1_pv, _ = evaluate_routing(cands_pv, gt_categories)

        hints_p = build_hint_set(cands_pv, HINT_COUNT)
        subtasks_ps = decomposer.decompose_with_hints(para_text, hints_p)
        texts_ps = [st.description for st in subtasks_ps]
        cands_ps = retriever.search_batch(texts_ps)
        da_ps = 1 if len(subtasks_ps) == gt_num else 0
        cr1_ps, _ = evaluate_routing(cands_ps, gt_categories)

        results_para["vanilla"].append({"da": da_pv, "cat_r1": cr1_pv})
        results_para["sad"].append({"da": da_ps, "cat_r1": cr1_ps})

        if (qi + 1) % 25 == 0:
            orig_sad_da = np.mean([r["da"] for r in results_orig["sad"]])
            para_sad_da = np.mean([r["da"] for r in results_para["sad"]])
            agreement = np.mean([
                1 if results_orig["sad"][j]["da"] == results_para["sad"][j]["da"] else 0
                for j in range(len(results_orig["sad"]))
            ])
            print(f"  [{qi+1}/{len(sample)}] Orig_SAD_DA={orig_sad_da:.3f} Para_SAD_DA={para_sad_da:.3f} Agreement={agreement:.3f}")

    # Compute summary
    orig_sad_da = round(np.mean([r["da"] for r in results_orig["sad"]]), 3)
    para_sad_da = round(np.mean([r["da"] for r in results_para["sad"]]), 3)
    da_agreement = round(np.mean([
        1 if results_orig["sad"][j]["da"] == results_para["sad"][j]["da"] else 0
        for j in range(len(results_orig["sad"]))
    ]), 3)
    orig_sad_cr1 = round(np.mean([r["cat_r1"] for r in results_orig["sad"]]), 3)
    para_sad_cr1 = round(np.mean([r["cat_r1"] for r in results_para["sad"]]), 3)

    output = {
        "experiment": "paraphrase_expanded",
        "n_queries": len(sample),
        "total_with_existing": len(sample) + len(existing_ids),
        "summary": {
            "orig_sad_da": orig_sad_da,
            "para_sad_da": para_sad_da,
            "da_drop": round(orig_sad_da - para_sad_da, 3),
            "da_agreement": da_agreement,
            "orig_sad_cr1": orig_sad_cr1,
            "para_sad_cr1": para_sad_cr1,
        },
        "results_original": results_orig,
        "results_paraphrase": results_para,
        "paraphrased_queries": paraphrased_queries[:20],  # Save first 20 examples
    }

    out_path = OUTPUT_DIR / "paraphrase_expanded.json"
    with open(out_path, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nPart 2 saved: {out_path}")
    print(f"  Original SAD DA: {orig_sad_da}")
    print(f"  Paraphr. SAD DA: {para_sad_da} (drop={orig_sad_da - para_sad_da:+.3f})")
    print(f"  DA Agreement: {da_agreement}")
    print(f"  Original SAD CatR@1: {orig_sad_cr1}")
    print(f"  Paraphr. SAD CatR@1: {para_sad_cr1}")

    return output["summary"]


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    random.seed(SEED)

    # Load shared resources
    print("Loading skills...")
    skills = load_skills()

    print("Building retriever index...")
    retriever = SkillRetriever(encoder_name=ENCODER, use_body=False, top_k=TOP_K)
    retriever.build_index(skills)

    queries = [json.loads(line) for line in open(QUERIES_PATH)]
    print(f"Loaded {len(queries)} queries")

    # Part 1: Cross-model 14B
    t0 = time.time()
    summary_14b = run_cross_model_14b(queries, skills, retriever)
    print(f"  Part 1 took {time.time()-t0:.0f}s")

    # Part 2: Expanded paraphrase
    t1 = time.time()
    summary_para = run_paraphrase_expanded(queries, skills, retriever)
    print(f"  Part 2 took {time.time()-t1:.0f}s")

    # Final summary
    print("\n" + "=" * 60)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 60)
    print(f"14B cross-model: SAD DA={summary_14b['sad']['da']}, CatR@1={summary_14b['sad']['cat_r1']}")
    print(f"Paraphrase expanded: DA drop={summary_para['da_drop']}, agreement={summary_para['da_agreement']}")


if __name__ == "__main__":
    main()
