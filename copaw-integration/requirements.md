# 需求文档：CoPaw 语义技能路由与组合编排

## 简介

本功能在 CoPaw（agentscope-ai/CoPaw）中原生开发语义技能路由和组合编排能力。核心算法（embedding + FAISS 检索、token budget 过滤、任务分解）借鉴 SkillWeaver（EMNLP 2026）的方法论，但代码完全写在 CoPaw 的 `src/copaw/` 目录下，遵循 CoPaw 架构规范，不引入 SkillWeaver 作为外部依赖。

目标是解决 CoPaw 在 skill 数量增长和 MCP server 增多时面临的三大痛点：
1. skill 发现效率低（全量 metadata 注入导致 context 膨胀）
2. MCP 工具过多时 agent 选择困难
3. 复杂任务缺乏多 skill 协作编排

功能按 3 个独立 PR 交付，每个 PR 独立可用，遵循 CoPaw 贡献指南的 "small, focused changes" 原则。所有功能默认关闭，通过配置开关启用，未安装可选依赖时 CoPaw 完全保持原有行为。

## 术语表

- **CoPaw**: Co Personal Agent Workstation，阿里 AgentScope 团队开发的开源个人 AI 助手，基于 FastAPI 单体服务架构
- **Skill_Pool**: CoPaw 的技能池，包含 builtin、customized、active 三层架构，skill 以 SKILL.md 格式描述
- **SKILL.md**: CoPaw 的技能描述格式，包含 YAML frontmatter（name、description、parameters 等）和 markdown body
- **Skill_Router**: 本功能新增的 CoPaw 原生模块，负责语义技能检索和 MCP 工具过滤，代码位于 `src/copaw/` 下
- **Skill_Composer**: 本功能新增的 CoPaw 原生模块，负责多技能组合编排（任务分解 + DAG 编排），代码位于 `src/copaw/` 下
- **FAISS_Index**: Facebook AI Similarity Search 索引，用于高效向量近邻搜索，通过 faiss-cpu 可选依赖提供
- **Token_Budget**: 工具描述在 agent context window 中允许占用的最大 token 数，CoPaw 使用 Qwen2.5-7B tokenizer 计算
- **MCP**: Model Context Protocol，AI 工具通信协议，CoPaw 已支持 stdio/http/sse 三种传输方式
- **MCPConfigWatcher**: CoPaw 现有的 MCP 配置监视器，2 秒轮询检测 MCP server 变更并热重载
- **ConfigWatcher**: CoPaw 现有的配置监视器，2 秒轮询 `~/.copaw/config.json` 检测配置变更
- **Friday**: CoPaw 的单 agent，基于 AgentScope 的 ReAct loop 运行
- **SAD**: Skill-Aware Decomposition，SkillWeaver 论文提出的检索增强分解反馈循环，用于提升任务分解质量

---

## Phase 1（PR1）：语义 Skill 过滤

> 最核心痛点，改动最小。Skill loading 时用 embedding 过滤，只注入相关 skill。

### 需求 1.1：Skill Embedding 索引构建

**用户故事：** 作为 CoPaw 用户，我希望系统能对所有已注册的 skills 建立语义索引，为后续的语义检索提供基础。

#### 验收标准

1. WHEN CoPaw 启动且 `semantic_routing.enabled` 配置为 true, THE Skill_Router SHALL 扫描 Skill_Pool 中所有已注册的 SKILL.md 文件，提取 name 和 description 字段，使用 sentence-transformers 编码为向量并构建 FAISS_Index
2. THE Skill_Router SHALL 支持通过 `~/.copaw/config.json` 中的 `semantic_routing.encoder` 字段配置 embedding 模型名称，默认值为 `all-MiniLM-L6-v2`
3. WHEN Skill_Pool 中的 skills 发生变更（新增、删除、修改 SKILL.md）, THE Skill_Router SHALL 在下一次查询前自动重建 FAISS_Index
4. IF embedding 模型加载失败（如模型文件不存在或下载超时）, THEN THE Skill_Router SHALL 记录 WARNING 级别日志并回退到 CoPaw 原有的全量 skill metadata 注入方式

### 需求 1.2：语义 Skill 检索

**用户故事：** 作为 CoPaw 用户，我希望系统根据我的查询语义自动找到最匹配的 skills，而不是把所有 skill 描述都塞进 LLM context。

#### 验收标准

1. WHEN 用户发送一条消息且 Skill_Router 已启用, THE Skill_Router SHALL 将用户消息编码为向量，从 FAISS_Index 中检索 top_k 个最相关的 skills，并将检索结果传递给 Friday agent 进行 skill 选择
2. THE Skill_Router SHALL 支持通过 `semantic_routing.top_k` 配置项设置检索数量，默认值为 10
3. THE Skill_Router SHALL 返回每个匹配 skill 的名称、描述和相似度分数，分数范围为 0.0 到 1.0
4. WHEN Skill_Pool 中注册的 skill 数量小于或等于 top_k, THE Skill_Router SHALL 返回全部 skills 而不执行向量检索

### 需求 1.3：FAISS 索引持久化

**用户故事：** 作为 CoPaw 用户，我希望语义索引能持久化到磁盘，避免每次启动都重新编码所有 skills。

#### 验收标准

1. WHEN Skill_Router 首次构建 FAISS_Index, THE Skill_Router SHALL 将索引文件和 skill 元数据持久化到 `~/.copaw/semantic_index/` 目录
2. WHEN CoPaw 重新启动且持久化索引存在且与当前 Skill_Pool 一致, THE Skill_Router SHALL 从磁盘加载索引而非重新构建
3. WHEN Skill_Pool 内容与持久化索引不一致（通过 skill 文件的修改时间戳或哈希值检测）, THE Skill_Router SHALL 自动触发全量重建并更新持久化文件
4. IF 持久化索引文件损坏或格式不兼容, THEN THE Skill_Router SHALL 删除旧索引文件并触发全量重建

### 需求 1.4：零侵入安装与回退

**用户故事：** 作为 CoPaw 用户，我希望语义路由功能是完全可选的，不安装额外依赖时 CoPaw 的行为与之前完全一致。

#### 验收标准

1. THE Skill_Router SHALL 将 sentence-transformers 和 faiss-cpu 声明为 CoPaw 的可选依赖（optional extras），不添加到核心安装依赖中
2. WHEN CoPaw 启动且 sentence-transformers 或 faiss-cpu 未安装, THE CoPaw SHALL 使用原有的 skill 选择逻辑，不产生任何 import 错误或功能异常
3. WHEN `semantic_routing.enabled` 配置为 true 但所需可选依赖未安装, THE Skill_Router SHALL 记录一条 WARNING 级别日志（包含 `pip install copaw[semantic]` 安装提示）并自动回退到原有逻辑
4. THE Skill_Router SHALL 不改动 CoPaw 现有的任何公开接口签名或函数参数

### 需求 1.5：检索结果序列化

**用户故事：** 作为 CoPaw 开发者，我希望语义检索结果能序列化为 JSON 格式，便于日志记录和调试。

#### 验收标准

1. THE Skill_Router SHALL 提供将检索结果（skill 名称、描述、相似度分数）序列化为 JSON 字符串的方法
2. THE Skill_Router SHALL 提供从 JSON 字符串反序列化为检索结果对象的方法
3. FOR ALL 有效的检索结果对象, 序列化后再反序列化 SHALL 产生与原始对象等价的结果（round-trip 属性）
4. WHEN 序列化输入包含非 ASCII 字符（如中文 skill 名称）, THE 序列化方法 SHALL 使用 `ensure_ascii=False` 正确保留原始字符


---

## Phase 2（PR2）：MCP 工具过滤

> 复用 PR1 的检索基础设施，对 MCP server 暴露的工具按查询语义过滤。

### 需求 2.1：MCP 工具索引集成

**用户故事：** 作为连接了多个 MCP server 的 CoPaw 用户，我希望系统能将 MCP 工具也纳入语义索引，与 skills 统一管理。

#### 验收标准

1. WHEN CoPaw 连接到一个或多个 MCP server 且 Skill_Router 已启用, THE Skill_Router SHALL 将所有 MCP server 暴露的工具定义（tool name + description）编码为向量并纳入 FAISS_Index
2. THE Skill_Router SHALL 在 FAISS_Index 中区分 Skill_Pool 来源的 skill 和 MCP server 来源的工具，通过 source 字段标识（值为 `skill_pool` 或 `mcp:{server_name}`）
3. WHEN MCPConfigWatcher 检测到 MCP server 变更（新增、移除、工具列表变化）, THE Skill_Router SHALL 在下一次查询前更新 FAISS_Index 中的 MCP 工具条目

### 需求 2.2：MCP 工具语义过滤

**用户故事：** 作为 CoPaw 用户，我希望系统只把与当前任务相关的 MCP 工具暴露给 agent，避免大量工具描述占满 context window。

#### 验收标准

1. WHEN 用户发送一条消息且 Skill_Router 已启用, THE Skill_Router SHALL 根据查询语义从全部 MCP 工具中筛选出不超过 `semantic_routing.max_tools` 个最相关的工具，默认 max_tools 为 20
2. THE Skill_Router SHALL 在过滤时使用 Token_Budget 限制（默认 8000 tokens，通过 `semantic_routing.token_budget` 配置），确保选中工具的描述总 token 数不超过预算
3. THE Skill_Router SHALL 在过滤时保证跨 MCP server 的多样性：单个 MCP server 的工具数量不超过 max_tools 的三分之一（向上取整，最小为 3）
4. THE Skill_Router SHALL 支持通过 `semantic_routing.mandatory_tools` 配置项指定始终包含的工具名称列表，mandatory_tools 中的工具在每次查询时优先包含且不受 top_k 限制

### 需求 2.3：MCP 工具过滤回退

**用户故事：** 作为 CoPaw 用户，我希望 MCP 工具过滤功能关闭或不可用时，系统保持原有行为。

#### 验收标准

1. IF Skill_Router 功能未启用或可选依赖未安装, THEN THE CoPaw SHALL 保持现有行为，将所有 MCP 工具暴露给 Friday agent
2. IF 某个 MCP server 的工具定义缺少 description 字段, THEN THE Skill_Router SHALL 使用工具名称作为 fallback 文本进行编码，并在日志中记录 INFO 级别提示
3. THE Skill_Router SHALL 不修改 CoPaw 现有的 MCP 客户端接口（MCPConfigWatcher、MCP 连接管理），仅在工具列表传递给 Friday agent 之前进行过滤

---

## Phase 3（PR3）：组合编排

> 最复杂的功能，需要 PR1 和 PR2 建立社区信任后再提交。复杂任务自动分解为多 skill 协作。

### 需求 3.1：任务分解

**用户故事：** 作为 CoPaw 用户，我希望对于需要多个 skills 协作的复杂任务，系统能自动将任务分解为多个原子子任务。

#### 验收标准

1. WHEN 用户发送一条复杂任务描述且 `composer.enabled` 配置为 true, THE Skill_Composer SHALL 将任务分解为多个原子子任务，每个子任务包含描述文本
2. THE Skill_Composer SHALL 支持通过 `composer.backend` 配置项选择分解后端：`rule`（基于规则的分解引擎，默认值）、`ollama`（本地 Ollama 模型）、`openai`（OpenAI API）
3. WHEN 使用 `rule` 后端, THE Skill_Composer SHALL 基于关键词匹配和句法模式（如 "先...然后..."、"and then"、"步骤1..."）将任务拆分为子任务
4. WHEN 使用 `ollama` 或 `openai` 后端, THE Skill_Composer SHALL 通过 LLM 生成结构化的子任务列表，输出格式为 JSON 数组

### 需求 3.2：子任务 Skill 匹配与 Plan 生成

**用户故事：** 作为 CoPaw 用户，我希望系统能为每个子任务自动匹配最合适的 skill，并生成一个可执行的 Plan。

#### 验收标准

1. WHEN 任务分解完成, THE Skill_Composer SHALL 使用 Skill_Router 的语义检索能力为每个子任务检索匹配的 skill，并选择相似度最高的 skill 作为该步骤的执行 skill
2. THE Skill_Composer SHALL 生成一个 Plan 对象，Plan 中每个步骤包含：子任务描述（description）、选中的 skill 名称（skill_name）、相似度分数（confidence）
3. WHEN Plan 中存在无数据依赖的子任务, THE Skill_Composer SHALL 在 Plan 中标注并行分组信息（parallel_group 字段），同一 parallel_group 内的步骤可并行执行
4. IF 某个子任务的最高匹配 skill 置信度低于 0.3, THEN THE Skill_Composer SHALL 在 Plan 中将该步骤标记为 `unresolved`，并在返回给用户的消息中说明哪些子任务未找到匹配的 skill

### 需求 3.3：Plan 序列化与反序列化

**用户故事：** 作为 CoPaw 开发者，我希望 Plan 对象能序列化为 JSON 格式，便于日志记录、调试和 API 传输。

#### 验收标准

1. THE Skill_Composer SHALL 提供将 Plan 对象（包含步骤列表、并行分组、置信度分数）序列化为 JSON 字符串的方法
2. THE Skill_Composer SHALL 提供从 JSON 字符串反序列化为 Plan 对象的方法
3. FOR ALL 有效的 Plan 对象, 序列化后再反序列化 SHALL 产生与原始对象等价的结果（round-trip 属性）
4. WHEN Plan 中包含非 ASCII 字符, THE 序列化方法 SHALL 使用 `ensure_ascii=False` 正确保留原始字符

### 需求 3.4：组合编排零侵入

**用户故事：** 作为 CoPaw 用户，我希望组合编排功能是完全可选的，不启用时不影响 CoPaw 的任何现有行为。

#### 验收标准

1. THE Skill_Composer SHALL 通过 `~/.copaw/config.json` 中的 `composer.enabled` 开关控制启用或禁用，默认值为 false
2. WHEN `composer.enabled` 为 false 或未配置, THE CoPaw SHALL 完全跳过任务分解和编排逻辑，保持原有的单 skill 调用行为
3. THE Skill_Composer SHALL 不改动 CoPaw 现有的 Friday agent ReAct loop 接口，仅在 skill 选择阶段提供增强的 Plan 信息
4. WHEN `composer.backend` 配置为 `ollama` 或 `openai` 但对应服务不可用, THEN THE Skill_Composer SHALL 记录 WARNING 级别日志并回退到 `rule` 后端

---

## 跨 Phase 需求

### 需求 C.1：统一配置管理

**用户故事：** 作为 CoPaw 开发者或运维人员，我希望所有语义路由和编排功能都通过 CoPaw 现有的配置机制统一管理。

#### 验收标准

1. THE 功能模块 SHALL 在 `~/.copaw/config.json` 中使用以下配置结构：`semantic_routing` 段包含 `enabled`（布尔值，默认 false）、`encoder`（字符串，默认 `all-MiniLM-L6-v2`）、`top_k`（整数，默认 10）、`max_tools`（整数，默认 20）、`token_budget`（整数，默认 8000）、`mandatory_tools`（字符串数组，默认空）；`composer` 段包含 `enabled`（布尔值，默认 false）、`backend`（字符串，默认 `rule`）
2. WHEN ConfigWatcher 检测到配置文件变更, THE 功能模块 SHALL 在下一次查询时使用更新后的配置值，无需重启 CoPaw
3. IF 配置文件中缺少 `semantic_routing` 或 `composer` 段, THEN THE 功能模块 SHALL 使用全部默认值，等同于功能未启用

### 需求 C.2：测试与质量保证

**用户故事：** 作为 CoPaw 贡献者，我希望每个 PR 都附带完整的测试，确保代码质量符合 CoPaw 的 CI 标准。

#### 验收标准

1. THE 每个 PR SHALL 提供单元测试，覆盖该 PR 引入的核心逻辑路径（语义检索、工具过滤、任务分解）
2. THE 测试 SHALL 在未安装可选依赖（sentence-transformers、faiss-cpu）时自动跳过（使用 pytest.importorskip 或 skipIf 标记）
3. THE 测试 SHALL 通过 CoPaw 现有的 pre-commit 和 pytest CI 流水线
4. THE 每个 PR 的代码 SHALL 遵循 CoPaw 的 Conventional Commits 规范（如 `feat(routing): add semantic skill filtering`）
