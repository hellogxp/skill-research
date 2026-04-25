# PR #3117 Review Feedback To-dos

> Reviewer: xieyxclack (maintainer), Apr 20, 2026

---

## 代码修改（按文件分组）

### 1. react_agent.py — 缓存 SkillRouter 实例
- 问题：每次 `_build_skill_hint()` 都 `SkillRouter(config=sr_config, persist_dir=persist_dir)` 新建实例，还可能重建 embedding index
- 修复：把 SkillRouter 缓存为 `self._skill_router`，只在 skill 列表变化时重建

### 2. react_agent.py — 缓存 skill metadata 读取
- 问题：`_read_skill_metas()` 每次调用都读磁盘 YAML frontmatter，50+ skills 有性能问题
- 修复：加 mtime 缓存，只在文件变化时重新读取

### 3. router.py — 延迟导入移到文件顶部
- 问题：`_ensure_index()` 里 `from .index import SemanticIndex` 是延迟导入
- 修复：移到文件顶部 import
- 注意：这个可以直接改，因为 index.py 和 router.py 在同一个包内，不存在循环导入

### 4. index.py — 延迟导入移到文件顶部（多处）
- 问题：`_get_embedding_config()` 和 `_apply_hf_mirror_if_needed()` 里的 `from qwenpaw.config.utils import load_config` 是延迟导入
- 修复：移到文件顶部
- 注意：这些延迟导入是有意为之的（避免 routing 模块成为硬依赖），需要判断是否真的能移到顶部。如果移到顶部会导致没装 routing 依赖时 import 失败，就不能移。但 maintainer 明确要求了，可以移——因为这些 import 的是 qwenpaw.config，不是可选依赖
- 同类问题：`import httpx` 也是延迟导入，也要移到顶部

### 5. index.py — 同步 httpx 阻塞事件循环
- 问题：`_embed_via_api()` 用同步 `httpx.post()`，在 async `reply()` 调用链中会阻塞事件循环
- 修复方案 A：改用 `httpx.AsyncClient`（需要把 `_embed_via_api` 改成 async，连带 `_encode`、`build`、`search` 都要改）
- 修复方案 B：用 `asyncio.to_thread()` 包装同步调用（改动最小）
- 建议：方案 B，在 `_build_skill_hint()` 里用 `asyncio.to_thread()` 包装整个路由调用

### 6. en.json / zh.json — i18n 不一致
- 问题：en.json 有 `semanticRouting` 的详细描述（enableDescription、depsHint、encoderLabel 等），zh.json 没有对应的翻译
- 修复：zh.json 里补上对应的中文翻译，或者删掉 en.json 里多余的 key（因为这些 key 在当前 SemanticRoutingCard 里没用到）
- 注意：当前 SemanticRoutingCard 只用了 agentConfig 里的 semanticRoutingTitle/Hint/Enabled/TopK/MinScore，不用 semanticRouting section 的 key。所以可以直接删掉 `semanticRouting` section

### 7. 删除所有测试文件
- 问题：maintainer 明确要求 "Please remove all the test files in this pr"
- 修复：删除以下文件
  - `tests/test_hint_injection.py`
  - `tests/test_routing/__init__.py`
  - `tests/test_routing/test_config.py`
  - `tests/test_routing/test_models.py`
  - `tests/test_routing/test_router.py`

### 8. 代码格式化
- 问题：maintainer 要求按 CONTRIBUTING.md#4-code-and-quality 格式化
- 修复：对所有修改的 Python 文件运行 `pre-commit run --all-files`（包括 black、isort、flake8）

---

## Rebase

### 9. 解决 pyproject.toml 冲突
- 原因：upstream 新合了 ACP PR，改了 pyproject.toml
- 操作：`git fetch upstream && git rebase upstream/main`，解决 pyproject.toml 冲突
- 时机：所有代码修改完成后再 rebase，避免反复 rebase

---

## 执行顺序建议

1. 先做代码修改（1-8）
2. 运行 `pre-commit run --all-files` 格式化
3. 提交
4. Rebase 到最新 upstream/main
5. Force push
6. 在 PR 页面回复每个 review comment，说明修改内容
7. Resolve conversations
