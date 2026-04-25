# QwenPaw PR #3117 完整测试与审查报告

> **PR**: https://github.com/agentscope-ai/QwenPaw/pull/3117
> **分支**: feat/semantic-skill-routing
> **作者**: hellogxp (燕衡)
> **测试日期**: 2026-04-17
> **测试环境**: Ubuntu 22.04, Python 3.10.12, ECS 42.121.222.15

---

## 一、测试报告

### 1.1 官方全量单元测试

| 指标 | 结果 |
|------|------|
| 总用例数 | 1873 |
| 通过 | 1868 |
| 失败 | 2 (预先存在，与 PR 无关) |
| 跳过 | 3 |
| 耗时 | 72.49s |

**失败用例分析（均为预先存在的问题，非 PR 引入）：**

| 用例 | 原因 |
|------|------|
| test_app_startup_and_console | Console 返回 404（需要预构建 console dist） |
| test_walk_and_grep_file_read_error | root 用户可读取 0o000 权限文件，断言失败 |

**结论：PR 未破坏任何原有功能**

### 1.2 PR 新增单元测试 (test_routing/)

| 指标 | 结果 |
|------|------|
| 总用例数 | 23 |
| 通过 | 23 |
| 失败 | 0 |
| 耗时 | 5.55s |

覆盖范围：
- test_config.py (7 cases): 配置默认值、自定义参数、额外字段忽略、字典加载
- test_models.py (5 cases): IndexItem 创建、RoutingResult 序列化往返、Unicode、边界分数
- test_router.py (11 cases): bypass 逻辑、空查询、空技能列表、fallback 降级

### 1.3 test_hint_injection.py

| 指标 | 结果 |
|------|------|
| 状态 | ImportError |
| 原因 | `from qwenpaw.agents.react_agent import CoPawAgent` 失败 |
| 根因 | 类名已从 CoPawAgent 改为 QwenPawAgent，测试文件未同步更新 |
| 严重性 | 高 - 冲突解决时的漏改 |

### 1.4 PR 功能验证测试

| 测试项 | 结果 | 说明 |
|--------|------|------|
| SemanticRoutingConfig 加载 | PASS | enabled/top_k/min_score 正确 |
| 数据模型序列化往返 | PASS | IndexItem/SearchHit/RoutingResult |
| SkillRouter bypass 逻辑 | PASS | 小技能池(2 <= top_k=10)正确 bypass |
| SemanticIndex 构建与搜索 | PASS | API embedding (text-embedding-v3, 1024维) |
| 搜索质量 | PASS | "帮我读取PDF文件" -> pdf(0.760) > file_reader(0.632) > news(0.481) |
| is_routing_available | PASS | sentence-transformers + API 均可用 |
| QwenPawAgent 方法检查 | PASS | _build_skill_hint OK, _read_skill_metas OK, _apply_semantic_routing 已删除 |
| 大技能池路由 (10 skills, top_k=3) | PASS | pdf(0.771) > file_reader(0.625) > xlsx(0.550) |

### 1.5 E2E 服务部署测试

| 测试项 | 结果 |
|--------|------|
| 服务启动 (端口 8099) | 启动成功，耗时 2.576s |
| API /api/version | 返回 {"version":"1.1.3b1"} |
| Console 页面 /console/ | HTTP 200 |
| 语义路由 API GET /api/config/semantic-routing | 返回正确配置 |
| DashScope Embedding 集成 | text-embedding-v3 正常工作 |
| 外网访问 | 需开放阿里云安全组 8099 端口 |

**验收地址**: http://42.121.222.15:8099/console/ (需开放安全组)
**内网地址**: http://127.0.0.1:8099/console/ (已验证正常)

---

## 二、代码差异报告

### 2.1 简洁版 - PR 作者变更的文件清单

PR 包含 **14 个 commits**，变更了以下文件：

#### 新增文件 (11个)
| 文件 | 行数 | 说明 |
|------|------|------|
| src/qwenpaw/routing/__init__.py | 77 | 语义路由模块入口，懒加载 API |
| src/qwenpaw/routing/config.py | 58 | SemanticRoutingConfig Pydantic 模型 |
| src/qwenpaw/routing/index.py | 435 | SemanticIndex，双后端 embedding 索引 |
| src/qwenpaw/routing/models.py | 85 | IndexItem/SearchHit/RoutingResult 数据模型 |
| src/qwenpaw/routing/router.py | 162 | SkillRouter 语义技能检索引擎 |
| console/.../SemanticRoutingCard.tsx | 53 | 前端语义路由配置卡片 |
| tests/test_hint_injection.py | ~60 | Hint injection 集成测试 (有 bug) |
| tests/test_routing/__init__.py | 0 | 测试包初始化 |
| tests/test_routing/test_config.py | 59 | 配置模型单元测试 |
| tests/test_routing/test_models.py | 146 | 数据模型序列化测试 |
| tests/test_routing/test_router.py | 126 | 路由器 bypass/fallback 测试 |

#### 修改文件 (8个)
| 文件 | 变更 | 说明 |
|------|------|------|
| src/qwenpaw/agents/react_agent.py | +137 行 | 添加 _build_skill_hint, _read_skill_metas, reply() hint injection |
| src/qwenpaw/config/config.py | +15 行 | 集成 SemanticRoutingConfig 到 Config 模型 |
| src/qwenpaw/app/routers/config.py | +25 行 | 添加 GET/PUT /api/config/semantic-routing API |
| console/src/locales/en.json | +22 行 | 英文 i18n |
| console/src/locales/zh.json | +10 行 | 中文 i18n |
| console/.../Config/components/index.ts | +1 行 | 导出 SemanticRoutingCard |
| console/.../Config/index.tsx | +13 行 | 添加语义路由配置 Tab |
| pyproject.toml | +8/-8 行 | 添加 semantic extras (有问题) |

### 2.2 详细版 - 各文件变更内容

#### react_agent.py 变更详解

**1. _register_skills 方法** - 新增 2 行存储元数据：
```python
# Store skill metadata for hint injection (used in reply())
self._effective_skill_names = list(effective_skills)
self._working_skills_dir = working_skills_dir
```

**2. 新增 _build_skill_hint 方法** (~75 行)：
- 检查路由可用性 -> 加载配置 -> 读取技能元数据 -> 调用 SkillRouter.route()
- 格式化 hint 文本：`[Skill Hint] Relevant skills for this query: ...`
- 异常时返回空字符串（fail-open 设计）

**3. 新增 _read_skill_metas 静态方法** (~20 行)：
- 从磁盘读取技能 frontmatter，返回 name+description 列表

**4. reply 方法修改** - hint injection 逻辑：
```python
hint_injected = False
if query and msg is not None:
    hint = self._build_skill_hint(query)
    if hint:
        hint_msg = Msg(name="system", role="system", content=hint)
        await self.memory.add(hint_msg, marks="skill_hint")
        hint_injected = True
try:
    result = await super().reply(msg=msg, structured_model=structured_model)
    return result
finally:
    if hint_injected:
        await self.memory.delete_by_mark("skill_hint")
```

#### config.py 变更详解
- 添加 `semantic_routing` 字段到 Config 模型
- 使用 TYPE_CHECKING + forward reference + model_rebuild 解决循环导入

#### routing/ 模块详解
- **index.py**: 双后端 embedding (API 优先 -> 本地 fallback)，numpy 存储，持久化缓存
- **router.py**: bypass 模式 (skills <= top_k)，min_score 过滤，异常降级
- **config.py**: 7 个配置字段，全部有安全默认值
- **models.py**: 3 个 dataclass，支持 JSON 序列化

---

## 三、完整性检查报告

### 3.1 检查项汇总

| 检查项 | 结果 | 说明 |
|--------|------|------|
| Git 冲突标记残留 | 无 | 无 <<<, ===, >>> 标记 |
| V1 残留 (_apply_semantic_routing) | 已清理 | 仅在测试断言中引用 |
| V2 残留 (_routing_cache, _skill_meta_cache) | 已清理 | 仅在测试断言中引用 |
| src/copaw/ 旧命名空间 | 已清理 | 已迁移到 src/qwenpaw/ |
| Import 完整性 | 正确 | 延迟导入设计合理 |
| 方法调用链 | 正确 | _register_skills -> reply -> _build_skill_hint |

### 3.2 发现的问题

#### 问题 1: test_hint_injection.py 漏改 (严重)
```
错误: from qwenpaw.agents.react_agent import CoPawAgent
原因: 类名已改为 QwenPawAgent，测试文件未同步更新
修复: 将所有 CoPawAgent 替换为 QwenPawAgent
```

#### 问题 2: pyproject.toml 丢失 optional dependencies (严重)
```
官方 main 有:
  llamacpp = ["copaw[local]", "llama-cpp-python>=0.3.0"]
  mlx = ["copaw[local]", "mlx-lm>=0.10.0; sys_platform == 'darwin'"]
  ollama = ["ollama>=0.6.1"]
  full = ["copaw[local,ollama,llamacpp,whisper]", "mlx-lm>=0.10.0; sys_platform == 'darwin'"]

PR 分支:
  这三个 extras 被完全删除！
  full = ["qwenpaw[local,whisper,semantic]"]  <- 丢失了 ollama, llamacpp, mlx

修复: 恢复 llamacpp, mlx, ollama extras（更新包名为 qwenpaw），并更新 full 依赖
```

#### 问题 3: FAISS 依赖不一致 (中等)
```
pyproject.toml: faiss-cpu>=1.7 仍在 semantic extras 中
代码: 已改用 numpy 存储，FAISS 仅用于旧格式迁移
注释: __init__.py 仍写 "requires sentence-transformers + faiss-cpu"

建议: 如果不再需要 FAISS，移除依赖和迁移代码；
      如果保留向后兼容，更新注释说明
```

#### 问题 4: 注释中的旧品牌名 (轻微)
```
routing/__init__.py: "uses CoPaw's EmbeddingConfig"
routing/index.py: "uses CoPaw's existing EmbeddingConfig"
应改为: QwenPaw
```

---

## 四、总结

### QwenPaw 功能状态: 完好
- 1868/1873 测试通过（2 个失败为预先存在的问题）
- 服务正常启动，API 和 Console 均可访问

### PR 功能状态: 核心功能完好
- 语义路由核心链路全部正常
- DashScope API embedding 集成正常
- 搜索质量符合预期

### 必须修复的问题:
1. **test_hint_injection.py**: CoPawAgent -> QwenPawAgent
2. **pyproject.toml**: 恢复丢失的 llamacpp/mlx/ollama extras

### 建议修复的问题:
3. **FAISS 依赖**: 确认是否需要，统一代码和依赖
4. **注释**: CoPaw -> QwenPaw 品牌名更新

