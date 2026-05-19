#!/usr/bin/env python3
"""Run all core experiments on the real 2209-skill pool.

Experiments:
1. Main results: Vanilla vs SAD (Table 1)
2. Iterative SAD convergence (Table 7)
3. Transfer: Leave-K-Categories-Out + 80/20 Skill Split (Table 8)

All use Qwen2.5-7B-Instruct as the primary model.
"""
import json
import sys
import time
import random
import numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).parent))

from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

# Config - adjust paths to your environment
DATA_DIR = Path("data")
RESULTS_DIR = Path("results")
SKILL_POOL_PATH = DATA_DIR / "skill_pool.jsonl"
QUERIES_PATH = DATA_DIR / "compositional_queries.jsonl"
MODEL_7B = "Qwen/Qwen2.5-7B-Instruct"  # HuggingFace model ID or local path
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

H = 15  # hint set size
RANDOM_SEED = 42
MAX_ROUNDS = 4  # for iterative SAD

RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def load_skills():
    skills = []
    with open(SKILL_POOL_PATH) as f:
        for line in f:
            if line.strip():
                skills.append(Skill.from_dict(json.loads(line.strip())))
    return skills


def load_queries():
    queries = []
    with open(QUERIES_PATH) as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line.strip()))
    return queries


def compute_metrics(subtasks, candidates, query, skills_by_id):
    """Compute DA, CatR@1, CatR@10, Chain_cat for a single query."""
    gt_subtasks = query.get("subtasks", [])
    gt_num = query.get("num_skills", len(gt_subtasks))
    gt_categories = [st.get("required_category", "") for st in gt_subtasks]

    da = 1 if len(subtasks) == gt_num else 0

    # CatR@1: fraction of ground-truth categories matched by top-1 candidate
    cat_hits_1 = 0
    cat_hits_10 = 0
    for i, gc in enumerate(gt_categories):
        if i < len(candidates) and candidates[i]:
            top1 = candidates[i][0].skill
            if gc in top1.categories:
                cat_hits_1 += 1
            # CatR@10: any of top-10 match
            for match in candidates[i][:10]:
                if gc in match.skill.categories:
                    cat_hits_10 += 1
                    break

    cat_r1 = cat_hits_1 / len(gt_categories) if gt_categories else 0
    cat_r10 = cat_hits_10 / len(gt_categories) if gt_categories else 0

    # Chain_cat: all categories correct in order
    chain_cat = 1 if cat_hits_1 == len(gt_categories) and len(subtasks) == gt_num else 0

    return {
        "da": da,
        "cat_r1": cat_r1,
        "cat_r10": cat_r10,
        "chain_cat": chain_cat,
        "n_subtasks": len(subtasks),
        "gt_num": gt_num,
    }


def run_experiment_1_main(decomposer, retriever, queries, skills_by_id):
    """Experiment 1: Main results - Vanilla vs SAD."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 1: Main Results (Vanilla vs SAD)")
    print("=" * 70)

    results = {"vanilla": [], "sad": []}

    for qi, q in enumerate(queries):
        query_text = q["query"]

        # Vanilla
        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever.search_batch(texts_v)
        m_v = compute_metrics(subtasks_v, cands_v, q, skills_by_id)
        results["vanilla"].append(m_v)

        # SAD
        hints = build_hint_set(cands_v, H)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever.search_batch(texts_s)
        m_s = compute_metrics(subtasks_s, cands_s, q, skills_by_id)
        results["sad"].append(m_s)

        if (qi + 1) % 50 == 0:
            print(f"  Progress: {qi+1}/{len(queries)}")

    # Summary
    print("\n  MAIN RESULTS SUMMARY:")
    for mode in ["vanilla", "sad"]:
        da = np.mean([r["da"] for r in results[mode]])
        cr1 = np.mean([r["cat_r1"] for r in results[mode]])
        cr10 = np.mean([r["cat_r10"] for r in results[mode]])
        chain = np.mean([r["chain_cat"] for r in results[mode]])
        avg_n = np.mean([r["n_subtasks"] for r in results[mode]])
        print(f"  {mode.upper():8s}: DA={da:.3f}, CatR@1={cr1:.3f}, CatR@10={cr10:.3f}, "
              f"Chain_cat={chain:.3f}, avg_subtasks={avg_n:.2f}")

    # By difficulty
    print("\n  BY DIFFICULTY:")
    for diff in ["easy", "medium", "hard"]:
        idx = [i for i, q in enumerate(queries) if q["difficulty"] == diff]
        if not idx:
            continue
        for mode in ["vanilla", "sad"]:
            da = np.mean([results[mode][i]["da"] for i in idx])
            cr1 = np.mean([results[mode][i]["cat_r1"] for i in idx])
            print(f"  {diff:8s} {mode:8s}: DA={da:.3f}, CatR@1={cr1:.3f} (n={len(idx)})")

    # Save
    out_path = RESULTS_DIR / "main_results_v4.json"
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to {out_path}")

    return results


def run_experiment_2_convergence(decomposer, retriever, queries, skills_by_id):
    """Experiment 2: Iterative SAD convergence."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 2: Iterative SAD Convergence")
    print("=" * 70)

    round_metrics = {r: [] for r in range(MAX_ROUNDS)}

    for qi, q in enumerate(queries):
        query_text = q["query"]
        hints = []
        prev_hints_set = set()

        for r in range(MAX_ROUNDS):
            if r == 0:
                subtasks = decomposer.decompose(query_text)
            else:
                subtasks = decomposer.decompose_with_hints(query_text, hints)

            texts = [st.description for st in subtasks]
            candidates = retriever.search_batch(texts)
            new_hints = build_hint_set(candidates, H)
            new_set = set(new_hints)

            jaccard = (len(prev_hints_set & new_set) / len(prev_hints_set | new_set)
                       if prev_hints_set | new_set else 0.0)

            m = compute_metrics(subtasks, candidates, q, skills_by_id)
            m["jaccard"] = jaccard
            m["hint_set_size"] = len(new_set)
            round_metrics[r].append(m)

            prev_hints_set = new_set
            hints = new_hints

        if (qi + 1) % 50 == 0:
            print(f"  Progress: {qi+1}/{len(queries)}")

    # Summary
    print("\n  CONVERGENCE RESULTS:")
    for r in range(MAX_ROUNDS):
        da = np.mean([m["da"] for m in round_metrics[r]])
        cr1 = np.mean([m["cat_r1"] for m in round_metrics[r]])
        cr10 = np.mean([m["cat_r10"] for m in round_metrics[r]])
        chain = np.mean([m["chain_cat"] for m in round_metrics[r]])
        j = np.mean([m["jaccard"] for m in round_metrics[r]]) if r > 0 else 0
        label = "Vanilla" if r == 0 else f"SAD-{r}"
        print(f"  Round {r} ({label:8s}): DA={da:.3f}, CatR@1={cr1:.3f}, "
              f"CatR@10={cr10:.3f}, Chain={chain:.3f}, Jaccard={j:.3f}")

    # Save
    out_path = RESULTS_DIR / "convergence_v4.json"
    with open(out_path, "w") as f:
        json.dump({str(k): v for k, v in round_metrics.items()}, f, indent=2)
    print(f"\n  Saved to {out_path}")

    return round_metrics


def run_experiment_3_transfer(decomposer, retriever_class, all_skills, queries, skills_by_id):
    """Experiment 3: Transfer experiments."""
    print("\n" + "=" * 70)
    print("EXPERIMENT 3: Generalization / Transfer")
    print("=" * 70)
    random.seed(RANDOM_SEED)

    # Group skills by category
    cat_to_skills = defaultdict(list)
    for s in all_skills:
        for c in s.categories:
            cat_to_skills[c].append(s)

    all_categories = sorted(cat_to_skills.keys())
    print(f"  Total categories: {len(all_categories)}")

    # === 3A: Leave-2-Categories-Out ===
    print("\n  --- Leave-2-Categories-Out ---")
    held_out_cats = random.sample([c for c in all_categories if len(cat_to_skills[c]) >= 20], 2)
    print(f"  Held-out categories: {held_out_cats}")

    train_skills = [s for s in all_skills if not any(c in held_out_cats for c in s.categories)]
    test_queries = [q for q in queries
                    if any(st.get("required_category", "") in held_out_cats
                           for st in q.get("subtasks", []))]

    print(f"  Train skills: {len(train_skills)}, Test queries: {len(test_queries)}")

    retriever_train = retriever_class(encoder_name=EMBEDDING_MODEL, use_body=False, top_k=10)
    retriever_train.build_index(train_skills)

    transfer_results = {"vanilla": [], "sad": []}
    for qi, q in enumerate(test_queries):
        query_text = q["query"]

        # Vanilla
        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever_train.search_batch(texts_v)
        m_v = compute_metrics(subtasks_v, cands_v, q, skills_by_id)
        transfer_results["vanilla"].append(m_v)

        # SAD
        hints = build_hint_set(cands_v, H)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever_train.search_batch(texts_s)
        m_s = compute_metrics(subtasks_s, cands_s, q, skills_by_id)
        transfer_results["sad"].append(m_s)

    print(f"  Transfer (L2CO) - Vanilla: DA={np.mean([r['da'] for r in transfer_results['vanilla']]):.3f}, "
          f"CatR@1={np.mean([r['cat_r1'] for r in transfer_results['vanilla']]):.3f}")
    print(f"  Transfer (L2CO) - SAD:     DA={np.mean([r['da'] for r in transfer_results['sad']]):.3f}, "
          f"CatR@1={np.mean([r['cat_r1'] for r in transfer_results['sad']]):.3f}")

    # === 3B: 80/20 Skill Split ===
    print("\n  --- 80/20 Skill Split ---")
    all_ids = list(range(len(all_skills)))
    random.shuffle(all_ids)
    split_point = int(0.8 * len(all_ids))
    train_ids = set(all_ids[:split_point])

    train_skills_split = [all_skills[i] for i in train_ids]
    test_skill_ids = set(all_skills[i].skill_id for i in all_ids[split_point:])

    print(f"  Train skills: {len(train_skills_split)}, Test skills: {len(test_skill_ids)}")

    # Queries involving test skills
    test_queries_split = [q for q in queries
                          if any(st.get("ground_truth_skill_id", "") in test_skill_ids
                                 for st in q.get("subtasks", []))]
    print(f"  Test queries (involve held-out skills): {len(test_queries_split)}")

    retriever_split = retriever_class(encoder_name=EMBEDDING_MODEL, use_body=False, top_k=10)
    retriever_split.build_index(train_skills_split)

    split_results = {"vanilla": [], "sad": []}
    for qi, q in enumerate(test_queries_split[:100]):  # cap at 100
        query_text = q["query"]

        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever_split.search_batch(texts_v)
        m_v = compute_metrics(subtasks_v, cands_v, q, skills_by_id)
        split_results["vanilla"].append(m_v)

        hints = build_hint_set(cands_v, H)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever_split.search_batch(texts_s)
        m_s = compute_metrics(subtasks_s, cands_s, q, skills_by_id)
        split_results["sad"].append(m_s)

    print(f"  Split (80/20) - Vanilla: DA={np.mean([r['da'] for r in split_results['vanilla']]):.3f}, "
          f"CatR@1={np.mean([r['cat_r1'] for r in split_results['vanilla']]):.3f}")
    print(f"  Split (80/20) - SAD:     DA={np.mean([r['da'] for r in split_results['sad']]):.3f}, "
          f"CatR@1={np.mean([r['cat_r1'] for r in split_results['sad']]):.3f}")

    # Save
    transfer_output = {
        "leave_2_categories_out": {
            "held_out_categories": held_out_cats,
            "n_train_skills": len(train_skills),
            "n_test_queries": len(test_queries),
            "vanilla": transfer_results["vanilla"],
            "sad": transfer_results["sad"],
        },
        "skill_split_80_20": {
            "n_train_skills": len(train_skills_split),
            "n_test_skills": len(test_skill_ids),
            "n_test_queries": len(test_queries_split),
            "vanilla": split_results["vanilla"],
            "sad": split_results["sad"],
        },
    }
    out_path = RESULTS_DIR / "transfer_v4.json"
    with open(out_path, "w") as f:
        json.dump(transfer_output, f, indent=2)
    print(f"\n  Saved to {out_path}")

    return transfer_output


def main():
    print("=" * 70)
    print("FULL EXPERIMENT SUITE v4 (Real 2209-skill pool)")
    print("=" * 70)

    # Load data
    print("\nLoading skills...")
    all_skills = load_skills()
    print(f"  Loaded {len(all_skills)} skills")

    queries = load_queries()
    print(f"  Loaded {len(queries)} queries")

    skills_by_id = {s.skill_id: s for s in all_skills}

    # Build retriever
    print("\nBuilding retriever index (2209 skills)...")
    t0 = time.time()
    retriever = SkillRetriever(encoder_name=EMBEDDING_MODEL, use_body=False, top_k=10)
    retriever.build_index(all_skills)
    print(f"  Index built in {time.time()-t0:.1f}s")

    # Load decomposer
    print("\nLoading Qwen2.5-7B-Instruct...")
    t0 = time.time()
    decomposer = LocalDecomposer(model_path=MODEL_7B, temperature=0.1)
    print(f"  Model loaded in {time.time()-t0:.1f}s")

    # Run experiments
    exp1 = run_experiment_1_main(decomposer, retriever, queries, skills_by_id)
    exp2 = run_experiment_2_convergence(decomposer, retriever, queries, skills_by_id)
    exp3 = run_experiment_3_transfer(decomposer, SkillRetriever, all_skills, queries, skills_by_id)

    # Final summary
    print("\n" + "=" * 70)
    print("ALL EXPERIMENTS COMPLETE")
    print("=" * 70)
    print(f"Results saved to: {RESULTS_DIR}/")

    # Compact summary
    summary = {
        "config": {
            "model": "Qwen2.5-7B-Instruct",
            "encoder": "all-MiniLM-L6-v2",
            "n_skills": len(all_skills),
            "n_queries": len(queries),
            "n_categories": len(set(c for s in all_skills for c in s.categories)),
            "H": H,
        },
        "main_results": {
            "vanilla": {
                "DA": float(np.mean([r["da"] for r in exp1["vanilla"]])),
                "CatR@1": float(np.mean([r["cat_r1"] for r in exp1["vanilla"]])),
                "CatR@10": float(np.mean([r["cat_r10"] for r in exp1["vanilla"]])),
                "Chain_cat": float(np.mean([r["chain_cat"] for r in exp1["vanilla"]])),
            },
            "sad": {
                "DA": float(np.mean([r["da"] for r in exp1["sad"]])),
                "CatR@1": float(np.mean([r["cat_r1"] for r in exp1["sad"]])),
                "CatR@10": float(np.mean([r["cat_r10"] for r in exp1["sad"]])),
                "Chain_cat": float(np.mean([r["chain_cat"] for r in exp1["sad"]])),
            },
        },
        "convergence": {
            f"round_{r}": {
                "DA": float(np.mean([m["da"] for m in exp2[r]])),
                "CatR@1": float(np.mean([m["cat_r1"] for m in exp2[r]])),
                "Jaccard": float(np.mean([m["jaccard"] for m in exp2[r]])) if r > 0 else 0.0,
            }
            for r in range(MAX_ROUNDS)
        },
    }
    with open(RESULTS_DIR / "summary_v4.json", "w") as f:
        json.dump(summary, f, indent=2)
    print(f"\nSummary saved to {RESULTS_DIR / 'summary_v4.json'}")


if __name__ == "__main__":
    main()
