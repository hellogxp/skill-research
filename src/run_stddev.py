"""Run key experiments multiple times with different seeds to compute standard deviations.
Runs: Qwen-7B vanilla (3x), Qwen-7B+SAD (3x).
"""
import sys, json, logging, time, random
from pathlib import Path
from dataclasses import asdict
import numpy as np
import torch

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
        self._init_llm()
        prompt = self._format_prompt(query)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(**inputs, max_new_tokens=256,
                                       temperature=0.1, do_sample=True)
        text = self._tokenizer.decode(
            out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        return self._parse_output(text, query)


def run_single(decomposer, skills, benchmark, retriever, experiment_name):
    """Run a single experiment pass."""
    compat = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compat)
    planner.set_skill_map(skills)

    results = []
    for i, qd in enumerate(benchmark):
        t0 = time.time()
        subs = decomposer.decompose(qd["query"])
        if not subs: subs = [qd["query"]]
        cps = [retriever.retrieve(s, top_k=10) for s in subs]
        preds, edges = planner.plan(subs, cps)
        results.append(PipelineResult(
            query_id=qd["query_id"], query=qd["query"],
            decomposed_subtasks=subs, predictions=preds,
            predicted_edges=edges, latency_ms=(time.time()-t0)*1000))
        if (i+1) % 100 == 0:
            logger.info(f"  [{experiment_name}] {i+1}/{len(benchmark)}")

    metrics = evaluate(results, benchmark, skill_pool=skills)
    return metrics


def main():
    skills = load_skill_pool()
    benchmark = load_benchmark()
    N_RUNS = 3
    SEEDS = [42, 123, 456]

    # Build retriever once (deterministic)
    retriever = SkillRetriever(use_body=False, top_k=10)
    retriever.build_index(skills)

    all_runs = {"vanilla": [], "sad": []}

    for run_idx, seed in enumerate(SEEDS):
        logger.info(f"\n{'='*60}")
        logger.info(f"RUN {run_idx+1}/{N_RUNS} (seed={seed})")
        logger.info(f"{'='*60}")

        # Set seeds
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)
        if torch.cuda.is_available():
            torch.cuda.manual_seed_all(seed)

        # Vanilla
        vanilla_decomposer = TaskDecomposer(model_name="Qwen2.5-7B-Instruct")
        m = run_single(vanilla_decomposer, skills, benchmark, retriever,
                       f"vanilla_run{run_idx}")
        all_runs["vanilla"].append(m)
        logger.info(f"  Vanilla: DA={m['decomposition_accuracy']:.3f} "
                    f"CR@1={m['cat_recall_at_1']:.3f} CC={m['chain_cat_match']:.3f}")

        # Free model memory for SAD
        del vanilla_decomposer
        import gc; gc.collect(); torch.cuda.empty_cache()

        # SAD
        sad_retriever = SkillRetriever(use_body=False, top_k=15)
        sad_retriever.build_index(skills)
        sad_decomposer = SkillAwareDecomposer(
            model_name="Qwen2.5-7B-Instruct", retriever=sad_retriever,
            skill_pool=skills, num_hints=15)
        m = run_single(sad_decomposer, skills, benchmark, retriever,
                       f"sad_run{run_idx}")
        all_runs["sad"].append(m)
        logger.info(f"  SAD: DA={m['decomposition_accuracy']:.3f} "
                    f"CR@1={m['cat_recall_at_1']:.3f} CC={m['chain_cat_match']:.3f}")

        del sad_decomposer, sad_retriever
        gc.collect(); torch.cuda.empty_cache()

    # Compute statistics
    logger.info(f"\n{'='*60}")
    logger.info("STANDARD DEVIATION SUMMARY")
    logger.info(f"{'='*60}")

    key_metrics = ["decomposition_accuracy", "cat_recall_at_1", "chain_cat_match",
                   "skill_recall_at_1", "cat_recall_at_10"]
    summary = {}

    for mode in ["vanilla", "sad"]:
        summary[mode] = {}
        logger.info(f"\n{mode.upper()} ({N_RUNS} runs):")
        for metric in key_metrics:
            vals = [run[metric] for run in all_runs[mode]]
            mean = np.mean(vals)
            std = np.std(vals)
            summary[mode][metric] = {
                "mean": float(mean), "std": float(std),
                "values": [float(v) for v in vals]
            }
            logger.info(f"  {metric:<30} {mean:.4f} ± {std:.4f}  ({vals})")

    # Save
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "stddev_summary.json", "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"\nSaved to {RESULTS_DIR / 'stddev_summary.json'}")


if __name__ == "__main__":
    main()
