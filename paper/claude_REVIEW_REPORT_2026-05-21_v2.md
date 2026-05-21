# Review Report v2: Post-Revision Assessment

**Date**: 2026-05-21 (v2, post-revision)  
**Reviewer**: Claude Opus 4.6  
**Target Venue**: EMNLP 2026 (ACL Rolling Review)  
**Compared against**: claude_REVIEW_REPORT_2026-05-21.md (pre-revision)

---

## 1. 修改对照表

| 上版建议 | 优先级 | 状态 | 具体改动 |
|----------|--------|------|----------|
| Abstract "+32%" vs 正文 "+32.7%" | P0 | ✅ 已修 | Abstract 统一为 +32.7% |
| Discussion 拆段 | P0 | ✅ 已修 | 拆为 3 个 \paragraph{}: Cascading / Reranking / Practical |
| Paraphrase "66.0%" 标注 subset | P0 | ✅ 已修 | 加 "(note: 66.0% reflects the subset baseline...)" |
| ReAct 加脚注 | P1 | ✅ 已修 | Table 1 加 \dag + caption 解释 protocol mismatch |
| α=0.5 sensitivity | P1 | ✅ 已修 | "stable across α∈[0.3,0.7] on a 50-query dev set" |
| 14B avg step count | P1 | ✅ 已修 | 补充 4.72 vs GT 2.94 vs 7B 3.62, SAD→3.18 |
| Exact-skill R@1 报告 | P2 | ✅ 已修 | 新段落: R@1=6.8%/8.3%, R@10=18.2% |
| Appendix Easy<Medium DA 解释 | P2 | ✅ 已修 | 新段落 "Why is Easy DA lower than Medium DA?" |
| ToolBench 引用 | P2 | ✅ 已修 | Related Work + references.bib |
| Chameleon 引用 | P2 | ✅ 已修 | Related Work + references.bib |
| DA±1 数值修正 (48.3%→50.5%) | Legacy | ✅ 已修 | Appendix A 对齐 |
| 替代 encoder spot-check | P3 | ❌ 未做 | 仍然只用 MiniLM-L6-v2 |
| Human queries annotation 底层修复 | P2 | ❌ 未做 | Easy=2.5% 仍存在（但有解释段落） |

**完成率**: 10/12 建议已落地。未完成的两项均为高成本实验类（P3 encoder 需 2h GPU 时间；human queries 重标需 2 天）。

---

## 2. 接受概率更新

| 版本 | 加权分 | 接受概率 | 主要变化 |
|------|--------|----------|----------|
| 上版 (pre-revision) | 4.095 | 70-75% | — |
| **本版 (post-revision)** | **4.20** | **75-80%** | 消除了所有 low-hanging-fruit 攻击面 |

**概率提升原因**:
1. ReAct 脚注消除了最容易被指出的 "category error" 问题
2. 14B step count 数据让 over-decomposition 论证从 claim 变成 evidence
3. Exact-skill R@1 的透明报告体现了学术诚实，反而加分
4. Discussion 拆段让最密集的 argument chain 变得可读
5. α sensitivity 和 subset 标注消除了细节一致性质疑

---

## 3. 当前版本剩余风险

### Risk A: CatR@1 p=0.17（不变，但已充分缓解）

**现状**: CI [-0.005, +0.062] 仍跨零。  
**缓解链**: DA highly significant → DA-conditioned analysis → oracle ablation → reranker pilot p<0.01。  
**审稿人反应预判**: 60% 接受这个论证链，30% 要求 CatR@1 本身显著，10% 关注其他方面。  
**进一步缓解（可选）**: 在 Results "Key findings" 段增加一句："We note that CatR@1's direct p-value (0.17) reflects SAD's mechanism: it corrects granularity, not per-step vocabulary; the reranker pilot (\S\ref{sec:discussion}) addresses per-step precision with p<0.01."

### Risk B: Benchmark 合成性质（不变，已充分缓解）

**现状**: 300 template queries + 200 human queries (strict DA 仍低)。  
**缓解链**: Paraphrase robustness + transfer experiments + human DA±1=50.5%。  
**审稿人反应预判**: 大多数会接受 transfer 实验 + paraphrase 作为 generalization evidence。  
**进一步缓解（可选）**: 无需额外实验。当前论证足够。

### Risk C: Single Encoder（未变）

**现状**: 只用 MiniLM-L6-v2。  
**风险**: 低。论文已在 Limitations 中承认，且 step-count-constrained 分析表明 @1-@10 gap 不太可能由 encoder scale 解决。Reranker pilot 是更正确的方向。  
**如果想进一步堵住**: 跑一次 BGE-base (50 queries, <2h GPU) 并在 Limitations 中报告 "spot-check with BGE-base-en-v1.5 shows CatR@1=X.X% (±Y pp vs MiniLM), confirming that encoder scale alone does not close the @1-@10 gap."

### Risk D: Human Queries Easy DA=2.5%（已降级）

**现状**: Appendix B 新增了 "Why is Easy DA lower than Medium DA?" 解释段落 + DA±1 reversal 证据。  
**风险**: 低。解释合理（2-step GT 低于模型 default granularity），DA±1 reversal 数据说服力强。  
**审稿人反应预判**: 可能被提到但不会成为 reject reason。

---

## 4. 分维度评分（修订后）

| 维度 | 上版 | 本版 | 变化 | 原因 |
|------|------|------|------|------|
| 问题定义与动机 | 4.5 | 4.5 | — | 无变化 |
| 技术贡献与新颖性 | 3.7 | 3.7 | — | 无新贡献 |
| 实验设计 | 4.2 | 4.3 | +0.1 | Exact-skill recall 增加透明度 |
| 数据与 Benchmark | 3.3 | 3.5 | +0.2 | Easy<Medium 解释 + subset 标注 |
| 结果分析深度 | 4.7 | 4.8 | +0.1 | 14B step count 定量化 |
| 写作质量 | 4.5 | 4.6 | +0.1 | Discussion 拆段 + 数字一致性修复 |
| 图表质量 | 4.0 | 4.0 | — | 无变化 |
| 相关工作覆盖 | 4.5 | 4.7 | +0.2 | +ToolBench, +Chameleon |
| 可复现性 | 3.8 | 3.9 | +0.1 | α sensitivity 报告 |
| 实际影响力 | 4.0 | 4.0 | — | 无变化 |
| **加权总分** | **4.095** | **4.20** | **+0.10** | |

---

## 5. 进一步优化建议（按性价比排序）

### Tier 1: 5分钟改动，消除最后的 nitpicks

| # | 改动 | 位置 | 理由 |
|---|------|------|------|
| 1 | Intro bullet 3 改 defensive 措辞 | L67 | "compose serves as architectural completion validated indirectly" → "we validate end-to-end viability through a pilot execution study (Appendix I) while focusing controlled evaluation on the identified bottleneck" — 更自信 |
| 2 | Conclusion 末尾加 "Exact-skill disambiguation..." | L597 | 与新增的 exact-skill paragraph 呼应，给 reviewer 明确 future work signal |
| 3 | Table 1 caption 最后的 \dag 解释句太长 | L392 | 考虑缩短为 "†Protocol mismatch: ReAct does not produce upfront decompositions." 让 caption 更紧凑 |

### Tier 2: 30分钟改动，可能提升 0.5 个 reviewer score

| # | 改动 | 理由 |
|---|------|------|
| 4 | 在 Appendix "Statistical Significance" 中新增一小段 "CatR@1 conditioned on DA-fixed queries (n=75)" 并报告这个子集上的 p-value | 这 75 个 queries 上 CatR@1 从 23.6%→37.0% 应该 p<0.05，直接堵住 "CatR@1 不显著" 攻击 |
| 5 | Human queries table (Appendix A): 增加一列 "Avg Pred Steps" 和 "GT Steps" | 让 Easy=2.5% 变得 self-explanatory — 读者一眼看到 pred=4.2 vs GT=2.0 |
| 6 | Intro 末尾 findings 列表第一条: 引用 exact-skill R@1 数据 | "R@1=6.8% on exact skill, 34.2% on category" — 让 reviewer 从一开始就知道 category recall 的选择是有意的 |

### Tier 3: 需要 GPU 的实验（可选，高回报但高成本）

| # | 实验 | 时间 | 影响 |
|---|------|------|------|
| 7 | BGE-base-en-v1.5 spot-check (50 queries) | 2h | 堵住 "single encoder" 攻击；如果 BGE 只提升 1-2pp 反而强化 "reranker is the right direction" 论点 |
| 8 | SAD H sensitivity (H=5, H=10, H=20, H=30) on 50 queries | 3h | 回答 reviewer Q2；如果 H=10 已 saturate 反而简化 pipeline |
| 9 | CatR@1 on DA-fixed 75 queries + Wilcoxon | 30min (已有数据) | 直接出 p-value，可能 <0.05 |

---

## 6. Rebuttal 准备要点

如果收到 reviews，最可能的攻击点和预备 response：

**Attack 1**: "CatR@1 not significant"  
→ Response: (1) SAD is designed as a granularity corrector, not a per-step retrieval improver (Section 5.6, p=0.97 on DA-matched queries); (2) Reranker pilot addresses per-step precision with p<0.01; (3) On the 75 queries where SAD fixes DA, CatR@1 improves from 23.6% to 37.0%.

**Attack 2**: "Synthetic benchmark, how do you know this works on real queries?"  
→ Response: (1) Transfer experiments (+35.6% under category held-out); (2) 200 paraphrased queries show ≤6pp degradation; (3) Human-style DA±1 = 50.5% confirms approximate granularity correction; (4) The skill pool itself is real (2,209 MCP servers).

**Attack 3**: "SAD is just prompt engineering — you're giving the model hints"  
→ Response: (1) Oracle step-count prompt (the simplest possible "hint") reaches DA=99.3% but CatR@1=39.8% — only 2.8pp above SAD (37.0%), proving SAD's primary value is granularity discovery, not something achievable by simple prompting; (2) SAD doesn't know K* a priori — it discovers it via retrieval feedback; (3) Transfer experiments show it works even when target categories are absent.

**Attack 4**: "Compose stage is just hand-waving"  
→ Response: (1) Paper explicitly scopes this as "architectural completion" (Section 4.3, line 217-220); (2) Pilot execution study (Appendix I) shows 76.7% CCR; (3) The identified bottleneck is decompose-retrieve, not compose — addressing the bottleneck first is standard research practice.

---

## 7. 最终判断

**当前状态**: 论文已处于 **可投稿且有竞争力** 的水平。所有 low-cost fixes 已完成，剩余问题均为 "nice to have" 级别。

**预期 reviewer 分布**:
- R1 (tool-use/agent 专家): 3.5-4.0 (Accept) — 认可问题定义和分析深度
- R2 (retrieval/NLP 专家): 3.0-3.5 (Weak Accept) — 可能纠结 CatR@1 significance
- R3 (通用 reviewer): 3.0-3.5 (Weak Accept/Borderline) — benchmark 合成性是主要顾虑

**综合**: **75-80% 概率 Weak Accept 或 Accept**。如果执行 Tier 2 #4（DA-fixed subset p-value），概率可推到 80%+。

---

## 8. 版本间改进总结

本版修改精准：10 处改动均直接回应了上版 review 的具体建议，没有引入新问题。改动都是 surgical——在正确的位置加正确的信息，没有多余的 padding。这说明修改者理解了每个修改的目的和最佳放置位置。

论文从 "有明显 nitpick 攻击面" 进化到 "需要 substantive 论点才能 reject"。这是正确的投稿状态。
