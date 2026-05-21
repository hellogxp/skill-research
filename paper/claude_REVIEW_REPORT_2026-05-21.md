# Review Report: Compositional Skill Routing for LLM Agents

**Date**: 2026-05-21  
**Reviewer**: Claude Opus 4.6 (Independent Review)  
**Target Venue**: EMNLP 2026 (ACL Rolling Review)  
**Paper Version**: main.tex @ commit 379b1049

---

## 1. Summary

This paper formalizes *Compositional Skill Routing* — given a complex user query and a large skill library (2,209 MCP skills), decompose the query into atomic sub-tasks, retrieve appropriate skills for each, and compose an execution plan. The proposed system SkillWeaver uses a three-stage decompose-retrieve-compose pipeline. The key contribution is SAD (Skill-Aware Decomposition), a retrieval-augmented feedback loop that iteratively aligns decomposition granularity with the available skill vocabulary. Experiments show SAD improves decomposition accuracy (DA) from 51.0% to 67.7% (p < 10^-6), and a DA-conditioned analysis + oracle ablation identifies granularity as the gating factor for retrieval quality.

---

## 2. Reviewer Scores (ARR Format)

| Criterion | Score (1-5) | Justification |
|-----------|-------------|---------------|
| Soundness | 3.5 | Core mechanism well-isolated via oracle ablation; CatR@1 p=0.17 but explained and addressed |
| Substance | 4.0 | 300 queries, 2209 skills, 3 models, transfer experiments, reranker pilot, paraphrase robustness |
| Novelty | 3.5 | Input-side feedback is a meaningful distinction; problem formalization is timely for MCP ecosystem |
| Clarity | 4.0 | Well-structured; discussion section slightly dense; minor notation inconsistencies |
| Significance | 3.5 | Practical value for agent skill routing; benchmark fills a gap; impact depends on adoption |
| **Overall** | **3.5** | **Weak Accept** |
| Confidence | 4 | Familiar with tool-use, retrieval, and agent planning literature |

---

## 3. Strengths

### S1: Problem Formalization is Timely and Well-Scoped

The distinction between *single-skill routing* (SkillRouter, Gorilla) and *compositional* routing is clearly motivated. With MCP servers at 10K+ and growing, this is a real and underserved problem. The formalization (Eq. 1-2) is clean and actionable.

### S2: Analysis-Driven Contribution Structure

The paper's strongest aspect is not SAD itself but the *analytical chain* that contextualizes it:

1. DA-conditioned analysis shows CatR@1 jumps from 34% to 41% when DA=1 → granularity is the gate
2. Oracle step-count ablation (DA=99.3%, CatR@1=39.8%) → isolates representation bottleneck
3. Reranker pilot (+10.3%, p<0.01) → validates the next fix direction

This "diagnose → isolate → validate" structure is rare in the tool-use literature and makes the paper's claims much more credible than raw metric tables would.

### S3: Input-Side vs Output-Side Feedback Taxonomy

The Related Work clearly positions SAD relative to Self-RAG, ReAct, and Reflexion by the *direction* of feedback (modifying the decomposition input vs. refining generation output). This is a conceptual contribution with value beyond this paper.

### S4: 14B Cross-Model Anomaly as Evidence

The counter-intuitive finding (14B Vanilla DA=32% < 7B=51%) is analyzed rather than hidden. The explanation (over-decomposition tendency corrected by SAD) elegantly demonstrates that SAD is a granularity corrector independent of model capacity.

### S5: Transfer Experiments

Category-level held-out (+35.6% relative DA) and random skill held-out (+23.2%) confirm that SAD leverages structural vocabulary rather than memorizing specific skill-hint mappings. This addresses the most obvious generalization concern preemptively.

---

## 4. Weaknesses

### W1 (Major): CatR@1 Improvement is Not Statistically Significant

SAD's primary retrieval metric CatR@1 improves from 34.2% to 37.0% with p=0.17 (Wilcoxon) and CI [-0.005, +0.062] — this spans zero. The paper's argument that "SAD fixes granularity and retrieval follows" is theoretically sound, and the reranker pilot (p<0.01) provides an alternative validated path, but a reviewer focused on the main table will note that the *direct* retrieval improvement is not significant.

**Mitigation in paper**: The oracle ablation and DA-conditioned analysis partially address this. The reranker pilot shifts attention to the @10-to-@1 gap. But the fact remains: SAD's *measured* CatR@1 effect on the main benchmark is within noise.

**Suggestion**: Consider reporting CatR@1 conditioned on DA-improvement queries specifically (the 75 queries SAD fixes), where the effect should be much larger and likely significant. This already appears in Section 5.6 (23.6% → 37.0%) but could be elevated to the main results narrative.

### W2 (Major): Benchmark Queries Are Synthetic

All 300 compositional queries are template-generated from verb phrases. While the skill pool is real (2,209 MCP servers), the queries are artificial compositions. This raises concerns:

- Template patterns may inflate DA (the model learns "verb1 X, verb2 Y" → 2 steps)
- Real user queries are more ambiguous (as shown by human-style DA=8.5%)
- The paraphrase test (200 queries, -4 to -6pp DA) partially mitigates but uses the same template backbone

The human-style evaluation (Appendix A) helps but introduces its own issues: Easy strict DA=2.5% is a red flag that suggests annotation granularity mismatch rather than system failure.

**Suggestion**: (1) Add a BM25 baseline to quantify query-skill lexical overlap; (2) Include 2-3 examples of template queries alongside human queries to let readers calibrate the gap; (3) Explicitly discuss in Limitations whether the template structure inflates DA by making step boundaries unnaturally crisp.

### W3 (Moderate): Compose Stage is Unvalidated

The paper acknowledges this (Section 4.3: "architectural completion"), and the pilot execution study (Appendix I, 76.7% CCR on 30 queries with mock executors) provides some signal. However:

- The compose objective (Eq. 3) uses compatibility scores (I/O type coercion, category Jaccard, keyword co-occurrence) that are never evaluated in isolation
- The DAG construction via "linguistic markers" is underspecified
- α=0.5 is chosen without justification

The paper's explicit scoping helps, but a reviewer may still feel the three-stage framework is oversold relative to a two-stage (decompose-retrieve) system that is actually evaluated.

**Suggestion**: Either (1) rename the framework to emphasize the two evaluated stages, or (2) add a small ablation showing compose-stage selection outperforms greedy top-1 on a subset.

### W4 (Minor): ReAct Baseline is a Category Error

ReAct (DA=0%, CatR@1=15.4%) appears in Table 1 but ReAct does not perform upfront decomposition — it processes tasks incrementally via thought-action-observation loops. Evaluating it on DA (exact step-count match) is measuring something the system is not designed to produce.

**Suggestion**: Add a footnote to Table 1: "ReAct does not produce explicit decompositions; DA=0 reflects protocol mismatch. Included to demonstrate the necessity of structured decomposition for compositional routing."

### W5 (Minor): Single Primary Encoder

All experiments use all-MiniLM-L6-v2 (384-dim, 22M params). The paper acknowledges this in Limitations but does not test even one alternative (e.g., BGE-base, E5-base). Given that the step-count-constrained analysis shows CatR@1 plateaus at ~40% with perfect DA, the encoder choice may be a significant confound.

**Suggestion**: Even a spot-check with one larger encoder (e.g., BGE-base-en-v1.5) on 50 queries would strengthen the claim that the bottleneck is representational ranking rather than embedding capacity.

---

## 5. Questions for Authors

**Q1**: The oracle step-count baseline achieves DA=99.3% and CatR@1=39.8%. SAD achieves DA=67.7% and CatR@1=37.0%. The gap between oracle (39.8%) and SAD (37.0%) is only 2.8pp — does this mean SAD's retrieval benefit is *already* near-optimal conditional on its DA, and further DA improvement would yield diminishing CatR@1 returns?

**Q2**: SAD's hint set uses H=15 skills. How sensitive is performance to H? Have you tested H=5, H=30? The convergence analysis (Table 4) varies iterations but not H.

**Q3**: The 14B model's average predicted step count would disambiguate whether its low DA is truly over-decomposition vs. instruction-following failure (e.g., outputting prose instead of JSON). Can you provide this number?

**Q4**: For the reranker pilot, the 7B model serves as both decomposer and reranker. This means the reranker has already "seen" the decomposition vocabulary. Would an independent reranker (different model or trained cross-encoder) show different patterns?

**Q5**: The paper evaluates category recall (any skill from the correct category) rather than exact skill recall. What is the exact-skill R@1 and R@10? If category recall is 37% but exact recall is 5%, the practical gap is much larger than presented.

---

## 6. Detailed Comments

### Section-by-Section

| Location | Issue | Severity | Suggestion |
|----------|-------|----------|------------|
| Abstract, L46 | "+32%" — main text says "+32.7%" | Nitpick | Align to one decimal |
| Section 5.3, L422 | "SAD DA drops from 66.0%" — Table 1 says 67.7% | Minor | Clarify this is 50-query subset |
| Section 7 (Discussion) | Single dense paragraph (~15 lines) | Minor | Split into 2-3 \paragraph{} blocks |
| Table 4, R0 DA=0.513 | vs Table 1 DA=0.510 | Nitpick | Caption explains; acceptable |
| Section 4.2, L199 | "all-MiniLM-L6-v2 (384-dim)" repeated from Setup | Nitpick | Consider removing from Method |
| Appendix A, Table 8 | Easy Vanilla DA=2.5% | Notable | Add explanation for why easy < hard (counter-intuitive) |
| Eq. 3 | α=0.5 chosen without justification | Minor | Add one sentence on sensitivity |
| Algorithm 1, L239 | τ=0.6 convergence threshold | Minor | Report what happens at τ=0.4, τ=0.8 |

### Writing Quality

The paper is well-written overall. Specific suggestions:

- **Discussion section**: Currently one mega-paragraph. Break into: (1) Cascading structure and SAD's mechanism, (2) Closing the @10-to-@1 gap via reranking, (3) Practical implications (context reduction, latency).
- **Introduction bullet 3** (line 67): "compose serves as architectural completion validated indirectly" — this phrasing is slightly defensive. Consider: "we validate end-to-end viability through a pilot execution study (Appendix I) while focusing our controlled evaluation on the identified bottleneck."
- **Related Work**: The input-side vs output-side paragraph is excellent and could be cited independently.

---

## 7. Missing References / Comparisons

| Work | Relevance | Action |
|------|-----------|--------|
| Chameleon (Lu et al., 2024) | Compositional tool planning with LLM | Cite in Related Work |
| ToolBench (Xu et al., 2024) | 16K+ real APIs benchmark | Compare scale in benchmark section |
| AnyTool (Du et al., 2024) | Hierarchical API retrieval | Already cited, adequate |
| TaskWeaver (Qiao et al., 2024) | Code-first agent framework | Tangentially related, optional |

---

## 8. Acceptance Probability Estimate

| Factor | Assessment |
|--------|------------|
| Problem relevance | High — MCP ecosystem growing, compositional routing underserved |
| Technical contribution | Moderate-High — SAD is simple but well-analyzed; oracle ablation is compelling |
| Experimental rigor | Moderate — good statistical reporting; synthetic benchmark is the weak link |
| Novelty bar for EMNLP | Meets — input-side feedback + comprehensive ablation structure |
| Likely reviewer variance | High — R1 (tool-use expert) likely Accept, R2 (benchmark purist) likely Borderline |

**Estimated Score Distribution**:
- Optimistic case (2/3 reviewers positive): 3.5, 4.0, 3.0 → Accept
- Expected case: 3.5, 3.5, 3.0 → Weak Accept / Borderline
- Pessimistic case (benchmark concerns dominate): 3.0, 3.0, 2.5 → Reject

**Overall Probability**: **70-75% Weak Accept / Accept**

The paper's strongest defense against rejection is the oracle ablation chain — it's very hard to dismiss a paper that precisely isolates its mechanism and validates the next step empirically. The biggest risk is a reviewer who fixates on (1) CatR@1 p=0.17 without reading the DA-conditioned analysis, or (2) the synthetic benchmark without crediting the transfer experiments.

---

## 9. Recommended Priority Fixes Before Submission

| Priority | Fix | Time | Impact |
|----------|-----|------|--------|
| P0 | Split Discussion into 2-3 paragraphs | 10 min | Readability |
| P0 | Clarify paraphrase "66.0%" is 50-query subset | 5 min | Consistency |
| P1 | Add ReAct footnote in Table 1 | 5 min | Preempt W4 criticism |
| P1 | Add one sentence on α=0.5 sensitivity | 5 min | Preempt compose concerns |
| P1 | Add 14B avg step count to Section 5.5 | 10 min | Strengthen 14B argument |
| P2 | Appendix A: explain easy < hard DA inversion | 15 min | Preempt Q5 from reviewers |
| P2 | Report exact-skill R@1 alongside CatR@1 | 30 min | Transparency |
| P3 | Spot-check with one alternative encoder | 2 hours | Strengthen encoder claims |

---

## 10. Final Verdict

**Recommendation: Weak Accept (leaning Accept)**

The paper identifies a well-motivated problem, proposes a simple but effective solution (SAD), and — most importantly — provides an unusually thorough analytical chain that precisely isolates the mechanism and validates future directions. The analysis quality elevates what could be a "yet another pipeline" paper into a genuinely informative contribution to the agent/tool-use literature.

The main weaknesses (synthetic benchmark, non-significant CatR@1, unvalidated compose stage) are real but acknowledged and partially mitigated. The paper would benefit from the priority fixes above, particularly splitting the Discussion and adding the 14B step-count data.

For rebuttal preparation: the most likely fatal attack vector is "CatR@1 is not significant AND benchmark is synthetic — how do we know this works in practice?" The defense should lean on: (1) DA is highly significant and gates retrieval, (2) reranker pilot reaches p<0.01 on the @1 metric, (3) transfer experiments confirm generalization, (4) pilot CCR=76.7% with mock executors.
