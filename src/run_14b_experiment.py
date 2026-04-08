"""Run experiments with Qwen2.5-14B-Instruct."""
import sys, json, logging, time
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, "/mnt/workspace/skill-routing/src")
from pipeline.pipeline import (
    TaskDecomposer, SkillRetriever, CompatibilityScorer, DAGPlanner,
    PipelineResult, SubTaskPrediction, load_skill_pool, load_benchmark,
    evaluate, RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Reuse SAD classes from v2
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

class SkillAwareDecomposer14B(TaskDecomposer):
    def __init__(self, model_name="Qwen2.5-14B-Instruct", retriever=None,
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


def run_exp(name, decomposer_cls, llm, use_sad=False, nh=15, use_body=False, top_k=10):
    logger.info(f"\n{'='*60}")
    logger.info(f"Experiment: {name} (llm={llm}, SAD={use_sad})")
    logger.info(f"{'='*60}")

    skills = load_skill_pool()
    benchmark = load_benchmark()

    retriever = SkillRetriever(use_body=use_body, top_k=top_k)
    retriever.build_index(skills)

    if use_sad:
        decomposer = decomposer_cls(model_name=llm, retriever=retriever, skill_pool=skills, num_hints=nh)
    else:
        decomposer = TaskDecomposer(model_name=llm)

    compat = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compat)
    planner.set_skill_map(skills)

    results = []
    for i, qd in enumerate(benchmark):
        t0 = time.time()
        subs = decomposer.decompose(qd["query"])
        if not subs: subs = [qd["query"]]
        cps = [retriever.retrieve(s, top_k=top_k) for s in subs]
        preds, edges = planner.plan(subs, cps)
        results.append(PipelineResult(
            query_id=qd["query_id"], query=qd["query"],
            decomposed_subtasks=subs, predictions=preds,
            predicted_edges=edges, latency_ms=(time.time()-t0)*1000))
        if (i+1) % 50 == 0:
            logger.info(f"  {i+1}/{len(benchmark)}")

    metrics = evaluate(results, benchmark, skill_pool=skills)
    logger.info(f"Results: DA={metrics['decomposition_accuracy']:.3f} CR@1={metrics['cat_recall_at_1']:.3f} CC={metrics['chain_cat_match']:.3f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{name}.json", "w") as f:
        json.dump({"experiment": name,
                   "config": {"llm": llm, "sad": use_sad, "hints": nh if use_sad else 0},
                   "metrics": metrics,
                   "predictions": [asdict(r) for r in results]}, f, indent=2, default=str)
    return metrics


def main():
    R = {}

    # 14B vanilla (no SAD)
    R["14b_vanilla"] = run_exp(
        "qwen14b_vanilla", TaskDecomposer, "Qwen2.5-14B-Instruct", use_sad=False)

    # 14B with SAD
    R["14b_sad"] = run_exp(
        "qwen14b_sad_hints15", SkillAwareDecomposer14B, "Qwen2.5-14B-Instruct", use_sad=True)

    logger.info("\nSUMMARY")
    for n, m in R.items():
        logger.info(f"{n:<25} DA={m['decomposition_accuracy']:.3f} CR@1={m['cat_recall_at_1']:.3f} CC={m['chain_cat_match']:.3f}")

    with open(RESULTS_DIR / "14b_summary.json", "w") as f:
        json.dump(R, f, indent=2)

if __name__ == "__main__":
    main()
