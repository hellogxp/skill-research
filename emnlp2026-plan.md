# Compositional Skill Routing -- EMNLP 2026 Submission Plan

## Paper Direction
**Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose**

Core problem: Real-world user queries often require multiple skills working together,
but existing routing methods only select a single best-match skill.
We define and solve the Compositional Skill Routing problem.

## Target Venue

### Primary: EMNLP 2026 (CCF-A)
- ARR submission deadline: 2026-05-25
- Commitment deadline: 2026-08-02
- Conference: Oct 24-29, 2026
- Note: 走 ARR 系统

### Backup: NAACL 2027 (CCF-B)
- ARR submission deadline: ~2026-08-03
- Conference: ~2027-04

### COLM 2026 (abandoned for this paper)
- Abstract-only submitted, will not upload full paper
- Auto-expires after 3/31

## Execution Timeline

```
3/26 - 4/06   Phase 1: Data & Benchmark Construction (10 days)
              - Collect 2000-5000 skills from public repos
              - Construct compositional query set (200+ queries)
              - Each query requires 2-5 skills to complete
              - Annotate ground truth skill DAGs
              - Build difficulty levels (easy/medium/hard)

4/07 - 4/20   Phase 2: Core Method Implementation (14 days)
              - Task Decomposer (LLM-based sub-task generation)
              - Per-subtask Skill Retriever (learned representation)
              - Skill Compatibility Model (I/O format + semantic compatibility)
              - DAG Planner (composition optimizer)

4/21 - 5/04   Phase 3: Experiments & Ablations (14 days)
              - Main results: compositional task completion rate
              - Baselines: single-skill routing, LLM direct planning, 
                ReAct-style, pipeline variants
              - Ablation: w/o decomposer, w/o compatibility model, etc.
              - Analysis: error taxonomy, scaling behavior, case studies

5/05 - 5/18   Phase 4: Paper Writing (14 days)
              - Full paper draft (9 pages + references)
              - Figures, tables, formatting
              - Internal review and revision

5/19 - 5/25   Phase 5: Final Polish & Submit (7 days)
              - Final proofreading
              - Camera-ready quality check
              - Submit to ARR by 5/25
```

## Contributions (4 points)

1. **Problem Formalization**: First formal definition of Compositional Skill Routing 
   as a graph planning problem over a skill library.

2. **Complete Pipeline**: A three-stage framework -- Decompose (task → sub-tasks), 
   Retrieve (sub-task → candidate skills), Compose (candidates → executable DAG) -- 
   with a novel Skill Compatibility Model for inter-skill compatibility scoring.

3. **Open Benchmark**: First benchmark for compositional skill routing, with 200+ 
   multi-skill queries, ground-truth DAGs, and difficulty stratification.

4. **Comprehensive Evaluation**: Systematic comparison against single-skill routing, 
   LLM-based planning, and ablation variants, with error analysis and case studies.

## Compute Resources
- 4 x NVIDIA A100-SXM4-80GB (320GB total VRAM)
- 64-core Intel Xeon Platinum 8369B @ 2.90GHz
- 491GB RAM
- PyTorch 2.7.1 + CUDA 12.6
- Workspace: /mnt/workspace
- SSH: ssh -i ~/.ssh/pai_dsw_rsa root@120.55.88.46 -p 24
