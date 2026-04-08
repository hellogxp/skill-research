"""Run experiments with Qwen2.5-72B-Instruct (vanilla + SAD).
Uses device_map='auto' to spread across 4x A100-80GB GPUs.
"""
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


class SkillAwareDecomposer72B(TaskDecomposer):
    """SAD decomposer for 72B model with multi-GPU support."""

    def __init__(self, model_name="Qwen2.5-72B-Instruct", retriever=None,
                 skill_pool=None, num_hints=15, **kw):
        # Don't call parent __init__ yet, we'll override model loading
        self._model_name = model_name
        self._model = None
        self._tokenizer = None
        self.retriever = retriever
        self.skill_pool = skill_pool or []
        self.num_hints = num_hints
        self._skill_map = {s.skill_id: s for s in self.skill_pool}

    def _init_llm(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_path = f"/mnt/workspace/models/{self._model_name}"
        logger.info(f"Loading {self._model_name} with device_map='auto' (multi-GPU)...")
        self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        self._model.eval()
        logger.info(f"Model loaded across GPUs: {self._model.hf_device_map}")

    def _get_hints(self, query):
        if not self.retriever:
            return ""
        cands = self.retriever.retrieve(query, top_k=self.num_hints)
        lines = []
        for sid, sc in cands:
            sk = self._skill_map.get(sid)
            if sk:
                cat = f" [{sk.categories[0]}]" if sk.categories else ""
                lines.append(f"- {sk.name}{cat}: {sk.description[:120]}")
        return "\n".join(lines)

    def _format_sad_prompt(self, query):
        hints = self._get_hints(query)
        msgs = [{"role": "system", "content": SA_SYS.format(skill_hints=hints)},
                {"role": "user", "content": SA_USR.format(query=query)}]
        return self._tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)

    def decompose(self, query):
        import torch
        self._init_llm()
        prompt = self._format_sad_prompt(query)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(**inputs, max_new_tokens=256, temperature=0.1, do_sample=True)
        text = self._tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()
        return self._parse_output(text, query)


class VanillaDecomposer72B:
    """Vanilla (no SAD) decomposer for 72B model."""

    def __init__(self, model_name="Qwen2.5-72B-Instruct"):
        self._model_name = model_name
        self._model = None
        self._tokenizer = None

    def _init_llm(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_path = f"/mnt/workspace/models/{self._model_name}"
        logger.info(f"Loading {self._model_name} with device_map='auto' (multi-GPU)...")
        self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self._model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        self._model.eval()
        logger.info(f"Model loaded across GPUs: {self._model.hf_device_map}")

    def decompose(self, query):
        import torch, json as _json, re
        self._init_llm()

        sys_prompt = (
            "You are a task decomposition expert. Given a user query that requires "
            "multiple tools/skills to complete, break it down into a sequence of atomic sub-tasks.\n\n"
            "Rules:\n"
            "1. Each sub-task should require exactly ONE skill/tool to complete.\n"
            "2. List sub-tasks in execution order.\n"
            "3. Output ONLY a JSON array of strings, nothing else."
        )
        usr_prompt = f"Decompose this query into atomic sub-tasks. Output a JSON array of strings ONLY.\n\nQuery: {query}\n\nJSON array:"

        msgs = [{"role": "system", "content": sys_prompt},
                {"role": "user", "content": usr_prompt}]
        prompt = self._tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
        with torch.no_grad():
            out = self._model.generate(**inputs, max_new_tokens=256, temperature=0.1, do_sample=True)
        text = self._tokenizer.decode(out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

        # Parse JSON array
        try:
            # Try direct parse
            result = _json.loads(text)
            if isinstance(result, list):
                return [str(x) for x in result]
        except _json.JSONDecodeError:
            pass
        # Try to find JSON array in text
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            try:
                result = _json.loads(match.group())
                if isinstance(result, list):
                    return [str(x) for x in result]
            except _json.JSONDecodeError:
                pass
        # Fallback: split by newlines
        lines = [l.strip().lstrip('0123456789.-) ') for l in text.split('\n') if l.strip()]
        return lines if lines else [query]


def run_exp(name, decomposer, skills, benchmark, top_k=10):
    logger.info(f"\nExperiment: {name}")

    retriever = SkillRetriever(use_body=False, top_k=top_k)
    retriever.build_index(skills)

    compat = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compat)
    planner.set_skill_map(skills)

    results = []
    json_parse_ok = 0
    total = len(benchmark)
    for i, qd in enumerate(benchmark):
        t0 = time.time()
        subs = decomposer.decompose(qd["query"])
        if not subs:
            subs = [qd["query"]]
        # Track JSON parse success (did we get a proper list, not fallback?)
        if len(subs) > 0 and subs[0] != qd["query"]:
            json_parse_ok += 1
        cps = [retriever.retrieve(s, top_k=top_k) for s in subs]
        preds, edges = planner.plan(subs, cps)
        results.append(PipelineResult(
            query_id=qd["query_id"], query=qd["query"],
            decomposed_subtasks=subs, predictions=preds,
            predicted_edges=edges, latency_ms=(time.time()-t0)*1000))
        if (i+1) % 50 == 0:
            logger.info(f"  {i+1}/{total}")

    metrics = evaluate(results, benchmark, skill_pool=skills)
    metrics["json_parse_rate"] = json_parse_ok / total
    logger.info(f"Results: DA={metrics['decomposition_accuracy']:.3f} CR@1={metrics['cat_recall_at_1']:.3f} CC={metrics['chain_cat_match']:.3f} JSON_parse={metrics['json_parse_rate']:.3f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{name}.json", "w") as f:
        json.dump({"experiment": name,
                   "metrics": metrics,
                   "predictions": [asdict(r) for r in results]}, f, indent=2, default=str)
    return metrics


def main():
    skills = load_skill_pool()
    benchmark = load_benchmark()

    R = {}

    # 72B vanilla
    logger.info("=" * 60)
    logger.info("Starting Qwen2.5-72B-Instruct experiments")
    logger.info("=" * 60)

    vanilla_decomposer = VanillaDecomposer72B("Qwen2.5-72B-Instruct")
    R["72b_vanilla"] = run_exp("qwen72b_vanilla", vanilla_decomposer, skills, benchmark)

    # Free memory before loading SAD version
    del vanilla_decomposer
    import torch, gc
    gc.collect()
    torch.cuda.empty_cache()

    # 72B + SAD
    retriever_for_sad = SkillRetriever(use_body=False, top_k=15)
    retriever_for_sad.build_index(skills)
    sad_decomposer = SkillAwareDecomposer72B(
        "Qwen2.5-72B-Instruct", retriever=retriever_for_sad,
        skill_pool=skills, num_hints=15)
    R["72b_sad"] = run_exp("qwen72b_sad_hints15", sad_decomposer, skills, benchmark)

    logger.info("\n" + "=" * 60)
    logger.info("72B SUMMARY")
    logger.info("=" * 60)
    for n, m in R.items():
        logger.info(f"{n:<25} DA={m['decomposition_accuracy']:.3f} CR@1={m['cat_recall_at_1']:.3f} CC={m['chain_cat_match']:.3f} JSON={m['json_parse_rate']:.3f}")

    with open(RESULTS_DIR / "72b_summary.json", "w") as f:
        json.dump(R, f, indent=2)


if __name__ == "__main__":
    main()
