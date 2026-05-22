#!/usr/bin/env python3
"""H-sensitivity experiment using same protocol as main_results_v4."""
import json
import sys
import numpy as np
from pathlib import Path

sys.path.insert(0, "/mnt/workspace/skill-research/skillweaver/src")
from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

DATA_DIR = Path("/mnt/workspace/skill-research/data")
RESULTS_DIR = Path("/mnt/workspace/skill-research/results_v4")
SKILL_POOL_PATH = DATA_DIR / "processed_v3" / "skill_pool.jsonl"
QUERIES_PATH = DATA_DIR / "benchmark_v3" / "compositional_queries.jsonl"
MODEL_7B = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
EMBEDDING_MODEL = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"

H_VALUES = [5, 10, 25]  # H=15 already in main_results_v4.json

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
    gt_subtasks = query.get("subtasks", [])
    gt_num = query.get("num_skills", len(gt_subtasks))
    gt_categories = [st.get("required_category", "") for st in gt_subtasks]
    da = 1 if len(subtasks) == gt_num else 0
    cat_hits_1 = 0
    cat_hits_10 = 0
    for i, gc in enumerate(gt_categories):
        if i < len(candidates) and candidates[i]:
            top1 = candidates[i][0].skill
            if gc in top1.categories:
                cat_hits_1 += 1
            for match in candidates[i][:10]:
                if gc in match.skill.categories:
                    cat_hits_10 += 1
                    break
    cat_r1 = cat_hits_1 / len(gt_categories) if gt_categories else 0
    cat_r10 = cat_hits_10 / len(gt_categories) if gt_categories else 0
    chain_cat = 1 if cat_hits_1 == len(gt_categories) and len(subtasks) == gt_num else 0
    return {"da": da, "cat_r1": cat_r1, "cat_r10": cat_r10, "chain_cat": chain_cat}

def main():
    print("Loading skills...")
    skills = load_skills()
    skills_by_id = {s.skill_id: s for s in skills}
    print(f"  Loaded {len(skills)} skills")

    print("Loading queries...")
    queries = load_queries()
    print(f"  Loaded {len(queries)} queries")

    print("Initializing decomposer...")
    decomposer = LocalDecomposer(MODEL_7B)

    print("Building retriever index...")
    retriever = SkillRetriever(encoder_name=EMBEDDING_MODEL, use_body=False, top_k=10)
    retriever.build_index(skills)
    print("  Ready.\n")

    all_results = {}

    for h_val in H_VALUES:
        print("\n" + "=" * 60)
        print(f"Running SAD with H={h_val} on {len(queries)} queries...")
        print("=" * 60)
        results = []
        for qi, q in enumerate(queries):
            query_text = q["query"]
            # Vanilla decomposition first
            subtasks_v = decomposer.decompose(query_text)
            texts_v = [st.description for st in subtasks_v]
            cands_v = retriever.search_batch(texts_v)
            # SAD with current H
            hints = build_hint_set(cands_v, h_val)
            subtasks_s = decomposer.decompose_with_hints(query_text, hints)
            texts_s = [st.description for st in subtasks_s]
            cands_s = retriever.search_batch(texts_s)
            m = compute_metrics(subtasks_s, cands_s, q, skills_by_id)
            results.append(m)
            if (qi + 1) % 50 == 0:
                da_so_far = np.mean([r["da"] for r in results])
                cr1_so_far = np.mean([r["cat_r1"] for r in results])
                print(f"  [{qi+1}/{len(queries)}] DA={da_so_far:.3f}, CatR@1={cr1_so_far:.3f}")

        da = np.mean([r["da"] for r in results])
        cr1 = np.mean([r["cat_r1"] for r in results])
        cr10 = np.mean([r["cat_r10"] for r in results])
        chain = np.mean([r["chain_cat"] for r in results])
        print(f"\n  H={h_val}: DA={da:.3f}, CatR@1={cr1:.3f}, CatR@10={cr10:.3f}, ChainCat={chain:.3f}")
        all_results[f"h{h_val}"] = {"da": da, "cat_r1": cr1, "cat_r10": cr10, "chain_cat": chain, "per_query": results}

    # H=15 from existing main results
    with open(RESULTS_DIR / "main_results_v4.json") as f:
        main = json.load(f)
    sad_results = main["sad"]
    da15 = np.mean([r["da"] for r in sad_results])
    cr1_15 = np.mean([r["cat_r1"] for r in sad_results])
    cr10_15 = np.mean([r["cat_r10"] for r in sad_results])
    chain_15 = np.mean([r["chain_cat"] for r in sad_results])
    all_results["h15"] = {"da": da15, "cat_r1": cr1_15, "cat_r10": cr10_15, "chain_cat": chain_15}

    print("\n" + "=" * 60)
    print("FINAL H-SENSITIVITY SUMMARY")
    print("=" * 60)
    for h in [5, 10, 15, 25]:
        r = all_results[f"h{h}"]
        print(f"  H={h:2d}: DA={r[da]:.3f}, CatR@1={r[cat_r1]:.3f}, CatR@10={r[cat_r10]:.3f}, ChainCat={r[chain_cat]:.3f}")

    # Save
    out = {k: {kk: vv for kk, vv in v.items() if kk != "per_query"} for k, v in all_results.items()}
    out_path = RESULTS_DIR / "h_sensitivity_v4.json"
    with open(out_path, "w") as f:
        json.dump(out, f, indent=2)
    print(f"\nSaved to {out_path}")

if __name__ == "__main__":
    main()
