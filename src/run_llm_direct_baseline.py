"""LLM-direct baseline: give LLM query + top-N skill descriptions, ask it to select skills directly.
No decomposition step - tests whether decompose-retrieve-compose is better than retrieve-then-select.
"""
import sys, json, logging, time, re
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, "/mnt/workspace/skill-routing/src")
from pipeline.pipeline import (
    SkillRetriever, load_skill_pool, load_benchmark,
    evaluate, PipelineResult, SubTaskPrediction, RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SELECT_SYS = """You are a skill routing expert. Given a user query and a list of available skills, select the skills needed to accomplish the query.

Rules:
1. Select ONLY the skills needed - no more, no fewer.
2. Order them by execution sequence.
3. Output a JSON array of skill names (strings), nothing else.
4. Each selected skill should handle one atomic part of the task."""

SELECT_USR = """Query: {query}

Available skills (name: description):
{skill_list}

Select the skills needed to accomplish this query. Output a JSON array of skill names ONLY.

JSON array:"""


class LLMDirectSelector:
    """Directly selects skills from a candidate pool using LLM (no decomposition)."""

    def __init__(self, model_name="Qwen2.5-7B-Instruct", top_n=50):
        self._model_name = model_name
        self._model = None
        self._tokenizer = None
        self.top_n = top_n

    def _init_llm(self):
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_path = f"/mnt/workspace/models/{self._model_name}"
        logger.info(f"Loading {self._model_name}...")

        self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        if "72B" in self._model_name:
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=torch.float16,
                device_map="auto", trust_remote_code=True)
        else:
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path, torch_dtype=torch.float16,
                device_map="auto", trust_remote_code=True)
        self._model.eval()
        logger.info(f"Model loaded: {self._model_name}")

    def select(self, query, candidate_skills):
        """Given query and candidate skills (list of SkillRecord), select skills."""
        import torch

        self._init_llm()

        # Format skill list
        skill_lines = []
        for s in candidate_skills[:self.top_n]:
            skill_lines.append(f"- {s.name}: {s.description[:150]}")
        skill_list_str = "\n".join(skill_lines)

        msgs = [
            {"role": "system", "content": SELECT_SYS},
            {"role": "user", "content": SELECT_USR.format(
                query=query, skill_list=skill_list_str)}
        ]

        prompt = self._tokenizer.apply_chat_template(
            msgs, tokenize=False, add_generation_prompt=True)
        inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

        with torch.no_grad():
            out = self._model.generate(
                **inputs, max_new_tokens=256, temperature=0.1, do_sample=True)
        text = self._tokenizer.decode(
            out[0][inputs.input_ids.shape[1]:], skip_special_tokens=True).strip()

        # Parse skill names
        selected_names = self._parse_selection(text, candidate_skills)
        return selected_names

    def _parse_selection(self, text, candidates):
        name_set = {s.name.lower(): s.name for s in candidates}

        try:
            result = json.loads(text)
            if isinstance(result, list):
                return [str(x) for x in result]
        except json.JSONDecodeError:
            pass

        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group())
                if isinstance(result, list):
                    return [str(x) for x in result]
            except json.JSONDecodeError:
                pass

        # Fallback: extract skill names from text
        found = []
        for line in text.split('\n'):
            line = line.strip().strip('-').strip()
            if line.lower() in name_set:
                found.append(name_set[line.lower()])
        return found if found else []


def run_llm_direct(model_name, top_n, skills, benchmark):
    experiment_name = f"llm_direct_{model_name.replace('.', '').replace('-', '_').lower()}_top{top_n}"
    logger.info(f"\n{'='*60}")
    logger.info(f"Experiment: {experiment_name}")
    logger.info(f"{'='*60}")

    # Build retriever for candidate retrieval
    retriever = SkillRetriever(use_body=False, top_k=top_n)
    retriever.build_index(skills)
    skill_map = {s.skill_id: s for s in skills}
    name_to_skill = {}
    for s in skills:
        name_to_skill[s.name.lower()] = s

    selector = LLMDirectSelector(model_name=model_name, top_n=top_n)

    results = []
    total = len(benchmark)

    for i, qd in enumerate(benchmark):
        t0 = time.time()

        # Step 1: Retrieve top-N candidates for the full query
        cands = retriever.retrieve(qd["query"], top_k=top_n)
        cand_skills = [skill_map[sid] for sid, _ in cands if sid in skill_map]

        # Step 2: LLM selects from candidates
        selected_names = selector.select(qd["query"], cand_skills)

        # Map selected names back to skill IDs
        gt_subtasks = qd["subtasks"]
        predictions = []

        for step_idx in range(len(gt_subtasks)):
            if step_idx < len(selected_names):
                sel_name = selected_names[step_idx]
                # Find skill by name
                sel_skill = name_to_skill.get(sel_name.lower())
                if sel_skill:
                    sel_id = sel_skill.skill_id
                    sel_nm = sel_skill.name
                else:
                    sel_id = ""
                    sel_nm = sel_name
            else:
                # Not enough selections
                sel_id = cands[0][0] if cands else ""
                sel_nm = skill_map[sel_id].name if sel_id and sel_id in skill_map else ""

            # Build candidate list from retrieval (for evaluation)
            predictions.append(SubTaskPrediction(
                step_index=step_idx,
                description=qd["query"],
                candidate_skill_ids=[sel_id] + [sid for sid, _ in cands[:10]],
                candidate_scores=[1.0] + [sc for _, sc in cands[:10]],
                selected_skill_id=sel_id,
                selected_skill_name=sel_nm,
            ))

        latency = (time.time() - t0) * 1000
        results.append(PipelineResult(
            query_id=qd["query_id"],
            query=qd["query"],
            decomposed_subtasks=selected_names if selected_names else [qd["query"]],
            predictions=predictions,
            predicted_edges=[],
            latency_ms=latency,
        ))

        if (i+1) % 50 == 0:
            logger.info(f"  {i+1}/{total}")

    metrics = evaluate(results, benchmark, skill_pool=skills)
    # Also compute "selection accuracy" = did the model select the right NUMBER of skills
    n_correct = sum(1 for r, q in zip(results, benchmark)
                    if len(r.decomposed_subtasks) == len(q["subtasks"]))
    metrics["selection_count_accuracy"] = n_correct / len(benchmark)

    logger.info(f"Results: CR@1={metrics['cat_recall_at_1']:.3f} "
                f"CC={metrics['chain_cat_match']:.3f} "
                f"SelAcc={metrics['selection_count_accuracy']:.3f}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / f"{experiment_name}.json", "w") as f:
        json.dump({
            "experiment": experiment_name,
            "config": {"model": model_name, "top_n": top_n, "method": "llm_direct_selection"},
            "metrics": metrics,
            "predictions": [asdict(r) for r in results],
        }, f, indent=2, default=str)

    return metrics


def main():
    skills = load_skill_pool()
    benchmark = load_benchmark()

    R = {}

    # 7B direct selection (top-50)
    R["7b_direct_top50"] = run_llm_direct(
        "Qwen2.5-7B-Instruct", top_n=50, skills=skills, benchmark=benchmark)

    # 72B direct selection (top-50)
    import torch, gc
    gc.collect()
    torch.cuda.empty_cache()

    R["72b_direct_top50"] = run_llm_direct(
        "Qwen2.5-72B-Instruct", top_n=50, skills=skills, benchmark=benchmark)

    logger.info("\n" + "=" * 60)
    logger.info("LLM-DIRECT BASELINE SUMMARY")
    logger.info("=" * 60)
    for n, m in R.items():
        logger.info(f"{n:<25} CR@1={m['cat_recall_at_1']:.3f} "
                    f"CC={m['chain_cat_match']:.3f} "
                    f"SelAcc={m['selection_count_accuracy']:.3f}")

    with open(RESULTS_DIR / "llm_direct_summary.json", "w") as f:
        json.dump(R, f, indent=2)
    logger.info(f"Summary saved to {RESULTS_DIR / 'llm_direct_summary.json'}")


if __name__ == "__main__":
    main()
