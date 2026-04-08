<!--
  Sync Impact Report
  ===================
  Version change: 1.0.0 → 1.1.0 (MINOR — new principle added)
  Modified principles: none
  Added sections:
    - Principle VI: Scientific Rigor & Critical Thinking
  Removed sections: none
  Templates requiring updates:
    - .specify/templates/plan-template.md ✅ no update needed
    - .specify/templates/spec-template.md ✅ no update needed
    - .specify/templates/tasks-template.md ✅ no update needed
  Follow-up TODOs: none
-->

# Skill Research Constitution

## Core Principles

### I. Research Reproducibility

All experimental results MUST be reproducible. This requires:

- Fixed random seeds and deterministic configurations for every experiment run
- All hyperparameters, model versions, and data splits MUST be logged
  and version-controlled
- Scripts MUST accept configuration files or CLI arguments; no hardcoded
  experiment parameters in source code
- Every result reported in a paper MUST have a corresponding runnable
  script in `scripts/` that regenerates it

### II. Paper-Driven Development

Every implementation decision MUST be justified by the research
contribution it supports:

- Code exists to serve the paper; features not needed for experiments
  or the SkillWeaver MVP MUST NOT be implemented
- The EMNLP 2026 submission (ARR deadline 2026-05-25) is the primary
  deliverable; all engineering effort MUST align with this timeline
- Each module (TaskDecomposer, SkillRetriever, DAGPlanner) MUST map
  directly to a section or ablation in the paper

### III. Benchmark Integrity

CompSkillBench is a core contribution. Its credibility MUST be ensured:

- Ground-truth skill DAG annotations MUST follow a documented schema
  with inter-annotator agreement metrics where applicable
- Evaluation metrics MUST be clearly defined before experiments begin;
  no post-hoc metric selection
- Difficulty stratification (easy/medium/hard) MUST use objective,
  reproducible criteria (e.g., number of required skills, DAG depth)
- Data collection from public repos MUST respect licenses and attribute
  sources

### IV. Modular Pipeline Architecture

The three-stage pipeline (Decompose, Retrieve, Compose) MUST maintain
strict separation of concerns:

- Each stage MUST be independently testable with its own input/output
  contract
- Ablation studies require dropping or replacing any single stage;
  interfaces MUST support this
- Shared data structures (skill representations, DAG format) MUST be
  defined in `src/` and imported by all stages; no duplication
- Adapters for different skill formats (SKILL.md, MCP, OpenAI function)
  MUST be isolated in dedicated modules

### V. Efficiency First

Minimize waste in compute, tokens, and development time:

- LLM API calls MUST use caching where possible to avoid redundant
  requests during development and evaluation
- Batch processing MUST be preferred over sequential single-item calls
- Intermediate results (embeddings, decomposition outputs) MUST be
  persisted to disk to enable incremental experimentation
- Agent interactions (Qoder, etc.) SHOULD minimize token usage by
  omitting verbose intermediate output when not needed for decision-making

### VI. Scientific Rigor & Critical Thinking

All research work MUST reflect top-tier expertise in large language
models and maintain the intellectual standard of a best-paper-caliber
submission:

- Experimental design MUST be sound: every comparison MUST control
  variables properly, use appropriate baselines, and account for
  confounding factors. If a baseline is missing or unfair, the
  experiment MUST NOT proceed
- Results MUST be accurate and honestly reported: negative results,
  failure modes, and variance MUST be disclosed, not hidden. Cherry-
  picking favorable runs is prohibited; report mean and standard
  deviation across multiple seeds
- Insights MUST go beyond surface-level metrics: every experimental
  section MUST include analysis that explains *why* a method works
  or fails, not just *that* it does. Error taxonomies, case studies,
  and attention/attribution analysis are expected, not optional
- Critical thinking MUST be applied at every stage: actively challenge
  own assumptions, question whether observed improvements are real or
  artifacts of data/evaluation design, and preemptively address
  likely reviewer objections
- Discovery MUST be prioritized: when unexpected patterns emerge in
  data or results, they MUST be investigated rather than ignored.
  Anomalies are often the most valuable findings

## Research Ethics & Data Governance

- Skills collected from public repositories MUST only include those with
  permissive licenses (MIT, Apache-2.0, BSD, or equivalent)
- No private or proprietary skill implementations may be included in
  the benchmark without explicit permission
- Compute resources (A100 cluster) MUST be used responsibly; idle jobs
  MUST be terminated promptly
- SSH keys and API credentials MUST NOT be committed to the repository

## Development Workflow

- Python is the primary language; all code MUST target Python 3.10+
- Code in `src/` is the research pipeline; code in `skillweaver/` is
  the product tool; they share core logic but have separate entry points
- Experiment scripts in `scripts/` MUST be self-contained and runnable
  via `bash scripts/<name>.sh`
- Results MUST be written to `results/` with timestamped or
  experiment-tagged subdirectories
- Paper LaTeX source lives in `paper/`; figures MUST be generated
  programmatically from result data, not manually drawn

## Governance

This constitution supersedes ad-hoc decisions when conflicts arise.
Amendments require:

1. A documented rationale for the change
2. Version bump following semantic versioning (MAJOR for principle
   removal/redefinition, MINOR for additions, PATCH for clarifications)
3. Update to this file with amended date

All implementation plans MUST pass the Constitution Check gate in the
plan template before proceeding.

**Version**: 1.1.0 | **Ratified**: 2026-03-27 | **Last Amended**: 2026-03-27
