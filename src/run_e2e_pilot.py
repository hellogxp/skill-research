"""End-to-end pilot evaluation: full pipeline analysis on 20 queries.
Evaluates not just retrieval accuracy but also:
- DAG structure correctness
- Functional coherence (skill descriptions match intent)
- Latency distribution
- Comparison across difficulty levels
"""
import sys, json, logging, time, random
from pathlib import Path
from dataclasses import asdict
import numpy as np

sys.path.insert(0, "/mnt/workspace/skill-routing/src")
from pipeline.pipeline import (
    TaskDecomposer, SkillRetriever, CompatibilityScorer, DAGPlanner,
    PipelineResult, SubTaskPrediction, load_skill_pool, load_benchmark,
    evaluate, RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SA_SYS = """You are a task decomposition expert. Given a user query that requires multiple tools/skills to complete, break it down into a sequence of atomic sub-tasks.

You have access to a skill library. Below are the most relevant available skills for this query:

{skill_hints}

Rules:
1. Each sub-task should require exactly ONE skill/tool to complete.
2. Use the available skill names and descriptions to guide your decomposition.
3. Each sub-task description should closely match what one of the available skills does.
4. List sub-tasks in execution order.
5. Output ONLY a JSON array of strings, nothing else."""

SA_USR = """Decompose this query into atomic sub-tasks. Use the available skills listed above to guide your decomposition. Output a JSON array of strings ONLY.

Query: {query}

JSON array:"""


class SkillAwareDecomposer(TaskDecomposer):
    def __init__(self, model_name="Qwen2.5-7B-Instruct", retriever=None,
                 skill_pool=None, num_hints=15, **kw):
        super().__init__(model_name=model_name, **kw)
        self.retriever = retriever
        self.skill_pool = skill_pool or []
        self.num_hints = num_hints
        self._skill_map = {s.skill_id: s for s in self.skill_pool}

    def _get_hints(self, query):
        if not self.retriever: return ""
        cands = self.retriever.retrieve(query, top_k=self.num_hints)
        lines = []
        for sid, sc in cands:
            sk = self._skill_map.get(sid)
            if sk:
                cat = f" [{sk.categories[0]}]" if sk.categories else ""
                lines.append(f"- {sk.name}{cat}: {sk.description[:120]}")
        return "\n".join(lines)

    def _format_prompt(self, query):
        hints = self._get_hints(query)
        msgs = [{"role": "system", "content": SA_SYS.format(skill_hints=hints)},
                {"role": "user", "content": SA_USR.format(query=query)}]
        return self._tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    def decompose(self, query):
        import torch
        self._init_llm()
        prompt = self._format_prompt(query)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(**inputs, max_new_tokens=256, temperature=0.1, do_sample=True)
        text = self._tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        return self._parse_output(text, query)


def select_diverse_queries(benchmark, n=20, seed=42):
    """Select n diverse queries stratified by difficulty."""
    random.seed(seed)
    by_diff = {}
    for q in benchmark:
        d = q.get("difficulty", "medium")
        by_diff.setdefault(d, []).append(q)
    
    selected = []
    # Proportional allocation
    for diff in ["easy", "medium", "hard"]:
        pool = by_diff.get(diff, [])
        k = max(1, round(n * len(pool) / len(benchmark)))
        k = min(k, len(pool))
        selected.extend(random.sample(pool, k))
    
    # Fill remaining
    while len(selected) < n:
        remaining = [q for q in benchmark if q not in selected]
        if not remaining: break
        selected.append(random.choice(remaining))
    
    return selected[:n]


def analyze_dag_structure(results, benchmark):
    """Analyze DAG structure quality."""
    stats = {"total": len(results), "correct_num_steps": 0, "has_edges": 0,
             "avg_subtasks": 0, "avg_latency_ms": 0}
    
    total_subs = 0
    total_lat = 0
    
    for r, q in zip(results, benchmark):
        gt_steps = len(q["subtasks"])
        pred_steps = len(r.decomposed_subtasks)
        if pred_steps == gt_steps:
            stats["correct_num_steps"] += 1
        total_subs += pred_steps
        total_lat += r.latency_ms
        if r.predicted_edges:
            stats["has_edges"] += 1
    
    stats["avg_subtasks"] = total_subs / len(results) if results else 0
    stats["avg_latency_ms"] = total_lat / len(results) if results else 0
    stats["step_count_accuracy"] = stats["correct_num_steps"] / len(results) if results else 0
    stats["edge_rate"] = stats["has_edges"] / len(results) if results else 0
    
    return stats


def functional_coherence_check(results, benchmark, skill_pool):
    """Check if retrieved skills are functionally coherent with the query intent."""
    skill_map = {s.skill_id: s for s in skill_pool}
    
    coherence_scores = []
    for r, q in zip(results, benchmark):
        # For each prediction, check if the category matches
        matched = 0
        total = min(len(r.predictions), len(q["subtasks"]))
        for i in range(total):
            pred = r.predictions[i]
            gt = q["subtasks"][i]
            pred_skill = skill_map.get(pred.selected_skill_id)
            if pred_skill:
                # Category match
                if gt["required_category"] in pred_skill.categories:
                    matched += 1
        score = matched / total if total > 0 else 0
        coherence_scores.append(score)
    
    return {
        "mean_coherence": float(np.mean(coherence_scores)) if coherence_scores else 0,
        "per_query": coherence_scores
    }


def main():
    skills = load_skill_pool()
    benchmark = load_benchmark()
    
    # Select 20 diverse queries
    pilot_queries = select_diverse_queries(benchmark, n=20)
    logger.info(f"Selected {len(pilot_queries)} pilot queries")
    diff_counts = {}
    for q in pilot_queries:
        d = q.get("difficulty", "unknown")
        diff_counts[d] = diff_counts.get(d, 0) + 1
    logger.info(f"Difficulty distribution: {diff_counts}")
    
    # Build retriever
    retriever = SkillRetriever(use_body=False, top_k=10)
    retriever.build_index(skills)
    
    # SAD decomposer
    decomposer = SkillAwareDecomposer(
        model_name="Qwen2.5-7B-Instruct", retriever=retriever,
        skill_pool=skills, num_hints=15)
    
    compat = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compat)
    planner.set_skill_map(skills)
    
    # Run full pipeline
    results = []
    for i, qd in enumerate(pilot_queries):
        t0 = time.time()
        subs = decomposer.decompose(qd["query"])
        if not subs: subs = [qd["query"]]
        cps = [retriever.retrieve(s, top_k=10) for s in subs]
        preds, edges = planner.plan(subs, cps)
        lat = (time.time()-t0)*1000
        results.append(PipelineResult(
            query_id=qd["query_id"], query=qd["query"],
            decomposed_subtasks=subs, predictions=preds,
            predicted_edges=edges, latency_ms=lat))
        logger.info(f"  [{i+1}/{len(pilot_queries)}] {qd['query_id']} | {len(subs)} subs | {len(edges)} edges | {lat:.0f}ms")
    
    # Standard metrics
    metrics = evaluate(results, pilot_queries, skill_pool=skills)
    logger.info(f"\nStandard Metrics: DA={metrics['decomposition_accuracy']:.3f} CR@1={metrics['cat_recall_at_1']:.3f} CC={metrics['chain_cat_match']:.3f}")
    
    # DAG structure analysis
    dag_stats = analyze_dag_structure(results, pilot_queries)
    logger.info(f"DAG Analysis: step_acc={dag_stats['step_count_accuracy']:.3f} edge_rate={dag_stats['edge_rate']:.3f} avg_subs={dag_stats['avg_subtasks']:.1f} avg_lat={dag_stats['avg_latency_ms']:.0f}ms")
    
    # Functional coherence
    coherence = functional_coherence_check(results, pilot_queries, skills)
    logger.info(f"Functional Coherence: {coherence['mean_coherence']:.3f}")
    
    # Latency distribution
    latencies = [r.latency_ms for r in results]
    logger.info(f"Latency: p50={np.percentile(latencies,50):.0f}ms p95={np.percentile(latencies,95):.0f}ms max={max(latencies):.0f}ms")
    
    # Per-difficulty breakdown
    for diff in ["easy", "medium", "hard"]:
        idxs = [i for i, q in enumerate(pilot_queries) if q.get("difficulty") == diff]
        if idxs:
            sub_r = [results[i] for i in idxs]
            sub_b = [pilot_queries[i] for i in idxs]
            sub_m = evaluate(sub_r, sub_b, skill_pool=skills)
            logger.info(f"  {diff}: n={len(idxs)} DA={sub_m['decomposition_accuracy']:.3f} CR@1={sub_m['cat_recall_at_1']:.3f}")
    
    # Save full report
    report = {
        "experiment": "e2e_pilot_sad",
        "config": {"n_queries": len(pilot_queries), "method": "SAD", "hints": 15,
                   "llm": "Qwen2.5-7B-Instruct", "difficulty_dist": diff_counts},
        "standard_metrics": metrics,
        "dag_analysis": dag_stats,
        "functional_coherence": {"mean": coherence["mean_coherence"]},
        "latency": {"p50": float(np.percentile(latencies,50)),
                     "p95": float(np.percentile(latencies,95)),
                     "max": float(max(latencies)),
                     "mean": float(np.mean(latencies))},
        "per_query_details": []
    }
    
    for r, q, coh in zip(results, pilot_queries, coherence["per_query"]):
        report["per_query_details"].append({
            "query_id": q["query_id"],
            "query": q["query"],
            "difficulty": q.get("difficulty"),
            "gt_steps": len(q["subtasks"]),
            "pred_steps": len(r.decomposed_subtasks),
            "subtasks": r.decomposed_subtasks,
            "predictions": [asdict(p) for p in r.predictions],
            "edges": r.predicted_edges,
            "latency_ms": r.latency_ms,
            "coherence": coh,
        })
    
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "e2e_pilot_report.json", "w") as f:
        json.dump(report, f, indent=2, default=str)
    logger.info(f"\nFull report saved to {RESULTS_DIR / 'e2e_pilot_report.json'}")

if __name__ == "__main__":
    main()
