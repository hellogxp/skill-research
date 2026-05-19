"""Evaluate human-style queries with Vanilla and SAD decomposition.

Runs on server with Qwen2.5-7B-Instruct model.
Outputs: results_v4/human_queries_v2.json
"""

import json
import sys
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "/mnt/workspace/skill-research/skillweaver/src")

from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

MODEL = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
ENCODER = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"
HINT_COUNT = 15
TOP_K = 10

SKILL_POOL = Path("/mnt/workspace/skill-research/data/processed_v3/skill_pool.jsonl")
QUERIES_PATH = Path("/mnt/workspace/skill-research/data/benchmark_v3/human_queries.jsonl")
OUTPUT_DIR = Path("/mnt/workspace/skill-research/results_v4")


def load_skills():
    skills = []
    for line in open(SKILL_POOL):
        skills.append(Skill.from_dict(json.loads(line)))
    print(f"Loaded {len(skills)} skills")
    return skills


def evaluate_routing(candidates, ground_truth_categories):
    """Compute CatR@1 and CatR@10."""
    cat_hits_1 = 0
    cat_hits_10 = 0

    for i, gt_cat in enumerate(ground_truth_categories):
        if i >= len(candidates) or not candidates[i]:
            continue
        # CatR@1
        if gt_cat in candidates[i][0].skill.categories:
            cat_hits_1 += 1
        # CatR@10
        for match in candidates[i][:10]:
            if gt_cat in match.skill.categories:
                cat_hits_10 += 1
                break

    num_gt = len(ground_truth_categories)
    return (
        cat_hits_1 / num_gt if num_gt else 0,
        cat_hits_10 / num_gt if num_gt else 0,
    )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load components
    print("Loading skills...")
    skills = load_skills()

    print("Building retriever index...")
    retriever = SkillRetriever(encoder_name=ENCODER, use_body=False, top_k=TOP_K)
    retriever.build_index(skills)

    print("Loading decomposer (this may take a minute)...")
    decomposer = LocalDecomposer(model_path=MODEL, temperature=0.1)

    # Load queries
    queries = [json.loads(line) for line in open(QUERIES_PATH)]
    print(f"Loaded {len(queries)} queries")

    results = {"vanilla": [], "sad": []}

    for qi, q in enumerate(queries):
        gt_categories = [st["required_category"] for st in q["subtasks"]]
        gt_num = q["num_skills"]

        # === Pass 1: Vanilla ===
        subtasks_vanilla = decomposer.decompose(q["query"])
        texts_vanilla = [st.description for st in subtasks_vanilla]
        candidates_vanilla = retriever.search_batch(texts_vanilla)

        da_vanilla = 1 if len(subtasks_vanilla) == gt_num else 0
        cat_r1_v, cat_r10_v = evaluate_routing(candidates_vanilla, gt_categories)

        # === Pass 2: SAD ===
        hints = build_hint_set(candidates_vanilla, HINT_COUNT)
        subtasks_sad = decomposer.decompose_with_hints(q["query"], hints)
        texts_sad = [st.description for st in subtasks_sad]
        candidates_sad = retriever.search_batch(texts_sad)

        da_sad = 1 if len(subtasks_sad) == gt_num else 0
        cat_r1_s, cat_r10_s = evaluate_routing(candidates_sad, gt_categories)

        results["vanilla"].append({"da": da_vanilla, "cat_r1": cat_r1_v, "cat_r10": cat_r10_v})
        results["sad"].append({"da": da_sad, "cat_r1": cat_r1_s, "cat_r10": cat_r10_s})

        if (qi + 1) % 20 == 0:
            v_da_so_far = np.mean([r["da"] for r in results["vanilla"]])
            s_da_so_far = np.mean([r["da"] for r in results["sad"]])
            print(f"Progress: {qi+1}/{len(queries)} | V_DA={v_da_so_far:.3f} S_DA={s_da_so_far:.3f}")

    # Save full results
    output_path = OUTPUT_DIR / "human_queries_v2.json"
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {output_path}")

    # Print summary
    print("\n=== SUMMARY ===")
    for mode in ["vanilla", "sad"]:
        data = results[mode]
        da = np.mean([r["da"] for r in data])
        cr1 = np.mean([r["cat_r1"] for r in data])
        cr10 = np.mean([r["cat_r10"] for r in data])
        print(f"{mode:>8}: DA={da:.3f}  CatR@1={cr1:.3f}  CatR@10={cr10:.3f}")

    # Per-difficulty breakdown
    print("\n=== PER-DIFFICULTY ===")
    by_diff = defaultdict(lambda: {"vanilla": [], "sad": []})
    for i, q in enumerate(queries):
        by_diff[q["difficulty"]]["vanilla"].append(results["vanilla"][i])
        by_diff[q["difficulty"]]["sad"].append(results["sad"][i])

    breakdown = {}
    for diff in ["easy", "medium", "hard"]:
        if diff not in by_diff:
            continue
        v_data = by_diff[diff]["vanilla"]
        s_data = by_diff[diff]["sad"]
        row = {
            "n": len(v_data),
            "vanilla_da": round(np.mean([r["da"] for r in v_data]), 3),
            "vanilla_cat_r1": round(np.mean([r["cat_r1"] for r in v_data]), 3),
            "vanilla_cat_r10": round(np.mean([r["cat_r10"] for r in v_data]), 3),
            "sad_da": round(np.mean([r["da"] for r in s_data]), 3),
            "sad_cat_r1": round(np.mean([r["cat_r1"] for r in s_data]), 3),
            "sad_cat_r10": round(np.mean([r["cat_r10"] for r in s_data]), 3),
        }
        breakdown[diff] = row
        print(f"  {diff} (n={row['n']}): V_DA={row['vanilla_da']} S_DA={row['sad_da']} "
              f"V_CR1={row['vanilla_cat_r1']} S_CR1={row['sad_cat_r1']} "
              f"V_CR10={row['vanilla_cat_r10']} S_CR10={row['sad_cat_r10']}")

    # Save breakdown separately
    breakdown_path = OUTPUT_DIR / "human_queries_v2_breakdown.json"
    with open(breakdown_path, "w") as f:
        json.dump(breakdown, f, indent=2)
    print(f"\nBreakdown saved to {breakdown_path}")


if __name__ == "__main__":
    main()
