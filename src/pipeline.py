"""
Compositional Skill Router: Core Pipeline v2
Three-stage framework: Decompose -> Retrieve -> Compose

v2 fixes:
- Proper chat template for instruction-tuned LLMs
- Batch decomposition for performance
- Better generation parameters
- ModelScope encoder path support
"""

import json
import logging
import re
import time
from pathlib import Path
from dataclasses import dataclass, asdict, field

import torch
import numpy as np
import faiss
from sentence_transformers import SentenceTransformer

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SKILL_POOL_PATH = Path("/mnt/workspace/skill-routing/data/processed_v3/skill_pool.jsonl")
BENCHMARK_PATH = Path("/mnt/workspace/skill-routing/data/benchmark_v3/compositional_queries.jsonl")
RESULTS_DIR = Path("/mnt/workspace/skill-routing/results_v3")

# ModelScope local path for BGE encoder
ENCODER_LOCAL_PATHS = {
    "BAAI/bge-large-en-v1.5": "/mnt/workspace/models/embeddings/BAAI/bge-large-en-v1___5",
}


# ============================================================
# Data Structures
# ============================================================

@dataclass
class SkillRecord:
    skill_id: str
    name: str
    description: str
    body: str
    categories: list[str]
    embedding: np.ndarray = field(default=None, repr=False)


@dataclass
class SubTaskPrediction:
    step_index: int
    description: str
    candidate_skill_ids: list[str]
    candidate_scores: list[float]
    selected_skill_id: str
    selected_skill_name: str


@dataclass
class PipelineResult:
    query_id: str
    query: str
    decomposed_subtasks: list[str]
    predictions: list[SubTaskPrediction]
    predicted_edges: list[dict]
    latency_ms: float


# ============================================================
# Stage 1: Task Decomposer (v2 - with chat template)
# ============================================================

class TaskDecomposer:
    """Decomposes a complex query into ordered sub-tasks using an LLM."""

    SYSTEM_PROMPT = """You are a task decomposition expert. Given a user query that requires multiple tools/skills to complete, break it down into a sequence of atomic sub-tasks.

Rules:
1. Each sub-task should require exactly ONE skill/tool to complete.
2. List sub-tasks in execution order.
3. Be specific about what each sub-task does.
4. Output ONLY a JSON array of strings, nothing else. No explanation."""

    USER_PROMPT_TEMPLATE = """Decompose this query into atomic sub-tasks. Output a JSON array of strings ONLY.

Query: {query}

JSON array:"""

    def __init__(self, model_name: str = "Qwen2.5-7B-Instruct", use_vllm: bool = False):
        self.model_name = model_name
        self.use_vllm = use_vllm
        self._llm = None
        self._model = None
        self._tokenizer = None

    def _init_llm(self):
        if self._llm is not None or self._model is not None:
            return
        model_path = f"/mnt/workspace/models/{self.model_name}"

        if self.use_vllm:
            from vllm import LLM, SamplingParams
            self._llm = LLM(
                model=model_path,
                tensor_parallel_size=1,
                gpu_memory_utilization=0.3,
                max_model_len=4096,
                trust_remote_code=True,
            )
            self._sampling_params = SamplingParams(
                temperature=0.1,
                top_p=0.9,
                max_tokens=512,
                stop=["<|im_end|>", "<|endoftext|>"],
            )
            from transformers import AutoTokenizer
            self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        else:
            from transformers import AutoTokenizer, AutoModelForCausalLM
            logger.info(f"Loading {self.model_name} with transformers...")
            self._tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
            self._model = AutoModelForCausalLM.from_pretrained(
                model_path, dtype=torch.float16, device_map="auto", trust_remote_code=True
            )
            self._model.eval()
            logger.info(f"Model loaded on {self._model.device}")

    def _format_prompt(self, query: str) -> str:
        """Format query using the model's chat template."""
        messages = [
            {"role": "system", "content": self.SYSTEM_PROMPT},
            {"role": "user", "content": self.USER_PROMPT_TEMPLATE.format(query=query)},
        ]
        # Apply chat template - this produces the proper <|im_start|> format
        prompt = self._tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        return prompt

    def _parse_output(self, text: str, fallback_query: str) -> list[str]:
        """Parse LLM output into a list of subtask strings."""
        text = text.strip()
        # Try to find JSON array
        try:
            match = re.search(r'\[.*?\]', text, re.DOTALL)
            if match:
                subtasks = json.loads(match.group())
                if isinstance(subtasks, list) and len(subtasks) > 0:
                    return [str(s) for s in subtasks if str(s).strip()]
        except (json.JSONDecodeError, AttributeError):
            pass

        # Fallback: try to parse numbered list
        lines = []
        for line in text.split("\n"):
            line = line.strip()
            # Remove numbering patterns like "1.", "1)", "- ", "* "
            cleaned = re.sub(r'^[\d]+[.)]\s*', '', line)
            cleaned = re.sub(r'^[-*]\s*', '', cleaned)
            cleaned = cleaned.strip().strip('"').strip("'")
            if cleaned:
                lines.append(cleaned)

        if lines:
            return lines

        # Last resort: return the query itself
        return [fallback_query]

    def decompose(self, query: str) -> list[str]:
        """Decompose a query into sub-tasks."""
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

    def decompose_batch(self, queries: list[str]) -> list[list[str]]:
        """Batch decompose queries. Uses sequential generation with transformers."""
        self._init_llm()

        if self.use_vllm:
            prompts = [self._format_prompt(q) for q in queries]
            outputs = self._llm.generate(prompts, self._sampling_params)
            results = []
            for i, output in enumerate(outputs):
                text = output.outputs[0].text.strip()
                results.append(self._parse_output(text, queries[i]))
            return results

        # Transformers: sequential generation (still fast enough for 300 queries)
        results = []
        for i, query in enumerate(queries):
            subtasks = self.decompose(query)
            results.append(subtasks)
            if (i + 1) % 20 == 0:
                logger.info(f"    Decomposed {i+1}/{len(queries)} queries")
        return results


# ============================================================
# Stage 2: Skill Retriever
# ============================================================

class SkillRetriever:
    """Retrieves candidate skills for each sub-task using bi-encoder + FAISS."""

    def __init__(
        self,
        encoder_name: str = "BAAI/bge-large-en-v1.5",
        use_body: bool = False,
        top_k: int = 10,
    ):
        self.encoder_name = encoder_name
        self.use_body = use_body
        self.top_k = top_k
        self.encoder = None
        self.index = None
        self.skills: list[SkillRecord] = []
        self.id_to_idx: dict[str, int] = {}

    def _init_encoder(self):
        if self.encoder is None:
            # Use local path if available (ModelScope download)
            local_path = ENCODER_LOCAL_PATHS.get(self.encoder_name)
            if local_path and Path(local_path).exists():
                logger.info(f"Loading encoder from local path: {local_path}")
                self.encoder = SentenceTransformer(local_path)
            else:
                logger.info(f"Loading encoder: {self.encoder_name}")
                self.encoder = SentenceTransformer(self.encoder_name)
            if torch.cuda.is_available():
                self.encoder = self.encoder.to("cuda")

    def build_index(self, skills: list[SkillRecord]):
        """Build FAISS index from skills."""
        self._init_encoder()
        self.skills = skills
        self.id_to_idx = {s.skill_id: i for i, s in enumerate(skills)}

        # Prepare texts for encoding
        texts = []
        for s in skills:
            if self.use_body:
                text = f"{s.name}\n{s.description}\n{s.body[:2000]}"
            else:
                text = f"{s.name}\n{s.description}"
            texts.append(text)

        logger.info(f"Encoding {len(texts)} skills (use_body={self.use_body})...")
        embeddings = self.encoder.encode(texts, show_progress_bar=True, batch_size=64)
        embeddings = embeddings.astype(np.float32)

        # Normalize for cosine similarity
        faiss.normalize_L2(embeddings)

        # Store embeddings
        for i, s in enumerate(self.skills):
            s.embedding = embeddings[i]

        # Build FAISS index
        dim = embeddings.shape[1]
        self.index = faiss.IndexFlatIP(dim)
        self.index.add(embeddings)
        logger.info(f"FAISS index built: {self.index.ntotal} vectors, dim={dim}")

    def retrieve(self, query: str, top_k: int = None) -> list[tuple[str, float]]:
        """Retrieve top-k skills for a query."""
        self._init_encoder()
        k = top_k or self.top_k

        q_emb = self.encoder.encode([query], show_progress_bar=False).astype(np.float32)
        faiss.normalize_L2(q_emb)

        scores, indices = self.index.search(q_emb, k)
        results = []
        for score, idx in zip(scores[0], indices[0]):
            if idx < len(self.skills):
                results.append((self.skills[idx].skill_id, float(score)))
        return results

    def retrieve_batch(self, queries: list[str], top_k: int = None) -> list[list[tuple[str, float]]]:
        """Batch retrieve."""
        self._init_encoder()
        k = top_k or self.top_k

        q_embs = self.encoder.encode(queries, show_progress_bar=False, batch_size=64).astype(np.float32)
        faiss.normalize_L2(q_embs)

        scores, indices = self.index.search(q_embs, k)
        results = []
        for i in range(len(queries)):
            hits = []
            for score, idx in zip(scores[i], indices[i]):
                if idx < len(self.skills):
                    hits.append((self.skills[idx].skill_id, float(score)))
            results.append(hits)
        return results


# ============================================================
# Stage 3: Skill Compatibility Model & DAG Planner
# ============================================================

class CompatibilityScorer:
    """Scores compatibility between consecutive skills in a pipeline."""

    def __init__(self, encoder: SentenceTransformer = None):
        self.encoder = encoder
        self._cache: dict[tuple[str, str], float] = {}

    def score(self, skill_a: SkillRecord, skill_b: SkillRecord) -> float:
        """Score how compatible skill_a's output is with skill_b's input."""
        cache_key = (skill_a.skill_id, skill_b.skill_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        if skill_a.embedding is not None and skill_b.embedding is not None:
            # Category overlap bonus
            cat_overlap = len(set(skill_a.categories) & set(skill_b.categories))
            cat_bonus = 0.1 * min(cat_overlap, 2)

            # Embedding-based semantic compatibility
            sim = float(np.dot(skill_a.embedding, skill_b.embedding))

            # Name/description heuristic: check for input/output pattern matching
            io_bonus = 0.0
            a_text = f"{skill_a.name} {skill_a.description}".lower()
            b_text = f"{skill_b.name} {skill_b.description}".lower()

            output_keywords = ["generate", "create", "produce", "output", "export", "write", "build"]
            input_keywords = ["read", "parse", "process", "analyze", "import", "consume", "load"]
            if any(kw in a_text for kw in output_keywords) and any(kw in b_text for kw in input_keywords):
                io_bonus = 0.15

            score = 0.5 * sim + 0.3 * cat_bonus + 0.2 * io_bonus
        else:
            score = 0.5

        self._cache[cache_key] = score
        return score


class DAGPlanner:
    """Plans the skill execution DAG."""

    def __init__(self, retriever: SkillRetriever, compatibility: CompatibilityScorer):
        self.retriever = retriever
        self.compatibility = compatibility
        self.skill_map: dict[str, SkillRecord] = {}

    def set_skill_map(self, skills: list[SkillRecord]):
        self.skill_map = {s.skill_id: s for s in skills}

    def plan(
        self,
        subtasks: list[str],
        candidates_per_step: list[list[tuple[str, float]]],
    ) -> tuple[list[SubTaskPrediction], list[dict]]:
        """
        Given decomposed subtasks and candidate skills per step,
        select the best skill chain maximizing retrieval score + compatibility.
        """
        num_steps = len(subtasks)
        predictions = []

        selected_skills: list[SkillRecord | None] = [None] * num_steps

        for step in range(num_steps):
            best_score = -1
            best_id = None
            candidates = candidates_per_step[step] if step < len(candidates_per_step) else []

            for skill_id, retrieval_score in candidates:
                skill = self.skill_map.get(skill_id)
                if not skill:
                    continue

                total_score = retrieval_score

                # Compatibility with previous step
                if step > 0 and selected_skills[step - 1]:
                    compat = self.compatibility.score(selected_skills[step - 1], skill)
                    total_score = 0.7 * retrieval_score + 0.3 * compat

                if total_score > best_score:
                    best_score = total_score
                    best_id = skill_id

            selected_skill = self.skill_map.get(best_id) if best_id else None
            selected_skills[step] = selected_skill

            predictions.append(SubTaskPrediction(
                step_index=step,
                description=subtasks[step],
                candidate_skill_ids=[sid for sid, _ in candidates],
                candidate_scores=[sc for _, sc in candidates],
                selected_skill_id=best_id or "",
                selected_skill_name=selected_skill.name if selected_skill else "",
            ))

        # Build edges (sequential by default)
        edges = []
        for i in range(num_steps - 1):
            edges.append({
                "from_step": i,
                "to_step": i + 1,
                "dependency_type": "sequential",
            })

        return predictions, edges


# ============================================================
# Full Pipeline
# ============================================================

class CompositionalSkillRouter:
    """The complete Decompose-Retrieve-Compose pipeline."""

    def __init__(
        self,
        decomposer: TaskDecomposer,
        retriever: SkillRetriever,
        compatibility: CompatibilityScorer,
        planner: DAGPlanner,
    ):
        self.decomposer = decomposer
        self.retriever = retriever
        self.compatibility = compatibility
        self.planner = planner

    def route(self, query: str, query_id: str = "") -> PipelineResult:
        """Run the full pipeline on a single query."""
        start = time.time()

        # Stage 1: Decompose
        subtasks = self.decomposer.decompose(query)

        # Stage 2: Retrieve candidates per subtask
        candidates_per_step = self.retriever.retrieve_batch(subtasks)

        # Stage 3: Plan (select + compose)
        predictions, edges = self.planner.plan(subtasks, candidates_per_step)

        latency = (time.time() - start) * 1000

        return PipelineResult(
            query_id=query_id,
            query=query,
            decomposed_subtasks=subtasks,
            predictions=predictions,
            predicted_edges=edges,
            latency_ms=latency,
        )

    def route_batch(self, queries: list[dict], batch_size: int = 32) -> list[PipelineResult]:
        """Run pipeline on a batch of queries for better throughput."""
        all_results = []

        for start_idx in range(0, len(queries), batch_size):
            batch = queries[start_idx : start_idx + batch_size]
            batch_queries = [q["query"] for q in batch]
            batch_ids = [q["query_id"] for q in batch]

            batch_start = time.time()

            # Stage 1: Batch decompose
            logger.info(f"  Batch decomposing {len(batch)} queries...")
            all_subtasks = self.decomposer.decompose_batch(batch_queries)

            # Stage 2: Batch retrieve (flatten all subtasks, then unflatten)
            flat_subtasks = []
            subtask_counts = []
            for subtasks in all_subtasks:
                flat_subtasks.extend(subtasks)
                subtask_counts.append(len(subtasks))

            logger.info(f"  Batch retrieving {len(flat_subtasks)} subtask queries...")
            flat_candidates = self.retriever.retrieve_batch(flat_subtasks)

            # Unflatten
            candidates_per_query = []
            offset = 0
            for count in subtask_counts:
                candidates_per_query.append(flat_candidates[offset : offset + count])
                offset += count

            # Stage 3: Plan each query
            for i, (subtasks, candidates_per_step) in enumerate(zip(all_subtasks, candidates_per_query)):
                query_start = time.time()
                predictions, edges = self.planner.plan(subtasks, candidates_per_step)
                latency = (time.time() - query_start) * 1000

                all_results.append(PipelineResult(
                    query_id=batch_ids[i],
                    query=batch_queries[i],
                    decomposed_subtasks=subtasks,
                    predictions=predictions,
                    predicted_edges=edges,
                    latency_ms=latency,
                ))

            batch_elapsed = time.time() - batch_start
            logger.info(f"  Batch {start_idx//batch_size + 1}: {len(batch)} queries in {batch_elapsed:.1f}s")

        return all_results


# ============================================================
# Evaluation
# ============================================================

def evaluate(results: list[PipelineResult], ground_truth: list[dict], skill_pool: list[SkillRecord] = None) -> dict:
    """Evaluate pipeline results against ground truth.

    Includes both exact-ID metrics and category-level metrics.
    """
    gt_map = {q["query_id"]: q for q in ground_truth}

    # Build skill-to-category map for category-level evaluation
    skill_cat_map = {}
    if skill_pool:
        for s in skill_pool:
            if s.categories:
                skill_cat_map[s.skill_id] = s.categories[0]  # Primary category

    metrics = {
        "decomposition_accuracy": [],
        "skill_recall_at_1": [],
        "skill_recall_at_5": [],
        "skill_recall_at_10": [],
        "cat_recall_at_1": [],
        "cat_recall_at_5": [],
        "cat_recall_at_10": [],
        "chain_exact_match": [],
        "chain_partial_match": [],
        "chain_cat_match": [],
        "avg_latency_ms": [],
    }

    for result in results:
        gt = gt_map.get(result.query_id)
        if not gt:
            continue

        gt_subtasks = gt["subtasks"]
        gt_skill_ids = [st["ground_truth_skill_id"] for st in gt_subtasks]
        gt_categories = [st.get("required_category", "") for st in gt_subtasks]

        # Decomposition accuracy
        metrics["decomposition_accuracy"].append(
            1.0 if len(result.decomposed_subtasks) == len(gt_subtasks) else 0.0
        )

        # Per-step metrics
        n_steps = min(len(result.predictions), len(gt_skill_ids))
        step_correct = []
        step_cat_correct = []

        for i in range(n_steps):
            pred = result.predictions[i]
            gt_id = gt_skill_ids[i]
            gt_cat = gt_categories[i] if i < len(gt_categories) else ""

            # Exact ID metrics
            metrics["skill_recall_at_1"].append(
                1.0 if pred.selected_skill_id == gt_id else 0.0
            )
            top5 = pred.candidate_skill_ids[:5]
            metrics["skill_recall_at_5"].append(1.0 if gt_id in top5 else 0.0)
            top10 = pred.candidate_skill_ids[:10]
            metrics["skill_recall_at_10"].append(1.0 if gt_id in top10 else 0.0)
            step_correct.append(1.0 if pred.selected_skill_id == gt_id else 0.0)

            # Category-level metrics
            if gt_cat and skill_cat_map:
                selected_cat = skill_cat_map.get(pred.selected_skill_id, "")
                metrics["cat_recall_at_1"].append(1.0 if selected_cat == gt_cat else 0.0)
                top5_cats = [skill_cat_map.get(sid, "") for sid in top5]
                metrics["cat_recall_at_5"].append(1.0 if gt_cat in top5_cats else 0.0)
                top10_cats = [skill_cat_map.get(sid, "") for sid in top10]
                metrics["cat_recall_at_10"].append(1.0 if gt_cat in top10_cats else 0.0)
                step_cat_correct.append(1.0 if selected_cat == gt_cat else 0.0)

        # Chain metrics
        if step_correct:
            metrics["chain_exact_match"].append(1.0 if all(s == 1.0 for s in step_correct) else 0.0)
            metrics["chain_partial_match"].append(sum(step_correct) / len(step_correct))
        if step_cat_correct:
            metrics["chain_cat_match"].append(sum(step_cat_correct) / len(step_cat_correct))

        metrics["avg_latency_ms"].append(result.latency_ms)

    return {k: float(np.mean(v)) if v else 0.0 for k, v in metrics.items()}


# ============================================================
# Main: Load data, run pipeline, evaluate
# ============================================================

def load_skill_pool() -> list[SkillRecord]:
    """Load skill pool."""
    skills = []
    with open(SKILL_POOL_PATH) as f:
        for line in f:
            d = json.loads(line)
            skills.append(SkillRecord(
                skill_id=d["skill_id"],
                name=d["name"],
                description=d.get("description", ""),
                body=d.get("body", ""),
                categories=d.get("categories", []),
            ))
    return skills


def load_benchmark() -> list[dict]:
    """Load benchmark queries."""
    queries = []
    with open(BENCHMARK_PATH) as f:
        for line in f:
            queries.append(json.loads(line))
    return queries


def run_experiment(
    experiment_name: str,
    use_body: bool = False,
    encoder_name: str = "BAAI/bge-large-en-v1.5",
    llm_name: str = "Qwen2.5-7B-Instruct",
    use_vllm: bool = False,
    top_k: int = 10,
    batch_size: int = 32,
):
    """Run a single experiment configuration."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Experiment: {experiment_name}")
    logger.info(f"  encoder={encoder_name}, use_body={use_body}, llm={llm_name}")
    logger.info(f"{'='*60}")

    # Load data
    skills = load_skill_pool()
    benchmark = load_benchmark()
    logger.info(f"Loaded {len(skills)} skills, {len(benchmark)} queries")

    # Initialize components
    decomposer = TaskDecomposer(model_name=llm_name, use_vllm=use_vllm)
    retriever = SkillRetriever(encoder_name=encoder_name, use_body=use_body, top_k=top_k)
    retriever.build_index(skills)

    compatibility = CompatibilityScorer(encoder=retriever.encoder)
    planner = DAGPlanner(retriever=retriever, compatibility=compatibility)
    planner.set_skill_map(skills)

    router = CompositionalSkillRouter(decomposer, retriever, compatibility, planner)

    # Run on benchmark using batch mode
    logger.info(f"Running pipeline with batch_size={batch_size}...")
    results = router.route_batch(benchmark, batch_size=batch_size)

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
                "encoder": encoder_name,
                "use_body": use_body,
                "llm": llm_name,
                "top_k": top_k,
                "batch_size": batch_size,
            },
            "metrics": metrics,
            "predictions": [asdict(r) for r in results],
        }, f, indent=2, ensure_ascii=False, default=str)
    logger.info(f"Results saved to {result_file}")

    return metrics


if __name__ == "__main__":
    run_experiment(
        experiment_name="full_pipeline_metadata",
        use_body=False,
        encoder_name="BAAI/bge-large-en-v1.5",
        llm_name="Qwen2.5-7B-Instruct",
    )
