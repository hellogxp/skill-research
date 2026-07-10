#!/usr/bin/env python3
"""Experiment 5: Compose Eval on Human-Style Queries.

Addresses reviewer usWc ("Expand human natural query test set") and
wkod ("benchmark may not reflect real use cases as they are generated
using templates and LLMs").

Runs the full compose eval (decompose -> retrieve -> compose -> evaluate)
on the 50 human-style queries in CompSkillBench, reporting the same
metrics as the 300-query benchmark:
  - Edge precision/recall/F1
  - Plan validity
  - Chain compatibility (DAG vs greedy vs random)
  - Skill selection accuracy

Usage:
    cd /mnt/workspace/skill-research
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=skillweaver/src \
        python3 scripts/run_human_compose_eval.py
"""
import json
import logging
import os
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
ENCODER = "sentence-transformers/all-MiniLM-L6-v2"
SAD_HINT_COUNT = 15
TOP_K = 10


def load_data():
    from skillweaver.core.models import Skill

    skills = []
    with open(DATA_DIR / "processed_v3" / "skill_pool.jsonl") as f:
        for line in f:
            if line.strip():
                skills.append(Skill.from_dict(json.loads(line.strip())))

    # Load human queries
    human_path = DATA_DIR / "benchmark_v3" / "human_queries.jsonl"
    queries = []
    with open(human_path) as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line.strip()))

    logger.info(f"Loaded {len(skills)} skills, {len(queries)} human queries")
    return skills, queries


def run_experiment():
    from skillweaver.core.decomposer import LocalDecomposer
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.core.dag_planner import DAGPlanner, detect_dependencies, assign_parallel_groups
    from skillweaver.core.planner import Planner
    from skillweaver.core.pipeline import build_hint_set
    from skillweaver.core.compatibility import CompatibilityScorer

    skills, queries = load_data()
    logger.info(f"Running compose eval on {len(queries)} human-style queries")

    # Build retriever
    retriever = SkillRetriever(encoder_name=ENCODER, use_body=False, top_k=TOP_K)
    retriever.build_index(skills)

    skill_id_to_cat = {s.skill_id: s.categories[0] for s in skills if s.categories}
    skill_by_id = {s.skill_id: s for s in skills}

    # Load model
    decomposer = LocalDecomposer(model_path=MODEL_PATH, temperature=0.1)

    dag_planner = DAGPlanner(alpha=0.7)
    greedy_planner = Planner(alpha=1.0)
    compat_scorer = CompatibilityScorer()

    all_results = {"vanilla": [], "sad": []}
    t0 = time.time()

    for qi, q in enumerate(queries):
        query_text = q["query"]
        gt_subtasks = q.get("subtasks", [])
        gt_num = q.get("num_skills", len(gt_subtasks))
        gt_edges = [(i, i + 1) for i in range(gt_num - 1)]
        gt_skill_ids = [st.get("ground_truth_skill_id", "") for st in gt_subtasks]
        gt_categories = [
            skill_id_to_cat.get(st.get("ground_truth_skill_id", ""),
                                 st.get("required_category", ""))
            for st in gt_subtasks
        ]

        # Vanilla
        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever.search_batch(texts_v)

        # SAD
        hints = build_hint_set(cands_v, SAD_HINT_COUNT)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever.search_batch(texts_s)

        for mode, subtasks, cands in [
            ("vanilla", subtasks_v, cands_v),
            ("sad", subtasks_s, cands_s),
        ]:
            plan_dag = dag_planner.plan(query_text, subtasks, cands)
            plan_greedy = greedy_planner.plan(query_text, subtasks, cands)

            pred_edges = detect_dependencies(subtasks)
            n_pred = len(subtasks)

            # Edge metrics
            edge_eval = {}
            if n_pred == gt_num:
                tp = len(set(pred_edges) & set(gt_edges))
                fp = len(set(pred_edges) - set(gt_edges))
                fn = len(set(gt_edges) - set(pred_edges))
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
                edge_eval = {"precision": prec, "recall": rec, "f1": f1,
                             "exact_match": int(pred_edges == gt_edges)}
            else:
                edge_eval = {"precision": 0, "recall": 0, "f1": 0, "exact_match": 0}

            # Plan validity
            dag_valid = all(s.selected_skill is not None for s in plan_dag.steps)
            greedy_valid = all(s.selected_skill is not None for s in plan_greedy.steps)

            # CatR@1
            catr1_hits = sum(1 for i, gc in enumerate(gt_categories)
                           if i < len(cands) and cands[i] and cands[i][0].skill.categories
                           and gc in cands[i][0].skill.categories)
            catr1 = catr1_hits / len(gt_categories) if gt_categories else 0

            # Chain compatibility
            dag_chain = [s.selected_skill for s in plan_dag.steps if s.selected_skill]
            greedy_chain = [s.selected_skill for s in plan_greedy.steps if s.selected_skill]
            dag_compat = compat_scorer.score_chain(dag_chain) if len(dag_chain) >= 2 else 0.0
            greedy_compat = compat_scorer.score_chain(greedy_chain) if len(greedy_chain) >= 2 else 0.0

            random_compats = []
            if len(dag_chain) >= 2:
                for _ in range(10):
                    rc = []
                    for i in range(len(dag_chain)):
                        if i < len(cands) and cands[i]:
                            rc.append(cands[i][np.random.randint(len(cands[i]))].skill)
                    valid = [s for s in rc if s is not None]
                    if len(valid) >= 2:
                        random_compats.append(compat_scorer.score_chain(valid))
            random_compat = np.mean(random_compats) if random_compats else 0.0

            da = 1 if n_pred == gt_num else 0

            all_results[mode].append({
                "query_id": q.get("query_id", str(qi)),
                "query": query_text[:80],
                "mode": mode,
                "da": da,
                "n_pred": n_pred,
                "gt_num": gt_num,
                "catr1": round(catr1, 4),
                "dag_valid": int(dag_valid),
                "greedy_valid": int(greedy_valid),
                "dag_compat": round(dag_compat, 4),
                "greedy_compat": round(greedy_compat, 4),
                "random_compat": round(random_compat, 4),
                "edge": edge_eval,
            })

        if (qi + 1) % 10 == 0:
            elapsed = time.time() - t0
            logger.info(f"  Progress: {qi+1}/{len(queries)} ({elapsed:.0f}s)")

    elapsed = time.time() - t0
    logger.info(f"Experiment complete in {elapsed:.0f}s")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_DIR / "human_compose_eval.json", "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)

    # Print summary
    print("\n" + "=" * 60)
    print("HUMAN-STYLE QUERY COMPOSE EVAL (n=50)")
    print("=" * 60)
    for mode in ["vanilla", "sad"]:
        rs = all_results[mode]
        n = len(rs)
        da = np.mean([r["da"] for r in rs])
        catr1 = np.mean([r["catr1"] for r in rs])
        dag_valid = np.mean([r["dag_valid"] for r in rs])
        dag_compat = np.mean([r["dag_compat"] for r in rs])
        greedy_compat = np.mean([r["greedy_compat"] for r in rs])
        random_compat = np.mean([r["random_compat"] for r in rs])
        edges = [r["edge"] for r in rs if r["edge"].get("f1") is not None]
        edge_f1 = np.mean([e["f1"] for e in edges]) if edges else 0
        edge_em = np.mean([e["exact_match"] for e in edges]) if edges else 0

        print(f"\n  [{mode.upper()}] n={n}")
        print(f"  DA:                {da:.3f}")
        print(f"  CatR@1:            {catr1:.3f}")
        print(f"  Plan validity:     {dag_valid:.3f}")
        print(f"  Chain compat (DAG):    {dag_compat:.3f}")
        print(f"  Chain compat (greedy): {greedy_compat:.3f}")
        print(f"  Chain compat (random): {random_compat:.3f}")
        print(f"  Edge F1:           {edge_f1:.3f}")
        print(f"  Edge exact match:  {edge_em:.3f}")

    # Comparison with 300-query benchmark
    print("\n  Comparison with 300-query benchmark (SAD):")
    bench_path = OUTPUT_DIR / "compose_eval_detailed.json"
    if bench_path.exists():
        with open(bench_path) as f:
            bench = json.load(f)
        bs = bench["sad"]
        print(f"    300-query: DA={np.mean([r['da'] for r in bs]):.3f} CatR@1={np.mean([r['catr1'] for r in bs]):.3f}")
        hs = all_results["sad"]
        print(f"    50-human:  DA={np.mean([r['da'] for r in hs]):.3f} CatR@1={np.mean([r['catr1'] for r in hs]):.3f}")

    print("=" * 60)


if __name__ == "__main__":
    run_experiment()
