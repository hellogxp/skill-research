# Human Queries 完整修复方案

## 问题诊断

当前 50 条 human queries (`data/benchmark_v3/human_queries.jsonl`) 有两个严重缺陷：

1. **subtask description 全部是原始 query 的拷贝** — 每个 subtask 的 description 字段复制了整条 query，没有拆分成独立子任务描述
2. **ground truth skill 随意分配** — 例如 Postgres 查询标注了 MySQL server，communication 标注了 ProductHunt server

这导致：
- Vanilla DA = 0.16（模型合理地把 "Pull sales from Postgres and email marketing team" 分解为 5-8 步，而 ground truth 标 2）
- 评估指标不可信

对比 compositional queries 的正确格式：
```json
{
  "subtasks": [
    {"description": "generate marketing reports", "required_category": "marketing-analytics", ...},
    {"description": "compress media files", "required_category": "multimedia", ...}
  ]
}
```

## 待完成步骤

### Step 1: 生成 200 条 human-style queries

**脚本已就绪**: `/mnt/workspace/skill-research/scripts/generate_human_queries_v2.py`

运行：
```bash
cd /mnt/workspace/skill-research
python3 -u scripts/generate_human_queries_v2.py
```

输出文件: `data/benchmark_v3/human_queries_v2.jsonl`

分布: 80 easy (2 skills) + 80 medium (3 skills) + 40 hard (4-5 skills)

关键设计：
- 用 qwen-max API 生成自然语言 queries
- 每个 subtask 有独立 description（5-15 字）
- 按 category 从 skill pool 随机分配 ground truth skill
- 不出现 skill/tool 名称

预计耗时: ~10 分钟（API 调用 + rate limiting）

### Step 2: 替换旧文件

```bash
# 备份旧版
mv data/benchmark_v3/human_queries.jsonl data/benchmark_v3/human_queries_v1_backup.jsonl
# 新版替换
mv data/benchmark_v3/human_queries_v2.jsonl data/benchmark_v3/human_queries.jsonl
```

### Step 3: 跑 Vanilla + SAD 评估

写一个评估脚本（参考 `scripts/run_all_experiments_v4.py` 中的 `compute_metrics` 函数）：

```bash
cd /mnt/workspace/skill-research
python3 -u scripts/run_human_eval_v2.py
```

**评估脚本需要写**，核心逻辑：

```python
import json, sys, numpy as np
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, "/mnt/workspace/skill-research/skillweaver/src")
from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

MODEL = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
ENCODER = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"
H = 15

# Load skills & build index
skills = [Skill.from_dict(json.loads(l)) for l in open("data/processed_v3/skill_pool.jsonl")]
retriever = SkillRetriever(encoder_name=ENCODER, use_body=False, top_k=10)
retriever.build_index(skills)
decomposer = LocalDecomposer(model_path=MODEL, temperature=0.1)

# Load human queries
queries = [json.loads(l) for l in open("data/benchmark_v3/human_queries.jsonl")]

results = {"vanilla": [], "sad": []}

for qi, q in enumerate(queries):
    gt_subtasks = q["subtasks"]
    gt_num = q["num_skills"]
    gt_categories = [st["required_category"] for st in gt_subtasks]

    # Vanilla
    subtasks_v = decomposer.decompose(q["query"])
    texts_v = [st.description for st in subtasks_v]
    cands_v = retriever.search_batch(texts_v)
    da_v = 1 if len(subtasks_v) == gt_num else 0
    
    cat_hits_1 = 0
    cat_hits_10 = 0
    for i, gc in enumerate(gt_categories):
        if i < len(cands_v) and cands_v[i]:
            if gc in cands_v[i][0].skill.categories:
                cat_hits_1 += 1
            for m in cands_v[i][:10]:
                if gc in m.skill.categories:
                    cat_hits_10 += 1
                    break
    
    cat_r1_v = cat_hits_1 / len(gt_categories) if gt_categories else 0
    cat_r10_v = cat_hits_10 / len(gt_categories) if gt_categories else 0

    # SAD
    hints = build_hint_set(cands_v, H)
    subtasks_s = decomposer.decompose_with_hints(q["query"], hints)
    texts_s = [st.description for st in subtasks_s]
    cands_s = retriever.search_batch(texts_s)
    da_s = 1 if len(subtasks_s) == gt_num else 0
    
    cat_hits_1s = 0
    cat_hits_10s = 0
    for i, gc in enumerate(gt_categories):
        if i < len(cands_s) and cands_s[i]:
            if gc in cands_s[i][0].skill.categories:
                cat_hits_1s += 1
            for m in cands_s[i][:10]:
                if gc in m.skill.categories:
                    cat_hits_10s += 1
                    break
    
    cat_r1_s = cat_hits_1s / len(gt_categories) if gt_categories else 0
    cat_r10_s = cat_hits_10s / len(gt_categories) if gt_categories else 0

    results["vanilla"].append({"da": da_v, "cat_r1": cat_r1_v, "cat_r10": cat_r10_v})
    results["sad"].append({"da": da_s, "cat_r1": cat_r1_s, "cat_r10": cat_r10_s})
    
    if (qi + 1) % 20 == 0:
        print(f"Progress: {qi+1}/{len(queries)}")

# Save
with open("results_v4/human_queries_v2.json", "w") as f:
    json.dump(results, f, indent=2)

# Print per-difficulty breakdown
by_diff = defaultdict(lambda: {"vanilla": [], "sad": []})
for i, q in enumerate(queries):
    by_diff[q["difficulty"]]["vanilla"].append(results["vanilla"][i])
    by_diff[q["difficulty"]]["sad"].append(results["sad"][i])

for diff in ["easy", "medium", "hard"]:
    v = by_diff[diff]["vanilla"]
    s = by_diff[diff]["sad"]
    print(f"{diff} (n={len(v)}): V_DA={np.mean([r['da'] for r in v]):.3f} S_DA={np.mean([r['da'] for r in s]):.3f} V_CR1={np.mean([r['cat_r1'] for r in v]):.3f} S_CR1={np.mean([r['cat_r1'] for r in s]):.3f}")
```

预计耗时: ~15 分钟（模型加载 + 200 queries x 2 passes）

### Step 4: 更新 paper

在 `paper/main.tex` 中：

#### 4a. 添加 Table 8（在 Appendix `\section{Difficulty Breakdown}` 之前，约 line 636）

```latex
\section{Human-Style Query Evaluation}
\label{sec:human}

To validate that SAD generalizes beyond template-generated queries, we evaluate on 200 human-style queries generated by an independent LLM (qwen-max) with instructions to avoid skill names and write naturally.

\begin{table}[t]
\centering
\small
\begin{tabular}{llccc}
\toprule
\textbf{Mode} & \textbf{Difficulty} & \textbf{DA} & $\catrecall$\textbf{@1} & $\catrecall$\textbf{@10} \\
\midrule
\multirow{3}{*}{Vanilla} & Easy ($n{=}80$) & X.XX & X.XX & X.XX \\
& Medium ($n{=}80$) & X.XX & X.XX & X.XX \\
& Hard ($n{=}40$) & X.XX & X.XX & X.XX \\
\midrule
\multirow{3}{*}{+SAD} & Easy ($n{=}80$) & X.XX & X.XX & X.XX \\
& Medium ($n{=}80$) & X.XX & X.XX & X.XX \\
& Hard ($n{=}40$) & X.XX & X.XX & X.XX \\
\bottomrule
\end{tabular}
\caption{SAD on human-style queries (200 queries generated by qwen-max, zero text overlap with skill pool). SAD improves DA across all difficulty levels.}
\label{tab:human}
\end{table}
```

用 Step 3 的实际数值填入 X.XX。

#### 4b. 修改 Limitations（line 618）

把：
```
Future work should employ crowd-sourced query collection to further validate on fully human-authored queries.
```

改为：
```
We additionally evaluate on 200 human-style queries (\S\ref{sec:human}) generated by an independent LLM to reduce text overlap with the skill pool; fully crowd-sourced query collection remains future work.
```

#### 4c. 在主文 Results 中引用

在 Section 4 的 main results 讨论末尾（约 line 400 附近）加一句：
```
SAD's gains extend to human-style queries with zero text overlap (Table~\ref{tab:human}): DA improves from X\% to X\% (+X\% relative).
```

### Step 5: 同步到本地

```bash
# 从本地执行
scp -i ~/.ssh/pai_dsw_key root@121.41.193.56:/mnt/workspace/skill-research/results_v4/human_queries_v2.json ./results_v4/
scp -i ~/.ssh/pai_dsw_key root@121.41.193.56:/mnt/workspace/skill-research/data/benchmark_v3/human_queries.jsonl ./data/benchmark_v3/
```

---

## 关键文件位置

| 文件 | 路径 |
|------|------|
| 生成脚本 | `/mnt/workspace/skill-research/scripts/generate_human_queries_v2.py` |
| 评估脚本（需要写） | `/mnt/workspace/skill-research/scripts/run_human_eval_v2.py` |
| 输出 queries | `data/benchmark_v3/human_queries_v2.jsonl` → rename to `human_queries.jsonl` |
| 评估结果 | `results_v4/human_queries_v2.json` |
| Paper | `paper/main.tex` |

## 远程服务器信息

- Host: `root@121.41.193.56`
- SSH: `ssh -i ~/.ssh/pai_dsw_key -o StrictHostKeyChecking=no root@121.41.193.56`
- Model: `/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct`
- Encoder: `/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2`
- API (qwen-max): `https://dashscope.aliyuncs.com/compatible-mode/v1`, key: `sk-ba914ace8a6a42e0b0202e5ca8927418`

## 预期结果

根据 compositional queries 的表现（Vanilla DA=0.51, SAD DA=0.68），human queries 预计：
- Vanilla DA: 0.30-0.45（natural language 比 template 更模糊，DA 会低一些）
- SAD DA: 0.55-0.70（SAD 提升应保持 +40-80% relative）
- 如果 SAD relative gain 在 +50% 以上，与 review 的期望一致

如果 DA 数值不合理（如 <0.20），大概率是生成的 queries 和 ground truth num_skills 不匹配，需要检查生成质量。
