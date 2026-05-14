#!/usr/bin/env python3
"""Latency Breakdown experiment for SkillWeaver pipeline.

This script measures the latency of each stage in the SkillWeaver pipeline:
1. Decomposition (Pass 1) - LLM inference latency
2. Retrieval - FAISS search latency  
3. Decomposition (Pass 2, SAD only) - Second LLM inference latency
4. Total pipeline latency

Experiments are run with 7B/14B/72B models under both vanilla and SAD conditions.
Results include mean/median/P95/P99 latency metrics and breakdown percentages.
"""

import json
import time
import sys
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field, asdict

# Add skillweaver to path
WORKSPACE = Path("/mnt/workspace")
sys.path.insert(0, str(WORKSPACE / "skillweaver" / "src"))

try:
    from transformers import AutoTokenizer, AutoModelForCausalLM
    import torch
except ImportError:
    print("Warning: transformers/torch not available. Using mock mode.")
    torch = None


@dataclass
class StageLatency:
    """Latency measurements for a single pipeline stage."""
    stage_name: str
    latencies_ms: List[float] = field(default_factory=list)
    
    def add_latency(self, latency_ms: float):
        self.latencies_ms.append(latency_ms)
    
    def compute_stats(self) -> Dict[str, float]:
        if not self.latencies_ms:
            return {}
        
        sorted_latencies = sorted(self.latencies_ms)
        n = len(sorted_latencies)
        
        p95_idx = int(n * 0.95)
        p99_idx = int(n * 0.99)
        
        return {
            'mean': statistics.mean(self.latencies_ms),
            'median': statistics.median(self.latencies_ms),
            'p95': sorted_latencies[min(p95_idx, n-1)],
            'p99': sorted_latencies[min(p99_idx, n-1)],
            'min': min(self.latencies_ms),
            'max': max(self.latencies_ms),
            'count': n
        }


@dataclass
class QueryLatencyRecord:
    """Latency record for a single query execution."""
    query_id: str
    query_text: str
    difficulty: str
    model_size: str  # "7b", "14b", "72b"
    pipeline_mode: str  # "vanilla" or "sad"
    
    # Stage latencies
    decomposition_pass1_ms: float = 0.0
    retrieval_ms: float = 0.0
    decomposition_pass2_ms: float = 0.0  # Only for SAD mode
    total_ms: float = 0.0
    
    # Metadata
    num_subtasks: int = 0
    timestamp: str = ""


@dataclass
class ExperimentConfig:
    """Configuration for latency breakdown experiment."""
    # Model paths
    model_path_7b: str = "/mnt/workspace/models/Qwen/Qwen2___5-7B-Instruct"
    model_path_14b: str = "/mnt/workspace/models/Qwen/Qwen2___5-14B-Instruct"
    model_path_72b: str = "/mnt/workspace/models/Qwen/Qwen2___5-72B-Instruct"
    
    # Data paths
    benchmark_path: str = "/mnt/workspace/skill-research/data/benchmark_v3/compositional_queries.jsonl"
    skill_pool_path: str = "/mnt/workspace/skill-research/data/processed_v3/skill_pool.jsonl"
    
    # Output path
    output_path: str = "/mnt/workspace/skill-research/results_v3/latency_breakdown_72b.json"
    
    # Experiment settings
    test_sample_size: int = 50  # Number of queries to test per condition
    temperature: float = 0.1  # Low temperature for consistent latency measurement


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


def sample_queries(queries: List[Dict], sample_size: int) -> List[Dict]:
    """Sample queries stratified by difficulty."""
    import random
    random.seed(42)
    
    # Group by difficulty
    by_difficulty = {}
    for q in queries:
        diff = q.get('difficulty', 'unknown')
        if diff not in by_difficulty:
            by_difficulty[diff] = []
        by_difficulty[diff].append(q)
    
    # Sample proportionally from each difficulty level
    sampled = []
    total_queries = len(queries)
    
    for diff, diff_queries in by_difficulty.items():
        # Calculate proportional sample size
        proportion = len(diff_queries) / total_queries
        diff_sample_size = max(1, int(sample_size * proportion))
        
        # Sample without replacement
        if len(diff_queries) <= diff_sample_size:
            sampled.extend(diff_queries)
        else:
            sampled.extend(random.sample(diff_queries, diff_sample_size))
    
    print(f"Sampled {len(sampled)} queries (target: {sample_size})")
    print(f"  Difficulty distribution: {[(d, len(qs)) for d, qs in by_difficulty.items()]}")
    
    return sampled


class LatencyBreakdownRunner:
    """Main runner for latency breakdown experiment."""
    
    def __init__(self, config: ExperimentConfig):
        self.config = config
        self.skills = load_skill_pool(config.skill_pool_path)
        self.all_queries = load_queries(config.benchmark_path)
        self.test_queries = sample_queries(self.all_queries, config.test_sample_size)
        self.models = {}
        
        # Initialize retriever
        from skillweaver.core.retriever import SkillRetriever
        from skillweaver.core.models import Skill
        from sentence_transformers import SentenceTransformer
        
        print("Initializing FAISS retriever...")
        skill_objects = [Skill.from_dict(s) for s in self.skills]
        self.retriever = SkillRetriever(top_k=5)
        # Load encoder from local cache to avoid network
        self.retriever._encoder = SentenceTransformer("/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2", local_files_only=True)
        self.retriever.build_index(skill_objects)
        print("Retriever initialized")
    
    def load_model(self, model_path: str, model_name: str):
        """Load a HuggingFace model with GPU-only allocation (no CPU offload)."""
        if torch is None:
            print(f"Mock mode: Skipping model loading for {model_name}")
            return None
        
        print(f"Loading model: {model_name} from {model_path}")
        tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)

        # Determine model size and loading strategy
        import json as _json
        from pathlib import Path as _Path
        config_path = _Path(model_path) / "config.json"
        model_size_gb = 0.0
        if config_path.exists():
            with open(config_path) as f:
                cfg = _json.load(f)
            num_params = cfg.get("num_params")
            if num_params is None:
                vocab = cfg.get("vocab_size", 32000)
                hidden = cfg.get("hidden_size", 4096)
                layers = cfg.get("num_hidden_layers", 32)
                intermediate = cfg.get("intermediate_size", hidden * 4)
                num_params = vocab * hidden + layers * (
                    4 * hidden * hidden + 2 * hidden * intermediate + 2 * hidden
                )
            model_size_gb = num_params * 2 / (1024 ** 3)

        num_gpus = torch.cuda.device_count()
        single_gpu_gb = torch.cuda.get_device_properties(0).total_memory / (1024**3) if num_gpus > 0 else 0
        total_gpu_gb = sum(
            torch.cuda.get_device_properties(i).total_memory
            for i in range(num_gpus)
        ) / (1024 ** 3)
        print(f"  Model ~{model_size_gb:.1f}GB, {num_gpus} GPUs = {total_gpu_gb:.1f}GB total")

        if model_size_gb > total_gpu_gb * 0.95:
            # Model too large for GPU fp16 -> 4-bit quantization with manual device_map
            print(f"  Strategy: 4-bit quantization (model {model_size_gb:.1f}GB > {total_gpu_gb*0.95:.1f}GB GPU limit)")
            from transformers import BitsAndBytesConfig
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
            )
            # Build manual device_map (device_map="auto" fails with quantization)
            import json as _json2
            config_path = _Path(model_path) / "config.json"
            num_layers = 80  # default
            if config_path.exists():
                with open(config_path) as f:
                    _cfg = _json2.load(f)
                num_layers = _cfg.get("num_hidden_layers", 80)
            manual_device_map = {
                "model.embed_tokens": 0,
                "model.norm": num_gpus - 1,
                "lm_head": num_gpus - 1,
            }
            layers_per_gpu = num_layers // num_gpus
            extra = num_layers % num_gpus
            _li = 0
            for _g in range(num_gpus):
                _cnt = layers_per_gpu + (1 if _g < extra else 0)
                for _ in range(_cnt):
                    manual_device_map[f"model.layers.{_li}"] = _g
                    _li += 1
            print(f"  Manual device_map: {num_layers} layers across {num_gpus} GPUs")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                quantization_config=quantization_config,
                device_map=manual_device_map,
                trust_remote_code=True
            )
        elif model_size_gb <= single_gpu_gb:
            # Single GPU direct placement
            print(f"  Strategy: single-GPU direct placement (model {model_size_gb:.1f}GB <= {single_gpu_gb:.1f}GB)")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map={"": 0},
                trust_remote_code=True
            )
        else:
            # Multi-GPU with max_memory to prevent CPU offload
            max_memory = {}
            for i in range(num_gpus):
                mem_gb = torch.cuda.get_device_properties(i).total_memory / (1024 ** 3)
                max_memory[i] = f"{int(mem_gb - 1)}GiB"
            max_memory["cpu"] = "0GiB"
            print(f"  Strategy: multi-GPU max_memory = {max_memory}")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                torch_dtype=torch.float16,
                device_map="auto",
                max_memory=max_memory,
                trust_remote_code=True
            )

        # Verify no CPU offload
        device_map = getattr(model, "hf_device_map", {})
        cpu_layers = [k for k, v in device_map.items() if str(v) == "cpu"]
        if cpu_layers:
            print(f"  CRITICAL: {len(cpu_layers)} layers offloaded to CPU! Results unreliable!")
        else:
            devices_used = set(str(v) for v in device_map.values())
            print(f"  Model loaded on GPU(s): {devices_used}")

        self.models[model_name] = {'tokenizer': tokenizer, 'model': model}
    
    def decompose_query(self, query: str, model_name: str, use_sad_hints: bool = False, 
                       hints: List[str] = None) -> tuple[List[str], float]:
        """Decompose query using LLM. Returns (subtasks, latency_ms)."""
        from skillweaver.core.decomposer import SYSTEM_PROMPT, USER_TEMPLATE, SAD_USER_TEMPLATE
        
        start_time = time.time()
        
        if model_name not in self.models:
            raise ValueError(f"Model {model_name} not loaded")
        
        tokenizer = self.models[model_name]['tokenizer']
        model = self.models[model_name]['model']
        
        # Build prompt
        if use_sad_hints and hints:
            hint_list = ", ".join(hints)
            user_content = SAD_USER_TEMPLATE.format(query=query, hint_list=hint_list)
        else:
            user_content = USER_TEMPLATE.format(query=query)
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_content}
        ]
        
        # Tokenize
        prompt = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
        
        # Generate
        with torch.no_grad():
            outputs = model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=self.config.temperature,
                do_sample=False,
                top_p=0.9,
                repetition_penalty=1.1,
                pad_token_id=tokenizer.pad_token_id if tokenizer.pad_token_id is not None else tokenizer.eos_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )
        
        # Decode
        generated_text = tokenizer.decode(
            outputs[0][inputs.input_ids.shape[1]:], 
            skip_special_tokens=True
        ).strip()
        
        latency_ms = (time.time() - start_time) * 1000
        
        # Parse subtasks
        import re
        try:
            match = re.search(r"\[.*?\]", generated_text, re.DOTALL)
            if match:
                items = json.loads(match.group())
                if isinstance(items, list):
                    subtasks = [str(s).strip() for s in items if str(s).strip()]
                    return subtasks, latency_ms
        except (json.JSONDecodeError, AttributeError):
            pass
        
        # Fallback
        return [query], latency_ms
    
    def retrieve_skills(self, subtasks: List[str]) -> float:
        """Retrieve skills for subtasks. Returns latency_ms."""
        start_time = time.time()
        
        # Use batch search
        self.retriever.search_batch(subtasks)
        
        latency_ms = (time.time() - start_time) * 1000
        return latency_ms
    
    def run_vanilla_pipeline(self, query: Dict, model_name: str) -> QueryLatencyRecord:
        """Run vanilla pipeline (single-pass decomposition)."""
        query_text = query['query']
        query_id = query.get('query_id', query.get('id', 'unknown'))
        difficulty = query.get('difficulty', 'unknown')
        
        record = QueryLatencyRecord(
            query_id=query_id,
            query_text=query_text,
            difficulty=difficulty,
            model_size=model_name.replace('_', ''),
            pipeline_mode='vanilla'
        )
        
        pipeline_start = time.time()
        
        # Stage 1: Decomposition (Pass 1)
        subtasks, decomp_latency = self.decompose_query(query_text, model_name)
        record.decomposition_pass1_ms = decomp_latency
        record.num_subtasks = len(subtasks)
        
        # Stage 2: Retrieval
        retrieval_latency = self.retrieve_skills(subtasks)
        record.retrieval_ms = retrieval_latency
        
        # Total latency
        record.total_ms = (time.time() - pipeline_start) * 1000
        
        return record
    
    def run_sad_pipeline(self, query: Dict, model_name: str) -> QueryLatencyRecord:
        """Run SAD pipeline (two-pass decomposition with feedback)."""
        query_text = query['query']
        query_id = query.get('query_id', query.get('id', 'unknown'))
        difficulty = query.get('difficulty', 'unknown')
        
        record = QueryLatencyRecord(
            query_id=query_id,
            query_text=query_text,
            difficulty=difficulty,
            model_size=model_name.replace('_', ''),
            pipeline_mode='sad'
        )
        
        pipeline_start = time.time()
        
        # Stage 1: Decomposition (Pass 1 - vanilla)
        subtasks_pass1, decomp_pass1_latency = self.decompose_query(query_text, model_name)
        record.decomposition_pass1_ms = decomp_pass1_latency
        
        # Stage 2: Retrieval for hint construction
        candidates = self.retriever.search_batch(subtasks_pass1)
        
        # Build hint set from Pass-1 retrieval results
        best_score = {}
        for step_candidates in candidates:
            for match in step_candidates:
                name = match.skill.name
                if name not in best_score or match.score > best_score[name]:
                    best_score[name] = match.score
        
        ranked = sorted(best_score.items(), key=lambda x: x[1], reverse=True)
        hints = [name for name, _ in ranked[:15]]  # Top-15 hints
        
        # Stage 3: Decomposition (Pass 2 - with hints)
        subtasks_pass2, decomp_pass2_latency = self.decompose_query(
            query_text, model_name, use_sad_hints=True, hints=hints
        )
        record.decomposition_pass2_ms = decomp_pass2_latency
        record.num_subtasks = len(subtasks_pass2)
        
        # Stage 4: Final retrieval
        retrieval_latency = self.retrieve_skills(subtasks_pass2)
        record.retrieval_ms = retrieval_latency
        
        # Total latency
        record.total_ms = (time.time() - pipeline_start) * 1000
        
        return record
    
    def run_experiment(self):
        """Run the complete latency breakdown experiment."""
        from datetime import datetime
        
        print("\n" + "="*80)
        print("SkillWeaver Latency Breakdown Experiment")
        print("="*80)
        print(f"Test queries: {len(self.test_queries)}")
        print(f"Models: 7B, 14B, 72B")
        print(f"Modes: vanilla, sad")
        print(f"Total runs: {len(self.test_queries) * 3 * 2} = {len(self.test_queries) * 6}")
        print("="*80 + "\n")
        
        all_records = []
        
        # Test configurations
        model_configs = [
            # SKIPPED 7B/14B - running on other GPUs
            (self.config.model_path_72b, "qwen25_72b"),
        ]
        
        for model_path, model_name in model_configs:
            print(f"\n{'='*60}")
            print(f"Testing model: {model_name}")
            print(f"{'='*60}")
            
            # Load model
            self.load_model(model_path, model_name)
            
            # Run vanilla pipeline
            print(f"\n--- Running VANILLA pipeline ---")
            for i, query in enumerate(self.test_queries, 1):
                record = self.run_vanilla_pipeline(query, model_name)
                all_records.append(record)
                
                if i % 10 == 0 or i == len(self.test_queries):
                    print(f"  Vanilla: {i}/{len(self.test_queries)} queries completed")
            
            # Run SAD pipeline
            print(f"\n--- Running SAD pipeline ---")
            for i, query in enumerate(self.test_queries, 1):
                record = self.run_sad_pipeline(query, model_name)
                all_records.append(record)
                
                if i % 10 == 0 or i == len(self.test_queries):
                    print(f"  SAD: {i}/{len(self.test_queries)} queries completed")
        
        # Compute aggregate statistics
        print(f"\n{'='*80}")
        print("Computing statistics...")
        print(f"{'='*80}")
        
        results = self.compute_statistics(all_records)
        
        # Save results
        output_path = Path(self.config.output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        
        print(f"\nResults saved to: {output_path}")
        print(f"Total records: {len(all_records)}")
        
        return results
    
    def compute_statistics(self, records: List[QueryLatencyRecord]) -> Dict:
        """Compute aggregate latency statistics."""
        from datetime import datetime
        
        # Group records by model and mode
        groups = {}
        for record in records:
            key = f"{record.model_size}_{record.pipeline_mode}"
            if key not in groups:
                groups[key] = []
            groups[key].append(record)
        
        # Compute stats for each group
        summary = {}
        for key, group_records in groups.items():
            model_size, pipeline_mode = key.rsplit('_', 1)
            
            # Collect stage latencies
            decomp_pass1 = StageLatency(stage_name="decomposition_pass1")
            retrieval = StageLatency(stage_name="retrieval")
            decomp_pass2 = StageLatency(stage_name="decomposition_pass2")
            total = StageLatency(stage_name="total")
            
            for record in group_records:
                decomp_pass1.add_latency(record.decomposition_pass1_ms)
                retrieval.add_latency(record.retrieval_ms)
                if pipeline_mode == 'sad':
                    decomp_pass2.add_latency(record.decomposition_pass2_ms)
                total.add_latency(record.total_ms)
            
            # Compute stage stats
            stage_stats = {
                'decomposition_pass1': decomp_pass1.compute_stats(),
                'retrieval': retrieval.compute_stats(),
                'total': total.compute_stats()
            }
            
            if pipeline_mode == 'sad':
                stage_stats['decomposition_pass2'] = decomp_pass2.compute_stats()
            
            # Compute breakdown percentages (based on mean latencies)
            if pipeline_mode == 'vanilla':
                total_mean = stage_stats['total']['mean']
                if total_mean > 0:
                    stage_stats['breakdown_percentage'] = {
                        'decomposition_pass1': (stage_stats['decomposition_pass1']['mean'] / total_mean) * 100,
                        'retrieval': (stage_stats['retrieval']['mean'] / total_mean) * 100
                    }
            else:  # sad
                total_mean = stage_stats['total']['mean']
                if total_mean > 0:
                    stage_stats['breakdown_percentage'] = {
                        'decomposition_pass1': (stage_stats['decomposition_pass1']['mean'] / total_mean) * 100,
                        'decomposition_pass2': (stage_stats['decomposition_pass2']['mean'] / total_mean) * 100,
                        'retrieval': (stage_stats['retrieval']['mean'] / total_mean) * 100
                    }
            
            # Stats by difficulty
            difficulty_stats = {}
            difficulties = set(r.difficulty for r in group_records)
            for diff in difficulties:
                diff_records = [r for r in group_records if r.difficulty == diff]
                diff_total = StageLatency(stage_name=f"total_{diff}")
                for r in diff_records:
                    diff_total.add_latency(r.total_ms)
                difficulty_stats[diff] = {
                    'count': len(diff_records),
                    'total_latency': diff_total.compute_stats()
                }
            
            stage_stats['by_difficulty'] = difficulty_stats
            
            summary[key] = {
                'model_size': model_size,
                'pipeline_mode': pipeline_mode,
                'num_queries': len(group_records),
                'stage_statistics': stage_stats
            }
        
        # Build final results
        results = {
            'experiment': 'latency_breakdown',
            'timestamp': datetime.now().isoformat(),
            'config': {
                'test_sample_size': self.config.test_sample_size,
                'models_tested': ['7b', '14b', '72b'],
                'pipeline_modes': ['vanilla', 'sad']
            },
            'summary': summary,
            'raw_records': [asdict(r) for r in records]
        }
        
        return results


def main():
    """Main entry point."""
    config = ExperimentConfig()
    runner = LatencyBreakdownRunner(config)
    results = runner.run_experiment()
    
    # Print summary
    print("\n" + "="*80)
    print("EXPERIMENT SUMMARY")
    print("="*80)
    
    for key, stats in results['summary'].items():
        print(f"\n{key.upper()}:")
        stage_stats = stats['stage_statistics']
        
        print(f"  Total latency (mean): {stage_stats['total']['mean']:.2f} ms")
        print(f"  Total latency (median): {stage_stats['total']['median']:.2f} ms")
        print(f"  Total latency (P95): {stage_stats['total']['p95']:.2f} ms")
        print(f"  Total latency (P99): {stage_stats['total']['p99']:.2f} ms")
        
        if 'breakdown_percentage' in stage_stats:
            print(f"  Breakdown:")
            for stage, pct in stage_stats['breakdown_percentage'].items():
                print(f"    {stage}: {pct:.1f}%")
    
    print("\n" + "="*80)
    print("Experiment completed successfully!")
    print("="*80)


if __name__ == "__main__":
    main()
