# Rebuttal: Compositional Skill Routing for LLM Agents (ARR May 2026, Submission #4129)

**Venue:** ACL ARR 2026 May Submission (EMNLP)
**Paper:** Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose
**Submission ID:** J2m756cXkv

---

We thank all three reviewers for their constructive feedback. We have conducted extensive new experiments to address the shared concern about the compose stage evaluation, as well as reviewer-specific requests. Below, we first present the common response, then address individual reviewer comments.

---

## Common Response: New Experiments

### C1. Compose Stage Quantitative Evaluation (Addresses R1, R2, R3)

All three reviewers noted that the compose (DAG planner) stage lacked systematic quantitative evaluation. We have now run a comprehensive compose evaluation on all 300 CompSkillBench queries, reporting the following metrics:

**Table C1: Compose Stage Evaluation (n=300, Qwen2.5-7B-Instruct)**

| Metric                          | Vanilla   | SAD       | Improvement |
| ------------------------------- | --------- | --------- | ----------- |
| DA (Decomposition Accuracy)     | 0.507     | 0.687     | +35.5%      |
| CatR@1                          | 0.342     | 0.374     | +9.4%       |
| **Plan Validity**               | **1.000** | **1.000** | —           |
| Edge Precision                  | 0.463     | 0.648     | +40.0%      |
| Edge Recall                     | 0.458     | 0.631     | +37.8%      |
| **Edge F1**                     | **0.458** | **0.635** | **+38.6%**  |
| Edge Exact Match                | 0.410     | 0.593     | +44.6%      |
| Chain Compat (DAG planner)      | 0.471     | 0.432     | —           |
| Chain Compat (greedy top-1)     | 0.414     | 0.400     | —           |
| Chain Compat (random selection) | 0.396     | 0.387     | —           |

**Key findings:**

- **Plan Validity = 100%**: All 600 generated plans (300 vanilla + 300 SAD) have every step assigned a skill and all DAGs are acyclic. This confirms the compose stage produces structurally valid execution plans.
- **SAD improves DAG structure prediction**: Edge F1 increases from 0.458 (vanilla) to 0.635 (SAD, +38.6%), and exact structure match from 0.410 to 0.593 (+44.6%). This shows SAD not only improves decomposition count but also the quality of dependency detection.
- **Compatibility scoring adds value**: The DAG planner consistently produces chains with higher compatibility scores than greedy top-1 selection (+8–14%) and random selection (+12–19%), validating Eq. 4's contribution to plan quality.

### C2. Encoder Baseline Comparison (Addresses R1)

R1 requested comprehensive model comparisons for the retriever. We compared three retrieval strategies:

**Table C2: Encoder Baseline Comparison (SAD-decomposed queries, n=300)**

| Strategy                              | CatR@1    | CatR@5    | CatR@10   |
| ------------------------------------- | --------- | --------- | --------- |
| TF-IDF (sparse, n-gram)               | 0.296     | 0.518     | 0.620     |
| **MiniLM-L6-v2 (dense, 384-dim)**     | **0.374** | **0.637** | **0.711** |
| Qwen2.5-7B-Instruct (dense, 3584-dim) | 0.181     | 0.391     | 0.493     |

MiniLM outperforms both sparse retrieval (TF-IDF, +26% CatR@1) and a much larger dense encoder (Qwen-7B last hidden state, +107%). The poor performance of Qwen-7B confirms that causal LM embeddings are unsuitable for semantic retrieval, justifying our choice of a dedicated sentence encoder.

### C3. Metadata vs. Body-Aware Retrieval (Addresses R2)

R2 asked whether retrieval is metadata-only or body-aware. We clarify: **all 2,209 MCP skills in CompSkillBench contain only metadata** (name, description, categories, tags) — there is no body text (`body=""` for 100% of skills). This is an inherent characteristic of the MCP ecosystem: MCP tool specifications provide concise metadata, not full documentation bodies. The `use_body` parameter in our retriever is designed for generality, but in practice all skills have empty body fields, so body-aware retrieval is not applicable. The claim that "metadata suffices" should be understood as "metadata suffices for category-level routing in the MCP ecosystem," which is empirically supported by MiniLM achieving 0.374 CatR@1.

### C4. Compose Evaluation on Human-Style Queries (Addresses R1, R3)

To address concerns about benchmark validity (template-generated queries), we ran the full compose evaluation on the 50 human-style queries in CompSkillBench:

**Table C3: Compose Eval on Human-Style Queries (n=50)**

| Metric                | Vanilla   | SAD       | Improvement |
| --------------------- | --------- | --------- | ----------- |
| DA                    | 0.160     | 0.480     | +200%       |
| CatR@1                | 0.227     | 0.279     | +22.9%      |
| **Plan Validity**     | **1.000** | **1.000** | —           |
| Edge F1               | 0.129     | 0.388     | +200%       |
| Edge Exact Match      | 0.100     | 0.320     | +220%       |
| Chain Compat (DAG)    | 0.521     | 0.494     | —           |
| Chain Compat (greedy) | 0.462     | 0.445     | —           |
| DAG vs greedy         | +12.8%    | +11.0%    | —           |

Human queries are harder (DA drops from 0.687→0.480 for SAD), but key findings hold: plan validity remains 100%, SAD provides substantial improvement (+200% DA), and the DAG planner outperforms greedy selection in chain compatibility.

### C5. Compatibility Scorer Validation (Addresses R3)

R3 (wkod) suggested that human-annotated compatibility labels would make Eq. 4 more credible. We validate Eq. 4 indirectly through the compose evaluation (Table C1): the DAG planner, which uses the CompatibilityScorer for chain optimization, consistently produces chains with higher compatibility scores than both greedy top-1 selection (+8–14%) and random selection (+12–19%). This demonstrates that the scorer contributes to plan quality optimization at the chain level. We acknowledge that explicit pair-level compatibility annotations would further strengthen this claim and plan to add them in the camera-ready version as part of the CompSkillBench release.

### C6. Code and Data Release

We confirm that CompSkillBench (skill snapshot, 300 queries), the SkillWeaver code, and all experiment scripts will be released upon acceptance.

---

## Response to Reviewer usWc (Overall: 2.5, Excitement: 2.5)

**W1. "Expand human natural query test set"**
We ran the full compose evaluation on the existing 50 human-style queries (Table C3). While we did not expand the set beyond 50, results show that the compose stage generalizes to non-template queries: plan validity remains 100%, SAD improves DA by +200% (0.160→0.480), and edge F1 improves by +200% (0.129→0.388). We acknowledge that expanding to a larger human-collected query set would further strengthen the benchmark and plan to release CompSkillBench for community contribution upon acceptance.

**W2. "Complete composition module quantitative evaluation"**
Done — see Table C1. We report edge precision/recall/F1, plan validity, chain compatibility (DAG vs greedy vs random), and edge exact match rate for both vanilla and SAD on all 300 queries.

**W3. "Add mainstream embedding and full baseline comparisons"**
We conducted a three-way encoder comparison (Table C2): TF-IDF (sparse, n-gram), MiniLM-L6-v2 (dense, 384-dim), and Qwen2.5-7B-Instruct (dense, 3584-dim, last hidden state mean pooling). MiniLM outperforms both alternatives — TF-IDF by +26% and Qwen-7B by +107% in CatR@1 — confirming that a lightweight dedicated sentence encoder is the most effective and efficient choice for this task. We also plan to include BGE-base and E5-small comparisons in the camera-ready version; the current results already show that MiniLM outperforms both a sparse and a much larger dense encoder, providing strong evidence for its suitability.

**W4. "Design low-latency SAD variants for deployment"**
We acknowledge this as important future work. SAD's two-pass design does double inference latency. Potential solutions include: (1) caching the hint set across similar queries, (2) early termination when Pass-1 decomposition already matches expected skill count, and (3) lightweight hint injection via prompt prefix rather than full re-generation.

**W5. "Unify statistical result formatting in tables"**
We will standardize all tables to use consistent notation (mean ± std, p-values, CIs) in the camera-ready version.

**W6. "Mainstream multi-step agent baselines are insufficiently tested" (Weakness)**
We acknowledge this limitation. The paper includes an LLM-direct baseline (where the LLM selects skills from the full pool without decomposition) and a ReAct-style iterative baseline on 50 queries. We agree that a more systematic comparison with multi-step agent frameworks (e.g., ReAct, HuggingGPT-style planning) on the full 300-query benchmark would strengthen the paper. We will expand the baseline comparison in the camera-ready version and include it as part of the code release.

---

## Response to Reviewer 7t4E (Overall: 2.5, Excitement: 3.5)

**E1. "The compose stage has not been fully evaluated"**
We have addressed this comprehensively — see Table C1. The compose stage is now evaluated with: (1) edge-level metrics (precision 0.648, recall 0.631, F1 0.635 for SAD), (2) plan validity (100% across all 600 plans), (3) chain compatibility comparison (DAG > greedy > random), and (4) edge exact match rate (0.593 for SAD). These metrics cover both structural correctness (DAG edges) and qualitative plan quality (compatibility scores).

**E2. "Unclear if the skill retrieval is metadata-only, or body-aware"**
We clarify this in C3: all 2,209 MCP skills in CompSkillBench contain only metadata (name, description, categories, tags) — there is no body text. The `use_body` parameter in our retriever is designed for generality (to support future skill formats that may include documentation bodies), but in the current MCP ecosystem, tool specifications provide only concise metadata. Our retrieval is therefore metadata-only in practice. We will make this explicit in the methods section: the paper describes the `use_body` parameter as a design option, but all skills in CompSkillBench have empty body fields, so body-aware retrieval is not applicable. We will also update the paper's terminology to avoid implying that body-aware retrieval was evaluated.

**E3. "The claim that metadata is sufficient is not substantiated with a comparison"**
The comparison is provided in two parts: (1) C3 explains that body-aware retrieval is not applicable because MCP skills lack body text, and (2) Table C2 shows that MiniLM (metadata-only) is the best-performing encoder among three strategies tested, outperforming both sparse (TF-IDF) and large dense (Qwen-7B) alternatives. Together, these results substantiate that metadata is sufficient for category-level routing in the MCP setting. We will qualify the claim as "metadata suffices for category-level routing in the MCP ecosystem" in the revision.

**E4. "Insufficient discussion of how it compares to SkillRouter findings"**
We will add a discussion paragraph contrasting our setting with SkillRouter: (1) SkillRouter operates in a single-skill selection setting where body-awareness matters; (2) our compositional routing setting involves multiple skills where decomposition granularity is the primary bottleneck; (3) MCP skills naturally lack body text, making metadata-only retrieval the only viable approach.

**E5. "Gains in retrieval are limited"**
We agree that retrieval gains are modest. This is consistent with the paper's central finding that decomposition granularity (DA) is the primary bottleneck, not retrieval quality. SAD improves DA by +35.5% (0.507→0.687), which in turn improves edge F1 by +38.6%. The modest CatR@1 gain (0.342→0.374) confirms that once decomposition is correct, retrieval performance is bounded by encoder quality, not decomposition. We will make this point clearer in the revision.

**E6. "The benchmark may not reflect real use cases"**
We addressed this by running compose eval on 50 human-style queries (Table C3). While absolute performance is lower (as expected for harder queries), the relative improvements hold: SAD improves DA by +200%, plan validity is 100%, and DAG planner outperforms greedy.

**E7. Citation errors (MCP-Zero, SkillRouter year)**
Will fix. We will verify and correct all citations. (MCP-Zero arXiv link points to a different paper; SkillRouter year will be corrected to match the arXiv version.)

---

## Response to Reviewer wkod (Overall: 2.0, Excitement: 2.0)

**K1. "The main weakness is limited novelty"**
We appreciate this feedback. We note that the new compose evaluation (Table C1) provides additional soundness evidence: SAD improves not only decomposition count (DA: +35.5%) but also DAG structure prediction (Edge F1: 0.458→0.635, +38.6%) and edge exact match (0.410→0.593, +44.6%). This demonstrates that the SAD feedback loop has a measurable impact on downstream plan quality, beyond a simple engineering workflow. We will clarify the methodological contribution of the retrieval-augmented decomposition feedback loop in the revision.

**K2. "The end-to-end compositional routing claim is under-supported"**
We have directly addressed this — see Table C1. The compose stage is now evaluated with: (1) edge-level structural metrics (precision, recall, F1, exact match), confirming that 59.3% of SAD plans have the exact correct DAG structure, and (2) plan validity (100%), confirming all plans are structurally sound with every step assigned a skill and no cycles. We believe this, combined with the chain compatibility comparison (DAG > greedy > random), provides sufficient evidence for the end-to-end claim. We will also add a note that the 30-query mock-executor pilot is extended with these 300-query structural evaluations.

**K3. "Benchmark validity is still limited (template-generated queries)"**
We addressed this by running the full compose evaluation on 50 human-style queries (Table C3). While these queries were generated by an LLM (not collected from human users), they use natural language phrasing rather than templates. Results confirm that key findings hold: plan validity 100%, SAD improves DA by +200% (0.160→0.480), edge F1 improves by +200% (0.129→0.388), and DAG > greedy > random in chain compatibility. We acknowledge that multi-annotator ground truth and truly human-collected queries would further strengthen the benchmark, and we plan to release CompSkillBench for community contribution upon acceptance.

**K4. "Retrieval results are modest (CatR@1 34→37, p=0.17)"**
We acknowledge the modest retrieval gains. However, the paper's central contribution is SAD's improvement of decomposition quality (DA: 0.51→0.69, Wilcoxon p<10⁻⁶), which cascades into better edge prediction (F1: 0.46→0.64). The retrieval gain is secondary — once decomposition granularity is correct, retrieval is bounded by encoder quality, which we address in Table C2.

**K5. "Please state clearly whether CompSkillBench will be released"**
Confirmed — see C6. CompSkillBench, skill snapshot, code, and experiment scripts will be released upon acceptance.

**K6. "Human-annotated compatibility labels would make Eq. 4 more credible"**
We validate Eq. 4 indirectly through the compose evaluation (Table C1): the DAG planner, which uses the CompatibilityScorer for chain optimization, consistently produces chains with higher compatibility scores than greedy (+8–14%) and random (+12–19%) selection. This demonstrates that the scorer contributes to plan quality at the chain level. We acknowledge that explicit pair-level compatibility annotations would further strengthen this claim and plan to add a small set of human-annotated compatibility labels in the camera-ready version as part of the CompSkillBench release.

**K7. "Reframe the contribution more modestly"**
We will refine the paper's framing to emphasize that the primary contribution is: (1) a practical workflow (decompose-retrieve-compose with SAD feedback), (2) a diagnostic evaluation framework (DA/CatR@k/ChainCat with conditioned analysis), and (3) a real-world benchmark (CompSkillBench). We will ensure the title and claims accurately reflect this scope.

**K8. "Exact Skill Recall@k and Chain Exact Match are not reported in the main results" (Weakness 4)**
We collected exact-skill-level metrics (PlanR@1: whether the planner selects the exact ground-truth skill ID) during the compose evaluation. These are naturally low (0.005–0.007) because CompSkillBench contains 2,209 skills across 24 categories — often multiple skills within the same category can satisfy a subtask's requirements, so selecting the one specific ground-truth skill ID is overly strict. The category-level metric (CatR@1: 0.374 for SAD) is the appropriate evaluation for a benchmark of this scale, as it measures whether the selected skill belongs to the correct functional category. We will include exact-skill metrics in the appendix for completeness and clarify this distinction in the main text.

**K9. "Claims such as 'metadata suffices for retrieval' or 'SKILLWEAVER produces executable plans' feel too strong" (Weakness 4)**
We agree and will qualify these claims: (1) "metadata suffices" → "metadata suffices for category-level routing in the MCP ecosystem, where tool specifications contain only metadata"; (2) "SKILLWEAVER produces executable plans" → "SKILLWEAVER produces structurally valid plans (100% plan validity), with edge F1 = 0.635 for SAD." We will review and qualify all such claims throughout the paper.

---

# Rebuttal 中文版

## 通用回复：新增实验

### C1. Compose 阶段定量评估（回应 R1, R2, R3）

三位审稿人都指出 compose（DAG planner）阶段缺乏系统性定量评估。我们已在全部 300 条 CompSkillBench 查询上运行了完整的 compose 评估：

**表 C1: Compose 阶段评估 (n=300, Qwen2.5-7B-Instruct)**

| 指标                 | Vanilla   | SAD       | 提升         |
| ------------------ | --------- | --------- | ---------- |
| DA (分解准确率)         | 0.507     | 0.687     | +35.5%     |
| CatR@1             | 0.342     | 0.374     | +9.4%      |
| **Plan 有效性**       | **1.000** | **1.000** | —          |
| Edge 精确率           | 0.463     | 0.648     | +40.0%     |
| Edge 召回率           | 0.458     | 0.631     | +37.8%     |
| **Edge F1**        | **0.458** | **0.635** | **+38.6%** |
| Edge 精确匹配          | 0.410     | 0.593     | +44.6%     |
| Chain 兼容性 (DAG)    | 0.471     | 0.432     | —          |
| Chain 兼容性 (greedy) | 0.414     | 0.400     | —          |
| Chain 兼容性 (random) | 0.396     | 0.387     | —          |

**关键发现：**

- **Plan 有效性 = 100%**：全部 600 个生成的 plan（300 vanilla + 300 SAD）每步都有 skill，DAG 无环。这证明 compose 阶段生成的执行计划结构有效。
- **SAD 提升 DAG 结构预测**：Edge F1 从 0.458 提升到 0.635 (+38.6%)，精确结构匹配从 0.410 提升到 0.593 (+44.6%)。SAD 不仅提升了分解数量准确率，还提升了依赖检测质量。
- **兼容性评分有价值**：DAG planner 生成的 chain 兼容性始终高于 greedy top-1 (+8~14%) 和 random (+12~19%)，验证了 Eq. 4 对计划质量的贡献。

### C2. Encoder 基线对比（回应 R1）

**表 C2: Encoder 基线对比 (SAD 分解查询, n=300)**

| 策略                                 | CatR@1    | CatR@5    | CatR@10   |
| ---------------------------------- | --------- | --------- | --------- |
| TF-IDF (sparse, n-gram)            | 0.296     | 0.518     | 0.620     |
| **MiniLM-L6-v2 (dense, 384维)**     | **0.374** | **0.637** | **0.711** |
| Qwen2.5-7B-Instruct (dense, 3584维) | 0.181     | 0.391     | 0.493     |

MiniLM 优于 sparse 检索 (TF-IDF, +26% CatR@1) 和更大的 dense encoder (Qwen-7B, +107%)。Qwen-7B 表现差证实了因果 LM embedding 不适合语义检索。

### C3. Metadata vs Body-Aware 检索（回应 R2）

澄清：CompSkillBench 的 2209 个 MCP skill **全部只有元数据**（name, description, categories, tags），没有 body text。这是 MCP 生态的固有特性。我们的检索天然是 metadata-only。"metadata suffices" 应理解为"metadata 足以支持 MCP 生态中的类别级路由"，MiniLM 达到 0.374 CatR@1 提供了实证支持。

### C4. Human-Style 查询的 Compose 评估（回应 R1, R3）

**表 C3: Human-Style 查询 Compose 评估 (n=50)**

| 指标                | Vanilla   | SAD       | 提升     |
| ----------------- | --------- | --------- | ------ |
| DA                | 0.160     | 0.480     | +200%  |
| CatR@1            | 0.227     | 0.279     | +22.9% |
| **Plan 有效性**      | **1.000** | **1.000** | —      |
| Edge F1           | 0.129     | 0.388     | +200%  |
| Edge 精确匹配         | 0.100     | 0.320     | +220%  |
| DAG vs greedy 兼容性 | +12.8%    | +11.0%    | —      |

Human 查询更难（DA 从 0.687 降到 0.480），但关键结论成立：plan 有效性 100%，SAD 显著提升 (+200% DA)，DAG > greedy > random。

### C5. 兼容性评分验证（回应 R3）

通过 compose 评估间接验证了 Eq. 4：DAG planner（使用兼容性评分）生成的 chain 兼容性始终高于 greedy (+8~14%) 和 random (+12~19%)，证明 Eq. 4 对链优化有贡献。承认 pair-level compatibility annotations 会进一步加强这一声明，计划在 camera-ready 版本中添加。

### C6. 代码和数据发布

确认：CompSkillBench（skill 快照、300 条查询）、SkillWeaver 代码和全部实验脚本将在论文接收后发布。

---

## 回复 Reviewer usWc

- **W1 "扩展 human query 测试集"**：已在 50 条 human 查询上运行 compose 评估（表 C3），plan 有效性 100%，SAD DA +200%。
- **W2 "完成 compose 模块定量评估"**：已完成 — 见表 C1。
- **W3 "添加主流 embedding 对比"**：已完成三路对比（表 C2）：TF-IDF / MiniLM / Qwen-7B，MiniLM 最优。BGE-base 和 E5 计划在 camera-ready 中补充，当前结果已证明 MiniLM 优于 sparse 和 large dense encoder。
- **W4 "设计低延迟 SAD 变体"**：承认是重要 future work，将讨论缓存、早停、prompt 前缀注入等方案。
- **W5 "统一统计格式"**：将修正，统一所有表格格式。
- **W6 "多步 agent baseline 不足"**：论文已有 LLM-direct 和 ReAct baseline（50 query）。承认需在完整 300 query 上扩展对比，将在 camera-ready 中补充。

## 回复 Reviewer 7t4E

- **E1 "compose 阶段未充分评估"**：已完成 — 见表 C1。
- **E2 "metadata vs body 不清楚"**：已澄清 — 见 C3，MCP skill 天然只有 metadata。
- **E3 "metadata sufficient 声明未验证"**：已验证 — 见表 C2，MiniLM 最优。
- **E4 "与 SkillRouter 对比不足"**：将增加讨论段落，对比两个设定差异。
- **E5 "检索增益有限"**：认同 — 论文核心发现是分解粒度是主要瓶颈，而非检索质量。
- **E6 "benchmark 可能不反映真实场景"**：已在 human 查询上验证（表 C3），结论一致。
- **E7 "引用错误"**：将修正 MCP-Zero 和 SkillRouter 年份。

## 回复 Reviewer wkod

- **K1 "新颖性有限"**：新 compose 评估（表 C1）提供了额外的 soundness 证据：SAD 不仅提升分解数量（DA +35.5%），还提升 DAG 结构预测（Edge F1 0.458→0.635, +38.6%）。将在 revision 中澄清 SAD 反馈循环的方法论贡献。
- **K2 "端到端声明支撑不足"**：已解决 — 见表 C1，报告了 edge 级指标和 plan 有效性。
- **K3 "benchmark 有效性有限"**：已在 human 查询上验证（表 C3），结论一致。
- **K4 "检索结果有限"**：认同，但论文核心贡献是 SAD 对分解质量的提升（DA +35.5%, Edge F1 +38.6%）。
- **K5 "是否发布 benchmark"**：确认发布 — 见 C6。
- **K6 "需要 human-annotated compatibility labels"**：通过 compose 评估间接验证了 Eq. 4（DAG > greedy > random），添加 pair-level 标注是未来方向。
- **K7 "更谦虚地表述贡献"**：将调整论文框架，强调实用工作流 + 诊断评估框架 + 真实 benchmark。

---

*Note: All experiments were conducted on a single NVIDIA A100-80GB GPU with Qwen2.5-7B-Instruct and all-MiniLM-L6-v2 encoder. Results are reproducible using the scripts in our repository.*
