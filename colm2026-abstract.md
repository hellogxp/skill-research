# COLM 2026 Submission Draft

## Title

**Is the Skill Body Truly Indispensable? Rethinking Skill Routing via Metadata Enhancement and Context-Aware Personalization**

## Abstract (250 words) -- For OpenReview Submission

As LLM agent ecosystems scale to tens of thousands of available skills, accurate skill routing becomes a critical bottleneck. Recent work demonstrates that removing the skill body -- the full implementation text -- degrades routing accuracy by 29-44 percentage points, concluding that metadata (name and description) alone is fundamentally insufficient. This finding implies that agent platforms must expose complete skill implementations during retrieval, raising significant scalability, privacy, and security concerns.

We challenge this conclusion. We hypothesize that the observed metadata inadequacy stems not from an inherent information deficit, but from the low quality of existing community-authored metadata, which is often vague, duplicated, or inconsistent across functionally overlapping skills. To test this, we propose a two-stage framework: (1) LLM-powered metadata enhancement, which automatically distills discriminative semantics from skill bodies into enriched metadata as a one-time offline process, and (2) context-aware personalized reranking, which incorporates user history and environmental context to resolve ambiguity when multiple skills match a query equally well under static routing.

Our approach decouples the routing signal from the skill body at inference time, requiring no access to full implementations during retrieval. We construct and evaluate on a large-scale skill routing benchmark assembled from publicly available skill repositories, systematically comparing enhanced-metadata routing against body-dependent baselines. Our analysis provides three contributions: (i) evidence that metadata quality, not metadata modality, is the true bottleneck in skill routing; (ii) a privacy-preserving routing pipeline that approaches body-dependent accuracy without exposing implementations; and (iii) the first investigation of personalized skill routing conditioned on user context.


## Abstract -- Plain Text (copy this to OpenReview)

As LLM agent ecosystems scale to tens of thousands of available skills, accurate skill routing becomes a critical bottleneck. Recent work demonstrates that removing the skill body -- the full implementation text -- degrades routing accuracy by 29-44 percentage points, concluding that metadata (name and description) alone is fundamentally insufficient. This finding implies that agent platforms must expose complete skill implementations during retrieval, raising significant scalability, privacy, and security concerns.

We challenge this conclusion. We hypothesize that the observed metadata inadequacy stems not from an inherent information deficit, but from the low quality of existing community-authored metadata, which is often vague, duplicated, or inconsistent across functionally overlapping skills. To test this, we propose a two-stage framework: (1) LLM-powered metadata enhancement, which automatically distills discriminative semantics from skill bodies into enriched metadata as a one-time offline process, and (2) context-aware personalized reranking, which incorporates user history and environmental context to resolve ambiguity when multiple skills match a query equally well under static routing.

Our approach decouples the routing signal from the skill body at inference time, requiring no access to full implementations during retrieval. We construct and evaluate on a large-scale skill routing benchmark assembled from publicly available skill repositories, systematically comparing enhanced-metadata routing against body-dependent baselines. Our analysis provides three contributions: (i) evidence that metadata quality, not metadata modality, is the true bottleneck in skill routing; (ii) a privacy-preserving routing pipeline that approaches body-dependent accuracy without exposing implementations; and (iii) the first investigation of personalized skill routing conditioned on user context.

---

## Keywords

LLM agents, skill routing, metadata enhancement, personalized routing, tool selection

## Contributions Summary (for full paper structure)

1. **Empirical Reassessment**: We demonstrate that the "body is indispensable" conclusion is an artifact of low-quality metadata, not a fundamental limitation. After LLM-powered metadata enhancement, metadata-only routing recovers the majority of the accuracy gap.

2. **Context-Aware Personalized Routing**: We introduce the first personalized skill routing framework that conditions selection on user interaction history and environmental context, addressing the "one query, many valid skills" problem.

3. **Privacy-Preserving Architecture**: Our framework decouples routing from skill body access at inference time, providing a practical alternative for Skill ecosystems where exposing full implementations is undesirable (security, IP protection, etc.).

4. **Open Benchmark**: We construct and release an open-source skill routing benchmark from publicly available skill repositories, enabling reproducible evaluation of skill routing methods.

5. **Comprehensive Analysis**: We provide detailed ablation studies, attention analysis, and case studies showing when and why metadata enhancement succeeds or fails.

## Suggested Paper Outline

### 1. Introduction (1.5 pages)
- LLM agent skill ecosystems are exploding (80K+ skills)
- The routing challenge: how to select the right skill from thousands
- SkillRouter's finding: body is the decisive signal (91.7% attention)
- Our question: is this truly about body, or about metadata quality?
- Preview of contributions

### 2. Related Work (1 page)
- Skill/Tool selection for LLM agents (SkillRouter, AutoTool, ASI)
- Metadata and documentation quality in software ecosystems
- Personalized information retrieval
- Agent skill lifecycle and security (SoK, Zhejiang survey)

### 3. Reassessing the Body Hypothesis (2 pages)
- 3.1 Experimental setup: reproduce SkillRouter's key findings
- 3.2 Metadata quality analysis: quantify vagueness, duplication, inconsistency
- 3.3 LLM-powered metadata enhancement pipeline
  - Prompt design for discriminative description generation
  - One-time offline process (no runtime cost)
- 3.4 Results: enhanced metadata vs. original metadata vs. full body

### 4. Context-Aware Personalized Routing (2 pages)
- 4.1 Motivation: same query, different optimal skills for different users
- 4.2 User context representation (interaction history, environment, preferences)
- 4.3 Personalized reranking module
- 4.4 Integration with metadata-enhanced retrieval pipeline

### 5. Experiments (2.5 pages)
- 5.1 Setup: open-source skill routing benchmark from public repositories, baselines, metrics
- 5.2 Main results (Table 1: metadata-only → enhanced → +personalization)
- 5.3 Ablation studies
  - w/o metadata enhancement
  - w/o personalization
  - different LLM enhancers (GPT-4 / Qwen / Llama)
  - metadata enhancement quality vs. compression ratio
- 5.4 Analysis
  - Attention distribution shift after metadata enhancement
  - When does enhancement fail? (case study)
  - Privacy-accuracy trade-off curve

### 6. Discussion (0.5 pages)
- Implications for skill ecosystem design (SKILL.md spec improvements)
- Limitations and future work: lifelong skill evolution, behavioral routing, skill deduplication

### 7. Conclusion (0.5 pages)
