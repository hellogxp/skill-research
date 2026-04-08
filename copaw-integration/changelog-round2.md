# 第二轮改动记录

> 基于同事测试反馈和 review 讨论，在 feat/semantic-skill-routing 分支上的增量改动。

## 改动清单

### 1. HuggingFace 镜像支持
- 文件：`src/copaw/routing/index.py`
- 改动：`_ensure_model()` 方法加载模型前，新增 `_apply_hf_mirror_if_needed()` 静态方法
- 逻辑：检查 CoPaw 已有的 `token_count_use_mirror` 配置，如果启用了就自动设置 `HF_ENDPOINT=https://hf-mirror.com`
- 复用 CoPaw 现有机制，不引入新配置项

### 2. min_score 阈值过滤
- 文件：`src/copaw/routing/config.py`
- 改动：`SemanticRoutingConfig` 新增 `min_score` 字段（float, 默认 0.0, 范围 0.0~1.0）
- 文件：`src/copaw/routing/router.py`
- 改动：`route()` 方法在返回结果前，过滤掉 score < min_score 的 hit
- 用途：防止 top-k 截断导致不相关 skill 被选中

### 3. pyproject.toml optional dependencies
- 文件：`pyproject.toml`
- 改动：新增 `semantic` extras（`sentence-transformers>=2.2`, `faiss-cpu>=1.7`）
- `full` extras 也包含了 `semantic`
- 用户安装：`pip install copaw[semantic]`

### 4. Console 前端配置页面
- 新增文件：
  - `console/src/pages/Agent/Config/components/SemanticRoutingCard.tsx` — 配置卡片组件
- 修改文件：
  - `console/src/pages/Agent/Config/components/index.ts` — 导出 SemanticRoutingCard
  - `console/src/pages/Agent/Config/index.tsx` — 在 Agent Config 页面添加 SemanticRoutingCard
  - `console/src/locales/en.json` — 英文 i18n（agentConfig.semanticRouting* 键）
  - `console/src/locales/zh.json` — 中文 i18n
- 删除文件（第一轮创建的独立页面，已废弃）：
  - `console/src/pages/Settings/SemanticRouting/index.tsx`
  - `console/src/pages/Settings/SemanticRouting/index.module.less`
- 位置：Agent Config 页面（`/agent-config`），在 EmbeddingConfigCard 下方
- UI 功能：
  - enabled 开关
  - encoder 模型名称输入（启用后显示）
  - top_k 滑块（1~50，启用后显示）
  - min_score 滑块（0~1，步长 0.05，启用后显示）
  - 启用时显示依赖安装提示

### 5. Config 根模型（已在第一轮完成）
- 文件：`src/copaw/config/config.py`
- `Config` 根模型已包含 `semantic_routing` 字段
- Console 前端通过 `/api/config` 端点读写此字段

## 完整改动文件列表

| 文件 | 类型 | 说明 |
|------|------|------|
| `src/copaw/routing/index.py` | 修改 | HF 镜像支持 |
| `src/copaw/routing/config.py` | 修改 | 新增 min_score 字段 |
| `src/copaw/routing/router.py` | 修改 | min_score 过滤逻辑 |
| `pyproject.toml` | 修改 | semantic extras |
| `console/src/pages/Agent/Config/components/SemanticRoutingCard.tsx` | 新增 | Agent Config 页面的配置卡片 |
| `console/src/pages/Agent/Config/components/index.ts` | 修改 | 导出 SemanticRoutingCard |
| `console/src/pages/Agent/Config/index.tsx` | 修改 | 添加 SemanticRoutingCard |
| `console/src/locales/en.json` | 修改 | 英文 i18n |
| `console/src/locales/zh.json` | 修改 | 中文 i18n |
| `console/src/pages/Settings/SemanticRouting/` | 删除 | 废弃独立页面 |

## 部署和测试步骤

```bash
cd copaw-test
git pull origin feat/semantic-skill-routing

# 后端
pip install -e ".[dev,full]"
pip install sentence-transformers faiss-cpu

# 前端构建
cd console && npm ci && npm run build && cd ..
cp -R console/dist/. src/copaw/console/

# 跑测试
python -m pytest tests/ -v --tb=short

# 启动验证
copaw app
# 打开 http://127.0.0.1:8088/ → Settings → Semantic Routing
```

## 待确认

- Console 前端使用 `api.getConfig()` 和 `api.updateConfig()` 读写配置，需要确认这两个 API 是否已支持 `semantic_routing` 字段的透传（大概率可以，因为 Config 是 Pydantic 模型自动序列化）
- 前端代码未在本地构建测试（本地无 Node.js 环境），需要在服务器上验证 `npm run build` 是否通过
