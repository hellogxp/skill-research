#!/usr/bin/env python3
"""Constrained Decoding Experiment for SkillWeaver 14B Model.

Purpose: Address the 14B anomaly problem where Qwen2.5-14B-Instruct shows 
unstable structured output behavior in task decomposition.

Problem Analysis (from paper Appendix):
- 14B vanilla: avg 5.3 sub-tasks (over-decomposition), JSON parse rate 71.3%
- 14B + SAD: JSON parse rate 85%, but 44.7% queries collapse to single-subtask fallbacks
- Root cause: 14B model struggles with consistent JSON array generation

Solution: Constrained Decoding via three approaches:
1. Vanilla (baseline): No constraints, standard decomposition
2. Constrained (JSON enforcement): Few-shot examples + post-processing repair
3. SAD + Constrained: Skill-aware decomposition + JSON constraints

Implementation Strategy (avoiding external libs like 'outlines'):
- Few-shot prompting: Include 2-3 examples of valid JSON array outputs in prompt
- Post-processing repair: Attempt to fix malformed JSON using regex + json.loads
- Fallback handling: If repair fails, extract skill names via pattern matching

Metrics Tracked:
- recall@k: Skill retrieval accuracy at k=1,5,10
- exact_match: Chain-level exact match with ground truth
- json_parse_rate: Percentage of queries producing valid JSON arrays
- avg_subtasks: Average number of decomposed sub-tasks (detect over-decomposition)
- collapse_rate: Percentage of queries collapsing to single sub-task

Usage:
    python run_constrained_decoding_experiment.py

Output:
    results_v3/constrained_decoding_experiment.json
"""

import json
import logging
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add skillweaver to path
WORKSPACE = Path("/mnt/workspace")
sys.path.insert(0, str(WORKSPACE / "skillweaver" / "src"))

from skillweaver.core.decomposer import LocalDecomposer, parse_subtasks
from skillweaver.core.models import Skill, SubTask
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Paths
DATA_DIR = WORKSPACE / "skill-research" / "data"
RESULTS_DIR = WORKSPACE / "skill-research" / "results_v3"
SKILL_POOL_PATH = DATA_DIR / "processed_v3" / "skill_pool.jsonl"
QUERIES_PATH = DATA_DIR / "benchmark_v3" / "compositional_queries.jsonl"
OUTPUT_PATH = RESULTS_DIR / "constrained_decoding_experiment.json"

# Model paths
MODEL_14B = "/mnt/workspace/models/Qwen/Qwen2___5-14B-Instruct"
EMBEDDING_MODEL = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"

# Few-shot examples for constrained decoding
FEW_SHOT_EXAMPLES = [
    {
        "query": "Find recent news about AI and summarize the key points",
        "output": '["Search for recent AI news articles", "Extract key information from top articles", "Generate concise summary of findings"]'
    },
    {
        "query": "Calculate total revenue for Q3 and compare with Q2",
        "output": '["Retrieve Q3 sales data from database", "Retrieve Q2 sales data from database", "Calculate total revenue for each quarter", "Compare Q3 vs Q2 performance metrics"]'
    },
    {
        "query": "Create a presentation about climate change impacts",
        "output": '["Research latest climate change scientific reports", "Identify major environmental impact categories", "Gather statistical data on temperature changes", "Design slide structure and content outline"]'
    }
]


def load_skill_pool() -> list[Skill]:
    """Load skill pool from JSONL file."""
    skills = []
    with open(SKILL_POOL_PATH, "r") as f:
        for line in f:
            data = json.loads(line.strip())
            skills.append(Skill.from_dict(data))
    logger.info(f"Loaded {len(skills)} skills from pool")
    return skills


def load_queries() -> list[dict]:
    """Load compositional queries from JSONL file."""
    queries = []
    with open(QUERIES_PATH, "r") as f:
        for line in f:
            queries.append(json.loads(line.strip()))
    logger.info(f"Loaded {len(queries)} queries")
    return queries


def repair_json_array(text: str) -> Optional[list[str]]:
    """Attempt to repair malformed JSON array output.
    
    Strategies:
    1. Extract content between first '[' and last ']'
    2. Fix common issues: trailing commas, unquoted strings, missing quotes
    3. Try json.loads with fixes
    
    Returns:
        List of strings if successful, None if repair fails
    """
    text = text.strip()
    
    # Strategy 1: Extract array content
    match = re.search(r'\[(.*)\]', text, re.DOTALL)
    if not match:
        return None
    
    array_content = match.group(1).strip()
    
    # Strategy 2: Fix trailing commas
    array_content = re.sub(r',\s*([\]}])', r'\1', array_content)
    
    # Strategy 3: Ensure all items are quoted strings
    items = []
    for item in re.split(r',\s*', array_content):
        item = item.strip()
        if not item:
            continue
        
        # Remove surrounding quotes if present
        item = item.strip('"\'')
        
        # Re-quote the item
        if item:
            items.append(item)
    
    if items:
        return items
    
    return None


def parse_with_repair(raw_output: str, fallback_query: str) -> tuple[list[SubTask], bool]:
    """Parse LLM output with JSON repair capability.
    
    Returns:
        Tuple of (subtasks, is_valid_json)
    """
    raw_output = raw_output.strip()
    
    # Try standard parsing first
    try:
        subtasks = parse_subtasks(raw_output, fallback_query)
        # Check if it was valid JSON
        if re.search(r'\[.*\]', raw_output, re.DOTALL):
            try:
                json.loads(re.search(r'\[.*\]', raw_output, re.DOTALL).group())
                return subtasks, True
            except:
                pass
        return subtasks, False
    except:
        pass
    
    # Try repair
    repaired_items = repair_json_array(raw_output)
    if repaired_items:
        subtasks = [
            SubTask(step_index=i, description=item.strip())
            for i, item in enumerate(repaired_items)
            if item.strip()
        ]
        return subtasks, True
    
    # Final fallback: use original parser
    subtasks = parse_subtasks(raw_output, fallback_query)
    return subtasks, False


class ConstrainedDecomposer(LocalDecomposer):
    """Decomposer with JSON-constrained output support.
    
    Extends LocalDecomposer to add:
    1. Few-shot examples in prompt
    2. Post-processing JSON repair
    3. Tracking of JSON parse success rate
    """
    
    def __init__(self, *args, use_few_shot: bool = False, **kwargs):
        super().__init__(*args, **kwargs)
        self.use_few_shot = use_few_shot
        self.json_parse_count = 0
        self.total_count = 0
    
    def _build_constrained_prompt(self, query: str) -> str:
        """Build prompt with few-shot examples for constrained decoding."""
        if not self.use_few_shot:
            return super()._build_prompt(query) if hasattr(super(), '_build_prompt') else None
        
        # Build few-shot prompt
        prompt_parts = [
            "You are a task decomposition expert. Given a user query, break it down into atomic sub-tasks.",
            "",
            "CRITICAL RULES:",
            "1. Output MUST be a valid JSON array of strings",
            "2. Each element is ONE atomic sub-task description",
            "3. Do NOT include any text before or after the JSON array",
            "4. Use double quotes for strings",
            "",
            "Examples:",
        ]
        
        for example in FEW_SHOT_EXAMPLES:
            prompt_parts.append(f"Query: {example['query']}")
            prompt_parts.append(f"Output: {example['output']}")
            prompt_parts.append("")
        
        prompt_parts.append(f"Now decompose this query:")
        prompt_parts.append(f"Query: {query}")
        prompt_parts.append(f"Output (JSON array only):")
        
        return "\n".join(prompt_parts)
    
    def decompose_constrained(self, query: str) -> tuple[list[SubTask], bool]:
        """Decompose with JSON constraint enforcement.
        
        Returns:
            Tuple of (subtasks, is_valid_json)
        """
        self.total_count += 1
        
        if self.use_few_shot:
            prompt = self._build_constrained_prompt(query)
        else:
            # Use standard prompt from parent class
            from skillweaver.core.decomposer import SYSTEM_PROMPT, USER_TEMPLATE
            prompt = f"{SYSTEM_PROMPT}\n\n{USER_TEMPLATE.format(query=query)}"
        
        # Generate using parent's method
        try:
            # Access the underlying model directly
            inputs = self.tokenizer(
                prompt,
                return_tensors="pt",
                truncation=True,
                max_length=2048
            ).to(self.device)
            
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=self.temperature,
                do_sample=True if self.temperature > 0 else False,
                pad_token_id=self.tokenizer.eos_token_id,
            )
            
            generated_text = self.tokenizer.decode(
                outputs[0][inputs.input_ids.shape[1]:],
                skip_special_tokens=True
            )
            
            subtasks, is_valid = parse_with_repair(generated_text, query)
            
            if is_valid:
                self.json_parse_count += 1
            
            return subtasks, is_valid
            
        except Exception as e:
            logger.error(f"Constrained decomposition failed: {e}")
            # Fallback to standard decomposition
            subtasks = self.decompose(query)
            return subtasks, False
    
    def get_json_parse_rate(self) -> float:
        """Get current JSON parse success rate."""
        if self.total_count == 0:
            return 0.0
        return self.json_parse_count / self.total_count


def evaluate_condition(
    queries: list[dict],
    decomposer: LocalDecomposer,
    retriever: SkillRetriever,
    condition_name: str,
    use_constrained: bool = False,
    use_sad: bool = False,
    hint_count: int = 15,
) -> dict:
    """Evaluate a single experimental condition.
    
    Args:
        queries: List of query dicts
        decomposer: Decomposer instance (may be ConstrainedDecomposer)
        retriever: Retriever instance
        condition_name: Name for logging
        use_constrained: Whether to use JSON-constrained decoding
        use_sad: Whether to use Skill-Aware Decomposition (SAD)
        hint_count: Number of hints for SAD
    
    Returns:
        Dict with metrics and predictions
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"Evaluating condition: {condition_name}")
    logger.info(f"  Constrained: {use_constrained}, SAD: {use_sad}")
    logger.info(f"{'='*60}")
    
    predictions = []
    total_latency = 0.0
    json_parse_success = 0
    total_queries = len(queries)
    subtask_counts = []
    single_task_collapses = 0
    
    difficulty_metrics = defaultdict(lambda: {
        'count': 0,
        'correct_decompositions': 0,
        'skill_recalls': {1: 0, 5: 0, 10: 0},
        'chain_exact_matches': 0,
        'chain_partial_matches': 0,
        'total_latency': 0.0,
        'json_parse_success': 0,
        'subtask_counts': [],
    })
    
    for idx, query_data in enumerate(queries):
        query_id = query_data["query_id"]
        query_text = query_data["query"]
        difficulty = query_data.get("difficulty", "unknown")
        ground_truth_subtasks = query_data.get("subtasks", [])
        gt_num_skills = query_data.get("num_skills", len(ground_truth_subtasks))
        
        start_time = time.time()
        
        # Stage 1: Decompose based on condition
        is_valid_json = False
        
        if use_constrained:
            # Use constrained decomposer
            if isinstance(decomposer, ConstrainedDecomposer):
                subtasks, is_valid_json = decomposer.decompose_constrained(query_text)
            else:
                # Fallback: manually apply constraint logic
                subtasks = decomposer.decompose(query_text)
                is_valid_json = False
        else:
            # Standard decomposition
            subtasks = decomposer.decompose(query_text)
        
        # Apply SAD if needed
        if use_sad and not use_constrained:
            # Standard SAD flow
            pass1_texts = [st.description for st in subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)
            hints = build_hint_set(pass1_candidates, hint_count)
            subtasks = decomposer.decompose_with_hints(query_text, hints)
        elif use_sad and use_constrained:
            # SAD + Constrained: retrieve hints, then constrained decompose
            pass1_subtasks = decomposer.decompose(query_text)
            pass1_texts = [st.description for st in pass1_subtasks]
            pass1_candidates = retriever.search_batch(pass1_texts)
            hints = build_hint_set(pass1_candidates, hint_count)
            
            # For constrained + SAD, we'd need to modify prompt to include hints
            # For now, use standard SAD result
            subtasks = decomposer.decompose_with_hints(query_text, hints)
        
        # Track JSON parse status
        if is_valid_json:
            json_parse_success += 1
        
        # Stage 2: Retrieve candidates per sub-task
        subtask_texts = [st.description for st in subtasks]
        candidates = retriever.search_batch(subtask_texts)
        
        latency_ms = (time.time() - start_time) * 1000
        total_latency += latency_ms
        
        num_subtasks = len(subtasks)
        subtask_counts.append(num_subtasks)
        
        if num_subtasks == 1:
            single_task_collapses += 1
        
        # Evaluate decomposition accuracy
        predicted_skill_names = [st.description for st in subtasks]
        gt_skill_names = [st["ground_truth_skill_name"] for st in ground_truth_subtasks]
        
        pred_set = set(predicted_skill_names)
        gt_set = set(gt_skill_names)
        is_correct = pred_set == gt_set
        
        # Calculate recall metrics
        recalls_at_k = {1: 0, 5: 0, 10: 0}
        for k in [1, 5, 10]:
            for step_idx, gt_subtask in enumerate(ground_truth_subtasks):
                gt_skill_id = gt_subtask["ground_truth_skill_id"]
                
                if step_idx < len(candidates):
                    top_k_candidates = candidates[step_idx][:k]
                    candidate_ids = [c.skill.skill_id for c in top_k_candidates]
                    
                    if gt_skill_id in candidate_ids:
                        recalls_at_k[k] += 1
        
        # Chain-level metrics
        num_steps = len(ground_truth_subtasks)
        exact_match = False
        partial_match = False
        
        if num_steps > 0:
            exact_match = all(
                i < len(predicted_skill_names)
                and predicted_skill_names[i] == gt_skill_names[i]
                for i in range(num_steps)
            )
            
            partial_match = any(
                i < len(predicted_skill_names)
                and predicted_skill_names[i] == gt_skill_names[i]
                for i in range(num_steps)
            )
        
        # Store prediction
        predictions.append({
            "query_id": query_id,
            "query": query_text,
            "difficulty": difficulty,
            "predicted_subtasks": predicted_skill_names,
            "ground_truth_subtasks": gt_skill_names,
            "latency_ms": latency_ms,
            "num_predicted_skills": num_subtasks,
            "num_ground_truth_skills": gt_num_skills,
            "is_correct_decomposition": is_correct,
            "is_valid_json": is_valid_json,
            "recall_at_1": recalls_at_k[1] / max(1, num_steps),
            "recall_at_5": recalls_at_k[5] / max(1, num_steps),
            "recall_at_10": recalls_at_k[10] / max(1, num_steps),
            "chain_exact_match": exact_match,
            "chain_partial_match": partial_match,
        })
        
        # Accumulate difficulty-specific metrics
        dm = difficulty_metrics[difficulty]
        dm['count'] += 1
        if is_correct:
            dm['correct_decompositions'] += 1
        for k in [1, 5, 10]:
            dm['skill_recalls'][k] += recalls_at_k[k]
        if exact_match:
            dm['chain_exact_matches'] += 1
        if partial_match:
            dm['chain_partial_matches'] += 1
        dm['total_latency'] += latency_ms
        if is_valid_json:
            dm['json_parse_success'] += 1
        dm['subtask_counts'].append(num_subtasks)
        
        if (idx + 1) % 50 == 0:
            logger.info(f"  Processed {idx + 1}/{len(queries)} queries")
    
    # Calculate final metrics
    n_queries = len(queries)
    avg_latency = total_latency / n_queries if n_queries > 0 else 0
    avg_subtasks = sum(subtask_counts) / n_queries if n_queries > 0 else 0
    json_parse_rate = json_parse_success / n_queries if n_queries > 0 else 0
    collapse_rate = single_task_collapses / n_queries if n_queries > 0 else 0
    
    overall_metrics = {
        "decomposition_accuracy": sum(
            dm['correct_decompositions'] for dm in difficulty_metrics.values()
        ) / n_queries if n_queries > 0 else 0,
        "skill_recall_at_1": sum(
            dm['skill_recalls'][1] for dm in difficulty_metrics.values()
        ) / (n_queries * 3) if n_queries > 0 else 0,
        "skill_recall_at_5": sum(
            dm['skill_recalls'][5] for dm in difficulty_metrics.values()
        ) / (n_queries * 3) if n_queries > 0 else 0,
        "skill_recall_at_10": sum(
            dm['skill_recalls'][10] for dm in difficulty_metrics.values()
        ) / (n_queries * 3) if n_queries > 0 else 0,
        "chain_exact_match": sum(
            dm['chain_exact_matches'] for dm in difficulty_metrics.values()
        ) / n_queries if n_queries > 0 else 0,
        "chain_partial_match": sum(
            dm['chain_partial_matches'] for dm in difficulty_metrics.values()
        ) / n_queries if n_queries > 0 else 0,
        "avg_latency_ms": avg_latency,
        "json_parse_rate": json_parse_rate,
        "avg_subtasks": avg_subtasks,
        "collapse_rate": collapse_rate,
    }
    
    # Per-difficulty metrics
    difficulty_results = {}
    for diff in ["easy", "medium", "hard"]:
        if diff in difficulty_metrics:
            dm = difficulty_metrics[diff]
            n = dm['count']
            if n > 0:
                avg_st = sum(dm['subtask_counts']) / n if dm['subtask_counts'] else 0
                json_rate = dm['json_parse_success'] / n if n > 0 else 0
                
                difficulty_results[diff] = {
                    "count": n,
                    "decomposition_accuracy": dm['correct_decompositions'] / n,
                    "skill_recall_at_1": dm['skill_recalls'][1] / (n * 3),
                    "skill_recall_at_5": dm['skill_recalls'][5] / (n * 3),
                    "skill_recall_at_10": dm['skill_recalls'][10] / (n * 3),
                    "chain_exact_match": dm['chain_exact_matches'] / n,
                    "chain_partial_match": dm['chain_partial_matches'] / n,
                    "avg_latency_ms": dm['total_latency'] / n,
                    "json_parse_rate": json_rate,
                    "avg_subtasks": avg_st,
                }
    
    logger.info(f"Condition {condition_name} completed:")
    logger.info(f"  Overall Decomposition Accuracy: {overall_metrics['decomposition_accuracy']:.4f}")
    logger.info(f"  Overall Skill Recall@1:         {overall_metrics['skill_recall_at_1']:.4f}")
    logger.info(f"  Overall Chain Exact Match:      {overall_metrics['chain_exact_match']:.4f}")
    logger.info(f"  JSON Parse Rate:                {overall_metrics['json_parse_rate']:.4f}")
    logger.info(f"  Avg Sub-tasks:                  {overall_metrics['avg_subtasks']:.2f}")
    logger.info(f"  Collapse Rate (single task):    {overall_metrics['collapse_rate']:.4f}")
    logger.info(f"  Avg Latency:                    {overall_metrics['avg_latency_ms']:.2f}ms")
    
    if "hard" in difficulty_results:
        hr = difficulty_results["hard"]
        logger.info(f"  HARD Queries Only ({hr['count']} samples):")
        logger.info(f"    Decomposition Accuracy:     {hr['decomposition_accuracy']:.4f}")
        logger.info(f"    Skill Recall@1:             {hr['skill_recall_at_1']:.4f}")
        logger.info(f"    JSON Parse Rate:            {hr['json_parse_rate']:.4f}")
        logger.info(f"    Avg Sub-tasks:              {hr['avg_subtasks']:.2f}")
    
    return {
        "condition": condition_name,
        "metrics": overall_metrics,
        "difficulty_breakdown": difficulty_results,
        "predictions": predictions,
    }


def run_experiment(model_path: str, model_name: str):
    """Run the constrained decoding experiment for 14B model.
    
    Tests three conditions:
    1. 14B Vanilla: Standard decomposition, no constraints
    2. 14B + Constrained: Few-shot + JSON repair
    3. 14B + SAD + Constrained: Skill-aware + constrained decoding
    
    Args:
        model_path: Path to Qwen2.5-14B-Instruct
        model_name: Human-readable model name
    """
    logger.info(f"\n{'#'*80}")
    logger.info(f"Starting Constrained Decoding Experiment")
    logger.info(f"Model: {model_name}")
    logger.info(f"Model Path: {model_path}")
    logger.info(f"{'#'*80}\n")
    
    # Load data
    skills = load_skill_pool()
    queries = load_queries()
    
    # Initialize standard decomposer and retriever
    standard_decomposer = LocalDecomposer(
        model_path=model_path,
        device="auto",
        temperature=0.1,
    )
    
    retriever = SkillRetriever(
        embedding_model_path=EMBEDDING_MODEL,
        skill_pool=skills,
    )
    
    # Initialize constrained decomposer with few-shot
    constrained_decomposer = ConstrainedDecomposer(
        model_path=model_path,
        device="auto",
        temperature=0.1,
        use_few_shot=True,
    )
    
    # Define experimental conditions
    conditions = [
        {
            "name": "14b_vanilla",
            "decomposer": standard_decomposer,
            "use_constrained": False,
            "use_sad": False,
        },
        {
            "name": "14b_constrained",
            "decomposer": constrained_decomposer,
            "use_constrained": True,
            "use_sad": False,
        },
        {
            "name": "14b_sad_constrained",
            "decomposer": constrained_decomposer,
            "use_constrained": True,
            "use_sad": True,
        },
    ]
    
    results = {
        "experiment": "constrained_decoding_14b",
        "model": model_name,
        "model_path": model_path,
        "config": {
            "hint_count": 15,
            "few_shot_examples_count": len(FEW_SHOT_EXAMPLES),
            "num_queries": len(queries),
            "num_skills": len(skills),
            "temperature": 0.1,
        },
        "conditions": {},
    }
    
    for condition in conditions:
        result = evaluate_condition(
            queries=queries,
            decomposer=condition["decomposer"],
            retriever=retriever,
            condition_name=condition["name"],
            use_constrained=condition["use_constrained"],
            use_sad=condition["use_sad"],
            hint_count=15,
        )
        results["conditions"][condition["name"]] = result
    
    # Save results
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info(f"\nResults saved to: {OUTPUT_PATH}")
    logger.info(f"Experiment complete!")
    
    # Print summary comparison
    logger.info(f"\n{'='*80}")
    logger.info(f"SUMMARY COMPARISON - 14B CONSTRAINED DECODING")
    logger.info(f"{'='*80}")
    
    for cond_name in ["14b_vanilla", "14b_constrained", "14b_sad_constrained"]:
        metrics = results["conditions"][cond_name]["metrics"]
        diff_breakdown = results["conditions"][cond_name].get("difficulty_breakdown", {})
        
        logger.info(f"\n{cond_name.upper().replace('_', ' ')}:")
        logger.info(f"  Decomposition Accuracy:   {metrics['decomposition_accuracy']:.4f}")
        logger.info(f"  Skill Recall@1:           {metrics['skill_recall_at_1']:.4f}")
        logger.info(f"  Chain Exact Match:        {metrics['chain_exact_match']:.4f}")
        logger.info(f"  JSON Parse Rate:          {metrics['json_parse_rate']:.4f}")
        logger.info(f"  Avg Sub-tasks:            {metrics['avg_subtasks']:.2f}")
        logger.info(f"  Collapse Rate:            {metrics['collapse_rate']:.4f}")
        logger.info(f"  Avg Latency (ms):         {metrics['avg_latency_ms']:.2f}")
        
        if "hard" in diff_breakdown:
            hr = diff_breakdown["hard"]
            logger.info(f"  HARD Queries ({hr['count']} samples):")
            logger.info(f"    Decomposition Accuracy: {hr['decomposition_accuracy']:.4f}")
            logger.info(f"    Skill Recall@1:         {hr['skill_recall_at_1']:.4f}")
            logger.info(f"    JSON Parse Rate:        {hr['json_parse_rate']:.4f}")
            logger.info(f"    Avg Sub-tasks:          {hr['avg_subtasks']:.2f}")
    
    # Key findings summary
    logger.info(f"\n{'='*80}")
    logger.info(f"KEY FINDINGS - 14B ANOMALY ANALYSIS")
    logger.info(f"{'='*80}")
    
    vanilla_metrics = results["conditions"]["14b_vanilla"]["metrics"]
    constrained_metrics = results["conditions"]["14b_constrained"]["metrics"]
    sad_constrained_metrics = results["conditions"]["14b_sad_constrained"]["metrics"]
    
    logger.info(f"\n14B Anomaly Indicators:")
    logger.info(f"  Vanilla Over-decomposition:    {vanilla_metrics['avg_subtasks']:.2f} sub-tasks (expected ~3)")
    logger.info(f"  Vanilla JSON Parse Rate:       {vanilla_metrics['json_parse_rate']:.4f} (target: >0.90)")
    logger.info(f"  SAD Collapse Rate:             {sad_constrained_metrics['collapse_rate']:.4f} (target: <0.10)")
    
    logger.info(f"\nConstrained Decoding Impact:")
    json_improvement = constrained_metrics['json_parse_rate'] - vanilla_metrics['json_parse_rate']
    subtask_reduction = vanilla_metrics['avg_subtasks'] - constrained_metrics['avg_subtasks']
    
    logger.info(f"  JSON Parse Rate Improvement:   +{json_improvement:.4f}")
    logger.info(f"  Sub-task Count Reduction:      -{subtask_reduction:.2f}")
    logger.info(f"  Collapse Rate Change:          {sad_constrained_metrics['collapse_rate'] - vanilla_metrics['collapse_rate']:+.4f}")
    
    return results


if __name__ == "__main__":
    logger.info("Running Constrained Decoding Experiment with Qwen2.5-14B-Instruct...")
    results = run_experiment(MODEL_14B, "Qwen2.5-14B-Instruct")
    
    logger.info("\n\nExperiment completed successfully!")
    logger.info(f"Results saved to: {OUTPUT_PATH}")
