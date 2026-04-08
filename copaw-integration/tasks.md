# 实现计划：CoPaw 语义技能路由（PR1：语义 Skill 过滤）

## 概述

本计划聚焦 Phase 1（PR1），在 `copaw-upstream/src/copaw/routing/` 下实现语义 Skill 过滤功能。包括延迟导入守卫、Pydantic 配置模型、数据模型、FAISS 索引管理、语义检索引擎，以及与 CoPaw 现有 `_register_skills()` 的集成。所有代码写在 `copaw-upstream/` 目录下。

## Tasks

- [ ] 1. 创建 routing 模块骨架与延迟导入守卫
  - [ ] 1.1 创建 `copaw-upstream/src/copaw/routing/__init__.py`
    - 实现 `_AVAILABLE` 标志和 `is_routing_available()` 函数
    - 尝试导入 `sentence_transformers` 和 `faiss`，捕获 ImportError
    - 公开模块级 API（SkillRouter, SemanticIndex, SemanticRoutingConfig 等）
    - _需求: 1.4.1, 1.4.2_

  - [ ] 1.2 创建 `copaw-upstream/src/copaw/routing/models.py`
    - 实现 `IndexItem` dataclass（id, name, description, source, metadata）
    - 实现 `SearchHit` dataclass（item, score）
    - 实现 `RoutingResult` dataclass（hits, query, total_skills, bypassed）
    - 实现 `RoutingResult.to_dict()`, `to_json()`, `from_json()` 序列化方法
    - 使用 `ensure_ascii=False` 处理非 ASCII 字符
    - _需求: 1.2.3, 1.5.1, 1.5.2, 1.5.3, 1.5.4_

  - [ ] 1.3 创建 `copaw-upstream/src/copaw/routing/config.py`
    - 实现 `SemanticRoutingConfig` Pydantic 模型
    - 字段：enabled(bool, False), encoder(str, "all-MiniLM-L6-v2"), top_k(int, 10), max_tools(int, 20), token_budget(int, 8000), mandatory_tools(list[str], [])
    - 使用 `ConfigDict(extra="ignore")` 与 CoPaw 配置模式一致
    - _需求: C.1.1_

- [ ] 2. 实现 SemanticIndex（FAISS 索引管理）
  - [ ] 2.1 创建 `copaw-upstream/src/copaw/routing/index.py`
    - 实现 `SemanticIndex.__init__(encoder_name, persist_dir)`
    - 实现 `build(items)` — 编码 IndexItem 列表并构建 FAISS IndexFlatIP 索引
    - 实现 `search(query, top_k)` — 语义检索，返回 SearchHit 列表，score 归一化到 [0.0, 1.0]
    - 实现 `needs_rebuild(items)` — 基于 SHA-256 内容哈希比对
    - 实现 `save()` / `load()` — 持久化到 `persist_dir`（index.faiss + metadata.json）
    - 所有 `sentence_transformers` 和 `faiss` 导入在方法内部延迟执行
    - 处理模型加载失败、索引文件损坏、目录无写权限等异常
    - _需求: 1.1.1, 1.1.2, 1.1.3, 1.3.1, 1.3.2, 1.3.3, 1.3.4, 1.4.1_

  - [ ]* 2.2 编写 Property 1 属性测试：索引构建保留所有条目
    - **Property 1: 索引构建保留所有条目**
    - 使用 Hypothesis 生成任意 IndexItem 集合，验证构建后索引条目数等于输入大小
    - 测试文件：`copaw-upstream/tests/test_routing/test_index.py`
    - **验证需求: 1.1.1**

  - [ ]* 2.3 编写 Property 2 属性测试：内容变更触发索引重建
    - **Property 2: 内容变更触发索引重建**
    - 使用 Hypothesis 生成变更操作（新增/删除/修改 description），验证 `needs_rebuild()` 返回 True
    - 测试文件：`copaw-upstream/tests/test_routing/test_index.py`
    - **验证需求: 1.1.3**

  - [ ]* 2.4 编写索引持久化单元测试
    - 测试 save/load round-trip
    - 测试损坏索引文件的处理
    - 测试目录无写权限时的 fallback
    - 测试文件：`copaw-upstream/tests/test_routing/test_index.py`
    - _需求: 1.3.1, 1.3.2, 1.3.3, 1.3.4_

- [ ] 3. 实现 SkillRouter（语义检索引擎）
  - [ ] 3.1 创建 `copaw-upstream/src/copaw/routing/router.py`
    - 实现 `SkillRouter.__init__(config: SemanticRoutingConfig)`
    - 实现 `route(query, skills) -> RoutingResult`
    - 当 `len(skills) <= top_k` 时直接返回全部，设置 `bypassed=True`
    - 否则将 skills 转换为 IndexItem，调用 SemanticIndex 检索
    - 实现 `invalidate()` 标记索引需要重建
    - 处理依赖缺失和模型加载失败的回退逻辑
    - _需求: 1.2.1, 1.2.2, 1.2.3, 1.2.4, 1.1.4, 1.4.3_

  - [ ]* 3.2 编写 Property 3 属性测试：检索结果不变量
    - **Property 3: 检索结果不变量**
    - 验证：(a) 结果数 ≤ min(top_k, 索引总数), (b) score 降序, (c) score ∈ [0.0, 1.0], (d) name/description 非空
    - 测试文件：`copaw-upstream/tests/test_routing/test_router.py`
    - **验证需求: 1.2.1, 1.2.3**

  - [ ]* 3.3 编写 Property 4 属性测试：小规模 Skill 池旁路
    - **Property 4: 小规模 Skill 池旁路**
    - 验证当 `len(skills) <= top_k` 时返回全部 skills 且 `bypassed=True`
    - 测试文件：`copaw-upstream/tests/test_routing/test_router.py`
    - **验证需求: 1.2.4**

  - [ ]* 3.4 编写 SkillRouter 回退行为单元测试
    - 测试依赖缺失时的回退
    - 测试模型加载失败时的回退
    - 测试文件：`copaw-upstream/tests/test_routing/test_router.py`
    - _需求: 1.1.4, 1.4.2, 1.4.3_

- [ ] 4. Checkpoint — 确保核心模块测试通过
  - 确保所有测试通过，如有问题请向用户确认。

- [ ] 5. 配置集成与序列化测试
  - [ ] 5.1 修改 `copaw-upstream/src/copaw/config/config.py`
    - 在 `Config` 根模型中添加 `semantic_routing: SemanticRoutingConfig = Field(default_factory=SemanticRoutingConfig)` 字段
    - 导入 `SemanticRoutingConfig`（使用条件导入或直接导入，因为 config.py 不依赖可选库）
    - 确保缺少 `semantic_routing` 段时使用默认值（功能未启用）
    - _需求: C.1.1, C.1.3_

  - [ ]* 5.2 编写 Property 5 属性测试：RoutingResult 序列化 Round-Trip
    - **Property 5: RoutingResult 序列化 Round-Trip**
    - 使用 Hypothesis 生成任意 RoutingResult（含 Unicode、各种 score 值），验证 `from_json(to_json())` 等价
    - 测试文件：`copaw-upstream/tests/test_routing/test_models.py`
    - **验证需求: 1.5.1, 1.5.2, 1.5.3, 1.5.4**

  - [ ]* 5.3 编写配置默认值与热重载单元测试
    - 测试 SemanticRoutingConfig 所有字段默认值
    - 测试 Config 根模型中 semantic_routing 字段的默认行为
    - 测试 ConfigWatcher 热重载兼容性
    - 测试文件：`copaw-upstream/tests/test_routing/test_config.py`
    - _需求: C.1.1, C.1.2, C.1.3_

- [ ] 6. 集成到 CoPawAgent._register_skills()
  - [ ] 6.1 修改 `copaw-upstream/src/copaw/agents/react_agent.py`
    - 在 `_register_skills()` 方法中，`resolve_effective_skills()` 返回后插入语义过滤逻辑
    - 从 `_request_context` 获取用户查询（如果可用）
    - 当 `semantic_routing.enabled=True` 且依赖可用时，调用 `SkillRouter.route()` 过滤 skills
    - 当依赖不可用或配置未启用时，保持原有逻辑不变
    - 不改动现有公开接口签名
    - _需求: 1.2.1, 1.4.2, 1.4.4_

  - [ ]* 6.2 编写集成点单元测试
    - Mock SkillRouter，测试 `_register_skills()` 在启用/禁用语义路由时的行为
    - 测试依赖缺失时的 passthrough 行为
    - 测试文件：`copaw-upstream/tests/test_routing/test_integration.py`
    - _需求: 1.4.2, 1.4.4_

- [ ] 7. 最终 Checkpoint — 确保所有测试通过
  - 确保所有测试通过，如有问题请向用户确认。

---

## PR2/PR3 任务（后续 PR，标记为可选参考）

> 以下任务属于 Phase 2 和 Phase 3，不在本次实现范围内，仅作为后续规划参考。

- [ ] 8. [PR2] 实现 ToolFilter（MCP 工具过滤）
  - 创建 `copaw-upstream/src/copaw/routing/filter.py`
  - 实现 token budget 控制、跨 server 多样性约束、mandatory 工具保留
  - 集成到 `register_mcp_clients()` 流程
  - Property 6（三重约束）、Property 7（mandatory 工具）属性测试
  - _需求: 2.1, 2.2, 2.3_

- [ ] 9. [PR3] 实现 SkillComposer（组合编排）
  - 创建 `copaw-upstream/src/copaw/routing/composer.py` 和 `decomposers.py`
  - 实现 RuleDecomposer、LLMDecomposer
  - 实现 Plan/PlanStep 模型和序列化
  - 集成到 CoPawAgent 查询入口
  - Property 8-11 属性测试
  - _需求: 3.1, 3.2, 3.3, 3.4_

## 备注

- 标记 `*` 的子任务为可选，可跳过以加速 MVP
- 每个任务引用了具体的需求编号，确保可追溯性
- Checkpoint 任务用于增量验证
- 属性测试验证设计文档中定义的正确性属性
- 单元测试验证具体示例和边界条件
- 所有代码写在 `copaw-upstream/` 目录下
