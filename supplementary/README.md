# SkillWeaver: Compositional Skill Routing for LLM Agents

Supplementary code for the paper "Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose" (EMNLP 2026).

## Overview

SkillWeaver implements a decompose-retrieve-compose framework for routing complex user queries to sequences of skills. The key contribution is **Skill-Aware Decomposition (SAD)**, an iterative alignment algorithm that feeds retrieved skill names back into the decomposer to improve decomposition quality.

## Structure

```
skillweaver/core/
  models.py       - Data models (Skill, SubTask, SkillMatch, Plan)
  decomposer.py   - LLM-based task decomposer (vanilla + SAD)
  retriever.py    - Bi-encoder skill retriever with FAISS
  pipeline.py     - Full pipeline orchestration + SAD feedback loop
  planner.py      - Sequential skill planner
  dag_planner.py  - DAG-based dependency-aware planner

run_experiments.py  - Reproduces main results (Table 1), convergence (Table 4), transfer (Table 5)
build_benchmark.py  - Generates CompSkillBench from skill pool
```

## Requirements

```
torch>=2.0
transformers>=4.35
sentence-transformers>=2.2
faiss-cpu>=1.7
numpy
```

## Reproducing Results

### 1. Prepare data

Place `skill_pool.jsonl` (2,209 skills) and `compositional_queries.jsonl` (300 queries) in `data/`.

### 2. Download models

- Decomposer: Qwen2.5-7B-Instruct
- Encoder: sentence-transformers/all-MiniLM-L6-v2

### 3. Run experiments

```bash
python run_experiments.py
```

This produces:
- `results/main_results_v4.json` - Vanilla vs SAD (Table 1)
- `results/convergence_v4.json` - Iterative SAD rounds (Table 4)
- `results/transfer_v4.json` - Held-out transfer (Table 5)

## Key Algorithm: SAD

```python
# Iterative Skill-Aware Decomposition (Algorithm 1)
hints = []
for i in range(T):  # T=1 default, T=2 for precision
    if i == 0:
        subtasks = decompose(query)  # vanilla
    else:
        subtasks = decompose_with_hints(query, hints)
    candidates = retrieve(subtasks)
    new_hints = build_hint_set(candidates, H=15)
    if jaccard(hints, new_hints) > tau:
        break  # converged
    hints = new_hints
```

## License

Apache 2.0
