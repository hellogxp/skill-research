# Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose

**Total Comments:** 4

---

# Main Submission

## Comment by aclweb.org/ACL/ARR/2026/May/Submission4129/Authors
**Date:** 2026-05-23 21:18:08

**A1 Limitations Section:** This paper has a limitations section.

**A2 Elaboration:** Ethics Statement section

**A2 Potential Risks:** Yes

**Association For Computational Linguistics - Blind Submission License Agreement:** On behalf of all authors, I agree

**B1 Cite Creators Of Artifacts:** Yes

**B1 Elaboration:** Section 4 cites FAISS, Qwen2.5, all-MiniLM-L6-v2, and MCP specification

**B2 Discuss The License For Artifacts:** N/A

**B2 Elaboration:** Skills sourced from public MCP registries; no proprietary licenses involved

**B3 Artifact Use Consistent With Intended Use:** Yes

**B3 Elaboration:** Section 4 and Ethics Statement

**B4 Data Contains Personally Identifying Info Or Offensive Content:** N/A

**B4 Elaboration:** Benchmark consists of tool metadata (names and descriptions) with no personal data

**B5 Documentation Of Artifacts:** Yes

**B5 Elaboration:** Section 4 details CompSkillBench construction; code and data to be released upon acceptance

**B6 Elaboration:** Section 4 and Appendix A provide category distributions and difficulty breakdown

**B6 Statistics For Data:** Yes

**B Use Or Create Scientific Artifacts:** Yes

**C1 Elaboration:** Section 4: Qwen2.5-7B and 14B; single NVIDIA V100 GPU

**C1 Model Size And Budget:** Yes

**C2 Elaboration:** Section 4 (Setup) and Appendix E: H=15 hints, temperature=0, FAISS HNSW index

**C2 Experimental Setup And Hyperparameters:** Yes

**C3 Descriptive Statistics:** Yes

**C3 Elaboration:** Section 5 and Appendix G: Wilcoxon signed-rank tests, bootstrap 95% CIs, n=300

**C4 Elaboration:**

Section 4: FAISS HNSW index (M=32, efSearch=64), all-MiniLM-L6-v2 encoder (384-dim), Qwen2.5-7B/14B (temperature=0, max_new_tokens=512)

**C4 Parameters For Packages:** Yes

**C Computational Experiments:** Yes

**D1 Elaboration:** No human annotation study

**D1 Instructions Given To Participants:** N/A

**D2 Elaboration:** No human subjects

**D2 Recruitment And Payment:** N/A

**D3 Data Consent:** N/A

**D3 Elaboration:** No human data collection

**D4 Elaboration:** No human subjects; uses only publicly available MCP metadata

**D4 Ethics Review Board Approval:** N/A

**D Human Subjects Including Annotators:** No

**E1 Elaboration:**

AI coding assistants used for implementation and writing refinement. All scientific claims, experimental design, and analysis are by the authors.

**E1 Information About Use Of Ai Assistants:** Yes

**Emnlp 2026 Ai Reviewing Experiment:** yes

**E Ai Assistants In Research Or Writing:** Yes

**Tldr:**

We formalize compositional skill routing for LLM agents and propose Iterative Skill-Aware Decomposition (SAD), achieving +32.7% decomposition accuracy on 2,209 real MCP skills.

**Abstract:**

LLM agents increasingly rely on external skills---reusable tool specifications---but real-world tasks often require composing multiple skills, not just selecting one. We formalize this as the Compositional Skill Routing problem: given a complex user query and a large skill library, decompose the query into atomic sub-tasks, retrieve the appropriate skill for each sub-task, and compose an executable plan. We present SkillWeaver, a decompose-retrieve-compose framework combining an LLM task decomposer, a bi-encoder skill retriever with FAISS indexing, and a dependency-aware DAG planner. To support evaluation, we introduce CompSkillBench, a benchmark of 300 compositional queries over 2,209 real MCP server skills spanning 24 functional categories, sourced from the public MCP ecosystem. Our experiments reveal that task decomposition quality is the primary bottleneck: standard LLM decomposition reaches only 34.2% category recall at the step level. To address this, we propose Iterative Skill-Aware Decomposition (SAD), a retrieval-augmented feedback loop that iteratively aligns decomposition with available skills. SAD improves decomposition accuracy from 51.0% to 67.7% (+32.7%, Wilcoxon $p < 10^{-6}$) in a single iteration; DA-conditioned analysis confirms that correct granularity is the prerequisite for effective retrieval (CatR@1 rises from 34% to 41% when DA=1). SkillWeaver reduces context window consumption by over 99%, and transfer experiments confirm generalization (+35.6% relative DA gain even when target categories are absent from the retrieval pool).

**Author Submission Checklist:** yes

**Authorids:** ['~Xueping_Gao1']

**Authors:** ['Xueping Gao']

**Consent To Share Data:** yes

**Consent To Share Submission Details:** On behalf of all authors, we agree to the terms above to share our submission details.

**Contribution Types:**

['NLP engineering experiment', 'Publicly available software and/or pre-trained models', 'Data resources']

**Country Of Origin:** CN

**Keywords:**

['compositional skill routing', 'task decomposition', 'tool retrieval', 'MCP skills', 'LLM agents', 'retrieval-augmented decomposition', 'multi-tool composition']

**Languages Studied:** English

**Paper Type:** Long

**Paperhash:** gao|compositional_skill_routing_for_llm_agents_decompose_retrieve_and_compose

**Pdf:** /pdf/df96d24c2b43e0603ca2e4fd43ad342131dd0027.pdf

**Preferred Venue:** EMNLP

**Preprint:** no

**Preprint Status:** There is a non-anonymous preprint (URL specified in the next question).

**Reassignment Request Area Chair:** This is not a resubmission

**Reassignment Request Reviewers:** This is not a resubmission

**Research Area:** LLM agents

**Research Area Keywords:** tool use, function calling, planning in agents, agent evaluation, LLM-based controllers

**Venue:** ACL ARR 2026 May Submission

**Venueid:** aclweb.org/ACL/ARR/2026/May/Submission

**Visa Needs:** yes

---


# Comments and Reviews

## Comment by aclweb.org/ACL/ARR/2026/May/Submission4129/Reviewer_usWc
**Date:** 2026-06-30 22:20:56

**Soundness:** 3

**Confidence:** 3

**Knowledge Of Or Educated Guess At Author Identity:** No

**Knowledge Of Paper:** N/A, I do not know anything about the paper from outside sources

**Knowledge Of Paper Source:** ['N/A, I do not know anything about the paper from outside sources']

**Comments Suggestions And Typos:**

Expand human natural query test set, complete composition module quantitative evaluation, add mainstream embedding and full baseline comparisons, design low-latency SAD variants for deployment. Unify statistical result formatting in tables.

**Datasets:** 4

**Ethical Concerns:** There are no concerns with this submission

**Excitement:** 2.5

**Impact Of Knowledge Of Paper:** N/A, I do not know anything about the paper from outside sources

**Overall Assessment:** 2.5

**Paper Summary:**

This paper studies multi-skill compositional routing for LLM agents, proposes SKILLWEAVER pipeline and SAD decomposition feedback method, and builds COMPSKILLBENCH benchmark based on MCP skills. Experiments prove decomposition granularity is the core bottleneck and SAD brings accuracy gains.

**Publication Ethics Policy Compliance:**

I used a privacy-preserving tool exclusively for the use case(s) approved by PEC policy, such as language edits

**Reproducibility:** 3

**Reviewer Certification:** Yes

**Software:** 4

**Summary Of Strengths:**

This work formalizes an overlooked multi-tool routing task, puts forward a novel retrieval feedback decomposition strategy, and constructs a large real-skill benchmark for follow-up research. SAD’s performance improvement is verified by sufficient ablation and generalization experiments.

**Summary Of Weaknesses:**

Benchmark queries are mostly template-generated with weak real-scene generalization; the DAG composition module lacks systematic quantitative evaluation; retrieval only uses a lightweight encoder without comprehensive model comparison; mainstream multi-step agent baselines are insufficiently tested; SAD doubles inference latency without optimization solutions. These critical flaws weaken overall contribution value.

---

## Comment by aclweb.org/ACL/ARR/2026/May/Submission4129/Reviewer_7t4E
**Date:** 2026-07-01 19:48:06

**Soundness:** 2

**Confidence:** 3

**Knowledge Of Or Educated Guess At Author Identity:** No

**Knowledge Of Paper:** N/A, I do not know anything about the paper from outside sources

**Knowledge Of Paper Source:** ['N/A, I do not know anything about the paper from outside sources']

**Comments Suggestions And Typos:**

- MCP-Zero citation is wrong, the arxiv link is for a completely different paper.
- year for SkillRouter is inconsistent with the year on arxiv link (2025 instead of 2026, though it's possible SkillRouter appeared in 2025 before being put on arxiv).

**Datasets:** 3

**Ethical Concerns:** There are no concerns with this submission.

**Excitement:** 3.5

**Impact Of Knowledge Of Paper:** N/A, I do not know anything about the paper from outside sources

**Needs Ethics Review:** No

**Overall Assessment:** 2.5

**Paper Summary:**

This paper studies if LLM agents can decompose a complex task into sub-tasks, assign skill per sub-task, and compose into a coherent plan.
contributions are SkillWeaver, a framework to do so, a CompSkillBench benchmark, and SAD, which uses retrieved skill hints to improve task decomposition (granularity).contributions are SkillWeaver, a framework to do so, and CompSkillBench benchmark.

**Publication Ethics Policy Compliance:** I did not use any generative AI tools for this review

**Reproducibility:** 3

**Reviewer Certification:** Yes

**Software:** 3

**Summary Of Strengths:**

- This is a timely and important area of research.
- There is a clear empirical finding, that getting the granularity of sub-task decomposition right is important, and that the SAD approach proposed is an effective way to do this.
- The paper is honest and upfront with some of its limitations, e.g. that the compose stage, while described, has not been fully empirically evaluated.

**Summary Of Weaknesses:**

- The compose stage has not been fully evaluated.
- It is unclear if the skill retrieval is metadata-only, or body-aware. The methods section describe both, but intro mentions only metadata and there is a claim that metadata is sufficient. However this claim is not substantiated with a comparison against body-aware retrieval empirically, which significantly weakens it.
- The above weakness is amplified by insufficient discussion of how it compares to the findings in the SkillRouter paper, which is that skill body-awareness is critical to successful skill retrieval (albeit in a different, single skill set-up, but I think still quite relevant to the claim in this paper.)  
- The gains in retrieval are limited, with the main finding that the gains in SAD is due to better granularity, rather than other aspects such as retrieval performance. Note that CatR@1 is about 40%, and gains are entirely explained by the better granularity. This point relates to the two above.
- The benchmark may not reflect real use cases as they are generated using templates and LLMs.

---

## Comment by aclweb.org/ACL/ARR/2026/May/Submission4129/Reviewer_wkod
**Date:** 2026-07-06 22:47:21

**Soundness:** 3

**Confidence:** 4

**Knowledge Of Or Educated Guess At Author Identity:** No

**Knowledge Of Paper:** N/A, I do not know anything about the paper from outside sources

**Knowledge Of Paper Source:** ['N/A, I do not know anything about the paper from outside sources']

**Comments Suggestions And Typos:**

1. Please reframe the contribution more modestly as a practical workflow plus benchmark/diagnostic evaluation, unless a genuinely new routing or decomposition method can be added. In the current version, the method itself does not seem sufficiently novel for a main ACL-style contribution.

2. Please either evaluate the compose stage directly or narrow the paper's claims/title to reflect that the current contribution is primarily decomposition plus retrieval. A small set of human-annotated compatibility labels would already make Eq. 4 much more credible.

3. Please state clearly whether COMPSKILLBENCH, the skill snapshot, and code will be released. If not, reproducibility and benchmark usefulness are substantially reduced.

**Datasets:** 3

**Ethical Concerns:** There are no concerns with this submission

**Excitement:** 2

**Impact Of Knowledge Of Paper:** N/A, I do not know anything about the paper from outside sources

**Needs Ethics Review:** No

**Overall Assessment:** 2

**Paper Summary:**

This paper studies compositional skill routing for LLM agents. Instead of selecting a single tool or skill for a user request, the paper formalizes the setting where a complex request must be decomposed into atomic sub-tasks, each sub-task must be matched to an appropriate skill from a large library, and the selected skills must be composed into an executable plan. The proposed framework, SKILLWEAVER, consists of an LLM-based decomposer, a bi-encoder/FAISS skill retriever, and a compatibility-aware DAG planner.

The main empirical contribution is COMPSKILLBENCH, a benchmark of 300 compositional queries over 2,209 MCP skills across 24 categories. The main method contribution is Skill-Aware Decomposition (SAD), a two-pass procedure that first decomposes the query, retrieves candidate skills, and then feeds the retrieved skill hints back into the decomposer to better align the decomposition granularity with the available skill library. The reported results show a significant improvement in decomposition accuracy from 51.0% to 67.7%, while the aggregate top-1 category retrieval gain is smaller and not statistically significant. The paper argues that decomposition granularity is the primary bottleneck, and that reranking or stronger encoders are promising next steps for improving top-1 skill retrieval. My overall reading is that the work is mostly an engineering workflow and a quantitative evaluation setup rather than a new technical method.

**Publication Ethics Policy Compliance:** I did not use any generative AI tools for this review

**Reproducibility:** 3

**Reviewer Certification:** Yes

**Software:** 3

**Summary Of Strengths:**

1. The paper addresses a timely and well-motivated problem. Many practical agent requests require multiple tools or skills, so moving beyond single-tool routing is a useful framing for the ACL community working on tool-augmented language agents.

2. The proposed workflow is practically useful. Even if the method is straightforward, a decompose-retrieve-compose pipeline with skill-aware feedback is something practitioners could adopt as a reasonable engineering recipe.

3. The decomposition/retrieval separation is analytically useful. The paper does not only report an end metric; it introduces DA, CatR@k, Chaincat, and conditioned analyses that make it possible to see where the routing pipeline fails.

**Summary Of Weaknesses:**

1. The main weakness is limited novelty. The proposed method is essentially a workflow that combines standard components: LLM decomposition, dense retrieval, retrieved hints, and a planner. The central conclusion, that better decomposition granularity improves downstream retrieval, is useful but fairly obvious. I do not see a substantial new algorithmic or methodological contribution beyond packaging this workflow and measuring it.

2. The end-to-end compositional routing claim is under-supported. The title and framework emphasize "Decompose, Retrieve, and Compose", but the compose stage is not isolatedly evaluated because the benchmark lacks compatibility annotations. The main experiments measure decomposition and category retrieval, not whether a correct executable DAG is produced. The 30-query mock-executor pilot is useful as a sanity check, but it does not establish real end-to-end skill execution or robust composition.

3. The benchmark validity is still limited. COMPSKILLBENCH uses real MCP skills, which is valuable, but the queries are template-generated from category verb phrases. The "human-style" set is also generated by another LLM rather than collected from human users. Since DA is the central metric, subjective step boundaries are a serious concern: the paper itself notes that reasonable decompositions can add authentication, verification, or preprocessing steps and be scored as DA=0. DA+/-1 partly mitigates this, but it does not replace multi-annotator ground truth or an ambiguity-aware evaluation protocol.

4. The main retrieval results are modest. SAD improves DA significantly, but aggregate CatR@1 improves only from 34.2% to 37.0% with p=0.17 and a confidence interval including zero. Chaincat remains very low (7.3% after SAD in Table 2). This makes claims such as "metadata suffices for retrieval" or "SKILLWEAVER produces executable plans" feel too strong unless they are qualified. The paper defines exact Skill Recall@k and Chain Exact Match, but these exact-skill metrics are not reported in the main results.

---
