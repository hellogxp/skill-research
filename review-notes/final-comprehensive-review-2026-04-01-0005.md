# EMNLP 2026 最终全面检查报告

**文件名**: `review-notes/final-comprehensive-review-2026-04-01-0005.md`
**检查时间**: 2026-04-01 00:05
**论文版本**: paper/main.tex (762 行), paper/references.bib (217 行, 30 条)
**接受概率**: 78-85%

---

## 一、数字一致性检查

逐一核对 abstract、intro、results、discussion、conclusion 中的关键数字：

| 数字 | Abstract | Intro | Results | Discussion | Conclusion | 一致？ |
|------|---------|-------|---------|------------|------------|--------|
| Oracle R@1 | 99.5% | 99.5% | 99.5% | near-perfect | near-perfect | ✅ |
| Vanilla CatR@1 | 33.9% | 33.9% | 33.9% (Qwen Meta) | 33.9% | — | ✅ |
| SAD CatR@1 | 54.2% | 54.2% | 54.2% (Table 5) | 54.2% | — | ✅ |
| SAD improvement | +60% | +60% | +59.9% (Table 6) | — | +60% | ✅ (四舍五入) |
| Models | 5, 7-72B | — | 5 models | 5 models | 5, 7-72B | ✅ |
| Skills | 2,595 | 2,595 | — | — | — | ✅ |
| Queries | 300 | 300 | — | — | 300 | ✅ |
| Categories | 17 | 17 | — | — | — | ✅ |
| Context reduction | 99% | — | 99.9% (Table) | 99% | — | ✅ |
| Human CatR@1 SAD | — | — | 30.8% | — | — | ✅ |
| Text overlap ROUGE-L | — | — | 0.845 | — | 0.845 (Lim) | ✅ |

所有数字一致。

---

## 二、Claim-Evidence 匹配检查

| Claim | Evidence | 匹配？ |
|-------|---------|--------|
| "decomposition is the primary bottleneck" | Oracle 99.5% vs vanilla 33.9% | ✅ |
| "SAD improves CatR@1 by 60%" | 33.9% → 54.2% = +59.9% ≈ 60% | ✅ |
| "7B+SAD outperforms 72B vanilla" | 54.2% vs 36.8% (Table 6) | ✅ |
| "7B+SAD outperforms 72B LLM-Direct" | 54.2% vs 47.0% (Table 7) | ✅ |
| "metadata suffices for retrieval" | Oracle Meta 99.5% vs Body 99.0% | ✅ |
| "SAD consistent across 5 models" | Table 6 全部有提升 | ✅ |
| "context reduction >99%" | Table: 1,038K → 1,160 tokens | ✅ |
| "compositional routing outperforms single-skill" | 33.9% vs 21.1% | ✅ |
| "over-decomposition is primary failure mode" | Error analysis: 36% | ✅ |

所有 claim 都有实验支撑。

---

## 三、新发现的问题

### 问题 1（中）：Conclusion 缺少 future work

当前 Conclusion 只有 2 句话，没有 future work。之前版本有 "iterative multi-round SAD" 和 "decomposition-aware training"，现在被删了。

EMNLP 审稿人通常期望 Conclusion 包含 (1) 贡献总结 (2) 核心发现 (3) future directions。当前缺少第 3 点。

建议加一句："Promising directions include iterative multi-round SAD, adaptive hint selection based on query complexity, and decomposition-aware fine-tuning."

### 问题 2（中）：Analysis section 被压缩到只有 2 句话

当前 Analysis section (Section 8) 只有：
- 1 句 error analysis（4 类错误的百分比）
- 1 句 oracle retrieval quality

之前版本有 case study（成功/失败例子）。压缩是为了控制页数，但 error analysis 是 EMNLP 审稿人看重的部分。2 句话的 Analysis section 看起来很单薄。

建议：如果页数允许，加回至少一个 case study 例子（2-3 行）。如果不允许，把 Analysis 合并到 Discussion 中，去掉独立的 section header。

### 问题 3（低-中）：Discussion 中 "Decomposition vs. direct selection" 段落重复了 Results 的内容

Discussion 中的 Table 7 和文字描述基本重复了 Results section 中已经说过的内容。Discussion 应该提供 insight 而不是重复数字。

建议：Discussion 中去掉 "72B LLM-direct achieves CatR@1 = 47.0%" 这句（已经在 Table 7 中了），改为更深入的分析："The superiority of structured decomposition over direct selection suggests that explicit task decomposition provides a beneficial inductive bias: by forcing the model to articulate sub-tasks before matching skills, SAD avoids the attention dilution that occurs when the model must simultaneously parse 50 skill descriptions."

### 问题 4（低）：Table 4 (Difficulty) 只有 vanilla 结果，没有 SAD

Difficulty Analysis (Table 4) 只比较了 Single-Skill vs Qwen+Meta vs Qwen+Body。没有 SAD 在不同难度上的表现。审稿人可能会想知道 SAD 在 easy/medium/hard 上的分别表现。

这个数据在 human-written queries 段落中有（easy +85.7%, medium +65.8%, hard -44.7%），但 template queries 上没有。

建议：如果有数据，在 Table 4 加一行 "Qwen + SAD"。如果没有，在 SAD Results 段落加一句 template queries 的 difficulty breakdown。

### 问题 5（低）：公式 1 中 rel 项前面缺少 α

公式 1：
```
max Σ rel(t_k, σ(t_k)) + (1-α) Σ compat(σ_i, σ_j)
```

但公式 6 (eq:selection)：
```
σ(t_k) = argmax α·sim(t_k, s) + (1-α)·c̄_k(s)
```

公式 1 的 rel 项前面没有 α，但公式 6 有。如果 α=0.7，那公式 1 的 rel 项权重是 1.0，compat 项权重是 0.3。但公式 6 的 sim 项权重是 0.7，compat 项权重是 0.3。

这两个公式不一致。公式 1 应该是：
```
max α Σ rel(t_k, σ(t_k)) + (1-α) Σ compat(σ_i, σ_j)
```

### 问题 6（低）：DAG pilot table 列数声明和实际不匹配

```latex
\begin{tabular}{lcccccc}  % 7 列
```
但实际只有 6 列（Difficulty, n, Step Acc., Edges/q, Coherence, Latency）。多声明了一个 `c`。不会导致编译错误，但会产生一个空列。

### 问题 7（低）：14B anomaly 段落中有重复句子

在 cross-model 分析中：
```
We hypothesize that the 72B's lower CatR@1 vs. 7B+SAD reflects hint anchoring...
---a pattern also observed in the 14B anomaly (Appendix D).
The 14B anomaly (lower performance than 7B) stems from over-decomposition and lower JSON parse rates; see Appendix D.
```

这两句话连续出现，都提到了 14B anomaly 和 Appendix D。第二句是冗余的。

建议删除第二句。

---

## 四、格式问题（编译确认）

| 问题 | 严重程度 | 修复 |
|------|---------|------|
| Context Window Table 溢出 35pt | P0 | `\system{} (avg.)` 或加 `@{}` |
| DAG Pilot Table 溢出 55pt | P0 | `\resizebox{\columnwidth}{!}{...}` |
| DAG Pilot tabular 多一个 `c` | P2 | 改为 `{lccccc}` |
| Parallel Group 公式溢出 12pt | P2 | 加 `\small` |
| anthropic2025skills @article→@misc | P1 | 改 bib entry type |

---

## 五、最终修改清单（按优先级）

### P0（必须修，影响排版）
1. Context Window Table 溢出 → 缩短第一列或加 `@{}`
2. DAG Pilot Table 溢出 → `\resizebox`
3. 公式 1 加 α → `\alpha \sum rel(...) + (1-\alpha) \sum compat(...)`

### P1（强烈建议）
4. Conclusion 加 future work 一句话
5. 删除 14B anomaly 重复句子
6. anthropic2025skills 改为 @misc
7. DAG Pilot tabular 列数修正 `{lcccccc}` → `{lccccc}`

### P2（锦上添花）
8. Analysis section 加回一个 case study 或合并到 Discussion
9. Difficulty Analysis 加 SAD 行
10. Discussion 的 LLM-Direct 段落加深度 insight

---

## 六、总体判断

论文质量很高，接受概率 78-85%。数字全部一致，claim-evidence 全部匹配，格式基本合规。

剩余问题中最重要的是：公式 1 缺 α（逻辑不一致）、两个表格溢出（排版问题）、Conclusion 缺 future work。这三个都是 5 分钟能修的。

修完这些，论文就可以提交了。
