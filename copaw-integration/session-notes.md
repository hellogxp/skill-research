# 会话关键信息备忘

> 记录本次 CoPaw 语义技能路由开发过程中的重要决策和上下文。

## 项目背景

- 用户来自 Alibaba Private Cloud，花名：燕衡
- GitHub 账号：hellogxp
- 有一篇关于 compositional skill routing 的论文，已投 EMNLP 2026，尚未公开
- 配套工具 SkillWeaver（github.com/hellogxp/skillweaver），尚未公开
- 目标：向 CoPaw（agentscope-ai/CoPaw）贡献代码，成为 committer

## 关键决策

1. 不是"集成 SkillWeaver"，而是在 CoPaw 中原生开发代码，SkillWeaver 仅作为技术背书
2. 产品形态选择了"核心模块方案"（方案 2），包含语义 Skill 过滤 + MCP 工具过滤 + 组合编排
3. 拆成 3 个独立 PR 提交：PR1 语义 Skill 过滤 → PR2 MCP 工具过滤 → PR3 组合编排
4. 所有功能默认关闭，可选依赖，零侵入
5. 论文在 Issue 中的表述：have a paper in preparation（不提会议名、不说 under review）
6. Issue 中写了花名"燕衡"和 Alibaba Private Cloud 身份，但不放邮箱

## 当前进度

- Issue 已开：https://github.com/agentscope-ai/CoPaw/issues/3091
- Fork 已完成：https://github.com/hellogxp/CoPaw
- PR1 代码已写完，在 copaw-upstream/ 的 feat/semantic-skill-routing 分支上
- 新增文件：
  - src/copaw/routing/__init__.py（延迟导入守卫）
  - src/copaw/routing/config.py（SemanticRoutingConfig）
  - src/copaw/routing/models.py（IndexItem, SearchHit, RoutingResult）
  - src/copaw/routing/index.py（SemanticIndex — FAISS 索引管理）
  - src/copaw/routing/router.py（SkillRouter — 语义检索引擎）
- 修改文件：
  - src/copaw/config/config.py（Config 根模型添加 semantic_routing 字段）
  - src/copaw/agents/react_agent.py（_register_skills 插入语义过滤 + 新增 _apply_semantic_routing 方法）
- 测试文件已写：
  - tests/test_routing/test_models.py
  - tests/test_routing/test_config.py
  - tests/test_routing/test_router.py

## 待完成

- 本地环境 Python 3.9.6，CoPaw 要求 3.10+，无法本地跑测试
- 需要在 Python 3.10+ 服务器上执行完整测试（见 testing-guide.md）
- 测试通过后，人工执行 git commit + push + 提 PR

## 分工

- Kiro：写代码、写测试、分析测试结果、修 bug
- 人工：GitHub 操作（Fork、commit、push、提 PR）、服务器上跑测试

## 文件位置

- 规划文档：copaw-integration/（README.md, requirements.md, design.md, tasks.md, testing-guide.md）
- Spec 文档：.kiro/specs/skillweaver-copaw-integration/
- CoPaw 代码：copaw-upstream/（feat/semantic-skill-routing 分支）
