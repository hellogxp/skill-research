# 第三轮改动记录 — API Embedding 支持 + UI 重构

> 基于讨论，重构 embedding 后端支持 API 模式和本地模式双轨运行，UI 从独立页面改为 Agent Config 页面内的 card。

## 核心变化

### 架构变化：双后端 embedding

原来只支持本地 sentence-transformers + FAISS，现在支持两种模式：

1. API 模式：复用 CoPaw 已有的 EmbeddingConfig（Agent Config 页面配置的 base_url + api_key + model_name），用 httpx 调远程 embedding API，numpy 做向量搜索。零额外依赖。
2. 本地模式：sentence-transformers 编码 + numpy 向量搜索。需要 `pip install copaw[semantic]`。

优先级：有 API 配置 → 用 API；没有 → 用本地模型；都没有 → 回退到原有行为。

### 存储变化：统一用 numpy

不再依赖 FAISS 做存储和搜索。两种模式都用 numpy array 存向量，`np.dot` 做余弦相似度搜索。持久化格式从 `index.faiss` 改为 `vectors.npy`（兼容加载旧的 FAISS 格式并自动迁移）。

### UI 变化：从独立页面改为 Agent Config card

删除了 `Settings/SemanticRouting/` 独立页面，改为在 Agent Config 页面（`/agent-config`）的 EmbeddingConfigCard 下方新增 SemanticRoutingCard。

UI 配置项：
- enabled 开关
- top_k 滑块（1~50）
- min_score 滑块（0~1）
- 提示文字说明 embedding 来源（自动检测 API 或本地模型）

去掉了 encoder 输入框（本地模型名用默认值 all-MiniLM-L6-v2，高级用户可以通过 config.json 修改）。

## 改动文件列表

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/copaw/routing/__init__.py` | 重写 | 双后端可用性检测 |
| `src/copaw/routing/index.py` | 重写 | 双后端 SemanticIndex（API + 本地），numpy 存储，持久化格式 v2 |
| `console/src/pages/Agent/Config/components/SemanticRoutingCard.tsx` | 重写 | 简化为 enabled + top_k + min_score |
| `console/src/locales/en.json` | 修改 | 更新 hint 文案，去掉 encoder 相关 key |
| `console/src/locales/zh.json` | 修改 | 同上 |
| `console/src/pages/Settings/SemanticRouting/` | 删除 | 废弃独立页面 |

以下文件在之前的 commit 中已修改，本轮未变：
| `src/copaw/routing/config.py` | 不变 | 已有 min_score 字段 |
| `src/copaw/routing/router.py` | 不变 | 已有 min_score 过滤 |
| `pyproject.toml` | 不变 | 已有 semantic extras |
| `console/src/pages/Agent/Config/index.tsx` | 不变 | 已导入 SemanticRoutingCard |
| `console/src/pages/Agent/Config/components/index.ts` | 不变 | 已导出 SemanticRoutingCard |

## 部署和测试步骤

```bash
cd copaw-test
git pull origin feat/semantic-skill-routing

# 后端安装
pip install -e ".[dev,full]"

# 前端构建
cd console && npm ci && npm run build && cd ..
cp -R console/dist/. src/copaw/console/

# 启动
copaw app
```

### 测试场景 1：API 模式（推荐先测这个）

1. 打开 Console → Agent Config
2. 在 Embedding Config card 里配置：
   - Base URL: `https://dashscope.aliyuncs.com/compatible-mode/v1`
   - Model Name: `text-embedding-v3`
   - API Key: 你的 DashScope key
3. 在 Semantic Routing card 里开启 enabled
4. 设置 top_k = 3
5. Save
6. 安装 10+ 个 skills
7. 发消息测试
8. 查看日志：应该看到 `Semantic routing: using API embedding (text-embedding-v3)`

### 测试场景 2：本地模式

1. 不配置 Embedding Config（或清空 base_url）
2. 安装本地依赖：`pip install copaw[semantic]`
3. 开启 Semantic Routing
4. 发消息测试
5. 查看日志：应该看到 `Semantic routing: using local model (all-MiniLM-L6-v2)`

### 测试场景 3：都没有（回退）

1. 不配置 Embedding Config
2. 不安装 sentence-transformers
3. 开启 Semantic Routing
4. 发消息测试
5. 应该正常工作，日志显示 WARNING 并回退到全量 skill 注入

### 测试场景 4：回归测试

```bash
python -m pytest tests/ -v --tb=short
```

期望：全部 PASSED，没有 FAILED。

## commit 命令

```bash
git add -A
git commit -m "feat(routing): add API embedding support and refactor UI

- Support dual embedding backends: API (EmbeddingConfig) and local
  (sentence-transformers). API mode requires zero extra dependencies.
- Replace FAISS storage with numpy for both backends.
- Move UI from standalone Settings page to Agent Config card.
- Simplify UI to enabled + top_k + min_score.
- Auto-detect embedding backend with graceful fallback.

Closes #3091"
```
