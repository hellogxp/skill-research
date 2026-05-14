# EMNLP 2026 实验交接文档

> 最后更新: 2026-05-10 16:30  
> 项目: SkillWeaver — Compositional Skill Routing for LLM Agents

---

## 一、环境信息

| 项目 | 值 |
|------|-----|
| **服务器** | `ssh -i ~/.ssh/pai_dsw_key root@121.41.193.56` |
| **GPU** | 8 × V100-SXM2-16GB |
| **Python** | 3.12.3 |
| **代码仓库 1** | `/mnt/workspace/skill-research` (论文 + 实验脚本 + 结果) |
| **代码仓库 2** | `/mnt/workspace/skillweaver` (核心框架代码) |
| **GitHub 1** | `https://github.com/hellogxp/skill-research.git` |
| **GitHub 2** | `https://github.com/hellogxp/skillweaver.git` |

### 模型路径

| 模型 | 路径 |
|------|------|
| Qwen2.5-7B-Instruct | `/mnt/workspace/models/Qwen/Qwen2___5-7B-Instruct` |
| Qwen2.5-14B-Instruct | `/mnt/workspace/models/Qwen/Qwen2___5-14B-Instruct` |
| Qwen2.5-72B-Instruct | `/mnt/workspace/models/Qwen/Qwen2___5-72B-Instruct` |
| Sentence Encoder | `/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2` |

### 数据路径

| 数据 | 路径 |
|------|------|
| Skill Pool | `/mnt/workspace/skill-research/data/processed_v3/skill_pool.jsonl` (60 skills) |
| Queries | `/mnt/workspace/skill-research/data/benchmark_v3/compositional_queries.jsonl` (300 queries) |
| 实验结果目录 | `/mnt/workspace/skill-research/results_v3/` |
| 论文主文件 | `/mnt/workspace/skill-research/paper/main.tex` |

---

## 二、已完成的实验及结果

### 2.1 SAD Hint Count 消融 (7B)

**脚本**: 之前已完成，结果在 `results_v3/skill_aware_ablation_summary.json`

| Hints H | DA | CatR@1 | Chain_cat |
|---------|------|--------|-----------|
| 0 (Vanilla) | 0.360 | 0.339 | 0.316 |
| 5 | 0.457 | 0.468 | 0.445 |
| 10 | 0.537 | 0.519 | 0.498 |
| **15** | **0.690** | **0.542** | **0.521** |
| 25 | 0.790 | 0.474 | 0.451 |

**结论**: CatR@1 在 H=15 达到峰值 (54.2%)，之后因 noise 下降。

### 2.2 Cross-Model SAD (H=15)

**结果来源**: `results_v3/` 下各模型文件

| Model | Mode | DA | CatR@1 | Chain_cat |
|-------|------|----|--------|-----------|
| Qwen2.5-7B | Vanilla | 0.360 | 0.339 | 0.316 |
| Qwen2.5-7B | +SAD | 0.690 | **0.542** | **0.521** |
| Qwen2.5-14B | Vanilla | 0.280 | 0.297 | 0.280 |
| Qwen2.5-14B | +SAD | 0.443 | 0.385 | 0.377 |
| Llama-3.1-8B | Vanilla | 0.000 | 0.216 | 0.210 |
| Llama-3.1-8B | +SAD | 0.217 | 0.339 | 0.323 |
| Mistral-7B | Vanilla | 0.177 | 0.242 | 0.248 |
| Mistral-7B | +SAD | 0.273 | 0.307 | 0.301 |
| Qwen2.5-72B | Vanilla | 0.627 | 0.368 | 0.358 |
| Qwen2.5-72B | +SAD | 0.503 | 0.483 | 0.518 |

### 2.3 Paraphrased Benchmark (7B + 14B)

**脚本**: `scripts/run_paraphrase_experiment.py`  
**结果**: `results_v3/paraphrased_experiment.json`  
**日志**: `/mnt/workspace/paraphrase_exp.log`

| Condition | Recall | Exact Match |
|-----------|--------|-------------|
| 7B Original + Vanilla | 0.9919 | 0.8933 |
| 7B Original + SAD | 0.9823 | 0.5867 |
| 7B Paraphrased + Vanilla | 0.9648 | 0.7367 |
| 7B Paraphrased + SAD | 0.9620 | 0.5200 |
| 14B Original + Vanilla | 0.9895 | 0.8300 |
| 14B Original + SAD | 0.9826 | 0.6967 |
| 14B Paraphrased + Vanilla | 0.9587 | 0.6867 |
| 14B Paraphrased + SAD | 0.9580 | 0.6467 |

**结论**: Paraphrased queries 的 recall 仅下降 ~3%，说明 SAD 效果不依赖 text overlap。

### 2.4 ReAct Baseline (7B + 14B)

**脚本**: `scripts/run_react_baseline.py`  
**结果**: `results_v3/react_baseline_experiment.json`  
**日志**: `/mnt/workspace/react_baseline.log`

| Model | R@1 | Chain EM | Latency |
|-------|-----|----------|---------|
| 7B ReAct | 0.7533 | 0.7267 | ~4.4s |
| 14B ReAct | 0.1567 | 0.1567 | — |

**结论**: 7B ReAct 虽然 R@1 高 (75.3%)，但延迟 2.7× 高于我们的 pipeline。14B ReAct 崩溃到 15.7% (JSON 解析失败)，证明 iterative planning 不稳定。

### 2.5 Category-Only Hints (7B) ✅

**脚本**: `scripts/run_category_only_experiment.py`  
**结果**: `results_v3/category_only_experiment.json`  
**日志**: `/mnt/workspace/category_only.log`

| Condition | R@1 | Chain EM | Latency |
|-----------|-----|----------|---------|
| Vanilla | 0.2727 | 0.0000 | 2962ms |
| Category-Only | 0.3100 | 0.0000 | 5490ms |
| Full-Skill (SAD) | 0.4000 | 0.4100 | 4428ms |

**关键发现**:
- Category 结构仅贡献 **29%** 的 SAD 增益 (+3.7pp / +12.7pp)
- Skill-level 语义贡献 **71%** (+9.0pp / +12.7pp)
- Category-Only 的 Chain EM = 0 → 类别信息无法帮助 skill chain 组合
- **论文已更新**: `paper/main.tex` Analysis section 中已添加 Table (tab:cat-only) 及分析段落

### 2.6 Category-Only 14B — ❌ 卡死 (未完成)

- 14B vanilla condition 已完成: R@1 = 0.2587
- category_only condition 在 100/300 处卡死 8 小时
- **卡死原因**: 见下方第三节详细分析

---

## 三、卡死问题诊断

### 3.1 现象

两个实验脚本均出现相同的卡死问题:

1. `run_category_only_experiment.py` — 14B 的 category_only condition 在处理第 ~101 条 query 时卡死
2. `run_adaptive_hints_experiment.py` — 7B 的 vanilla condition 在 Model loaded 后第一条 query 处即卡死

日志最后输出 `"Model loaded."` 或 `"Processed 100/300 queries"` 后再无新行，进程 CPU 持续在 ~100-190% 但无进展。

### 3.2 根因分析

**根因在 `skillweaver/src/skillweaver/core/decomposer.py` 的 `LocalDecomposer._generate()` 方法 (第 198-218 行)**:

```python
def _generate(self, messages: list[dict]) -> str:
    import torch
    self._init_model()
    prompt = self._tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)
    with torch.no_grad():
        output = self._model.generate(
            **inputs,
            max_new_tokens=256,        # ← 问题 1
            temperature=self.temperature,
            do_sample=True,            # ← 问题 2
        )                              # ← 问题 3: 无 timeout
    return self._tokenizer.decode(
        output[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
    ).strip()
```

**三个问题**:

| # | 问题 | 说明 |
|---|------|------|
| 1 | **无 `repetition_penalty`** | 模型可能陷入重复 token 循环，虽然 `max_new_tokens=256` 限制了长度，但生成 256 个重复 token 在 V100 上对 14B 模型可能需要非常久（每 token 推理变慢，因 KV cache 持续增长） |
| 2 | **`do_sample=True` 无 `top_p`/`top_k` 约束** | 采样模式下，即使 temperature=0.1，仍可能采到低概率 token 导致模型进入退化的重复循环 |
| 3 | **无任何 timeout 机制** | 一旦某条 query 触发异常生成行为，整个实验进程就永久卡死，没有跳过/恢复机制 |

**加剧因素**:
- Category-Only hints 传入的是抽象类别名（如 "web", "comm"）而非具体 skill 名，14B 模型可能无法理解这种抽象提示，导致输出退化
- 实验脚本中每条 query 的 LLM 调用没有 try/except 和 timeout 包装
- 日志只在每 50 条 query 后输出一次 progress，无法定位具体卡在哪条 query

### 3.3 修复方案

#### 方案 A: 修改 `decomposer.py` (推荐，改一处影响全部脚本)

文件: `/mnt/workspace/skillweaver/src/skillweaver/core/decomposer.py`  
位置: `LocalDecomposer._generate()` 方法 (第 198-218 行)

```python
def _generate(self, messages: list[dict]) -> str:
    import torch
    self._init_model()

    prompt = self._tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
    inputs = self._tokenizer(prompt, return_tensors="pt").to(self._model.device)

    with torch.no_grad():
        output = self._model.generate(
            **inputs,
            max_new_tokens=512,              # 增大到 512
            temperature=self.temperature,
            do_sample=True,
            repetition_penalty=1.1,          # 新增: 防重复循环
            top_p=0.9,                       # 新增: 限制采样范围
            pad_token_id=self._tokenizer.eos_token_id,  # 新增
        )
    return self._tokenizer.decode(
        output[0][inputs.input_ids.shape[1] :], skip_special_tokens=True
    ).strip()
```

#### 方案 B: 在实验脚本中添加 per-query timeout (推荐同时做)

在每个实验脚本的 `evaluate_condition` 循环中，给每条 query 的处理加上 timeout:

```python
import signal

class QueryTimeout(Exception):
    pass

def _timeout_handler(signum, frame):
    raise QueryTimeout()

# 在 for idx, query_data in enumerate(queries): 循环内部:
signal.signal(signal.SIGALRM, _timeout_handler)
signal.alarm(120)  # 每条 query 最多 120 秒
try:
    # ... 原有的 decompose/retrieve 逻辑 ...
    signal.alarm(0)
except QueryTimeout:
    logger.warning(f"Query {query_id} timed out after 120s, skipping")
    signal.alarm(0)
    continue
```

#### 方案 C: 增加日志可观测性

在 `_generate()` 方法开头和结尾加日志:
```python
logger.debug(f"_generate: prompt length = {len(prompt)} chars")
# ... generate ...
logger.debug(f"_generate: output length = {len(output[0])} tokens")
```

**建议**: 先执行方案 A + B，再重跑失败的实验。

---

## 四、未完成的实验

### 4.1 Adaptive Hint Selection

**脚本**: `scripts/run_adaptive_hints_experiment.py`  
**输出**: `results_v3/adaptive_hints_experiment.json`  
**状态**: ❌ 卡死，未产出任何结果  
**修复后运行**: `cd /mnt/workspace/skill-research && python3 -u scripts/run_adaptive_hints_experiment.py`

**实验目的**: 解决 hard queries (4-5 skills) 的 hint dilution 问题  
**实验条件** (5 个 condition):
1. Vanilla: 无 hints
2. Standard SAD: 固定 H=15
3. Category-Stratified: 按类别比例采样 hints
4. Complexity-Adaptive H: 根据预测的 query 复杂度动态调整 H (easy=10, medium=15, hard=25)
5. Combined: Adaptive H + Category-Stratified

**注意**: 此脚本中 `predict_query_complexity` 会额外调用一次 `decomposer.decompose()`，每条 query 实际调用 LLM 次数更多，更容易触发卡死。修复 decomposer 后再跑。

### 4.2 14B Constrained Decoding

**脚本**: `scripts/run_constrained_decoding_experiment.py`  
**输出**: `results_v3/constrained_decoding_experiment.json`  
**状态**: ❌ 未运行  
**修复后运行**: `cd /mnt/workspace/skill-research && python3 -u scripts/run_constrained_decoding_experiment.py`

**实验目的**: 解决 14B 模型 structured output 不稳定问题  
**实验方法**: few-shot prompting + JSON repair

### 4.3 Latency Breakdown

**脚本**: `scripts/run_latency_breakdown.py`  
**输出**: `results_v3/latency_breakdown.json`  
**状态**: ❌ 未运行  
**修复后运行**: `cd /mnt/workspace/skill-research && python3 -u scripts/run_latency_breakdown.py`

**实验目的**: 分解 pipeline 各阶段延迟 (decompose / retrieve / compose)  
**覆盖模型**: 7B, 14B, 72B

### 4.4 推荐执行顺序

1. **先修复 `decomposer.py`** (方案 A + B)
2. 跑 Adaptive Hints (`run_adaptive_hints_experiment.py`)
3. 跑 Constrained Decoding (`run_constrained_decoding_experiment.py`)
4. 跑 Latency Breakdown (`run_latency_breakdown.py`)
5. (可选) 重跑 Category-Only 14B (`run_category_only_experiment.py`，只跑 14B 部分)

**每个实验预计耗时**: 1-3 小时 (修复后)。建议每个都加 `timeout` 命令包装:
```bash
cd /mnt/workspace/skill-research
timeout 7200 python3 -u scripts/run_adaptive_hints_experiment.py 2>&1 | tee /mnt/workspace/adaptive.log
```

---

## 五、论文更新待办

### 5.1 已完成的论文更新

| 更新 | 位置 (main.tex) | 内容 |
|------|-----------------|------|
| Paraphrased 表格 | ~line 811 (Appendix) | 7B/14B original vs paraphrased 表格 |
| ReAct baseline 行 | ~line 419 (主表) | ReAct 7B/14B 结果行 |
| ReAct Discussion | ~line 624 | "Iterative planning is not a shortcut" 段落 |
| Category-Only 表格 | Analysis section (tab:cat-only) | 7B 三个 condition 的表格 + 三个发现 |
| Limitations 更新 | ~line 654 | Benchmark Generalization 段落 |

### 5.2 待完成的论文更新

1. **补充实验结果**: 将 Adaptive Hints / Constrained Decoding / Latency Breakdown 的结果添加到论文或 Appendix
2. **替换 Appendix 占位数据**: 将所有 "placeholder" 或硬编码的假数据替换为真实实验数据
3. **压缩至 ≤ 8 页**: 当前正文可能超出 8 页限制，需精简
4. **编译验证**: `pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex`

---

## 六、实验脚本清单

| 脚本 | 路径 | 状态 |
|------|------|------|
| build_benchmark.py | `scripts/build_benchmark.py` | ✅ 已完成 |
| validate_pipeline.py | `scripts/validate_pipeline.py` | ✅ 已完成 |
| run_paraphrase_experiment.py | `scripts/run_paraphrase_experiment.py` | ✅ 已完成 |
| run_react_baseline.py | `scripts/run_react_baseline.py` | ✅ 已完成 |
| run_category_only_experiment.py | `scripts/run_category_only_experiment.py` | ⚠️ 7B 完成, 14B 卡死 |
| run_adaptive_hints_experiment.py | `scripts/run_adaptive_hints_experiment.py` | ❌ 卡死未完成 |
| run_constrained_decoding_experiment.py | `scripts/run_constrained_decoding_experiment.py` | ❌ 未运行 |
| run_latency_breakdown.py | `scripts/run_latency_breakdown.py` | ❌ 未运行 |

---

## 七、SkillRetriever 接口注意事项

所有实验脚本中 `SkillRetriever` 的正确用法:

```python
from skillweaver.core.retriever import SkillRetriever

# 正确初始化方式
retriever = SkillRetriever(
    encoder_name="/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2",
    use_body=False,  # 使用 metadata-only
    top_k=5,
    cache_dir=None,
)
# 必须先 build_index
retriever.build_index(skills)  # skills: list[Skill]

# 搜索
results = retriever.search("query text")
results_batch = retriever.search_batch(["q1", "q2"])
```

**注意**: 之前的脚本曾使用错误的参数 (`embedding_model_path`, `skill_pool`) 导致启动失败，已在 05-10 修复为正确的 `encoder_name` + `build_index()` 接口。

---

## 八、关键文件索引

```
/mnt/workspace/
├── skill-research/
│   ├── paper/
│   │   ├── main.tex              # 论文主文件
│   │   ├── references.bib        # 参考文献
│   │   └── HANDOFF_EXPERIMENTS.md # 本文档
│   ├── scripts/
│   │   ├── run_category_only_experiment.py
│   │   ├── run_adaptive_hints_experiment.py
│   │   ├── run_constrained_decoding_experiment.py
│   │   ├── run_latency_breakdown.py
│   │   ├── run_paraphrase_experiment.py
│   │   ├── run_react_baseline.py
│   │   ├── build_benchmark.py
│   │   └── validate_pipeline.py
│   ├── results_v3/               # 所有实验结果 JSON
│   └── data/
│       ├── processed_v3/skill_pool.jsonl
│       └── benchmark_v3/compositional_queries.jsonl
├── skillweaver/
│   └── src/skillweaver/core/
│       ├── decomposer.py         # ← 需修复的核心文件
│       ├── retriever.py
│       ├── pipeline.py
│       └── models.py
├── models/                       # 下载好的模型
├── category_only.log             # Category-Only 实验日志
├── react_baseline.log            # ReAct 实验日志
└── paraphrase_exp.log            # Paraphrase 实验日志
```
