# CoPaw 语义技能路由 — 操作指南

> 本文件夹包含向 CoPaw 贡献"语义 Skill 路由"功能的全部规划文档。
> 技术背书：SkillWeaver (EMNLP 2026) — Compositional Skill Routing for LLM Agents

## 分工说明

| 角色 | 负责内容 |
|------|---------|
| Kiro（AI） | 在 `copaw-upstream/` 目录中编写全部代码和测试 |
| 人工操作 | GitHub 操作：Fork、建分支、push 代码、提 PR、开 Issue |

Kiro 会把代码写在已 clone 的 `copaw-upstream/` 目录下。人工只需要做下面的前置操作，然后等 Kiro 写完代码后做后置操作。

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `README.md` | 本文件，操作指南 |
| `requirements.md` | 需求文档（3 个 Phase + 跨 Phase 需求） |
| `design.md` | 技术设计文档（架构图、接口、数据模型、11 个正确性属性） |
| `tasks.md` | PR1 实现任务列表（7 个顶层任务） |

---

## 人工前置操作（Kiro 写代码之前做）

### Step 1: Fork CoPaw

1. 浏览器打开 https://github.com/agentscope-ai/CoPaw
2. 点击右上角 **Fork** 按钮
3. Fork 到 `hellogxp` 账号下，得到 `hellogxp/CoPaw`

### Step 2: 在 CoPaw 开 Issue（推荐但非必须）

在 https://github.com/agentscope-ai/CoPaw/issues 新建 Issue：

- 标题：`feat: Semantic skill routing for large skill pools`
- 内容直接复制下方模板：

```markdown
## Problem

When users install 50+ skills and connect multiple MCP servers, CoPaw injects
all skill metadata into the LLM context. This causes:
- Context overflow with large skill pools
- Poor skill selection accuracy due to information overload
- Unnecessary token consumption

As the skill ecosystem grows (Skills Hub, community skills, MCP servers),
this problem will become increasingly severe.

## Proposed Solution

Add an optional semantic routing layer that uses embedding-based retrieval
(sentence-transformers + FAISS) to filter skills before injecting them into
the agent context. Only the top-k most relevant skills are registered per query.

Key design principles:
- **Zero-invasive**: Disabled by default, optional dependency (`copaw[semantic]`)
- **Fail-open**: Falls back to existing behavior on any error
- **No interface changes**: All existing public APIs remain unchanged

### Background

I'm 燕衡 from Alibaba Private Cloud. We've been working on compositional skill
routing for LLM agents and have a paper in preparation on this topic.
Key findings from our experiments:

- Embedding-based skill retrieval reduces context consumption by 99%+
  while maintaining selection accuracy
- A lightweight encoder (all-MiniLM-L6-v2, ~80MB) is sufficient for
  skill-level routing — no GPU required
- Metadata-only retrieval (name + description) matches full-body retrieval

This PR adapts the core algorithms natively into CoPaw's codebase
(no external dependency). Happy to share more details about the research
privately if helpful.

## Scope

I plan to contribute this in 3 focused PRs:
- **PR1**: Semantic skill filtering (this issue) — smallest change, highest value
- **PR2**: MCP tool filtering — reuses PR1 infrastructure
- **PR3**: Multi-skill composition — task decomposition + DAG planning

## Implementation Plan

- New module: `src/copaw/routing/`
- Config: `semantic_routing` section in config.json (disabled by default)
- Optional deps: `sentence-transformers`, `faiss-cpu` (declared as extras)
- Integration point: `CoPawAgent._register_skills()`
- Full test coverage with auto-skip when optional deps not installed

Happy to discuss the approach before submitting code. Looking forward to
contributing to CoPaw!
```

### Step 3: 完成后通知 Kiro

告诉 Kiro：
- Fork 完成了
- Issue 编号是多少（如果开了的话）

然后 Kiro 开始在 `copaw-upstream/` 里写代码。

---

## 人工后置操作（Kiro 写完代码之后做）

Kiro 会在 `copaw-upstream/` 里完成所有代码编写和本地测试。之后人工执行：

### Step 4: 配置 git 身份并 commit

```bash
cd copaw-upstream

# 配置提交人信息（替换为实际姓名和邮箱）
git config user.name "燕衡"
git config user.email "你的邮箱"

# Kiro 已经在 feat/semantic-skill-routing 分支上写好了代码
# 确认当前分支
git branch
# 应该显示 * feat/semantic-skill-routing

# 查看改动的文件
git status

# 添加所有新增和修改的文件
git add src/copaw/routing/ src/copaw/config/config.py src/copaw/agents/react_agent.py

# 提交
git commit -m "feat(routing): add semantic skill routing module

Add optional embedding-based skill filtering that reduces context
consumption for large skill pools. Disabled by default.

- New src/copaw/routing/ module (SemanticIndex, SkillRouter, config, models)
- semantic_routing config section in Config root model
- Integration in CoPawAgent._register_skills()
- Zero-invasive: falls back to original behavior when deps missing

Closes #3091"
```

### Step 5: 设置 remote 并 push

```bash
# 把 origin 指向你的 fork
git remote set-url origin https://github.com/hellogxp/CoPaw.git

# 确认
git remote -v

# Push 到你的 fork
git push origin feat/semantic-skill-routing
```

### Step 6: 提 PR

在 GitHub 上从 `hellogxp/CoPaw` 的 `feat/semantic-skill-routing` 分支向 `agentscope-ai/CoPaw` 的 `main` 分支提 PR。

- PR 标题：`feat(routing): add semantic skill filtering for large skill pools`
- PR 内容直接复制下方模板：

```markdown
## Summary

Adds optional semantic skill routing that uses embedding-based retrieval
to filter skills before injecting them into the agent context. When users
have 50+ skills installed, only the top-k most relevant skills are
registered per query, reducing context consumption by 90%+.

Closes #<issue_number>

## Changes

- New `src/copaw/routing/` module:
  - `SemanticIndex`: FAISS-based embedding index with persistence
  - `SkillRouter`: Semantic skill retrieval with bypass for small pools
  - `SemanticRoutingConfig`: Pydantic config model
- `semantic_routing` config section in config.json (disabled by default)
- Optional deps: `sentence-transformers`, `faiss-cpu` (extras `[semantic]`)
- Integration in `CoPawAgent._register_skills()`
- Property tests + unit tests in `tests/test_routing/`

## Design Principles

- **Zero-invasive**: Disabled by default, no behavior change without opt-in
- **Fail-open**: Falls back to existing behavior on any error
- **No interface changes**: All existing public APIs unchanged
- **Optional deps**: `sentence-transformers` and `faiss-cpu` not in core install

Based on research from "Compositional Skill Routing for LLM Agents"
(EMNLP 2026).

## Testing

- All existing tests pass (no regressions)
- New tests in `tests/test_routing/` (auto-skip when optional deps missing)
- `pre-commit run --all-files` passes
```

---

## 后续 PR 规划

| PR | 功能 | 分支名 | 前置条件 |
|----|------|--------|---------|
| PR1 | 语义 Skill 过滤 | `feat/semantic-skill-routing` | 无 |
| PR2 | MCP 工具过滤 | `feat/mcp-tool-filtering` | PR1 合并 |
| PR3 | 组合编排 | `feat/skill-composition` | PR1+PR2 合并 |
