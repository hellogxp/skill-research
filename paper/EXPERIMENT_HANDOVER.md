# SkillWeaver 实验交接文档

> 最后更新: 2026-05-10 16:31
> 目标: EMNLP 2026 投稿

---

## 一、环境信息

| 项目 | 值 |
|------|-----|
| **服务器** | `ssh -i ~/.ssh/pai_dsw_key root@121.41.193.56` |
| **GPU** | 8×Tesla V100-SXM2-16GB (每卡 16384 MiB) |
| **Python** | 3.12.3 |
| **pip** | 24.0 |
| **虚拟环境** | `/mnt/workspace/venv_sw`（SkillWeaver 依赖已安装在此 venv 中） |
| **代码仓库** | `/mnt/workspace/skill-research` (论文+实验) |
| **框架仓库** | `/mnt/workspace/skillweaver` (SkillWeaver 包，`pip install -e .` 安装) |
| **GitHub** | `https://github.com/hellogxp/skill-research.git` / `https://github.com/hellogxp/skillweaver.git` |

### 模型路径

| 模型 | 实际路径 | 备注 |
|------|------|------|
| Qwen2.5-7B-Instruct | `/mnt/workspace/models/Qwen/Qwen2___5-7B-Instruct` | 另有软链接 `Qwen2.5-7B-Instruct` 指向此目录 |
| Qwen2.5-14B-Instruct | `/mnt/workspace/models/Qwen/Qwen2___5-14B-Instruct` | 另有软链接 `Qwen2.5-14B-Instruct` 指向此目录 |
| Qwen2.5-72B-Instruct | `/mnt/workspace/models/Qwen/Qwen2___5-72B-Instruct` | 另有软链接 `Qwen2.5-72B-Instruct` 指向此目录 |
| Embedding (MiniLM) | `/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2` | |

> ⚠️ 脚本中使用的是含 `___` 的实际目录名（如 `Qwen2___5-7B-Instruct`），不是带 `.` 的软链接名

### 服务器完整目录结构

```
/mnt/workspace/
├── skill-research/                  # 论文+实验仓库
│   ├── data/
│   │   ├── raw_skills/              # 原始 skill 数据
│   │   ├── processed_v3/
│   │   │   └── skill_pool.jsonl     # 60 个 skill（48KB）
│   │   └── benchmark_v3/
│   │       ├── compositional_queries.jsonl  # 300 条 benchmark queries（292KB）
│   │       ├── paraphrased_queries.jsonl    # 释义后的 queries（348KB）
│   │       ├── queries_easy.jsonl           # 按难度拆分：easy
│   │       ├── queries_medium.jsonl         # 按难度拆分：medium
│   │       ├── queries_hard.jsonl           # 按难度拆分：hard
│   │       └── benchmark_stats.json         # 统计信息
│   ├── scripts/                     # 实验脚本（详见第二节）
│   │   ├── build_benchmark.py
│   │   ├── validate_pipeline.py
│   │   ├── run_paraphrase_experiment.py
│   │   ├── run_react_baseline.py
│   │   ├── run_category_only_experiment.py
│   │   ├── run_adaptive_hints_experiment.py
│   │   ├── run_constrained_decoding_experiment.py
│   │   └── run_latency_breakdown.py
│   ├── results_v3/                  # 实验结果（详见下方说明）
│   ├── paper/
│   │   └── main.tex                 # 论文主文件
│   └── ...
├── skillweaver/                     # SkillWeaver 框架仓库
│   ├── src/skillweaver/core/        # 核心代码
│   │   ├── __init__.py
│   │   ├── models.py               # Skill 等数据模型
│   │   ├── decomposer.py           # LocalDecomposer（LLM 推理）
│   │   ├── retriever.py            # SkillRetriever（embedding 检索）
│   │   ├── pipeline.py             # build_hint_set 等 pipeline 函数
│   │   ├── planner.py              # skill chain 规划
│   │   ├── dag_planner.py          # DAG 规划器
│   │   ├── executor.py             # 执行器
│   │   └── compatibility.py        # 兼容性
│   ├── tests/
│   ├── pyproject.toml
│   └── ...
├── models/                          # 预下载的模型
│   ├── Qwen/
│   │   ├── Qwen2___5-7B-Instruct/
│   │   ├── Qwen2___5-14B-Instruct/
│   │   └── Qwen2___5-72B-Instruct/
│   └── sentence-transformers/
│       └── all-MiniLM-L6-v2/
├── venv_sw/                         # Python 虚拟环境
└── *.log                            # 实验日志文件（见下方）
```

### 日志文件

| 日志 | 路径 | 大小 | 对应实验 |
|------|------|------|----------|
| Paraphrased 实验 | `/mnt/workspace/paraphrase_exp.log` | 35KB | ✅ 完成 |
| ReAct Baseline | `/mnt/workspace/react_baseline.log` | 78KB | ✅ 完成 |
| Category-Only | `/mnt/workspace/category_only.log` | 16KB | ❌ 14B 卡死 |
| 剩余实验 v2 | `/mnt/workspace/remaining_v2.log` | 5KB | ❌ Adaptive 卡死 |
| 72B 下载 | `/mnt/workspace/download_72b.log` | 5.5MB | ✅ 下载完成 |

### results_v3/ 文件说明

> ⚠️ 注意：`results_v3/` 下有很多 **0 字节的占位文件**（创建于 May 7，来自 git 仓库），它们是空的，不包含任何数据。

| 文件 | 大小 | 状态 |
|------|------|------|
| `pipeline_validation.json` | 1.6KB | ✅ 有数据 |
| `paraphrased_experiment.json` | 1.4KB | ✅ 有数据 |
| `react_baseline_experiment.json` | 455KB | ✅ 有数据 |
| `category_only_experiment.json` | 583KB | ✅ 有数据（仅 7B） |
| `skill_aware_qwen7b_hints5.json` | 761KB | ✅ 有数据（早期实验） |
| `skill_aware_qwen7b_hints10.json` | 811KB | ✅ 有数据 |
| `skill_aware_qwen7b_hints15.json` | 935KB | ✅ 有数据 |
| `skill_aware_qwen7b_hints25.json` | 901KB | ✅ 有数据 |
| `qwen14b_vanilla.json` | 1.9MB | ✅ 有数据 |
| `qwen14b_sad_hints15.json` | 779KB | ✅ 有数据 |
| `qwen72b_vanilla.json` | 1.2MB | ✅ 有数据 |
| `qwen72b_sad_hints15.json` | 956KB | ✅ 有数据 |
| `skill_aware_llama_31_8b_instruct_hints15.json` | 2.2MB | ✅ 有数据 |
| `skill_aware_mistral_7b_instruct_v03_hints15.json` | 1.5MB | ✅ 有数据 |
| `skill_aware_ablation_summary.json` | 2.5KB | ✅ 有数据 |
| `stddev_summary.json` | 2.1KB | ✅ 有数据 |
| `topk_analysis.json` | 2.4KB | ✅ 有数据 |
| `14b_summary.json` | **0 字节** | ❌ 空占位文件 |
| `72b_summary.json` | **0 字节** | ❌ 空占位文件 |
| `ablation_constrained_decomp.json` | **0 字节** | ❌ 空占位文件 |
| `baseline_oracle_decomp_body.json` | **0 字节** | ❌ 空占位文件 |
| `baseline_oracle_decomp_meta.json` | **0 字节** | ❌ 空占位文件 |
| `baseline_single_skill_body.json` | **0 字节** | ❌ 空占位文件 |
| `baseline_single_skill_meta.json` | **0 字节** | ❌ 空占位文件 |
| `decomposer_llama_31_8b_instruct.json` | **0 字节** | ❌ 空占位文件 |
| `decomposer_mistral_7b_instruct_v03.json` | **0 字节** | ❌ 空占位文件 |
| `difficulty_breakdown.json` | **0 字节** | ❌ 空占位文件 |
| `e2e_pilot_report.json` | **0 字节** | ❌ 空占位文件 |
| `experiment_summary.json` | **0 字节** | ❌ 空占位文件 |
| `full_pipeline_body_v3.json` | **0 字节** | ❌ 空占位文件 |
| `full_pipeline_metadata_v3.json` | **0 字节** | ❌ 空占位文件 |
| `human_eval_summary.json` | **0 字节** | ❌ 空占位文件 |
| `human_qwen7b_sad.json` | **0 字节** | ❌ 空占位文件 |
| `human_qwen7b_vanilla.json` | **0 字节** | ❌ 空占位文件 |
| `llm_direct_qwen25_72b_instruct_top50.json` | **0 字节** | ❌ 空占位文件 |
| `llm_direct_qwen25_7b_instruct_top50.json` | **0 字节** | ❌ 空占位文件 |
| `llm_direct_summary.json` | **0 字节** | ❌ 空占位文件 |

---

## 二、实验总览（已完成 + 未完成）

### ✅ 已完成的实验

#### 1. 基础 Pipeline 验证
- **状态**: ✅ 完成
- **结果文件**: `results_v3/pipeline_validation.json`
- **说明**: 验证 SkillWeaver pipeline 在服务器上可以正常运行

#### 2. SAD Ablation (hint count H=0/5/10/15/25)
- **状态**: ✅ 完成（之前就有）
- **结果文件**: `results_v3/skill_aware_qwen7b_hints*.json`
- **关键结果**: H=15 时 CatR@1 峰值 54.2%，H=25 下降到 47.4%

#### 3. Cross-model SAD (7B/14B/72B/Llama/Mistral)
- **状态**: ✅ 完成（之前就有）
- **结果文件**: `results_v3/qwen14b_*.json`, `qwen72b_*.json`, `skill_aware_llama_*.json`, `skill_aware_mistral_*.json`

#### 4. Paraphrased Benchmark
- **状态**: ✅ 完成
- **结果文件**: `results_v3/paraphrased_experiment.json`
- **日志**: `/mnt/workspace/paraphrase_exp.log`
- **关键结果**: Paraphrased queries 下 SAD 仍有效，排除了 text overlap 解释
- **论文**: 已添加到 `paper/main.tex` (~line 811 附近，Paraphrased 表格)

#### 5. ReAct Baseline (7B + 14B)
- **状态**: ✅ 完成
- **结果文件**: `results_v3/react_baseline_experiment.json`
- **日志**: `/mnt/workspace/react_baseline.log`
- **关键结果**:
  - 7B ReAct: R@1=75.3%, Chain EM=72.7%, Latency=4.4s (2.7× slower)
  - 14B ReAct: R@1=15.7% (崩溃，JSON parse 大量失败)
- **论文**: 已添加到 Discussion section (Iterative planning 段落)，主表也加了 ReAct 行

#### 6. Category-Only Hints (7B)
- **状态**: ✅ 7B 完成 / ❌ 14B 卡死
- **结果文件**: `results_v3/category_only_experiment.json` (仅包含 7B 数据)
- **日志**: `/mnt/workspace/category_only.log`
- **7B 关键结果**:

| Condition | R@1 | Chain EM | Latency |
|-----------|------|----------|---------|
| Vanilla | 0.2727 | 0.0000 | 2962ms |
| Category-Only | 0.3100 | 0.0000 | 5490ms |
| Full-Skill (SAD) | 0.4000 | 0.4100 | 4428ms |

- **关键发现**: Category 结构仅贡献 SAD 增益的 29%，Skill-level 语义贡献 71%
- **论文**: 已添加到 Analysis section (Table `tab:cat-only` 和三个发现的分析段落)

---

### ❌ 卡死的实验

#### 7. Category-Only Hints (14B)
- **状态**: ❌ 卡死
- **现象**:
  - 14B 的 vanilla condition 正常完成（R@1=0.2587，耗时约 47 分钟）
  - 进入 category_only condition 后，跑到 100/300 queries 后卡死
  - 日志最后更新时间: `2026-05-10 08:10:58`，之后 **8 小时无任何输出**
  - 进程 PID 20402 仍存活，CPU 占用 102%，但无日志产出
  - 已手动 kill -9 终止
- **日志文件**: `/mnt/workspace/category_only.log`
- **脚本**: `scripts/run_category_only_experiment.py`
- **可能原因**: 14B 模型在 category_only prompt 下可能产生无限长输出或推理死循环（该脚本没有设置 `max_new_tokens` 或单 query 超时机制）

#### 8. Adaptive Hints (7B)
- **状态**: ❌ 卡死
- **现象**:
  - 模型加载成功（`Model loaded.` 日志已出现）
  - 进入 vanilla condition 评估后，**第一个 query 就卡死**，一个 Processed 日志都没有
  - 日志最后更新时间: `2026-05-10 08:23:06`，之后 **8 小时无输出**
  - 进程 PID 27994 存活，CPU 191%
  - 已手动 kill -9 终止
- **日志文件**: `/mnt/workspace/remaining_v2.log`
- **脚本**: `scripts/run_adaptive_hints_experiment.py`
- **可能原因**: 同上，推理过程无超时保护，模型可能在某个 query 上产生无限长输出

---

### ⏳ 未启动的实验

#### 9. 14B Constrained Decoding
- **状态**: ⏳ 未启动
- **脚本**: `scripts/run_constrained_decoding_experiment.py`
- **目的**: 用 few-shot prompting + JSON repair 解决 14B 模型 structured output 不稳定问题
- **输出**: `results_v3/constrained_decoding_experiment.json`
- **预计耗时**: 1-2 小时（如果不卡死）
- **⚠️ 风险**: 可能跟上面两个实验一样卡死，需要先修复超时问题

#### 10. Latency Breakdown (7B/14B/72B)
- **状态**: ⏳ 未启动
- **脚本**: `scripts/run_latency_breakdown.py`
- **目的**: 分别测量 decomposition、retrieval、planning 各阶段的延迟
- **输出**: `results_v3/latency_breakdown.json`
- **预计耗时**: 1-2 小时（如果不卡死）
- **⚠️ 风险**: 同上

---

## 三、卡死问题详细描述

### 共同特征

两个卡死的实验有相同的模式：
1. 模型加载成功，日志正常输出到 `Model loaded.`
2. 进入实验评估循环后，在某个 query 处卡死
3. 进程 CPU 占用率很高（100-190%），但无日志产出
4. 即使等待 8 小时以上也没有恢复

### 怀疑的根因

所有实验脚本都调用 `skillweaver.core.decomposer.LocalDecomposer` 做推理。该类底层使用 `transformers` 的 `model.generate()` 方法。**如果没有设置 `max_new_tokens` 参数或设置过大**，模型可能在某些 prompt 下进入重复输出模式，不断生成 token 直到 OOM 或无限循环。

### 对比：正常运行 vs 卡死

| 实验 | 模型 | Condition | 状态 | 备注 |
|------|------|-----------|------|------|
| Category-Only | 7B | vanilla | ✅ | 正常 |
| Category-Only | 7B | category_only | ✅ | 正常 |
| Category-Only | 7B | full_skill | ✅ | 正常 |
| Category-Only | 14B | vanilla | ✅ | 正常，耗时 47 分钟 |
| Category-Only | 14B | category_only | ❌ | 100/300 卡死 |
| Adaptive Hints | 7B | vanilla | ❌ | 第一个 query 就卡死 |

### 建议的修复方向

1. **检查 `LocalDecomposer` 的 `generate()` 调用**，确保设置了合理的 `max_new_tokens`（建议 512-1024）
2. **在实验脚本的评估循环中添加单 query 超时机制**，例如：
   ```python
   import signal
   def timeout_handler(signum, frame):
       raise TimeoutError("Query processing timed out")
   signal.signal(signal.SIGALRM, timeout_handler)
   signal.alarm(120)  # 120秒超时
   ```
3. **检查 SkillRetriever 接口**：之前所有 4 个脚本都存在 `SkillRetriever` 接口调用不匹配的问题，已修复为 `SkillRetriever(encoder_name, use_body, top_k, cache_dir)` + `build_index(skills)`，但可能仍有遗漏

---

## 四、论文当前状态

### 已完成的论文更新

1. **Paraphrased Evaluation 表格** (~line 811): 添加了释义评估结果
2. **ReAct Baseline**: 
   - 主表添加了 ReAct 行 (~line 419)
   - Discussion 添加了 "Iterative planning is not a shortcut" 段落 (~line 624)
3. **Category-Only Ablation**: 
   - Analysis section 添加了 Table `tab:cat-only` 和三个发现的分析 (~line 616)
4. **Limitations**: 更新了 Benchmark Generalization 段落 (~line 654)

### 未完成的论文更新

1. **补充实验结果**: 等 Adaptive Hints / Constrained Decoding / Latency Breakdown 完成后，需要：
   - 在 Appendix 中添加 Adaptive Hints 的结果表格
   - 在 14B Anomaly Analysis (Appendix) 中更新 Constrained Decoding 结果
   - 添加 Latency Breakdown 表格
2. **压缩到 ≤ 8 页**: 当前论文可能超页，需要压缩
3. **编译验证**: 需要在服务器上 `pdflatex` 编译通过

---

## 五、SkillRetriever 接口说明

之前所有 4 个实验脚本（category_only、adaptive_hints、constrained_decoding、latency_breakdown）都使用了错误的 `SkillRetriever` 初始化参数。正确的接口是：

```python
from skillweaver.core.retriever import SkillRetriever

retriever = SkillRetriever(
    encoder_name="/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2",
    use_body=False,
    top_k=15,
    cache_dir=None
)
retriever.build_index(skills)  # skills: List[Skill]
```

**不是** `SkillRetriever(embedding_model_path=..., skill_pool=...)`。此修复已在 2026-05-10 05:49 批量应用到 4 个脚本。

---

## 六、运行实验的命令

```bash
# SSH 到服务器
ssh -i ~/.ssh/pai_dsw_key root@121.41.193.56

# 进入项目目录
cd /mnt/workspace/skill-research

# 运行某个实验（建议加 timeout 防止卡死）
timeout 7200 python3 -u scripts/run_adaptive_hints_experiment.py 2>&1 | tee /mnt/workspace/adaptive_hints.log

# 查看 GPU 状态
nvidia-smi

# 查看结果
ls -lt results_v3/
```

---

## 七、GitHub 同步

本地仓库需要同步到 GitHub（两个仓库）：

```bash
# 在本地执行（macOS）
cd /Users/xuepinxueping.gxpg.gxp/skill-research
python3 _sync_to_github.py

# 或手动 push
git add -A && git commit -m "update" && git push origin main
```

服务器上的代码修改（results_v3 下的新结果文件）需要手动 scp 下来或在服务器上 git push。
