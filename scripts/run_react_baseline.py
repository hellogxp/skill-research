#!/usr/bin/env python3
"""ReAct-style baseline experiment for SkillWeaver.

This script implements a ReAct/Iterative baseline where the LLM directly selects
skills from the complete skill pool without decompose-then-retrieve architecture.
This addresses reviewer R3-P2's requirement for a compositional reasoning baseline.

Key features:
- Provides full skill pool (60 skills) to LLM in prompt
- LLM outputs JSON array of skill names in order
- Evaluates on 300 compositional queries using 7B and 14B models
- Computes recall, exact match, and latency metrics
- Saves results to results_v3/react_baseline_experiment.json
"""

import json
import time
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

# Add skillweaver to path for imports
WORKSPACE = Path("/mnt/workspace")
sys.path.insert(0, str(WORKSPACE / "skillweaver" / "src"))

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
except ImportError:
    print("Warning: transformers/torch not available. Using mock mode.")
    torch = None


@dataclass
class ExperimentConfig:
    """Configuration for ReAct baseline experiment."""
    model_path_7b: str = "/mnt/workspace/models/Qwen/Qwen2___5-7B-Instruct"
    model_path_14b: str = "/mnt/workspace/models/Qwen/Qwen2___5-14B-Instruct"
    benchmark_path: str = "/mnt/workspace/skill-research/data/benchmark_v3/compositional_queries.jsonl"
    skill_pool_path: str = "/mnt/workspace/skill-research/data/processed_v3/skill_pool.jsonl"
    output_path: str = "/mnt/workspace/skill-research/results_v3/react_baseline_experiment.json"
    max_new_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    batch_size: int = 1  # Process one query at a time for simplicity


def load_skill_pool(skill_pool_path: str) -> List[Dict[str, Any]]:
    """Load skill pool from JSONL file."""
    skills = []
    with open(skill_pool_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                skills.append(json.loads(line))
    print(f"Loaded {len(skills)} skills from {skill_pool_path}")
    return skills


def load_queries(benchmark_path: str) -> List[Dict[str, Any]]:
    """Load compositional queries from JSONL file."""
    queries = []
    with open(benchmark_path, 'r', encoding='utf-8') as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line))
    print(f"Loaded {len(queries)} queries from {benchmark_path}")
    return queries


def format_skill_list(skills: List[Dict[str, Any]]) -> str:
    """Format skill list for prompt."""
    skill_descriptions = []
    for i, skill in enumerate(skills, 1):
        name = skill.get('name', skill.get('skill_id', 'unknown'))
        description = skill.get('description', 'No description available')
        skill_descriptions.append(f"{i}. {name}: {description}")
    return "\n".join(skill_descriptions)


def build_react_prompt(query: str, skill_list_str: str) -> str:
    """Build ReAct-style prompt for skill selection.
    
    The prompt instructs the LLM to analyze the query and select appropriate
    skills from the provided skill pool, outputting them as a JSON array.
    """
    system_prompt = """You are a skill routing expert. Given a user query and a list of available skills, determine which skills are needed and in what order to complete the task.

Instructions:
1. Analyze the user query carefully
2. Select the most relevant skills from the provided skill list
3. Output the skills in the order they should be executed
4. Return ONLY a JSON array of skill names, nothing else
5. If no skills are relevant, return an empty array []

Example output format:
["skill_name_1", "skill_name_2", "skill_name_3"]
"""
    
    user_prompt = f"""Available Skills:
{skill_list_str}

User Query: {query}

Please output the skill names as a JSON array:"""
    
    return system_prompt + "\n\n" + user_prompt


def parse_llm_output(output_text: str) -> List[str]:
    """Parse LLM output to extract skill names.
    
    Handles various output formats:
    - Pure JSON array
    - JSON with markdown code blocks
    - Text with embedded JSON
    """
    try:
        # Try to find JSON array in the output
        text = output_text.strip()
        
        # Remove markdown code blocks if present
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0]
        elif "```" in text:
            text = text.split("```")[1].split("```")[0]
        
        # Find JSON array pattern
        start_idx = text.find('[')
        end_idx = text.rfind(']')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx+1]
            skill_names = json.loads(json_str)
            if isinstance(skill_names, list):
                return [str(name).strip() for name in skill_names if name]
        
        # Fallback: try parsing entire text as JSON
        skill_names = json.loads(text)
        if isinstance(skill_names, list):
            return [str(name).strip() for name in skill_names if name]
            
    except (json.JSONDecodeError, IndexError, KeyError) as e:
        print(f"Warning: Failed to parse LLM output: {e}")
        print(f"Output was: {output_text[:200]}...")
    
    return []


def compute_metrics(predictions: List[Dict], ground_truths: List[Dict]) -> Dict[str, float]:
    """Compute evaluation metrics for ReAct baseline.
    
    Metrics:
    - skill_recall_at_k: Recall of ground truth skills in top-k predictions
    - chain_exact_match: Exact match of skill sequence
    - chain_partial_match: Partial match (subset) of skill sequence
    - avg_latency_ms: Average inference latency
    """
    total_queries = len(predictions)
    if total_queries == 0:
        return {}
    
    # Initialize metric accumulators
    recall_at_1_count = 0
    recall_at_3_count = 0
    recall_at_5_count = 0
    exact_match_count = 0
    partial_match_count = 0
    total_latency = 0.0
    
    for pred, gt in zip(predictions, ground_truths):
        predicted_skills = pred.get('predicted_skills', [])
        gt_skills = gt.get('ground_truth_skills', [])
        latency = pred.get('latency_ms', 0)
        
        total_latency += latency
        
        # Compute recall at k
        gt_set = set(gt_skills)
        if len(predicted_skills) > 0:
            # Recall@1
            if len(gt_set.intersection(set(predicted_skills[:1]))) > 0:
                recall_at_1_count += 1
            # Recall@3
            if len(gt_set.intersection(set(predicted_skills[:3]))) > 0:
                recall_at_3_count += 1
            # Recall@5
            if len(gt_set.intersection(set(predicted_skills[:5]))) > 0:
                recall_at_5_count += 1
        
        # Exact match (order matters)
        if predicted_skills == gt_skills:
            exact_match_count += 1
        
        # Partial match (all GT skills present, order doesn't matter)
        if len(gt_set) > 0 and gt_set.issubset(set(predicted_skills)):
            partial_match_count += 1
    
    metrics = {
        'skill_recall_at_1': recall_at_1_count / total_queries,
        'skill_recall_at_3': recall_at_3_count / total_queries,
        'skill_recall_at_5': recall_at_5_count / total_queries,
        'chain_exact_match': exact_match_count / total_queries,
        'chain_partial_match': partial_match_count / total_queries,
        'avg_latency_ms': total_latency / total_queries,
    }
    
    return metrics


class ReActBaselineRunner:
    """Main runner for ReAct baseline experiment."""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.skills = load_skill_pool(config.skill_pool_path)
        self.queries = load_queries(config.benchmark_path)
        self.skill_list_str = format_skill_list(self.skills)
        self.models = {}
    
    def load_model(self, model_path: str, model_name: str):
        """Load a HuggingFace model."""
        if torch is None:
            print(f"Mock mode: Skipping model loading for {model_name}")
            return None
        
        print(f"Loading model: {model_name} from {model_path}")
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        model = AutoModelForCausalLM.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True
        )
        self.models[model_name] = {'tokenizer': tokenizer, 'model': model}
        print(f"Model {model_name} loaded successfully")
    
    def generate_with_model(self, prompt: str, model_name: str) -> tuple[str, float]:
        """Generate response using specified model. Returns (text, latency_ms)."""
        start_time = time.time()
        
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not loaded")
        
        tokenizer = self.models[model_name]['tokenizer']
        model = self.models[model_name]['model']
        
        # Tokenize input
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=self.config.max_new_tokens,
                temperature=self.config.temperature,
                top_p=self.config.top_p,
                do_sample=True,
                pad_token_id=tokenizer.eos_token_id
            )
        
        # Decode output
        generated_text = tokenizer.decode(outputs[0][inputs.input_ids.shape[1]:], skip_special_tokens=True)
        latency_ms = (time.time() - start_time) * 1000
        
        return generated_text, latency_ms
    
    def run_query(self, query: Dict, model_name: str) -> Dict:
        """Run a single query through ReAct baseline."""
        query_text = query['query']
        prompt = build_react_prompt(query_text, self.skill_list_str)
        
        # Generate response
        output_text, latency_ms = self.generate_with_model(prompt, model_name)
        
        # Parse predicted skills
        predicted_skills = parse_llm_output(output_text)
        
        # Extract ground truth skills
        gt_skills = [subtask['ground_truth_skill_name'] for subtask in query.get('subtasks', [])]
        
        result = {
            'query_id': query['query_id'],
            'query': query_text,
            'difficulty': query.get('difficulty', 'unknown'),
            'num_gt_skills': len(gt_skills),
            'predicted_skills': predicted_skills,
            'ground_truth_skills': gt_skills,
            'llm_raw_output': output_text[:500],  # Truncate for storage
            'latency_ms': latency_ms,
        }
        
        return result
    
    def run_experiment(self, model_name: str, model_path: str) -> Dict:
        """Run full experiment on all queries with specified model."""
        print(f"\n{'='*60}")
        print(f"Running ReAct baseline experiment with {model_name}")
        print(f"{'='*60}\n")
        
        # Load model
        self.load_model(model_path, model_name)
        
        # Run queries
        predictions = []
        total = len(self.queries)
        
        for i, query in enumerate(self.queries, 1):
            try:
                result = self.run_query(query, model_name)
                predictions.append(result)
                
                if i % 10 == 0 or i == total:
                    print(f"Progress: {i}/{total} queries processed")
                    
            except Exception as e:
                print(f"Error processing query {query.get('query_id', 'unknown')}: {e}")
                continue
        
        # Compute metrics
        ground_truths = [
            {
                'ground_truth_skills': [
                    subtask['ground_truth_skill_name'] 
                    for subtask in q.get('subtasks', [])
                ]
            }
            for q in self.queries
        ]
        
        # Align predictions with ground truths
        aligned_predictions = []
        aligned_ground_truths = []
        for pred in predictions:
            query_id = pred['query_id']
            # Find corresponding ground truth
            for gt in ground_truths:
                # Match by index (simplified - assumes same order)
                idx = int(query_id.split('_')[1])
                if idx < len(ground_truths):
                    aligned_predictions.append(pred)
                    aligned_ground_truths.append(ground_truths[idx])
                    break
        
        metrics = compute_metrics(aligned_predictions, aligned_ground_truths)
        
        # Build experiment result
        experiment_result = {
            'experiment': f'react_baseline_{model_name}',
            'config': {
                'model': model_name,
                'model_path': model_path,
                'temperature': self.config.temperature,
                'top_p': self.config.top_p,
                'max_new_tokens': self.config.max_new_tokens,
                'baseline_type': 'react_iterative',
                'description': 'LLM directly selects skills from full skill pool without decomposition'
            },
            'metrics': metrics,
            'num_queries_evaluated': len(predictions),
            'predictions': predictions,
        }
        
        return experiment_result
    
    def save_results(self, results: List[Dict]):
        """Save experiment results to JSON file."""
        output_path = Path(self.config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        combined_results = {
            'experiments': results,
            'summary': {
                'total_experiments': len(results),
                'models_tested': [r['config']['model'] for r in results],
                'timestamp': time.strftime('%Y-%m-%d %H:%M:%S'),
            }
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(combined_results, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to {output_path}")


def main():
    """Main entry point."""
    print("="*60)
    print("SkillWeaver ReAct Baseline Experiment")
    print("="*60)
    
    # Create configuration
    config = ExperimentConfig()
    
    # Create runner
    runner = ReActBaselineRunner(config)
    
    # Run experiments for both models
    results = []
    
    # Experiment 1: Qwen2.5-7B-Instruct
    print("\n" + "="*60)
    print("Experiment 1: Qwen2.5-7B-Instruct")
    print("="*60)
    result_7b = runner.run_experiment(
        model_name="Qwen2.5-7B-Instruct",
        model_path=config.model_path_7b
    )
    results.append(result_7b)
    
    # Print summary for 7B
    print(f"\n7B Model Summary:")
    print(f"  Skill Recall@1: {result_7b['metrics'].get('skill_recall_at_1', 0):.4f}")
    print(f"  Skill Recall@3: {result_7b['metrics'].get('skill_recall_at_3', 0):.4f}")
    print(f"  Skill Recall@5: {result_7b['metrics'].get('skill_recall_at_5', 0):.4f}")
    print(f"  Chain Exact Match: {result_7b['metrics'].get('chain_exact_match', 0):.4f}")
    print(f"  Chain Partial Match: {result_7b['metrics'].get('chain_partial_match', 0):.4f}")
    print(f"  Avg Latency: {result_7b['metrics'].get('avg_latency_ms', 0):.2f} ms")
    
    # Experiment 2: Qwen2.5-14B-Instruct
    print("\n" + "="*60)
    print("Experiment 2: Qwen2.5-14B-Instruct")
    print("="*60)
    result_14b = runner.run_experiment(
        model_name="Qwen2.5-14B-Instruct",
        model_path=config.model_path_14b
    )
    results.append(result_14b)
    
    # Print summary for 14B
    print(f"\n14B Model Summary:")
    print(f"  Skill Recall@1: {result_14b['metrics'].get('skill_recall_at_1', 0):.4f}")
    print(f"  Skill Recall@3: {result_14b['metrics'].get('skill_recall_at_3', 0):.4f}")
    print(f"  Skill Recall@5: {result_14b['metrics'].get('skill_recall_at_5', 0):.4f}")
    print(f"  Chain Exact Match: {result_14b['metrics'].get('chain_exact_match', 0):.4f}")
    print(f"  Chain Partial Match: {result_14b['metrics'].get('chain_partial_match', 0):.4f}")
    print(f"  Avg Latency: {result_14b['metrics'].get('avg_latency_ms', 0):.2f} ms")
    
    # Save all results
    runner.save_results(results)
    
    print("\n" + "="*60)
    print("Experiment completed successfully!")
    print("="*60)


if __name__ == "__main__":
    main()
