# SkillWeaver 开源工具产品评审

**文件名**: `review-notes/skillweaver-product-review-2026-03-29-0023.md`
**评审时间**: 2026-03-29 00:23
**评审范围**: 产品形态、竞品分析、设计理念、用户体验、爆火潜力

---

## 一、竞品格局（2026年3月）

你进入的赛道已经非常拥挤了。"MCP tool overload" 是 2025-2026 年 agent 生态的核心痛点，大量产品和论文都在解决这个问题。按类型分：

### 1.1 Tool Discovery / Routing 层（直接竞品）

| 产品 | 方式 | 特点 | 状态 |
|------|------|------|------|
| **Cloud MCP Router** | MCP 代理层 | Progressive discovery，按需加载 tool，不改现有 MCP server | 已上线，有文档 |
| **Adaptive Tool Routing (ATR)** by yess.ai | 开源库 | 每次 query 前过滤 tools，减少 system prompt 中的 tool 数量 | 已开源 (adaptive-tools) |
| **MCP-Zero** (论文) | Agent 主动发现 | LLM 自己决定何时需要什么 tool，按需请求，98% token 降低 | 学术论文，有代码 |
| **Apigene MCP Gateway** | 商业网关 | Progressive disclosure pattern，按需加载，98% token 降低 | 商业产品 |
| **Claude Code MCP Tool Search** | 内置功能 | Lazy loading，轻量搜索索引 + 按需获取 tool 详情 | Anthropic 官方，已内置 |
| **mcp2cli** | CLI 工具 | 把 MCP tool 转成 CLI 命令，按需发现，96-99% token 降低 | 开源 |
| **MCP Codemode** by Datalayer | 发现层 | Progressive tool discovery，文件系统式层级浏览 | 开源 |

### 1.2 Skill 市场 / 加载器（部分竞品）

| 产品 | 方式 | 特点 |
|------|------|------|
| **OpenClaw Skills / ClawHub** | 技能市场 | `openclaw skills install`，60+ skills，免费+付费 |
| **OpenSkills** | npm 包 | 通用 skills loader，支持多 agent（Claude Code, Cursor, Windsurf 等） |
| **OpenAI Codex Skills Catalog** | 官方仓库 | 5100+ stars，35+ 可复用 workflow，Codex 按需发现 |
| **VS Code Agent Skills** | 官方标准 | GitHub Copilot 原生支持，开放标准 |

### 1.3 关键观察

**"Progressive Tool Discovery" 已经成为行业共识**。Anthropic 官方博客、Cloud MCP Router、Apigene、MCP-Zero 论文都在推这个模式。核心思路一样：不要一次性把所有 tool 塞进 context，而是按需加载。

**你的 SkillWeaver 和这些产品的重叠度很高**，特别是：
- MCP proxy / inject 功能 ≈ Cloud MCP Router ≈ ATR ≈ Apigene Gateway
- search 功能 ≈ Claude Code MCP Tool Search
- hub 功能 ≈ OpenClaw / ClawHub

---

## 二、SkillWeaver 当前产品形态评估

### 2.1 优势（你有而别人没有的）

1. **Compositional routing（任务分解 + 多 skill 编排）**：这是你的核心差异化。竞品都在做 single-query → single-tool 的路由，没有人在做 "一句话描述复杂任务 → 自动分解 → 多 skill 编排成 DAG" 这件事。`skillweaver plan` 是独一无二的。

2. **学术论文背书**：有 EMNLP 论文支撑，这在开源社区是加分项。

3. **多格式适配**：SKILL.md + MCP + OpenAI Functions + LangChain 四种格式的统一适配层，比大多数竞品更通用。

4. **完整的技术栈**：CLI + HTTP API + MCP Proxy，三种使用方式覆盖不同场景。

### 2.2 问题（可能阻碍爆火的因素）

#### 问题 1：定位模糊 — 什么都想做，但没有一个杀手级场景

当前 SkillWeaver 同时是：
- 技能搜索引擎（search）
- 任务编排器（plan）
- MCP 代理网关（proxy）
- 技能市场（hub）
- HTTP API 服务（serve）

这对于一个 v0.1.0 来说太多了。用户打开 README 会困惑："这到底是什么？我为什么需要它？"

**对比爆火的开源项目**：
- `uv` 只做一件事：快速 Python 包管理
- `ruff` 只做一件事：快速 Python linter
- `ollama` 只做一件事：本地跑 LLM

**建议**：砍到只剩一个核心卖点。你最独特的是 `plan`（compositional routing），但最有市场需求的是 `proxy`（MCP tool overload 解决方案）。需要选一个。

#### 问题 2：`plan` 功能虽然独特，但用户场景不清晰

`skillweaver plan "爬取 GitHub trending，分析趋势，生成图表，发送 Slack"` 看起来很酷，但用户拿到这个 plan 之后呢？

- 没有执行能力（`skillweaver run` 是 "未来功能"）
- 生成的 plan 是 YAML 文件，但没有和任何 agent 框架集成
- 用户需要手动把 plan 喂给 agent 执行

这意味着 `plan` 目前是一个 demo 功能，不是一个解决实际问题的功能。用户会觉得 "cool but useless"。

#### 问题 3：`proxy` 功能是最有价值的，但竞品已经很多

MCP proxy / gateway 赛道已经有 Cloud MCP Router、ATR、Apigene 等。你的 proxy 实现（injector.py）做了语义检索 + token budget + diversity boost，技术上是 solid 的，但差异化不够。

#### 问题 4：首次使用体验太重

```bash
skillweaver init  # 需要选 LLM 后端
                  # 需要下载 1.2GB 的 BGE 模型
skillweaver index ./my-skills/  # 需要有 skills 目录
skillweaver search "..."  # 才能开始用
```

对比 Cloud MCP Router：配置一个 JSON，立刻可用。
对比 ATR：`pip install adaptive-tools`，一行代码集成。

你的工具需要下载 1.2GB 模型、有本地 skill 目录、选择 LLM 后端，门槛太高了。

#### 问题 5：缺少和主流 agent 框架的集成

当前没有和 Claude Code、Cursor、Windsurf、LangChain、CrewAI 等主流框架的原生集成。用户需要自己把 SkillWeaver 的输出接入 agent，这是一个很大的摩擦点。

---

## 三、爆火潜力评估

**当前形态爆火概率：15-20%**

原因：
- 定位模糊，用户不知道为什么需要它
- 首次使用门槛高（下载模型、准备 skill 目录）
- `plan` 功能没有执行能力，是 demo 而非产品
- MCP proxy 赛道已经拥挤
- 没有和主流 agent 框架集成

---

## 四、如何提升爆火概率 — 两条路线

### 路线 A：聚焦 MCP Smart Proxy（实用主义路线）

**核心定位**：SkillWeaver 是一个智能 MCP 代理，自动为每次 agent 调用选择最相关的 tools，解决 tool overload 问题。

**差异化**：不只是 single-query routing，而是 compositional routing — 理解复杂任务需要哪些 tools 的组合。

**产品形态**：
```json
// mcp.json — 用户唯一需要做的事
{
  "mcpServers": {
    "skillweaver": {
      "command": "uvx",
      "args": ["skillweaver-proxy", "--upstream", "path/to/mcp-config.json"]
    }
  }
}
```

**用户体验**：
1. `pip install skillweaver` 或 `uvx skillweaver-proxy`
2. 在 mcp.json 里加一行配置
3. 完成。SkillWeaver 自动拦截所有 MCP 请求，只暴露相关 tools

**不需要**：下载 BGE 模型（用轻量级 BM25 或 MiniLM），不需要 init，不需要 index。

**爆火概率**：40-50%

### 路线 B：聚焦 AI Workflow Composer（差异化路线）

**核心定位**：SkillWeaver 是第一个能用自然语言描述任务、自动编排多个 AI skill 的工具。

**差异化**：没有竞品做 compositional routing 的产品化。

**产品形态**：
```bash
# 一行命令，从描述到可执行 workflow
$ skillweaver "爬取网站，分析数据，生成图表，发送 Slack"

📋 Workflow: github-trending-analysis
  1. [web-scraper] 爬取数据        ─┐
  2. [data-analyzer] 分析趋势       ├─ sequential
  3. [chart-gen] 生成图表           ─┘
  4. [slack-notifier] 发送通知

Execute now? [Y/n]
```

**关键**：必须有执行能力。生成 plan 但不能执行 = demo。

**实现方式**：
- 对于 MCP tools：直接调用 MCP server 执行
- 对于 SKILL.md：生成 agent prompt + tool definitions，调用 LLM 执行
- 对于 OpenAI Functions：直接调用 API

**爆火概率**：30-40%（更高风险但更高回报）

---

## 五、具体建议

### 不管选哪条路线，都需要做的事：

1. **砍功能**：v0.1.0 只保留一个核心功能。hub、serve、benchmark 全部砍掉或隐藏。

2. **零配置启动**：
   - 默认用 `all-MiniLM-L6-v2`（80MB）而不是 BGE-large（1.2GB）
   - 或者用 BM25 做 fallback（零下载）
   - `skillweaver init` 应该是可选的，不是必须的

3. **一行安装，一行使用**：
   ```bash
   pip install skillweaver
   skillweaver plan "your task description"  # 自动下载轻量模型，自动发现本地 skills
   ```

4. **和主流 agent 集成**：
   - Claude Code：作为 MCP server 暴露 `plan` 和 `search` 工具
   - Cursor / Windsurf：同上
   - LangChain / CrewAI：提供 Python SDK

5. **README 要讲故事**：
   - 不要列功能清单
   - 用一个 30 秒 GIF 展示核心场景
   - 第一句话就要让人知道 "这解决了什么问题"

6. **名字可能需要改**：
   - "SkillWeaver" 搜索结果会和游戏、手工艺混在一起
   - 考虑更 developer-friendly 的名字，比如 `skillroute`、`toolmux`、`mcpx`

### 如果选路线 A（MCP Smart Proxy）：

7. 把 SkillWeaver 本身做成一个 MCP server，这样任何支持 MCP 的 agent 都能直接用
8. 支持 `.well-known/mcp.json` 自动发现（这是 2026 年的新标准）
9. 加 observability：每次路由决策的日志、token 节省统计
10. 对标 Cloud MCP Router，但强调 "compositional awareness"

### 如果选路线 B（Workflow Composer）：

7. 必须实现 `skillweaver run`（执行能力）
8. 支持 dry-run 模式（只生成 plan 不执行）
9. 支持 plan 导出为 LangGraph / CrewAI workflow
10. 录一个 demo 视频：从自然语言到执行完成的全流程

---

## 六、我的推荐

**选路线 A（MCP Smart Proxy）作为 v0.1.0 的核心**，原因：

1. MCP 生态正在爆发（97M monthly SDK downloads，10K+ public servers），市场需求确定
2. 实现难度低，你的 injector.py 已经基本完成
3. 用户获取成本低（一行配置）
4. 可以快速验证市场反应
5. `plan` 功能作为 v0.2.0 的差异化升级

**但要在 proxy 中嵌入 compositional awareness 作为差异化**：当 agent 的 query 是复杂任务时，不只是返回 top-k 相关 tools，而是返回一个 "recommended tool chain"。这是你论文的核心贡献，也是竞品没有的。

**时间线建议**：
```
4月上旬    砍功能，重构为 MCP-first 架构
4月中旬    零配置启动 + 一行安装
4月下旬    和 Claude Code / Cursor 集成测试
5月上旬    README + demo GIF + 文档
5月中旬    发布 v0.1.0，投 HN / Reddit
5月下旬    收集反馈，同时提交 EMNLP 论文
```

---

## 七、总结

SkillWeaver 的技术基础很扎实（论文验证 + 完整实现），但产品形态需要大幅聚焦。当前 "什么都做" 的状态会导致用户困惑和获取成本过高。建议砍到只做 MCP Smart Proxy，用 compositional routing 作为差异化，零配置启动，一行安装。这样爆火概率能从 15-20% 提升到 40-50%。
