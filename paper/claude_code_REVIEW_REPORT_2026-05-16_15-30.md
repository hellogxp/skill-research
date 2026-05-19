# 论文评审报告 (Claude Opus 4.6 via Claude Code)

**论文标题**: Compositional Skill Routing for LLM Agents: Decompose, Retrieve, and Compose

**目标会议**: EMNLP 2026 (ACL Rolling Review)

**评审日期**: 2026-05-16 15:30

**评审模型**: Claude Opus 4.6 (Claude Code CLI)

**PDF页数**: ~9页正文 + ~8页附录 | **引用数**: 30篇 | **tex行数**: 935行

---

## 一句话总结

本文形式化定义了Compositional Skill Routing问题，提出SkillWeaver三阶段框架（decompose-retrieve-compose）和Skill-Aware Decomposition (SAD)反馈机制，将CatR@1从33.9%提升至54.2%（+60%），使7B+SAD超越72B vanilla，并构建了首个组合式技能路由benchmark CompSkillBench。

---

## 十维度评分表

| # | 维度 | 分数 | 评价 |
|---|------|------|------|
| 1 | 问题定义与动机 | **4.0** | 问题定义清晰且重要——从single-skill到compositional routing是自然且必要的进化，Eq.1的形式化精准，动机充分 |
| 2 | 技术贡献与新颖性 | **3.0** | 三阶段pipeline属于合理工程组合；SAD的retrieval->decomposition反馈循环有一定新意，但核心仍是bi-encoder + LLM prompt的简单拼接，缺少learned components |
| 3 | 实验设计 | **3.0** | Baseline缺少关键竞品（无CRAFT、AnyTool的compositional对比），缺少closed-source模型实验，统计检验仅报告std未做显著性测试 |
| 4 | 数据与Benchmark | **2.5** | 核心问题：template-based query generation导致ROUGE-L=0.845，37.8%完全拷贝；paraphrase验证存在方法论缺陷；human queries仅55条且hard子集仅10条 |
| 5 | 结果分析深度 | **4.0** | Error analysis (50 cases)、14B anomaly分析、category-only ablation、hint dilution分析做得深入，提供了切实的insights |
| 6 | 写作质量 | **4.0** | 结构清晰，逻辑连贯，符号一致，Limitations诚实透明；少量冗余（Discussion与Results有重复） |
| 7 | 图表质量 | **3.5** | Figure 1 TikZ图信息量充足；表格格式专业；但缺少关键可视化（SAD前后decomposition case study图、per-category性能热力图） |
| 8 | 相关工作覆盖 | **3.0** | 覆盖了主要方向，但缺少重要前作讨论：ToolSandbox、AgentFlan（在bib中但未在正文讨论）、MetaTool、Decomposed Prompting (Khot et al. 2023) |
| 9 | 可复现性 | **3.0** | 承诺"upon acceptance"开源；超参数描述较完整；但数据构造的关键步骤（keyword matching规则、anti-keywords列表）未公开 |
| 10 | 实际影响力 | **3.5** | MCP生态的实际痛点，有工程价值；但CatR@1=54.2%、Chain_E=0.003的绝对性能限制了实际部署可行性 |

---

## 加权总分与接受概率

| 维度 | 权重 | 得分 | 加权 |
|------|------|------|------|
| 问题定义与动机 | 10% | 4.0 | 0.400 |
| 技术贡献与新颖性 | 20% | 3.0 | 0.600 |
| 实验设计 | 20% | 3.0 | 0.600 |
| 数据与Benchmark | 10% | 2.5 | 0.250 |
| 结果分析深度 | 10% | 4.0 | 0.400 |
| 写作质量 | 10% | 4.0 | 0.400 |
| 图表质量 | 5% | 3.5 | 0.175 |
| 相关工作覆盖 | 5% | 3.0 | 0.150 |
| 可复现性 | 5% | 3.0 | 0.150 |
| 实际影响力 | 5% | 3.5 | 0.175 |
| **加权总分** | | | **3.30** |

**接受概率**: 30-40%

**ARR评分等级**: Borderline Reject / Borderline Accept

---

## 核心优势

1. **问题定义有价值**: Compositional Skill Routing是一个真实且未被充分研究的问题，Eq.1的形式化清晰，对MCP生态有直接指导意义。首次将组合式路由与单技能路由明确区分。

2. **SAD的cross-stage feedback机制有洞察力**: retrieval -> decomposition的反馈循环不同于标准RAG（augment generation），SAD augment的是upstream planning step——这个insight值得关注，且5个模型上一致验证了model-agnostic的有效性。

3. **分析深度出色**: 14B anomaly（hint-induced consolidation）、hint dilution on hard queries、category-only ablation（71% gain from skill-level semantics）都是有价值的发现，展现了对方法优缺点的诚实理解。

4. **Limitations诚实全面**: 明确指出text overlap问题、evaluation scope局限、hard query统计功效不足，这在审稿时是加分项。

5. **7B+SAD > 72B vanilla的发现有实践意义**: 对latency-sensitive部署场景有直接的actionable implication，且cross-model结果一致。

---

## 核心问题（按严重程度排序）

### P0 (必须解决 — 可能导致reject)

1. **Benchmark的text overlap问题严重削弱核心主张**
   - **问题**: ROUGE-L=0.845，37.8%完全拷贝——oracle R@1=99.5%很可能大部分来自lexical matching而非semantic understanding。Paraphrase验证存在方法论缺陷：LLM paraphrase仍保留语义近义词，且bi-encoder (BGE)本身对近义词替换就有很强的鲁棒性——真正需要的是human-written queries with zero text overlap。55条human queries太少，hard子集仅10条，缺乏统计功效。
   - **风险**: 审稿人会质疑核心数字的可信度
   - **预判Rebuttal**: 作者可能指向paraphrase + human query的"一致相对增益"。但审稿人应追问：为什么不在500+ human queries上做完整评估？
   - **建议**: 扩大human query评估至200+条（可众包），覆盖Easy/Medium/Hard，提供完整指标

2. **绝对性能过低，质疑实际可用性**
   - **问题**: 最佳配置7B+SAD的CatRecall@1=54.2%，Chain_E=0.003——几乎没有一条query能正确路由整个skill chain。Oracle到SAD的gap（99.5% -> 54.2%）仍有45个百分点。
   - **风险**: 审稿人会问"这个系统能实际部署吗？"
   - **建议**: (1) 坦诚讨论Chain_E=0.003的含义；(2) 引入partial chain match或top-k chain recall等更宽松但更实用的指标；(3) 讨论error recovery/fallback机制

### P1 (强烈建议解决 — 影响评分)

3. **缺少关键baseline对比**
   - **问题**: 未与CRAFT (ICLR 2025)对比——CRAFT解决了高度相关的per-query tool set creation问题。未与任何closed-source model (GPT-4, Claude)对比——这些模型的decomposition能力可能远超开源模型。ReAct 14B崩溃归因于"malformed JSON"但未尝试修复。
   - **建议**: 增加GPT-4/Claude作为decomposer（至少做decomposition对比）；增加CRAFT对比；修复ReAct 14B后重新评估

4. **DAG planner评估不足**
   - **问题**: DAG planner是三阶段pipeline的核心Stage 3，但仅在20条query的pilot study上评估，Coherence=0.54（近半数依赖关系检测错误）。Main table中的所有结果实际上不包含DAG planner，定位混乱。
   - **建议**: 要么在全部300条query上完整评估，要么明确降级为"future work"而非核心贡献

5. **Compatibility scoring缺少消融验证**
   - **问题**: Eq.4的multi-dimensional compatibility scoring权重(0.4/0.2/0.2/0.2)是手工设定的，无消融实验。alpha参数的设置也未说明。
   - **建议**: 验证权重敏感性，报告不同alpha值的性能变化

### P2 (建议解决 — 锦上添花)

6. **Discussion与Results文本重复**
   - Discussion S7的"Metadata vs body"段与S6.1的key findings高度重复
   - 建议精简Discussion，增加新内容而非复述

7. **ReAct在Table 1中的呈现不清晰**
   - ReAct行缺少CatR@1和CatR@10列（标为"--"），但正文在比较时又引用ReAct的R@1=75.3%，混合比较标准不统一
   - 建议在caption中明确说明evaluation protocol差异

8. **Related Work遗漏重要前作**
   - Decomposed Prompting (Khot et al. 2023)是task decomposition领域最直接的前作，在bib中但未在正文讨论
   - ToolSandbox、AgentFlan、MetaTool也在bib中但未讨论
   - 建议补充1-2句对比讨论

9. **缺少per-category性能分析**
   - 目前只有difficulty维度的分析。17个category中哪些容易/困难？对实际部署有重要指导意义
   - 建议增加per-category性能热力图

---

## 具体修改建议

### P0-1: 扩大Human Query评估

至少200+条human queries（可通过众包平台如Prolific/MTurk收集），确保：
- 覆盖Easy/Medium/Hard三个难度级别（至少30条hard queries）
- 提供完整的CatR@1/CatR@10/Chain_E/Chain_cat指标
- 报告ROUGE-L与skill descriptions的overlap分布

### P0-2: 引入实用性指标 + 讨论绝对性能

在Results或Discussion中增加：

```latex
\paragraph{Practical deployment considerations.}
While Chain$_E$ = 0.003 indicates near-zero exact chain matching, this metric
is overly strict for practical use. We introduce \emph{Partial Chain Match}
(PCM): the fraction of correctly routed steps per query, averaged over all
queries. Our best configuration achieves PCM = 0.521 ($\chaincat$), meaning
that on average, 52.1\% of steps in each query are routed to the correct
functional category---sufficient for systems with fallback or human-in-the-loop
mechanisms. The remaining decomposition gap (54.2\% vs.\ 99.5\% oracle)
motivates future work on learned decomposers, iterative SAD, and error recovery.
```

### P1-3: 补充关键Baseline

建议在Experimental Setup中增加：

```latex
\paragraph{Additional baselines.}
We additionally compare with GPT-4o as a decomposer (API-based, zero-shot)
to establish an upper bound for vanilla decomposition quality. We also report
CRAFT~\cite{yuan2024craft} results on the subset of queries where tool creation
is applicable.
```

### P1-5: Compatibility权重消融

增加一个小表格：

```latex
\begin{table}[h]
\centering\small
\begin{tabular}{lccc}
\toprule
\textbf{$\alpha$} & $\catrecall$\textbf{@1} & $\chaincat$ & \textbf{Chain$_E$} \\
\midrule
0.5 (default) & 0.542 & 0.521 & 0.003 \\
0.7 (relevance-heavy) & ? & ? & ? \\
0.9 (retrieval-only) & ? & ? & ? \\
1.0 (no compat.) & ? & ? & ? \\
\bottomrule
\end{tabular}
\caption{Sensitivity to relevance--compatibility trade-off $\alpha$.}
\end{table}
```

---

## 与竞品/相关工作的对比分析

| 维度 | SkillWeaver (本文) | SkillRouter (2025) | CRAFT (ICLR 2025) | AnyTool (2024) | MCP-Zero (2025) |
|------|-------------------|-------------------|-------------------|----------------|-----------------|
| **问题范围** | Compositional (multi-skill) | Single-skill | Per-query toolset | Hierarchical API | Zero-shot discovery |
| **方法架构** | Decompose + Retrieve + DAG | Bi-encoder rerank | LLM creates tools | Self-reflective agent | Protocol-level |
| **Skill规模** | 2,595 | ~1,000 | N/A (creates) | 16,000+ APIs | N/A |
| **Query规模** | 300 template + 55 human | ~500 | ~200 | ~200 | N/A |
| **核心Insight** | Decomposition is bottleneck | Body is decisive | Create > retrieve | Hierarchy + reflection | Protocol optimization |
| **Token降低** | 99.9% | N/A | N/A | N/A | 98% |

**关键差距**: SkillWeaver的竞争力在于问题定义的独特性（compositional routing），但在技术方法上相对conservative（bi-encoder + prompt engineering），缺乏learned components来close decomposition gap。与CRAFT的直接对比尤为缺失。

**关键差异化声明有效性分析**:
> "None jointly optimizes decomposition, retrieval, and inter-skill compatibility for compositional tasks."

这个claim是准确的。但审稿人可能反驳：ReAct的iterative loop隐式地做了joint optimization。建议在Discussion中承认这一点并解释为何显式分解仍有优势（更快、更稳定、可解释）。

---

## 审稿人可能的Questions for Authors

1. **Q1 (Critical)**: CatR@1=54.2%意味着近一半的sub-task被路由到错误的category。在实际部署中，一个3-step pipeline中有1-2个step路由错误，整个任务很可能失败。你们如何看待这个gap？是否有计划引入error recovery或fallback机制？

2. **Q2 (Critical)**: 为什么不尝试用GPT-4/Claude 3.5作为decomposer？这些模型在structured reasoning和instruction following方面远超7B-72B开源模型，可能直接将vanilla decomposition提升到SAD的水平甚至更高——这会削弱SAD的核心claim。

3. **Q3 (Important)**: SAD的两次LLM推理增加了48%延迟。在实际部署中，为什么不直接用更大的模型（延迟类似）而是用小模型+SAD？需要更详细的cost-benefit分析。

4. **Q4 (Important)**: Skill pool的categorization使用keyword matching——这个过程中排除了多少multi-category skills？排除这些skills是否引入了selection bias（只保留容易分类的skills）？

5. **Q5 (Clarification)**: Eq.1中alpha的值是多少？在实验中如何设置？不同alpha值对性能的影响如何？

6. **Q6 (Clarification)**: Table 8 (paraphrase)中"Original + Vanilla"的Skill Recall=0.992，但Table 1中Oracle Decomp + Meta的R@1=0.995。这两个实验条件是否相同？如果是，为什么数值不同？

---

## 页数与格式检查

- **正文页数**: ~9页（Introduction到Conclusion）
- **ARR主文限制**: 8页
- **状态**: 可能超限，需确认编译后实际页数
- **Appendix**: ~8页（14个appendix sections）——内容充实但数量偏多
- **参考文献**: 30篇，覆盖合理
- **格式**: 使用acl.sty，符合ARR要求

---

## 结论

这篇论文定义了一个有价值的问题（Compositional Skill Routing），提出了合理的baseline framework (SkillWeaver)，并贡献了深入的分析发现（decomposition is the bottleneck + SAD的cross-stage feedback）。写作质量和分析深度高于平均水平。

但以下三个问题共同构成了较大的风险：
1. **Benchmark质量问题**（high text overlap + 少量human queries）使核心数字的可信度存疑
2. **绝对性能太低**（CatR@1=54.2%, Chain_E=0.003）——论文证明了"问题很难"但未给出足够有效的解决方案
3. **Baseline不充分**——缺少CRAFT和closed-source model的对比

**推荐决定**: Borderline Reject (leaning Weak Accept with major revisions)

**预期接受概率**: 30-40%

### 接受概率优化路径

| 修改项 | 预估接受概率提升 | 工作量 |
|--------|-----------------|--------|
| 扩大human query (200+) | +10-15% | 2-3周 |
| 增加GPT-4/Claude对比 | +5-8% | 1周 |
| 补充CRAFT baseline | +3-5% | 1-2周 |
| 完善DAG planner评估 | +3-5% | 1周 |
| 引入partial chain match指标 | +2-3% | 2-3天 |
| Per-category分析 + case study | +2-3% | 3-5天 |
| **全部完成后预估** | **~55-65%** | **~6周** |

### 与前次评审对比

| 指标 | 本次评审 (2026-05-16) | 上次评审 (2026-05-14) | 差异原因 |
|------|----------------------|----------------------|---------|
| 加权总分 | 3.30 | 4.10 | 本次采用更严格的审稿视角 |
| 接受概率 | 30-40% | 70-85% | 本次更重视benchmark可信度和绝对性能 |
| 技术新颖性 | 3.0 | 3.5 | 本次认为pipeline缺少learned components |
| 实验设计 | 3.0 | 4.5 | 本次重点扣分baseline缺失和显著性检验 |
| 数据与Benchmark | 2.5 | 3.5 | 本次认为text overlap问题更为严重 |

**说明**: 两次评审的差异反映了审稿人严格程度的自然变异。实际ARR审稿中，论文通常会收到2-4位审稿人的评分，覆盖从conservative到generous的评分范围。建议作者针对本次评审中识别的P0问题进行修改，以应对最严格的审稿人。
