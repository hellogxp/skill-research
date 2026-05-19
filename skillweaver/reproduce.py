#!/usr/bin/env python3
"""Reproduce key results from the paper.

Usage:
    pip install -e ".[local]"
    python reproduce.py --experiment main      # Table 1 (main results)
    python reproduce.py --experiment sad       # Table 5 (cross-model SAD)
    python reproduce.py --experiment converge  # Table 7 (iterative convergence)
    python reproduce.py --experiment transfer  # Table 8 (generalization)

Requirements:
    - Qwen2.5-7B-Instruct (or specify --model path)
    - sentence-transformers/all-MiniLM-L6-v2 (auto-downloaded)
    - data/processed_v3/skill_pool.jsonl
    - data/benchmark_v3/compositional_queries.jsonl
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np


def get_args():
    parser = argparse.ArgumentParser(description="Reproduce paper results")
    parser.add_argument("--experiment", choices=["main", "sad", "converge", "transfer", "all"],
                        default="main", help="Which experiment to run")
    parser.add_argument("--model", type=str, default=None,
                        help="Path to LLM model (default: auto-detect Qwen2.5-7B)")
    parser.add_argument("--encoder", type=str,
                        default="sentence-transformers/all-MiniLM-L6-v2",
                        help="Embedding model name/path")
    parser.add_argument("--data-dir", type=str, default="./data",
                        help="Path to data directory")
    parser.add_argument("--output-dir", type=str, default="./results",
                        help="Path to output directory")
    parser.add_argument("--n-queries", type=int, default=None,
                        help="Number of queries to evaluate (default: all)")
    return parser.parse_args()


def find_model():
    """Auto-detect model path."""
    candidates = [
        Path("/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"),
        Path.home() / "models" / "Qwen2.5-7B-Instruct",
        Path("./models/Qwen2.5-7B-Instruct"),
    ]
    for p in candidates:
        if p.exists():
            return str(p)
    return None


def load_data(data_dir):
    from skillweaver.core.models import Skill

    skill_path = Path(data_dir) / "processed_v3" / "skill_pool.jsonl"
    query_path = Path(data_dir) / "benchmark_v3" / "compositional_queries.jsonl"

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

    return skills, queries


def run_main(args):
    """Reproduce Table 1: Main results (vanilla vs SAD)."""
    from skillweaver.core.decomposer import LocalDecomposer
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.core.pipeline import build_hint_set

    print("=" * 60)
    print("Reproducing Table 1: Main Results (Vanilla vs SAD)")
    print("=" * 60)

    skills, queries = load_data(args.data_dir)
    if args.n_queries:
        queries = queries[:args.n_queries]

    model_path = args.model or find_model()
    if not model_path:
        print("ERROR: No model found. Specify --model path.")
        sys.exit(1)

    print(f"  Skills: {len(skills)}, Queries: {len(queries)}")
    print(f"  Model: {model_path}")
    print(f"  Encoder: {args.encoder}")

    retriever = SkillRetriever(encoder_name=args.encoder, use_body=False, top_k=10)
    retriever.build_index(skills)
    decomposer = LocalDecomposer(model_path=model_path, temperature=0.1)

    skill_id_to_cat = {s.skill_id: s.categories[0] for s in skills if s.categories}

    results = {"vanilla": [], "sad": []}

    for qi, q in enumerate(queries):
        query_text = q["query"]
        gt_subtasks = q.get("subtasks", [])
        gt_num = q.get("num_skills", len(gt_subtasks))
        gt_categories = [skill_id_to_cat.get(st.get("ground_truth_skill_id", ""),
                         st.get("required_category", "")) for st in gt_subtasks]

        # Vanilla
        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever.search_batch(texts_v)
        da_v = 1 if len(subtasks_v) == gt_num else 0
        cat_hits_v = sum(1 for i, gc in enumerate(gt_categories)
                        if i < len(cands_v) and cands_v[i]
                        and cands_v[i][0].skill.categories
                        and gc in cands_v[i][0].skill.categories)
        cat_r1_v = cat_hits_v / len(gt_categories) if gt_categories else 0

        # SAD
        hints = build_hint_set(cands_v, 15)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever.search_batch(texts_s)
        da_s = 1 if len(subtasks_s) == gt_num else 0
        cat_hits_s = sum(1 for i, gc in enumerate(gt_categories)
                        if i < len(cands_s) and cands_s[i]
                        and cands_s[i][0].skill.categories
                        and gc in cands_s[i][0].skill.categories)
        cat_r1_s = cat_hits_s / len(gt_categories) if gt_categories else 0

        results["vanilla"].append({"da": da_v, "cat_r1": cat_r1_v})
        results["sad"].append({"da": da_s, "cat_r1": cat_r1_s})

        if (qi + 1) % 50 == 0:
            print(f"  Progress: {qi+1}/{len(queries)}")

    # Summary
    print("\n" + "=" * 60)
    print("RESULTS")
    print("=" * 60)
    for mode in ["vanilla", "sad"]:
        avg_da = np.mean([r["da"] for r in results[mode]])
        avg_cr1 = np.mean([r["cat_r1"] for r in results[mode]])
        print(f"  {mode.upper():8s}: DA={avg_da:.3f}, CatR@1={avg_cr1:.3f}")

    # Save
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / "main_results.json", "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Saved to {out_dir / 'main_results.json'}")


def run_converge(args):
    """Reproduce Table 7: Iterative SAD convergence."""
    from skillweaver.core.decomposer import LocalDecomposer
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.core.pipeline import build_hint_set

    print("=" * 60)
    print("Reproducing Table 7: Iterative SAD Convergence")
    print("=" * 60)

    skills, queries = load_data(args.data_dir)
    if args.n_queries:
        queries = queries[:args.n_queries]

    model_path = args.model or find_model()
    if not model_path:
        print("ERROR: No model found. Specify --model path.")
        sys.exit(1)

    retriever = SkillRetriever(encoder_name=args.encoder, use_body=False, top_k=10)
    retriever.build_index(skills)
    decomposer = LocalDecomposer(model_path=model_path, temperature=0.1)

    max_rounds = 4
    round_metrics = {r: [] for r in range(max_rounds)}

    for qi, q in enumerate(queries):
        query_text = q["query"]
        hints = []
        prev_hints_set = set()

        for r in range(max_rounds):
            if r == 0:
                subtasks = decomposer.decompose(query_text)
            else:
                subtasks = decomposer.decompose_with_hints(query_text, hints)

            texts = [st.description for st in subtasks]
            candidates = retriever.search_batch(texts)
            new_hints = build_hint_set(candidates, 15)
            new_set = set(new_hints)

            jaccard = (len(prev_hints_set & new_set) / len(prev_hints_set | new_set)
                       if prev_hints_set else 0.0)

            da = 1 if len(subtasks) == q.get("num_skills", 0) else 0
            round_metrics[r].append({"da": da, "jaccard": jaccard})

            prev_hints_set = new_set
            hints = new_hints

        if (qi + 1) % 50 == 0:
            print(f"  Progress: {qi+1}/{len(queries)}")

    print("\n" + "=" * 60)
    print("CONVERGENCE RESULTS")
    print("=" * 60)
    for r in range(max_rounds):
        avg_da = np.mean([m["da"] for m in round_metrics[r]])
        avg_j = np.mean([m["jaccard"] for m in round_metrics[r]]) if r > 0 else 0
        label = "Vanilla" if r == 0 else f"SAD-{r}"
        print(f"  Round {r} ({label:8s}): DA={avg_da:.3f}, Jaccard={avg_j:.3f}")


def main():
    args = get_args()

    if args.experiment == "main":
        run_main(args)
    elif args.experiment == "converge":
        run_converge(args)
    elif args.experiment == "all":
        run_main(args)
        run_converge(args)
    else:
        print(f"Experiment '{args.experiment}' not yet implemented in this script.")
        print("See scripts/ directory for full experiment code.")


if __name__ == "__main__":
    main()
