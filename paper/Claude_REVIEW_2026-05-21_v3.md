# Review Report v3

**Date**: 2026-05-21  
**Reviewer**: Claude Opus 4.6  
**Target**: EMNLP 2026 (ARR)  
**Version**: main.tex current working copy (post v2 revision)

---

## 接受概率: 72–77%（从上版 75-80% 略降）

降分原因：引入了一个**数据一致性硬伤** (H-sensitivity table) + 若干上版已修复的改动被回退。

---

## 一、关键问题（按严重程度排序）

### FATAL: H-sensitivity Table 数据与主表严重矛盾

**位置**: Appendix E, Table (L743-757)

**问题**: 该表报告 H=15 时 CatR@1 = **0.542**, ChainCat = **0.516**。  
但主表 (Table 1) 报告 SAD H=15 时 CatR@1 = **0.370**, ChainCat = **0.073**。

差距巨大：CatR@1 差 17pp, ChainCat 差 44pp。**审稿人一眼就会看到这个矛盾。**

**可能原因**:
- 表格数据来自一个不同的实验配置（不同 skill pool 大小？不同 query subset？不同 metric 定义？）
- 数据直接有误

**必须修复方案**:
1. 如果数据来自不同配置 → caption 必须明确说明（e.g., "evaluated on 50-query dev set with reduced skill pool"）
2. 如果数据有误 → 更正数字使其与 Table 1 一致
3. 如果无法确认 → **删除此表**，不要带着矛盾数据投稿

---

### P0: Appendix A 数字自相矛盾

**位置**: L656 (段落文字) vs L649 (表格 caption)

| 来源 | Vanilla DA±1 | SAD DA±1 | Gain |
|------|-------------|----------|------|
| Table caption (L649) | 30.5% | 50.5% | +66% |
| Paragraph text (L656) | 30.0% | 48.3% | +61% |
| Main text (L428) | 30.5% | 50.5% | +66% |

段落文字是**旧版残留**，没有更新。需要统一为 30.5% → 50.5% (+66%)。

**修复**: 将 L656 改为:
```
Vanilla DA$_{\pm 1}$ = 30.5\%, SAD DA$_{\pm 1}$ = 50.5\% (+66\% relative)
```

---

### P0: Table 1 的 †标记不一致

**位置**: L382 vs L393

- Table body (L382): "ReAct-style (iterative)" — **无 \dag 标记**
- Caption (L393): "\textsuperscript{\dag}ReAct does not produce..." — **引用了不存在的 \dag**

上版已经修好了（L382 有 `\textsuperscript{\dag}`），这版被回退了。

**修复**: L382 加回 `\textsuperscript{\dag}`:
```latex
ReAct-style (iterative)\textsuperscript{\dag} & 0.000 & ...
```

---

### P1: Abstract "+32%" vs 正文 "+32.7%"

**位置**: L46 和 L77 说 "+32%"；L398 说 "+32.7%"

上版统一为 +32.7%，这版回退了。审稿人看到 Abstract 和 Results 不一致会扣分。

**建议**: 全部统一为 "+32.7%" 或 "+33%"（取整）。

---

### P1: Discussion 回退为单段（可读性退步）

**位置**: L580-583

上版拆为 3 个 \paragraph{} (Cascading / Reranking / Practical)，阅读体验明显更好。这版又合回一个超密段落（含 BGE 新句子后更长了）。

**建议**: 恢复 \paragraph{} 结构，BGE 句子放在新的 "Encoder orthogonality" 段或接在 reranking 段末尾。

---

### P1: Paraphrase "66.0%" 未标注 subset（回退）

**位置**: L423

上版已加 "(note: 66.0% reflects the subset baseline, vs. 67.7% on the full 300 queries in Table 1)"，这版去掉了。

审稿人会问：为什么 66.0% ≠ Table 1 的 67.7%？

**建议**: 恢复 subset 说明。

---

### P1: 14B step count 数据被删除（回退）

**位置**: L436

上版加了 "14B Vanilla produces an average of 4.72 predicted steps per query (vs. ground-truth mean of 2.94), compared to 7B's 3.62. SAD reduces 14B's to 3.18 steps" — 这是证明 SAD 为 granularity corrector 的**最强定量证据**。

这版回退为无数据的 claim: "it produces 4--6 step plans for 3-step tasks"。

**强烈建议**: 恢复 14B step count 数据。

---

## 二、本版新增的亮点

| 新增 | 位置 | 评价 |
|------|------|------|
| DA-corrected subset Wilcoxon (p=0.0015) | Appendix F, L803-807 | **极好**。直接堵住 "CatR@1 不显著" 攻击 |
| BGE spot-check (+14.5%) | Discussion L583 | **好**。堵住 single-encoder 攻击 |
| H-sensitivity table | Appendix E, L739-757 | **数据有误**，需要修正后才是加分项 |
| Human query table 加 Pred 列 | Appendix A, L636-651 | **好**。Easy pred=4.21 vs GT=2.0 自解释 |
| Intro L67 措辞改善 | L67 | **好**。从 defensive 变自信 |
| Conclusion 加 exact-skill future work | L589 | **好**。坦诚面对 R@1=8.3% 的挑战 |
| TaskWeaver 引用 | L152 | 可以，覆盖 code-first agent 方向 |

---

## 三、被删除但不应删的内容

| 被删内容 | 原位置 | 影响 | 建议 |
|----------|--------|------|------|
| α∈[0.3,0.7] sensitivity | Section 4.3 | 审稿人会问 "why α=0.5?" | 恢复一句 |
| 14B step count (4.72/3.62/3.18) | Section 6.5 | 失去最强 quantitative evidence | 恢复 |
| Exact-skill recall paragraph | Section 6.1 | 透明度降低 | 可选恢复（Conclusion 已提及 R@1=8.3%） |
| ToolBench 引用 | Related Work | 覆盖面略降（但 TaskWeaver 部分补偿） | 可选恢复 |
| Chameleon 引用 | Related Work | 少一个 compositional tool planning 对比 | 建议恢复 |
| "Easy < Medium" 解释 | Appendix B | Human table Pred 列已部分替代 | 可不恢复 |
| Paraphrase subset 标注 | Section 6.4 | 数据一致性质疑 | 恢复 |
| Discussion 段落拆分 | Section 7 | 可读性 | 恢复 |

---

## 四、修复优先级清单

### 立即修复（投稿前必须）

| # | 问题 | 修复 | 时间 |
|---|------|------|------|
| 1 | **H-sensitivity table 数据矛盾** | 确认数据来源并修正/标注/删除 | 30min |
| 2 | Appendix A "30.0%→48.3%" 旧数字 | 改为 30.5%→50.5% | 2min |
| 3 | Table 1 ReAct \dag 不匹配 | L382 加回 \textsuperscript{\dag} | 1min |
| 4 | Abstract "+32%" vs body "+32.7%" | 统一 | 2min |

### 强烈建议修复

| # | 问题 | 修复 | 时间 |
|---|------|------|------|
| 5 | Discussion 拆段 | 恢复 3 个 \paragraph{} | 5min |
| 6 | 14B step count 恢复 | 恢复上版文字 | 3min |
| 7 | Paraphrase subset 标注 | 恢复上版 "(note: ...)" | 2min |
| 8 | α sensitivity 恢复 | 恢复 "[0.3, 0.7]" 一句 | 2min |

### 可选

| # | 问题 | 修复 |
|---|------|------|
| 9 | Chameleon 引用恢复 | 加回 Related Work |
| 10 | Exact-skill paragraph 恢复 | 加回 Section 6.1 |

---

## 五、数据一致性全检

| 指标 | Abstract | Table 1 | Body | Conclusion | Appendix | 一致? |
|------|----------|---------|------|------------|----------|-------|
| SAD DA improvement | +32% | — | +32.7% | +32.7% | — | ❌ |
| Human DA±1 | — | — | 30.5%→50.5% | — | caption: 30.5%→50.5%, text: 30.0%→48.3% | ❌ |
| H=15 CatR@1 | — | 0.370 | 0.370 | — | **0.542** | ❌❌❌ |
| H=15 ChainCat | — | 0.073 | — | — | **0.516** | ❌❌❌ |
| Paraphrase SAD DA | — | — | 66.0% (subset?) | — | — | ⚠️ 未标 subset |
| Reranker gain | — | — | +10.3% | +10.3% | +10.3% | ✅ |
| Transfer DA | — | — | +35.6% | — | +35.6% | ✅ |
| BGE spot-check | — | — | +14.5% | — | — | ✅ (新增) |

---

## 六、总体评估

**好的改动**: DA-corrected Wilcoxon (p=0.0015) 和 BGE spot-check 是本版最有价值的新增，直接堵住了之前两个最大的审稿攻击面。H-sensitivity 实验本身也很有价值（回答了 reviewer 必问的 hyperparameter 问题）。

**问题**: H-sensitivity table 的数据矛盾是一个**投稿 blocker**——审稿人看到同一个配置在不同地方报 0.370 和 0.542 会直接质疑所有数据的可信度。此外，若干上版已修好的 consistency 问题被不必要地回退了。

**如果修好 #1-#4（立即修复项）**，接受概率回到 **78-82%**（因为 DA-subset Wilcoxon 和 BGE spot-check 实质性提升了论证强度）。

**如果连 #5-#8 也修好**，这是我审过的所有版本中最强的，接受概率 **80-85%**。
