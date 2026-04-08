"""
Experiment: Skill-Aware Decomposition (RAD)
============================================
Core methodological contribution for the paper.

Key insight: Standard decomposers don't know what skills exist in the library,
producing generic subtask descriptions ("process the data") that cause retrieval
mismatches. Skill-Aware Decomposition (RAD) provides the decomposer with
retrieved skill hints from the library, enabling it to generate subtask
descriptions that align with actual skill metadata.

This is a form of Retrieval-Augmented Decomposition: the skill library informs
the decomposition step, creating a feedback loop.

Pipeline:
    Query → [Preliminary Retrieval] → skill hints
                                         ↓
    Query + skill hints → [LLM Decomposer] → subtasks → [Retrieve] → [Plan]
"""

import sys
import json
import logging
import time
from pathlib import Path
from dataclasses import asdict

sys.path.insert(0, "/mnt/workspace/skill-routing/src")

from pipeline.pipeline import (
    TaskDecomposer,
    SkillRetriever,
    CompatibilityScorer,
    DAGPlanner,
    CompositionalSkillRouter,
    PipelineResult,
    SubTaskPrediction,
    load_skill_pool,
    load_benchmark,
    evaluate,
    RESULTS_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# ============================================================
# Skill-Aware Decomposer
# ============================================================

SKILL_AWARE_SYSTEM_PROMPT = """You are a task decomposition expert. Given a user query that requires multiple tools/skills to complete, break it down into a sequence of atomic sub-tasks.

You have access to a skill library. Below are the most relevant available skills for this query:

{skill_hints}

Rules:
1. Each sub-task should require exactly ONE skill/tool to complete.
2. Use the available skill names and descriptions to guide your decomposition.
3. Each sub-task description should closely match what one of the available skills does.
4. List sub-tasks in execution order.
5. Output ONLY a JSON array of strings, nothing else."""

SKILL_AWARE_USER_TEMPLATE = """Decompose this query into atomic sub-tasks. Use the available skills listed above to guide your decomposition. Output a JSON array of strings ONLY.

Query: {query}

JSON array:"""


class SkillAwareDecomposer(TaskDecomposer):
    """Decomposer that uses preliminary retrieval to inform decomposition.

    Before decomposing, retrieves top-k skills for the full query and includes
    their names/descriptions in the system prompt. This helps the LLM generate
    subtask descriptions that align with actual skill metadata.
    """

    def __init__(
        self,
        model_name: str = "Qwen2.5-7B-Instruct",
        retriever: SkillRetriever = None,
        skill_pool: list = None,
        num_hints: int = 15,
        use_vllm: bool = False,
    ):
        super().__init__(model_name=model_name, use_vllm=use_vllm)
        self.retriever = retriever
        self.skill_pool = skill_pool or []
        self.num_hints = num_hints
        self._skill_map = {s.skill_id: s for s in self.skill_pool}

    def _get_skill_hints(self, query: str) -> str:
        """Retrieve relevant skills and format as hints."""
        if not self.retriever:
            return ""

        candidates = self.retriever.retrieve(query, top_k=self.num_hints)

        hints = []
        seen_cats = set()
        for skill_id, score in candidates:
            skill = self._skill_map.get(skill_id)
            if skill:
                cat_str = f" [{skill.categories[0]}]" if skill.categories else ""
                hints.append(f"- {skill.name}{cat_str}: {skill.description[:120]}")
                if skill.categories:
                    seen_cats.update(skill.categories)

        return "\n".join(hints)

    def _format_prompt(self, query: str) -> str:
        """Override: format prompt with skill hints."""
        skill_hints = self._get_skill_hints(query)

        system_prompt = SKILL_AWARE_SYSTEM_PROMPT.format(skill_hints=skill_hints)

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": SKILL_AWARE_USER_TEMPLATE.format(query=query)},
        ]
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return prompt

    def decompose(self, query: str) -> list[str]:
        """Decompose with skill-aware hints."""
        import torch

        self._init_llm()
        prompt = self._format_prompt(query)

        if self.use_vllm:
            outputs = self._llm.generate([prompt], self._sampling_params)
            text = outputs[0].outputs[0].text.strip()
        else:
            inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
            with torch.no_grad():
                output = self._model.generate(
                    **inputs, max_new_tokens=256, temperature=0.1, do_sample=True
                )
            text = self._tokenizer.decode(
                output[0][inputs.input_ids.shape[1]:], skip_special_tokens=True
            ).strip()

        return self._parse_output(text, query)


# ============================================================
# Run experiments
# ============================================================

def run_skill_aware_experiment(
    experiment_name: str,
    llm_name: str = "Qwen2.5-7B-Instruct",
    num_hints: int = 15,
    use_body: bool = False,
    top_k: int = 10,
    batch_size: int = 32,
):
    """Run the skill-aware decomposition experiment."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Skill-Aware Decomposition Experiment: {experiment_name}")
    logger.info(f"  llm={llm_name}, num_hints={num_hints}, use_body={use_body}")
    logger.info(f"{'='*60}")

    skills = load_skill_pool()
    benchmark = load_benchmark()
    logger.info(f"Loaded {len(skills)} skills, {len(benchmark)} queries")

    # Build retriever (shared for both hint retrieval and final retrieval)
    retriever = SkillRetriever(use_body=use_body, top_k=top_k)
    retriever.build_index(skills)

    # Create skill-aware decomposer
    decomposer = SkillAwareDecomposer(
        model_name=llm_name,
        retriever=retriever,
        skill_pool=skills,
        num_hints=num_hints,
    )

    compatibility = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compatibility)
    planner.set_skill_map(skills)

    router = CompositionalSkillRouter(decomposer, retriever, compatibility, planner)

    # Run on benchmark
    logger.info(f"Running skill-aware pipeline with batch_size={batch_size}...")
    # Use sequential for skill-aware (each query needs unique hints)
    results = []
    for i, qdata in enumerate(benchmark):
        result = router.route(qdata["query"], qdata["query_id"])
        results.append(result)
        if (i + 1) % 20 == 0:
            logger.info(f"  Processed {i+1}/{len(benchmark)} queries")

    # Evaluate
    metrics = evaluate(results, benchmark, skill_pool=skills)
    logger.info(f"\nResults for {experiment_name}:")
    for k, v in metrics.items():
        logger.info(f"  {k}: {v:.4f}")

    # Save results
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    result_file = RESULTS_DIR / f"{experiment_name}.json"
    with open(result_file, "w") as f:
        json.dump({
            "experiment": experiment_name,
            "config": {
                "use_body": use_body,
                "llm": llm_name,
                "num_hints": num_hints,
                "top_k": top_k,
                "method": "skill_aware_decomposition",
            },
            "metrics": metrics,
            "predictions": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Results saved to {result_file}")

    return metrics


def main():
    all_results = {}

    # ============================================================
    # Experiment 1: Skill-Aware Decomp with Qwen2.5-7B (main result)
    # ============================================================
    all_results["skill_aware_qwen7b_h15"] = run_skill_aware_experiment(
        experiment_name="skill_aware_qwen7b_hints15",
        llm_name="Qwen2.5-7B-Instruct",
        num_hints=15,
    )

    # ============================================================
    # Experiment 2: Ablation on number of hints
    # ============================================================
    for nh in [5, 10, 25]:
        all_results[f"skill_aware_qwen7b_h{nh}"] = run_skill_aware_experiment(
            experiment_name=f"skill_aware_qwen7b_hints{nh}",
            llm_name="Qwen2.5-7B-Instruct",
            num_hints=nh,
        )

    # ============================================================
    # Experiment 3: Skill-Aware with other decomposers
    # ============================================================
    for llm in ["Llama-3.1-8B-Instruct", "Mistral-7B-Instruct-v0.3"]:
        safe_name = llm.lower().replace(".", "").replace("-", "_")
        all_results[f"skill_aware_{safe_name}"] = run_skill_aware_experiment(
            experiment_name=f"skill_aware_{safe_name}_hints15",
            llm_name=llm,
            num_hints=15,
        )

    # ============================================================
    # Summary
    # ============================================================
    logger.info("\n" + "=" * 70)
    logger.info("SKILL-AWARE DECOMPOSITION: SUMMARY")
    logger.info("=" * 70)
    header = f"{'Experiment':<40} {'DecompAcc':>9} {'CatR@1':>7} {'CatR@10':>8} {'ChainCat':>9}"
    logger.info(header)
    logger.info("-" * 80)
    for name, metrics in all_results.items():
        logger.info(
            f"{name:<40} "
            f"{metrics.get('decomposition_accuracy', 0):>8.4f} "
            f"{metrics.get('cat_recall_at_1', 0):>6.4f} "
            f"{metrics.get('cat_recall_at_10', 0):>7.4f} "
            f"{metrics.get('chain_cat_match', 0):>8.4f}"
        )

    # Save combined summary
    summary_file = RESULTS_DIR / "skill_aware_summary.json"
    with open(summary_file, "w") as f:
        json.dump(all_results, f, indent=2)
    logger.info(f"\nSummary saved to {summary_file}")


if __name__ == "__main__":
    main()
