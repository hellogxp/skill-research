# SkillWeaver 工具与论文匹配度 + 开源就绪度评估

**文件名**: `review-notes/tool-paper-alignment-2026-04-02-1730.md`
**评审时间**: 2026-04-02 17:30

---

## 第一部分：工具与论文的匹配度

### 论文中描述的每个组件 vs 工具中的实现

| 论文组件 | 论文描述 | 工具实现 | 匹配？ |
|---------|---------|---------|--------|
| Task Decomposer | LLM-based，JSON 输出，fallback parser | `decomposer.py`: 4 后端 (OpenAI/transformers/Ollama/规则) + JSON parse + fallback | ✅ |
| Skill Retriever | BGE-large + FAISS，metadata-only/body-aware | `retriever.py`: BGE + FAISS，两种 encoding 策略 | ✅ |
| DAG Planner | 依赖检测 (I/O + producer-consumer + linguistic)，Kahn's 并行分组，四维兼容性 | `dag_planner.py` + `compatibility.py`: 完整实现 | ✅ |
| SAD (Algorithm 1) | Two-pass: vanilla decompose → retrieve → build hints → re-decompose | `pipeline.py`: `build_hint_set()` + two-pass 逻辑 + `decompose_with_hints()` | ✅ |
| CompSkillBench | 2595 skills, 300 queries, 17 categories | `src/build_benchmark.py` 等脚本 + `results/` | ✅ (实验代码) |
| Skill 格式 | SKILL.md specification | `adapters/skill_md.py`: YAML frontmatter 解析 | ✅ |
| 评估指标 | R@k, CatR@k, ChainExact, ChainCat, DA | `src/run_experiments.py` 中的 evaluate() | ✅ (实验代码) |

### 论文中没有描述但工具中有的（额外功能）

| 工具功能 | 论文中提到？ | 说明 |
|---------|------------|------|
| MCP adapter | 否 | 解析 mcp.json，转换 MCP tools 为 Skill 对象 |
| OpenAI Functions adapter | 否 | 解析 OpenAI function definitions |
| LangChain adapter | 否 | 解析 LangChain BaseTool |
| MCP Proxy (stdio) | 否 | 拦截 MCP 通信，context-aware tool 过滤 |
| Tool Injector | 论文 §7.7 context window analysis 间接相关 | 语义检索 + token budget + diversity |
| HTTP Server (FastAPI) | 否 | REST API: /search, /plan, /inject |
| SDK Client | 否 | Python API，本地/远程模式 |
| Plan Executor | 否 | 异步执行 + 并行 group + callback |
| Hub (skill packs) | 否 | 本地 skill pack 发布/安装 |
| Rich CLI 可视化 | 否 | DAG 可视化 + execution trace |

### 匹配度结论

论文中描述的所有核心组件（Decomposer, Retriever, DAG Planner, SAD, Benchmark）在工具中都有完整实现。工具还额外提供了论文没有描述的产品化功能（MCP proxy, adapters, server, SDK, executor）。

**匹配度评分: 10/10** — 论文的每一个 claim 都能在代码中找到对应实现。

### 一个需要注意的差异

论文实验用的是 BGE-large-en-v1.5 (1024 维, 1.2GB)，但工具默认配置是 all-MiniLM-L6-v2 (384 维, 80MB)。这是有意为之（降低首次使用门槛），但需要在 README 中说明：

```
# 论文复现模式（需要 1.2GB 下载）
SKILLWEAVER_ENCODER=BAAI/bge-large-en-v1.5 skillweaver plan "..." --sad

# 默认模式（轻量，80MB）
skillweaver plan "..." --sad
```

---

## 第二部分：开源就绪度评估

### 2.1 产品设计

**评分: 7/10**

优点：
- 架构分层清晰（CLI → SDK → Pipeline → Core → Adapters → Store）
- 每层可独立使用
- 配置系统成熟（5 层配置 + 环境变量）
- 统一 Skill 模型是正确的抽象

问题：
- 功能太多（search/plan/proxy/serve/hub/benchmark），用户不知道从哪开始
- 首次使用需要 `init` + `index` + 下载模型，门槛偏高
- 没有内置 sample skills，用户需要自己准备 skill 目录

建议：
- README 的 Quick Start 只展示一个核心场景（`plan --sad`）
- 内置一个 10-20 个 skills 的 demo pack，`skillweaver init` 时自动安装
- 把 hub/benchmark/serve 标记为 experimental 或隐藏

### 2.2 产品形态

**评分: 8/10**

四种使用方式覆盖了不同场景：

| 方式 | 目标用户 | 场景 |
|------|---------|------|
| CLI | 开发者 | 日常搜索和编排 |
| Python SDK | 框架开发者 | 集成到 agent 框架 |
| HTTP Server | 微服务架构 | 团队共享 |
| MCP Proxy | Agent 用户 | 直接对接 Claude/Cursor |

这个覆盖面是合理的。MCP Proxy 是最有产品价值的形态——用户只需要一行配置就能让 agent 自动获得 skill routing 能力。

问题：
- 四种形态都暴露给用户会造成选择困难
- README 需要明确推荐 "如果你是 X 用户，用 Y 方式"

### 2.3 通用性

**评分: 8/10**

优点：
- 多格式适配（SKILL.md + MCP + OpenAI Functions + LangChain）覆盖了主流 agent 生态
- 多 LLM 后端（OpenAI API + transformers + Ollama + 规则）覆盖了不同部署场景
- HuggingFace 镜像自动切换，对中国用户友好
- 不依赖特定 agent 框架

问题：
- 没有 Anthropic API 后端（Claude 用户需要通过 OpenAI-compatible API 间接使用）
- 没有 vLLM/TGI 后端（高性能推理场景）

### 2.4 技术含量

**评分: 8/10**

核心技术栈：
- SAD two-pass feedback loop（论文核心贡献）
- BGE bi-encoder + FAISS 向量检索
- DAG 依赖检测（3 种信号）+ Kahn's 并行分组
- 四维兼容性评分（I/O type coercion + category Jaccard + tag Jaccard + keyword heuristic）
- MCP 协议拦截 + context-aware tool injection
- 异步 plan executor with parallel group support

这些不是简单的 API wrapper，有实质性的算法和工程设计。SAD 的 two-pass 逻辑、DAG planner 的依赖检测、compatibility scorer 的 type coercion matrix 都是有技术深度的实现。

### 2.5 是否能真实解决行业痛点

**评分: 7/10**

解决的痛点：

1. **Tool overload（最大痛点）**: MCP 生态 10K+ servers，agent 的 context window 装不下所有 tools。SkillWeaver 的 proxy/injector 通过语义检索 + token budget 把 tools 从几千个过滤到 2-5 个，99%+ token 降低。这是真实且紧迫的需求。

2. **复杂任务编排**: 用户说 "爬取数据、分析趋势、生成图表、发送通知"，需要 4 个 skills 协作。目前没有工具能自动做这个。SkillWeaver 的 `plan --sad` 是独一无二的。

3. **多格式割裂**: SKILL.md、MCP、OpenAI Functions 格式不统一。SkillWeaver 的 adapter 层提供了统一抽象。

未解决的痛点：

1. **执行能力有限**: `plan` 生成了 plan 但不能真正执行（executor 需要 callback）。用户拿到 plan 后还需要自己接入 agent 执行。
2. **Skill 质量评估**: 没有 skill 质量评分机制，用户不知道哪个 skill 更好。
3. **实时 skill 发现**: 没有从 GitHub/npm 实时搜索和安装 skills 的能力（hub 只有本地文件模式）。

### 2.6 开源就绪度总结

| 维度 | 评分 | 说明 |
|------|------|------|
| 代码完成度 | 9/10 | 核心功能全部实现，SAD 已补上 |
| 测试覆盖 | 7/10 | 14 个测试文件 + SAD 测试，但缺少端到端集成测试 |
| 文档 | 4/10 | README 只有基础内容，缺少详细使用文档、API 文档、贡献指南 |
| CI/CD | 2/10 | 没有 GitHub Actions，没有自动测试/发布 |
| 包发布 | 6/10 | pyproject.toml 完整，但没有实际发布到 PyPI |
| 示例 | 5/10 | 有 test-skills 目录（5 个 skills），但没有 examples/ 目录 |
| 论文匹配 | 10/10 | 所有论文组件都有对应实现 |

**综合开源就绪度: 6.5/10 — 代码就绪，但包装不够。**

---

## 第三部分：开源前必须做的事

### P0（必须做）

1. **README 重写**: 当前 README 太简单。需要：
   - 一句话定位
   - 30 秒 Quick Start（`pip install skillweaver && skillweaver plan "..." --sad`）
   - 核心功能 GIF/截图
   - 和论文的关系说明
   - 默认 encoder vs 论文 encoder 的差异说明

2. **端到端测试**: 确认 `pip install .` → `skillweaver init` → `skillweaver index test-skills/` → `skillweaver search "parse PDF"` → `skillweaver plan "..." --sad` 全链路能跑通

3. **内置 demo skills**: `skillweaver init` 时自动安装 test-skills/ 中的 5 个 skills，让用户零配置就能体验

### P1（强烈建议）

4. **GitHub Actions CI**: 至少跑 `pytest` + `ruff check`
5. **CONTRIBUTING.md**: 贡献指南
6. **LICENSE 文件**: 确认 Apache-2.0 license 文件存在
7. **隐藏未完成功能**: hub 的远程模式标记为 experimental

### P2（发布后做）

8. 发布到 PyPI
9. 详细 API 文档（可以用 mkdocs）
10. examples/ 目录（3-5 个使用场景）
11. Demo 视频/GIF
