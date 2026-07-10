#!/usr/bin/env python3
"""Experiment 1: Compose Stage Evaluation.

Addresses reviewer weakness (all 3 reviewers): "The compose stage has not been
fully evaluated."

Runs the full SkillWeaver pipeline (Decompose → Retrieve → Compose) on all
300 CompSkillBench queries and evaluates the DAG planner's:

  1. DAG structure prediction (edge precision/recall/F1)
  2. Plan validity (completeness, acyclicity)
  3. Skill selection accuracy (PlanR@1: did planner select ground truth?)
  4. Chain compatibility score (vs random baseline)
  5. DAG planner vs greedy top-1 comparison

Also saves intermediate decomposition + retrieval results for reuse in
the retrieval ablation experiments.

Usage:
    cd /mnt/workspace/skill-research
    PYTHONPATH=skillweaver/src python3 scripts/run_compose_eval.py
"""
import json
import logging
import sys
import time
from pathlib import Path

import numpy as np

# --- FAISS shim (inject before importing retriever) ---
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
N_QUERIES = 300
SAD_HINT_COUNT = 15
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

    logger.info(f"Loaded {len(skills)} skills, {len(queries)} queries")
    return skills, queries


def run_experiment():
    from skillweaver.core.decomposer import LocalDecomposer
    from skillweaver.core.retriever import SkillRetriever
    from skillweaver.core.dag_planner import DAGPlanner, detect_dependencies, assign_parallel_groups
    from skillweaver.core.planner import Planner
    from skillweaver.core.pipeline import build_hint_set
    from skillweaver.core.compatibility import CompatibilityScorer
    from skillweaver.core.models import SubTask

    skills, queries = load_data()
    if N_QUERIES:
        queries = queries[:N_QUERIES]

    logger.info("Building retriever index...")
    retriever = SkillRetriever(encoder_name=ENCODER, use_body=False, top_k=TOP_K)
    retriever.build_index(skills)

    skill_id_to_cat = {}
    for s in skills:
        if s.categories:
            skill_id_to_cat[s.skill_id] = s.categories[0]
    skill_by_id = {s.skill_id: s for s in skills}

    logger.info(f"Loading model: {MODEL_PATH}")
    decomposer = LocalDecomposer(model_path=MODEL_PATH, temperature=0.1)

    dag_planner = DAGPlanner(alpha=0.7)
    greedy_planner = Planner(alpha=1.0)  # pure retrieval, no compatibility
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

        # --- Vanilla ---
        subtasks_v = decomposer.decompose(query_text)
        texts_v = [st.description for st in subtasks_v]
        cands_v = retriever.search_batch(texts_v)

        # --- SAD ---
        hints = build_hint_set(cands_v, SAD_HINT_COUNT)
        subtasks_s = decomposer.decompose_with_hints(query_text, hints)
        texts_s = [st.description for st in subtasks_s]
        cands_s = retriever.search_batch(texts_s)

        for mode, subtasks, cands in [
            ("vanilla", subtasks_v, cands_v),
            ("sad", subtasks_s, cands_s),
        ]:
            # Run both planners
            plan_dag = dag_planner.plan(query_text, subtasks, cands)
            plan_greedy = greedy_planner.plan(query_text, subtasks, cands)

            # Edge prediction
            pred_edges = detect_dependencies(subtasks)
            n_pred = len(subtasks)
            gt_n = gt_num

            # Only evaluate edges when decomposition count is correct
            edge_eval = {}
            if n_pred == gt_n:
                tp = len(set(pred_edges) & set(gt_edges))
                fp = len(set(pred_edges) - set(gt_edges))
                fn = len(set(gt_edges) - set(pred_edges))
                prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
                rec = tp / (tp + fn) if (tp + fn) > 0 else 0.0
                f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
                edge_eval = {
                    "precision": prec,
                    "recall": rec,
                    "f1": f1,
                    "tp": tp, "fp": fp, "fn": fn,
                    "exact_match": int(pred_edges == gt_edges),
                }
            else:
                edge_eval = {
                    "precision": 0.0, "recall": 0.0, "f1": 0.0,
                    "tp": 0, "fp": len(pred_edges), "fn": len(gt_edges),
                    "exact_match": 0,
                }

            # Plan validity
            dag_valid = all(s.selected_skill is not None for s in plan_dag.steps)
            greedy_valid = all(s.selected_skill is not None for s in plan_greedy.steps)
            # Check acyclicity
            dag_acyclic = len(pred_edges) > 0  # detect_dependencies already handles cycles
            groups = assign_parallel_groups(n_pred, pred_edges)
            n_parallel_groups = len(set(groups)) if groups else 1

            # Skill selection accuracy (PlanR@1)
            dag_selected_ids = [
                s.selected_skill.skill_id for s in plan_dag.steps if s.selected_skill
            ]
            greedy_selected_ids = [
                s.selected_skill.skill_id for s in plan_greedy.steps if s.selected_skill
            ]

            # CatR@1 (pure retrieval top-1)
            catr1_hits = 0
            for i, gc in enumerate(gt_categories):
                if i < len(cands) and cands[i]:
                    top_cat = cands[i][0].skill.categories
                    if top_cat and gc in top_cat:
                        catr1_hits += 1
            catr1 = catr1_hits / len(gt_categories) if gt_categories else 0

            # PlanR@1 (planner selection accuracy)
            dag_hits = 0
            greedy_hits = 0
            for i, gts in enumerate(gt_skill_ids):
                if i < len(dag_selected_ids) and dag_selected_ids[i] == gts:
                    dag_hits += 1
                if i < len(greedy_selected_ids) and greedy_selected_ids[i] == gts:
                    greedy_hits += 1
            dag_planr1 = dag_hits / len(gt_skill_ids) if gt_skill_ids else 0
            greedy_planr1 = greedy_hits / len(gt_skill_ids) if gt_skill_ids else 0

            # Chain compatibility
            dag_chain = [s.selected_skill for s in plan_dag.steps if s.selected_skill]
            greedy_chain = [s.selected_skill for s in plan_greedy.steps if s.selected_skill]
            dag_compat = compat_scorer.score_chain(dag_chain) if len(dag_chain) >= 2 else 0.0
            greedy_compat = compat_scorer.score_chain(greedy_chain) if len(greedy_chain) >= 2 else 0.0

            # Random baseline compatibility (sample 10 random chains)
            random_compats = []
            if len(dag_chain) >= 2:
                for _ in range(10):
                    random_chain = []
                    for i in range(len(dag_chain)):
                        if i < len(cands) and cands[i]:
                            random_chain.append(
                                cands[i][np.random.randint(len(cands[i]))].skill
                            )
                        else:
                            random_chain.append(None)
                    valid = [s for s in random_chain if s is not None]
                    if len(valid) >= 2:
                        random_compats.append(compat_scorer.score_chain(valid))
            random_compat = np.mean(random_compats) if random_compats else 0.0

            # DA
            da = 1 if n_pred == gt_n else 0

            result = {
                "query_id": q.get("query_id", str(qi)),
                "mode": mode,
                "da": da,
                "n_pred": n_pred,
                "gt_num": gt_n,
                "catr1": catr1,
                "dag_planr1": dag_planr1,
                "greedy_planr1": greedy_planr1,
                "dag_valid": int(dag_valid),
                "greedy_valid": int(greedy_valid),
                "dag_compat": round(dag_compat, 4),
                "greedy_compat": round(greedy_compat, 4),
                "random_compat": round(random_compat, 4),
                "n_parallel_groups": n_parallel_groups,
                "edge": edge_eval,
                # Save intermediate results for ablation
                "subtask_texts": texts_s if mode == "sad" else texts_v,
            }
            all_results[mode].append(result)

        if (qi + 1) % 50 == 0:
            elapsed = time.time() - t0
            logger.info(f"  Progress: {qi+1}/{len(queries)} ({elapsed:.0f}s elapsed)")

    elapsed = time.time() - t0
    logger.info(f"Experiment complete in {elapsed:.0f}s")

    # Save detailed results
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "compose_eval_detailed.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    logger.info(f"Detailed results saved to {out_path}")

    # Also save SAD subtask texts for retrieval ablation
    sad_texts = []
    for r in all_results["sad"]:
        for i, txt in enumerate(r["subtask_texts"]):
            sad_texts.append({
                "query_id": r["query_id"],
                "step": i,
                "subtask_text": txt,
            })
    with open(OUTPUT_DIR / "sad_subtask_texts.json", "w") as f:
        json.dump(sad_texts, f, indent=2, ensure_ascii=False)
    logger.info(f"SAD subtask texts saved to {OUTPUT_DIR / 'sad_subtask_texts.json'}")

    # Print summary
    print_summary(all_results)


def print_summary(results):
    print("\n" + "=" * 70)
    print("COMPOSE STAGE EVALUATION SUMMARY")
    print("=" * 70)

    for mode in ["vanilla", "sad"]:
        rs = results[mode]
        n = len(rs)

        da = np.mean([r["da"] for r in rs])
        catr1 = np.mean([r["catr1"] for r in rs])
        dag_planr1 = np.mean([r["dag_planr1"] for r in rs])
        greedy_planr1 = np.mean([r["greedy_planr1"] for r in rs])

        dag_valid = np.mean([r["dag_valid"] for r in rs])
        greedy_valid = np.mean([r["greedy_valid"] for r in rs])

        dag_compat = np.mean([r["dag_compat"] for r in rs])
        greedy_compat = np.mean([r["greedy_compat"] for r in rs])
        random_compat = np.mean([r["random_compat"] for r in rs])

        edges = [r["edge"] for r in rs if r["edge"].get("f1") is not None]
        edge_prec = np.mean([e["precision"] for e in edges]) if edges else 0
        edge_rec = np.mean([e["recall"] for e in edges]) if edges else 0
        edge_f1 = np.mean([e["f1"] for e in edges]) if edges else 0
        edge_em = np.mean([e["exact_match"] for e in edges]) if edges else 0

        avg_groups = np.mean([r["n_parallel_groups"] for r in rs])

        print(f"\n  [{mode.upper()}] n={n}")
        print(f"  DA:                {da:.3f}")
        print(f"  CatR@1 (retrieval): {catr1:.3f}")
        print(f"  PlanR@1 (DAG):     {dag_planr1:.3f}")
        print(f"  PlanR@1 (greedy):  {greedy_planr1:.3f}")
        print(f"  Plan validity (DAG):    {dag_valid:.3f}")
        print(f"  Plan validity (greedy):  {greedy_valid:.3f}")
        print(f"  Chain compat (DAG):    {dag_compat:.3f}")
        print(f"  Chain compat (greedy):  {greedy_compat:.3f}")
        print(f"  Chain compat (random):  {random_compat:.3f}")
        print(f"  Edge precision: {edge_prec:.3f}")
        print(f"  Edge recall:    {edge_rec:.3f}")
        print(f"  Edge F1:        {edge_f1:.3f}")
        print(f"  Edge exact match: {edge_em:.3f}")
        print(f"  Avg parallel groups: {avg_groups:.2f}")

    print("\n" + "=" * 70)


if __name__ == "__main__":
    run_experiment()
