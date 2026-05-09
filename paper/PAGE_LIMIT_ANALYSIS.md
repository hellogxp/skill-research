# 论文页数限制分析与精简方案

## 检查日期：2026-05-07

---

## 当前状态

| 项目 | 数值 |
|------|------|
| **PDF 总页数** | 12 页 |
| **ARR/EMNLP 主文限制** | 8 页 |
| **预估主文页数** | ~9 页 |
| **超出限制** | 约 1 页 |

---

## ARR/EMNLP 页数规则

- **主文**：最多 **8 页**（含正文、图表、公式）
- **参考文献**：不计入页数限制
- **附录**：不计入页数限制
- **伦理声明**：不计入页数限制

---

## 精简方案（按优先级排序）

### 方案 1：将部分表格移至附录（推荐）

**预计节省：0.5-1 页**

| 表格 | 位置 | 建议 |
|------|------|------|
| Table 5 (tab:sad-ablation) | Section 7.4 | 移至附录，正文只保留关键数据点描述 |
| Table 8 (tab:dag-pilot) | Appendix E | 已在附录，保持不变 |
| Table 3 (tab:decomposer) | Section 7.2 | 可考虑移至附录 |

**具体修改**：

```latex
% 在 Section 7.4 中，将 Table 5 移至附录
% 正文改为：
We ablate over the hint count $H$ (see Appendix~\ref{app:sad-ablation} for full table).
DA increases monotonically (36.0\% to 79.0\%), but $\catrecall$@1 peaks at $H{=}15$ (54.2\%)...

% 在附录中添加：
\section{SAD Ablation Full Table}
\label{app:sad-ablation}
% 放入原 Table 5
```

---

### 方案 2：精简 Related Work

**预计节省：0.3-0.5 页**

当前 Related Work 包含 5 个段落：
1. Tool Selection and Routing
2. Tool-Augmented LLM Benchmarks
3. Task Decomposition and Planning
4. MCP Ecosystem and Tool Discovery
5. Retrieval-Augmented Generation

**建议精简**：

| 段落 | 当前长度 | 精简后 | 操作 |
|------|----------|--------|------|
| Tool Selection and Routing | ~8 行 | ~5 行 | 合并引用，减少描述 |
| Tool-Augmented LLM Benchmarks | ~6 行 | ~4 行 | 只保留最相关的 |
| Task Decomposition and Planning | ~6 行 | ~4 行 | 删减次要工作 |
| MCP Ecosystem | ~6 行 | ~4 行 | 已足够精简，保持 |
| RAG | ~4 行 | ~3 行 | 合并 |

**具体修改示例**：

```latex
% 原：
Tool selection for LLMs has been studied through API retrieval~\cite{patil2023gorilla,qin2023toolllm}, 
tool documentation matching~\cite{hao2024toolkengpt}, and hierarchical routing~\cite{xu2025skillrouter}.
AnyTool~\cite{du2024anytool} uses self-reflection to navigate hierarchical API pools, and 
CRAFT~\cite{yuan2024craft} creates specialized toolsets per query via retrieval.
SkillRouter~\cite{xu2025skillrouter} is closest to our work, introducing a bi-encoder approach 
for single-skill routing.

% 精简后：
Tool selection has been studied through API retrieval~\cite{patil2023gorilla,qin2023toolllm}, 
hierarchical routing~\cite{xu2025skillrouter,du2024anytool}, and toolset creation~\cite{yuan2024craft}.
SkillRouter~\cite{xu2025skillrouter} is closest to our work, introducing bi-encoder single-skill routing.
```

---

### 方案 3：精简 Method 部分描述

**预计节省：0.3 页**

当前 Method 部分较详细，可以精简：

| 小节 | 建议 |
|------|------|
| Stage 1: Task Decomposition | 保持，已足够精简 |
| Stage 2: Skill Retrieval | 合并 Skill Representation 到 2 行 |
| Stage 3: DAG Planning | 将 Compatibility 权重细节移至附录 |
| SAD | 保持，核心内容 |

**具体修改**：

```latex
% 将 Compatibility 权重细节移至附录
% 原：
We set weights $(0.4, 0.2, 0.2, 0.2)$ based on a grid search over a 30-query validation set; 
results are robust to weight variations ($\pm$0.1 changes alter $\catrecall$@1 by $<$0.5\%).

% 改为：
We set weights $(0.4, 0.2, 0.2, 0.2)$ based on grid search; see Appendix~\ref{app:compat} for details.
```

---

### 方案 4：合并部分实验结果到正文描述

**预计节省：0.2 页**

将部分表格数据改为文字描述：

```latex
% 原：完整 Table 5
% 改为：文字描述 + 附录表格

SAD improves $\catrecall$@1 across all five models (7--72B), with gains from +26.9\% (Mistral) 
to +59.9\% (Qwen-7B). Notably, Qwen2.5-7B+SAD (54.2\%) outperforms 72B vanilla (36.8\%) despite 
using 10$\times$ fewer parameters. Full results in Table~\ref{tab:sad-crossmodel}.
```

---

## 推荐执行顺序

| 优先级 | 方案 | 预计节省 | 风险 |
|--------|------|----------|------|
| 1 | 将 Table 5 移至附录 | 0.5 页 | 低 |
| 2 | 精简 Related Work | 0.3 页 | 低 |
| 3 | 精简 Method 细节 | 0.2 页 | 低 |
| **合计** | - | **1.0 页** | - |

---

## 执行后预期

| 项目 | 当前 | 精简后 |
|------|------|--------|
| 主文 | ~9 页 | ~8 页 |
| 参考文献 | ~1 页 | ~1 页 |
| 附录 | ~2 页 | ~3 页 |
| **总计** | **12 页** | **12 页** |

主文将符合 **8 页限制**。

---

## 验证步骤

1. 执行上述修改
2. 重新编译 PDF：
   ```bash
   cd paper
   pdflatex main && bibtex main && pdflatex main && pdflatex main
   ```
3. 检查主文页数（打开 PDF，确认前 8 页内包含所有正文内容）

---

## 注意事项

1. **不要删减核心贡献**：SAD 的描述和实验结果保持完整
2. **保持逻辑连贯**：精简时确保论证链条完整
3. **附录引用清晰**：所有移至附录的内容都要在正文中有明确引用

---

*Analysis generated: 2026-05-07*
