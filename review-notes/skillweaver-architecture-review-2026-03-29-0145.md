# SkillWeaver 架构与产品设计评审

**文件名**: `review-notes/skillweaver-architecture-review-2026-03-29-0145.md`
**评审时间**: 2026-03-29 01:45
**代码规模**: 4,930 行源码 + 2,036 行测试（13 个测试文件）

---

## 一、工作原理

SkillWeaver 的核心是论文中 Decompose-Retrieve-Compose pipeline 的工程化。数据流如下：

```
用户输入自然语言任务描述
        │
        ▼
┌─────────────────────┐
│  1. Decomposer      │  LLM 把复杂任务拆成原子 sub-tasks
│  (4种后端可选)        │  OpenAI API / transformers / Ollama / 规则
└─────────┬───────────┘
          │ [t1, t2, t3, ...]
          ▼
┌─────────────────────┐
│  2. Retriever        │  BGE 编码 + FAISS 向量检索
│  (bi-encoder)        │  每个 sub-task 检索 top-k 候选 skills
└─────────┬───────────┘
          │ [[candidates], [candidates], ...]
          ▼
┌─────────────────────┐
│  3. Planner          │  两种模式：
│  (Sequential / DAG)  │  - Sequential: 贪心 + 兼容性评分
│                      │  - DAG: 依赖检测 + 并行分组 + Kahn's
└─────────┬───────────┘
          │ Plan (steps + edges + confidence)
          ▼
┌─────────────────────┐
│  4. Executor         │  异步执行 + 并行 group 支持
│  (可选)              │  通过 callback 调用实际工具
└─────────────────────┘
```

### 关键设计决策

1. **统一 Skill 模型**: 所有格式（SKILL.md, MCP, OpenAI Functions, LangChain）都转换成统一的 `Skill` dataclass，包含 name, description, body, categories, tags, io_schema。这是正确的抽象。

2. **四维兼容性评分**: I/O type compatibility (0.4) + category Jaccard (0.2) + tag Jaccard (0.2) + keyword heuristic (0.2)。有 type coercion matrix 处理类型转换（如 INTEGER → NUMBER）。

3. **MCP Proxy 模式**: 作为 stdio MCP server 运行，拦截 `tools/list` 请求，用 Injector 过滤后只返回相关 tools。这是最有产品价值的功能。

4. **五层配置**: defaults → user config → project config → env vars → CLI flags。支持 `SKILLWEAVER_*` 环境变量。

---

## 二、设计优点

### 2.1 架构分层清晰

```
CLI (main.py)
  ↓
SDK (client.py)          ← 用户也可以直接用 Python API
  ↓
Pipeline (pipeline.py)   ← 串联 decompose → retrieve → compose
  ↓
Core modules             ← decomposer / retriever / planner / compatibility / executor
  ↓
Adapters                 ← skill_md / mcp / openai_func / langchain
  ↓
Index Store              ← JSONL + FAISS 持久化
```

每一层都可以独立使用。用户可以只用 CLI，也可以用 SDK 编程，也可以跑 HTTP server。这个分层是对的。

### 2.2 Decomposer 的多后端设计

4 种后端（OpenAI API, transformers, Ollama, 规则）通过 `BaseDecomposer` 抽象类统一接口，`create_decomposer()` 工厂函数创建。默认用规则后端（零依赖），用户可以按需升级到 LLM 后端。这个渐进式设计很好。

### 2.3 MCP Injector 的 token budget 机制

不只是 top-k 过滤，还有：
- token budget 限制（默认 8000 tokens）
- diversity boost（单个 server 不超过 max_tools/3）
- mandatory tools（始终包含的工具）

这比简单的 top-k 更实用。

### 2.4 Executor 的 callback 设计

Executor 不直接调用工具，而是通过 `AsyncToolCallback` 回调。这意味着同一个 executor 可以对接 MCP、直接 API 调用、mock 测试等不同后端。设计上是解耦的。

### 2.5 HuggingFace 镜像自动切换

Retriever 会检测 huggingface.co 是否可达，不可达时自动切换到 hf-mirror.com。对中国用户很友好。

### 2.6 配置系统成熟

五层配置 + 环境变量 + 类型自动转换 + 缓存。这是生产级的配置管理。

---

## 三、设计问题

### 问题 1（严重）：默认 encoder 不是论文中的 BGE

```python
# settings.py
"encoder": "sentence-transformers/all-MiniLM-L6-v2",
```

论文用的是 BGE-large-en-v1.5（1024 维），但工具默认用 MiniLM-L6-v2（384 维）。这意味着用户开箱即用的效果和论文报告的效果会有差距。

这个决策本身是合理的（MiniLM 只有 80MB vs BGE 1.2GB，降低首次使用门槛），但需要在文档中明确说明，并提供一键切换到 BGE 的方式：

```bash
skillweaver init --encoder bge-large  # 或者
SKILLWEAVER_ENCODER=BAAI/bge-large-en-v1.5 skillweaver search "..."
```

### 问题 2（严重）：SAD 没有在工具中实现

论文的核心贡献 Skill-Aware Decomposition（两次分解 + hints 反馈）在 SkillWeaver 代码中完全没有实现。`decomposer.py` 只有 vanilla decomposition，没有 SAD 的 two-pass 逻辑。

这是一个很大的遗漏。论文说 SAD 把 CatR@1 从 33.9% 提升到 54.2%，但用户用工具时只能得到 33.9% 的效果。

建议：在 `pipeline.py` 的 `plan()` 方法中加一个 `use_sad=True` 选项，实现 two-pass 逻辑：
1. 第一次 decompose → retrieve
2. 从 candidates 中提取 top-H skill names 作为 hints
3. 第二次 decompose（带 hints）→ retrieve → plan

### 问题 3（中等）：DAG 依赖检测全靠启发式

依赖检测用了三种信号（I/O type overlap, producer-consumer keywords, linguistic markers），但全是硬编码的关键词匹配。没有语义理解能力。

例如 "fetch data" → "analyze data" 能检测到（producer-consumer），但 "collect information" → "summarize findings" 可能检测不到（关键词不在列表中）。

这在 v0.1.0 是可以接受的，但需要在 README 中说明 DAG 检测是启发式的，复杂依赖可能需要用户手动调整。

### 问题 4（中等）：Planner 和 DAGPlanner 代码重复

`planner.py`（Sequential）和 `dag_planner.py`（DAG）有大量重复逻辑（skill selection 部分几乎一样）。DAGPlanner 应该继承 Planner 或者合并成一个类。

### 问题 5（中等）：Hub 没有实际的远程后端

`hub/client.py` 有完整的 SkillPack 格式定义和本地文件 hub，但远程 hub（`hub.skillweaver.dev`）不存在。CLI 的 `hub list` 和 `hub install` 在没有远程后端时只能操作本地文件。

对于 v0.1.0 这是可以接受的，但 CLI 不应该暴露 `hub` 命令给用户，避免困惑。

### 问题 6（低）：Executor 的 `execute_sync` 有问题

```python
def execute_sync(self, plan: Plan) -> ExecutionTrace:
    return asyncio.get_event_loop().run_until_complete(self.execute(plan))
```

在 Python 3.10+ 中，如果已经有 event loop 在运行（比如在 Jupyter 或 FastAPI 中），`get_event_loop().run_until_complete()` 会报错。应该用 `asyncio.run()` 或者 `nest_asyncio`。

### 问题 7（低）：SDK Client 的 remote mode 没有认证

`_remote_search` / `_remote_plan` 直接发 HTTP 请求，没有 API key 或 token 认证。如果 server 暴露在公网上，任何人都能调用。

---

## 四、产品形态评估

### 4.1 三种使用方式

| 方式 | 目标用户 | 完成度 |
|------|---------|--------|
| CLI (`skillweaver search/plan/index`) | 开发者日常使用 | 95% |
| Python SDK (`SkillWeaverClient`) | 集成到 agent 框架 | 100% |
| HTTP Server (`skillweaver serve`) | 微服务部署 | 100% |
| MCP Proxy (`skillweaver proxy`) | 直接对接 agent | 100% |

四种使用方式覆盖了不同场景，这个设计是合理的。

### 4.2 用户旅程分析

**场景 1：开发者想搜索 skill**
```bash
pip install skillweaver
skillweaver index ./my-skills/    # 需要有 skills 目录
skillweaver search "parse PDF"
```
问题：用户需要先有一个 skills 目录。如果没有，体验就断了。
建议：`skillweaver init` 时自动下载一个 sample skill pack（比如 10 个常用 skills）。

**场景 2：开发者想编排复杂任务**
```bash
skillweaver plan "fetch data, analyze it, generate report"
```
问题：默认用规则 decomposer（按 "and", "then", 逗号分割），效果很差。用户需要配置 LLM 后端才能得到好的分解结果。
建议：`plan` 命令在检测到规则 decomposer 效果差时，提示用户 "For better results, configure an LLM backend: skillweaver init --backend ollama"。

**场景 3：Agent 开发者想过滤 MCP tools**
```bash
skillweaver proxy --upstream ./mcp-config.json
```
这是最顺畅的场景。一行命令启动代理，agent 连接后自动获得过滤后的 tools。

### 4.3 和竞品的差异化

| 功能 | SkillWeaver | Cloud MCP Router | ATR | MCP-Zero |
|------|-------------|-----------------|-----|----------|
| 单 query → 单 tool 路由 | ✅ | ✅ | ✅ | ✅ |
| 复杂任务 → 多 tool 编排 | ✅ 独有 | ❌ | ❌ | ❌ |
| DAG 并行检测 | ✅ 独有 | ❌ | ❌ | ❌ |
| 多格式适配 | ✅ 4种 | MCP only | MCP only | MCP only |
| 兼容性评分 | ✅ 4维 | ❌ | ❌ | ❌ |
| 本地 CLI | ✅ | ❌ | ❌ | ❌ |
| Python SDK | ✅ | ❌ | ✅ | ❌ |
| 执行能力 | ✅ (callback) | ❌ | ❌ | ❌ |

SkillWeaver 的差异化很明确：compositional routing + multi-format + execution。

---

## 五、总体评价

### 做得好的
- 架构分层清晰，每层可独立使用
- 统一 Skill 模型是正确的抽象
- 四种使用方式覆盖不同场景
- 配置系统成熟
- 代码质量不错（docstring, 类型注解, 错误处理）
- 测试覆盖率可接受（41%）

### 需要改进的
- SAD 没有实现（论文核心贡献缺失）
- 默认 encoder 和论文不一致
- 首次使用体验需要优化（需要 skills 目录）
- Hub 远程后端不存在但 CLI 暴露了命令
- Planner 代码重复

### 发布前必须做的
1. 实现 SAD（这是论文的核心卖点，工具里没有说不过去）
2. README 写清楚默认 encoder 和论文的差异
3. 隐藏或标记 hub 命令为 experimental
4. 端到端测试 `pip install skillweaver` → `skillweaver init` → `skillweaver index` → `skillweaver search` → `skillweaver plan`

### 发布后优先做的
1. 内置 sample skill pack（降低首次使用门槛）
2. 合并 Planner 和 DAGPlanner
3. 修复 `execute_sync` 的 event loop 问题
4. 加 API 认证
5. CI/CD + PyPI 自动发布
