# Paper Review Report

**Date**: 2026-05-20  
**Reviewer**: Claude (Paper Reviewer Skill v1.0)  
**Target Venue**: EMNLP 2026 (ACL Rolling Review)  
**Reviewed Version**: main.tex @ 2026-05-20 17:19, references.bib @ 2026-05-19 21:52

---

## 1. 论文信息

| 项目 | 内容 |
|------|------|
| **标题** | Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose |
| **目标会议** | EMNLP 2026 (ARR submission) |
| **页数** | ~8 pages (main) + ~5 pages (appendix, 9 sections A-I) |
| **引用数** | 31 references |
| **系统名** | SkillWeaver |
| **Benchmark** | CompSkillBench (300 queries, 2,209 skills, 24 categories) |
| **核心方法** | SAD (Skill-Aware Decomposition) + LLM-Listwise Reranker pilot |

---

## 2. 一句话总结

本文形式化了 Compositional Skill Routing 问题，提出 SAD "input-side" 反馈环将分解准确率提升 32.7%（p<10⁻⁶），DA-conditioned 分析和 step-count-constrained oracle 精确定位了 granularity 作为 gating factor，LLM-listwise reranker pilot (+10.3% relative CatR@1, p<0.01) 验证了下一步瓶颈的解决方向。

---

## 3. 十维度评分表

| # | 维度 | 分数 | 一句话评价 |
|---|------|------|------|
| 1 | 问题定义与动机 | **4.5** | Compositional Skill Routing 形式化清晰(Eq.1)，与 single-skill/flat-toolset 工作区分明确 |
| 2 | 技术贡献与新颖性 | **3.7** | "Input-side vs output-side feedback" 框架提升了 novelty 叙事；step-count oracle + reranker pilot 完善了贡献层次 |
| 3 | 实验设计 | **4.2** | Step-count-constrained ablation 直接隔离 SAD 机制；reranker pilot 有 p-value；200-query paraphrase test；3 模型 cross-validation |
| 4 | 数据与 Benchmark | **3.3** | 2,209 真实 skills 优秀；human queries annotation 问题仍存在但呈现策略已优化（主文用 DA±1） |
| 5 | 结果分析深度 | **4.7** | DA-conditioned cascading analysis + oracle ablation + 14B anomaly insight + per-category breakdown，分析层次出色 |
| 6 | 写作质量 | **4.5** | Discussion 重写后更紧凑有力；intro item 3 清晰 scope compose 阶段；Related Work input-side/output-side 论述精彩 |
| 7 | 图表质量 | **4.0** | Figure 1 专业，convergence figure 清晰，tables 规范 |
| 8 | 相关工作覆盖 | **4.5** | 新增 Self-RAG/HuggingGPT/Plan-and-Execute 对比，input-side vs output-side 分类框架是 contribution 级别的 |
| 9 | 可复现性 | **3.8** | 承诺开源；prompt templates/hyperparams/hardware 完整；reranker prompt 有细节 |
| 10 | 实际影响力 | **4.0** | SAD+reranker pipeline 可直接部署；对 MCP/Agent 生态有实用价值 |

---

## 4. 加权总分与接受概率

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| 问题定义与动机 | 10% | 4.5 | 0.450 |
| 技术贡献与新颖性 | 20% | 3.7 | 0.740 |
| 实验设计 | 20% | 4.2 | 0.840 |
| 数据与 Benchmark | 10% | 3.3 | 0.330 |
| 结果分析深度 | 10% | 4.7 | 0.470 |
| 写作质量 | 10% | 4.5 | 0.450 |
| 图表质量 | 5% | 4.0 | 0.200 |
| 相关工作覆盖 | 5% | 4.5 | 0.225 |
| 可复现性 | 5% | 3.8 | 0.190 |
| 实际影响力 | 5% | 4.0 | 0.200 |
| **加权总分** | | | **4.095** |

**接受概率**: **70-80%** (Accept / Weak Accept)

---

## 5. 核心优势

1. **Analysis-driven contribution 结构精妙**: Oracle ablation (DA=99.3%, CatR@1=39.8%) → 精确定位 representation bottleneck → reranker pilot 验证解决方向 (+10.3%, p<0.01)。这种 "diagnose → isolate → validate fix" 链条比单纯堆实验数字更有说服力。

2. **Input-side vs output-side feedback 框架** (Related Work, line 146): 清晰区分 SAD（修改 decomposition input）与 Self-RAG/ReAct/Reflexion（修改 generation/action output）。这不是 surface-level 的 positioning，而是对 retrieval-augmented systems 中 feedback 方向的有意义分类。

3. **14B anomaly 是 evidence 而非 bug** (Section 5.5): 14B vanilla DA=32% < 7B vanilla DA=51%，因为 14B 更倾向 over-decomposition。SAD 将 14B 拉回 68%。这优雅地证明 SAD 是 "granularity corrector, not capacity booster"—最强的单句 take-away。

4. **Step-count-constrained ablation 关闭了最大质疑** (Section 5.6): Oracle step count → DA=99.3% but CatR@1=39.8% 证明: (a) SAD 的价值不可被简单 prompt engineering 替代（SAD 是怎么知道正确 K 的？通过 retrieval feedback！），(b) 即使 DA 完美，仍需 reranker 关闭 @1-to-@10 gap。

5. **Reranker pilot 将 speculative future work 升级为 validated lever**: 300 queries 全量评估，Wilcoxon p=0.007，53 improved vs 25 degraded—不是 cherry-picked。这将 "cross-encoder reranking as future work" 从空话变成了 empirically-supported roadmap。

---

## 6. 核心问题（按严重程度排序）

### P1: Human Queries Annotation 质量仍有结构性问题

**问题**: Table 8 (Appendix A) 仍报告 Easy Vanilla DA=2.5%。虽然主文 (line 427) 现在只引用 DA±1 (30.5%→50.5%)，呈现策略已大幅改善，但底层数据问题未解决：

- Ground truth subtask descriptions 仍是全 query 拷贝（而非独立子任务描述）
- 2.5% DA 意味着 80 个 easy queries 中只有 2 个步骤数匹配——模型分解出 5-8 步而 GT 标 2 步
- 审稿人如果细看 Appendix A 表格，仍会质疑：为什么 easy=2.5% 而 hard=15%？正常应该 easy > hard

**风险等级**: 中等。呈现策略改善降低了风险（DA±1 在主文，strict DA 只在 appendix），但 appendix 中 easy=2.5% 仍是红旗。

**建议**:
- 最理想：重新生成 200 条 human queries（每个 subtask 独立 description）— 已有脚本，只需执行
- 次选：在 Appendix A 中增加一段解释 "easy queries (2-step GT) are paradoxically hardest for strict DA because 2-step tasks have the most expansion room (model naturally adds auth/parse/validate steps)"

### P2: ReAct Baseline 仍然是 Category Error

**问题**: ReAct DA=0% 出现在 Table 1。ReAct agent 不做 upfront decomposition — 用 DA (step count match) 评它本质是在说 "ReAct 没有 decompose"，这是 by design 而非 failure。

**改进**: Baseline 段落 (line 415) 的表述已改善 ("the think-act-observe loop collapses multi-step tasks into single actions")，但 Table 1 中 DA=0% 的视觉效果仍然误导。

**建议**: 在 Table 1 中 ReAct 行加脚注标注 "†: ReAct does not perform explicit decomposition; DA=0 reflects protocol mismatch, not system failure. Included to demonstrate that compositional routing requires structured decomposition."

### P3: Paraphrase Robustness 扩展后的数字有轻微不一致

**问题**: 
- Line 422: "SAD DA drops marginally from 66.0% to 62.0%" — 这里 SAD DA=66.0% 与 Table 1 的 67.7% 不一致
- 可能是 50 queries 子集的 DA vs 全 300 queries，但未说明

**建议**: 明确写 "on the same 50-query subset, SAD DA drops from 66.0% to 62.0%"

### P4: Discussion 密度过高

**问题**: Section 7 (Discussion) 现在是一个超长段落 (line 580-581)，包含了 cascading analysis + oracle ablation + reranker pilot + transfer + context reduction。对于读者来说信息密度过大，没有 paragraph breaks。

**建议**: 拆分为 2-3 个 `\paragraph{}` 子标题:
- "Cascading structure"
- "Closing the @10-to-@1 gap"
- "Practical deployment"

---

## 7. 具体修改建议（按优先级排序）

### Must Fix (P0)

无。本版本没有 fatal flaws。

### Should Fix (P1) — 显著提升论文质量

| # | 问题 | 修改方案 | 工作量 |
|---|------|----------|--------|
| 1 | Human queries annotation (Appendix A easy=2.5%) | 增加解释段落 or 重新生成 | 30min / 2天 |
| 2 | ReAct baseline Table 1 误导 | 加脚注说明 protocol mismatch | 5分钟 |
| 3 | Discussion 段落过长 | 拆分为 2-3 paragraphs | 10分钟 |
| 4 | Paraphrase 50-query subset DA=66% vs Table 1 DA=67.7% | 明确标注是 subset | 5分钟 |

### Nice to Have (P2) — 锦上添花

| # | 问题 | 修改方案 |
|---|------|----------|
| 5 | Abstract 最后一句 "reduces context window consumption by over 99%" 放在末尾显得 anticlimactic | 移到中间或删掉（context reduction 不是核心贡献） |
| 6 | Convergence table R0 DA=0.513 vs Table 1 DA=0.510 不一致 | Caption 已解释，可接受 |
| 7 | Table 1 baselines (qwen-max) 与 main results (7B) 混合 | 分隔已足够，可接受 |

---

## 8. 竞品/相关工作对比分析

| 维度 | SkillWeaver (本文) | SkillRouter (2025) | CRAFT (ICLR 2025) | MCP-Zero (2025) | Self-RAG (2024) |
|------|-------------------|-------------------|-------------------|-----------------|-----------------|
| **Feedback 方向** | Input-side (decomp) | None | None | None | Output-side (gen) |
| **问题范围** | Compositional multi-skill | Single-skill | Per-query toolset | Zero-shot discovery | QA generation |
| **Skill 规模** | 2,209 | ~1,600 | ~8,000 APIs | variable | N/A |
| **核心机制** | Retrieval→Decompose loop | Retrieve+Rerank | LLM filter | Protocol-level lazy | Generate+Critique |
| **Token 减少** | 99.9% | N/A | N/A | 98% | N/A |
| **统计检验** | ✅ Wilcoxon + bootstrap | ❌ | ❌ | ❌ | ✅ |

**Input-side vs Output-side 框架评价**: 这是本文对 Related Work 最重要的贡献之一。Self-RAG/ReAct/Reflexion 都在 "given a plan, refine output" 层面操作；SAD 在 "given partial retrieval results, revise the plan itself" 层面操作。这个区分有 lasting value—后续论文会引用这个分类。

---

## 9. 审稿人可能的 Questions for Authors

**Q1** (针对 oracle ablation):
> Step-count-constrained baseline 给了 oracle K*。但在实际部署中 K* 未知。SAD 如何"知道"正确的 K？是 hint set 中的 skill 数量隐式传达了 granularity 信号吗？

**预判 Rebuttal**: 作者会指向 SAD prompt 中的 hint list——当 hints 覆盖 2 个 categories 时，模型倾向于输出 2 步分解。Hints 充当隐式 granularity anchor。
**评价**: 合理。这是 SAD 超越简单 "output K steps" prompt 的核心价值。

**Q2** (针对 reranker pilot):
> Reranker 使用同一个 7B checkpoint。如果换用专门训练的 cross-encoder (如 ms-marco-MiniLM)，提升可能更大。为什么不做这个实验？

**预判 Rebuttal**: 作者会说 (1) 同 checkpoint 证明无需额外训练就能获益，(2) 专用 cross-encoder 是 obvious next step 但超出本文 scope。
**评价**: 合理。pilot 的价值在于 proof-of-concept，不在于 SOTA reranking。

**Q3** (针对 14B anomaly):
> 14B Vanilla DA=32% 低于 7B 的 51%。你的解释是 over-decomposition。但是否有可能 14B 版本的 instruction following 能力不同（例如对 "output a JSON array" 的遵从度不同），而非真正的 granularity 问题？

**预判 Rebuttal**: 作者应展示 14B 的平均 subtask count (e.g., 5.2) vs 7B (4.09) vs ground truth (2.73/3.0/4.4)，证明确实是 over-decomposition。
**评价**: 如果有数据支持，这是强 rebuttal。建议在 paper 中补充 14B 的 avg subtask count。

**Q4** (针对 scalability):
> 2,209 skills 是 MCP 生态的 ~20%。如果 scale 到 10K+ skills，bi-encoder top-10 的 CatR@10 会如何变化？SAD 的 H=15 hints 是否足够覆盖更大的 skill space？

**预判 Rebuttal**: 作者可能指向 FAISS scalability (<15ms even at 10K) 和 transfer experiments 的 pool-size 鲁棒性。但未直接测试 10K scale。
**评价**: 合理的 limitation。建议在 Limitations 中明确提及 "scaling beyond 5K skills remains untested"。

**Q5** (针对 human queries):
> Appendix A 中 Easy DA=2.5% (Vanilla)。你解释为 "open-ended step boundaries"。但 compositional easy queries (也是 2-step GT) DA=44.7%。同样 2-step GT，为什么差 18x？

**预判 Rebuttal**: 作者应说 (1) compositional queries 结构是 "First X, then Y" 强制 2-step，(2) human queries 更自然/模糊所以模型展开更多步骤，(3) DA±1 更合适。
**评价**: 合理但不完全。真正的问题是 annotation 粒度不匹配——如果重新标注让 GT 允许 3-4 步分解，DA 会显著改善。建议在 Appendix 中承认这一点。

---

## 10. 数据一致性检查

| 指标 | Abstract | Table 1 | Results text | Conclusion | 一致? |
|------|----------|---------|-------------|------------|-------|
| Vanilla DA | 51.0% | 0.510 | 51.0% | — | ✅ |
| SAD DA | 67.7% | 0.677 | 67.7% | — | ✅ |
| DA improvement | +32% | — | +32.7% | +32.7% | ⚠️ Abstract +32% vs 正文 +32.7% (minor) |
| CatR@1 (DA=1 conditioned) | 41% | — | 41.2% | — | ✅ |
| Transfer DA gain | +35.6% | +35.6% | +35.6% | — | ✅ |
| Reranker CatR@1 gain | — | — | +10.3% | +10.3% | ✅ |
| Human DA±1 | — | — | 30.5%→50.5% | — | ✅ |
| Appendix F DA±1 | — | — | — | 30.5%→50.5% | ✅ (已修正，与手算一致) |
| Paraphrase subset DA | — | — | 66.0%→62.0% | — | ⚠️ 66.0% ≠ Table 1 的 67.7% (未说明是 subset) |

---

## 11. 对上版 Review 建议的完成情况

| 上版建议 | 状态 | 评价 |
|----------|------|------|
| P0: Human queries annotation | ⚠️ 数据未修，但呈现策略大幅改善 | 主文用 DA±1, strict DA 只在 appendix, 风险降低 |
| P0-b: DA±1 数字错误 (48.3% vs 50.5%) | ✅ 已修正 | Appendix F 和 Limitations 均为 50.5% |
| P1: CatR@1 不显著 | ✅ 解决 | Reranker pilot (+10.3%, p<0.01) + oracle ablation 完整闭环 |
| P1 (追问): step-count-constrained ablation | ✅ 新增 | Section 5.6, oracle K* → DA=99.3%, CatR@1=39.8% |
| P2: Baselines 不公平 | ⚠️ 部分 | LLM-Direct 改标为 "ceiling estimate"；ReAct 仍在 Table 1 |
| P3: Compose 阶段无评估 | ✅ 解决 | Intro 明确 scope "architectural completion"；不再 over-promise |
| P4: Query text overlap 未量化 | ❌ 未做 | 无 BM25 baseline，但 200-query paraphrase 间接缓解 |
| Minor: Discussion 重写 | ✅ | 更紧凑有力 |
| Minor: Abstract 精简 | ✅ | 去掉了 CatR@1 具体数字，改为 DA-conditioned framing |

---

## 12. 与上版对比：分数变化

| 维度 | 上版 | 本版 | 变化 | 原因 |
|------|------|------|------|------|
| 技术新颖性 | 3.3 | 3.7 | +0.4 | Input-side/output-side 框架 + reranker pilot 提升 contribution 层次 |
| 实验设计 | 3.5 | 4.2 | +0.7 | Oracle ablation + reranker pilot + expanded paraphrase + 14B cross-model |
| 数据 | 3.2 | 3.3 | +0.1 | 呈现策略改善但底层数据未变 |
| 结果分析 | 4.5 | 4.7 | +0.2 | 14B anomaly insight + oracle isolation 更精准 |
| 写作 | 4.3 | 4.5 | +0.2 | Discussion/Related Work 重写质量高 |
| 相关工作 | 4.0 | 4.5 | +0.5 | Self-RAG/HuggingGPT + feedback direction taxonomy |
| **加权总分** | **3.775** | **4.095** | **+0.32** | 整体从 Borderline 提升到 Accept 区间 |

---

## 结论

**显著改进**: 这一版解决了上版的核心弱点：

1. CatR@1 不显著 → reranker pilot 提供 validated solution path (p<0.01)
2. "SAD 是否可被 prompt engineering 替代" → oracle ablation 明确回答 No
3. Novelty 叙事 → input-side vs output-side 框架提升了技术定位
4. Compose 阶段 over-promise → 明确 scope 为 "architectural completion"
5. DA±1 数字错误 → 已修正

**仍存在但已降级的问题**:
- Human queries annotation 底层问题未修（but 呈现策略合理，风险已降至 P1）
- ReAct baseline 仍有 protocol mismatch 问题（minor, 加脚注即可）
- Query text overlap 未量化（但 200-query paraphrase 间接缓解）

**总体评估**: **Weak Accept → Accept**。论文现在有清晰的 contribution 层次结构（问题形式化 + SAD granularity correction + reranker as validated next step），分析深度是同类工作中少见的。如果修好 human queries 数据，可以更自信地推向 Accept。当前状态足以投稿。
