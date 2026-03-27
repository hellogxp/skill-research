# SkillWeaver - AI Agent 技能编排工具

> "Describe what you want, we compose the right skills for you."
> 用自然语言描述你的任务，SkillWeaver 自动找到并编排合适的 AI 技能组合。

## 项目定位

**AI Agent 的技能包管理器 + 自动工作流编排器**

类比：
- npm 之于 Node.js → SkillWeaver 之于 AI Agent
- Docker Compose 之于容器 → SkillWeaver 之于 AI 技能

## 解决的核心痛点

1. **技能发现难**: MCP server、Claude Skills、OpenAI Functions 数量爆炸，用户找不到合适的
2. **组合困难**: 复杂任务需要多个技能协作，手动拼接费时费力
3. **生态割裂**: SKILL.md、MCP、OpenAI function spec 格式不统一，无法互通
4. **质量参差**: 大量重复/低质量技能，没有评估和排序机制

## 核心功能

### 1. `skillweaver search` — 语义技能搜索

```bash
# 用自然语言搜索技能
$ skillweaver search "convert PDF to markdown"

Found 5 matching skills:
  1. pdf-to-markdown (score: 0.94) - Convert PDF files to clean markdown
  2. document-converter (score: 0.87) - Multi-format document conversion
  3. pdf-parser (score: 0.82) - Extract text and structure from PDFs
  ...

# 按类别过滤
$ skillweaver search "generate charts" --category visualizer

# 指定技能格式
$ skillweaver search "deploy to k8s" --format mcp
```

**技术实现**: BGE-large-en-v1.5 编码 + FAISS 索引（论文中的 SkillRetriever）

### 2. `skillweaver plan` — 自动任务编排 (核心卖点)

```bash
# 描述复杂任务，自动生成技能链
$ skillweaver plan "爬取 GitHub trending 项目，分析编程语言趋势，生成可视化图表，发送到 Slack"

📋 Task Plan:
  Step 1: [web-scraper] 爬取 GitHub trending 页面数据
  Step 2: [data-analyzer] 分析编程语言分布趋势
  Step 3: [chart-generator] 生成趋势可视化图表
  Step 4: [slack-notifier] 将图表发送到 Slack 频道

Dependencies: 1 → 2 → 3 → 4 (sequential)
Confidence: 0.87

Save plan? [Y/n] y
Plan saved to: .skillweaver/plans/github-trending-analysis.yaml

# 查看/编辑计划
$ skillweaver plan show github-trending-analysis

# 执行计划 (未来功能)
$ skillweaver run github-trending-analysis
```

**技术实现**: LLM 分解（论文中的 TaskDecomposer）+ 检索 + 兼容性规划（DAGPlanner）

### 3. `skillweaver index` — 技能索引管理

```bash
# 扫描本地目录，建立技能索引
$ skillweaver index ./my-skills/
Indexed 42 skills from ./my-skills/

# 扫描 MCP 配置
$ skillweaver index --from-mcp ~/.config/mcp/servers.json
Indexed 18 MCP servers (67 tools total)

# 从 GitHub repo 导入
$ skillweaver index --from-github user/repo
Indexed 15 skills from user/repo

# 查看索引状态
$ skillweaver index status
Total skills: 124
  SKILL.md: 42
  MCP tools: 67
  OpenAI functions: 15
Index size: 2.3 MB
Last updated: 2026-03-27
```

### 4. `skillweaver hub` — 社区技能市场 (后期)

```bash
# 浏览热门技能
$ skillweaver hub trending

# 发布技能
$ skillweaver hub publish ./my-skill/SKILL.md

# 安装社区技能
$ skillweaver hub install @awesome-user/pdf-analyzer
```

## 技术架构

```
skillweaver/
├── cli/                    # CLI 入口 (Click/Typer)
│   ├── main.py            # 主命令
│   ├── search.py          # search 子命令
│   ├── plan.py            # plan 子命令
│   └── index.py           # index 子命令
│
├── core/                   # 核心引擎 (来自论文)
│   ├── decomposer.py      # 任务分解 (TaskDecomposer)
│   ├── retriever.py       # 技能检索 (SkillRetriever + FAISS)
│   ├── planner.py         # DAG 规划 (DAGPlanner + CompatibilityScorer)
│   └── pipeline.py        # 完整流水线 (CompositionalSkillRouter)
│
├── adapters/               # 多格式适配层
│   ├── skill_md.py        # SKILL.md 格式 (Anthropic)
│   ├── mcp.py             # MCP server 格式
│   ├── openai_func.py     # OpenAI function calling 格式
│   └── langchain.py       # LangChain tool 格式
│
├── index/                  # 索引管理
│   ├── builder.py         # 索引构建
│   ├── store.py           # 本地存储 (~/.skillweaver/)
│   └── embeddings.py      # 嵌入模型管理
│
├── models/                 # LLM 后端
│   ├── local.py           # 本地模型 (transformers/ollama)
│   ├── openai.py          # OpenAI API
│   └── anthropic.py       # Claude API
│
└── config/                 # 配置
    └── settings.py        # 用户配置
```

## 与论文的关系

| 论文组件 | 工具模块 | 说明 |
|---|---|---|
| TaskDecomposer | core/decomposer.py | 论文的 LLM 分解器，工具中支持多种 LLM 后端 |
| SkillRetriever (BGE+FAISS) | core/retriever.py | 论文的检索器，工具中增加了增量索引 |
| DAGPlanner | core/planner.py | 论文的编排器，工具中增加了交互式编辑 |
| CompSkillBench | 不直接包含 | 但工具的 README 引用论文，论文引用工具 |
| 评估指标 | 可选的 eval 命令 | 用于用户评估自己的技能库质量 |

## 用户安装体验

```bash
# 安装
pip install skillweaver

# 首次使用：选择 LLM 后端
$ skillweaver init
? Choose LLM backend for task decomposition:
  > Local (Ollama - free, private, needs 8GB RAM)
    OpenAI API (fast, needs API key)
    Anthropic API (fast, needs API key)
    Skip (search only, no auto-compose)

? Choose embedding model:
  > BGE-large-en-v1.5 (recommended, 1.2GB)
    BGE-base-en-v1.5 (smaller, 440MB)

Downloading models... done.
SkillWeaver is ready! Try: skillweaver search "your task"
```

## MVP 范围 (v0.1.0)

最小可行版本只需要以下功能：

1. `skillweaver init` — 初始化配置，下载嵌入模型
2. `skillweaver index <path>` — 扫描 SKILL.md 文件建立索引
3. `skillweaver search <query>` — 语义搜索技能
4. `skillweaver plan <query>` — 自动分解 + 检索 + 编排

不包含: hub/市场、执行、MCP 适配（留给 v0.2+）

## 爆火策略

1. **Demo 视频**: 录一个 30 秒视频，展示 plan 命令自动编排 5 个技能完成复杂任务
2. **README 质量**: 精美的 README + GIF 动图 + 一键安装
3. **Reddit/HN 首发**: 投 r/MachineLearning + Hacker News
4. **论文背书**: "From our EMNLP 2026 paper on Compositional Skill Routing"
5. **实用性**: 开箱即用，不需要 GPU（嵌入模型用 CPU 也能跑）
6. **社区兼容**: 支持 MCP 生态（当前最火的 agent 工具协议）

## 开发计划

Phase 1 (MVP): CLI 骨架 + search + plan
Phase 2: MCP 适配 + OpenAI function 适配
Phase 3: Hub / 社区技能市场
Phase 4: VS Code 扩展 + IDE 集成
