# PR #3117 代码审查合并报告

**日期**: 2026-04-22 22:30  
**审查来源**: Aone Copilot + Kiro（两份独立审查合并去重）  
**PR 分支**: `feat/semantic-skill-routing`  
**Base**: `upstream/main` @ `6a7a01c1`  
**Commit**: `248cd754`  
**Diff**: 14 files, +1125 insertions, -10 deletions  

---

## 审查覆盖的文件

| # | 文件 | 类型 | 行数 |
|---|------|------|------|
| 1 | `src/qwenpaw/routing/__init__.py` | 新增 | 65 |
| 2 | `src/qwenpaw/routing/config.py` | 新增 | 59 |
| 3 | `src/qwenpaw/routing/index.py` | 新增 | 415 |
| 4 | `src/qwenpaw/routing/models.py` | 新增 | 86 |
| 5 | `src/qwenpaw/routing/router.py` | 新增 | 162 |
| 6 | `src/qwenpaw/agents/react_agent.py` | 修改 | +186 |
| 7 | `src/qwenpaw/config/config.py` | 修改 | +43 |
| 8 | `src/qwenpaw/app/routers/config.py` | 修改 | +27 |
| 9 | `console/.../SemanticRoutingCard.tsx` | 新增 | 53 |
| 10 | `console/.../components/index.ts` | 修改 | +1 |
| 11 | `console/.../Config/index.tsx` | 修改 | +20/-9 |
| 12 | `console/src/locales/en.json` | 修改 | +8 |
| 13 | `console/src/locales/zh.json` | 修改 | +8 |
| 14 | `pyproject.toml` | 修改 | +5/-1 |

---

## 🔴 必须修复（5 个）

### #1 — 3 个配置字段从未使用（死代码）

- **文件**: `src/qwenpaw/routing/config.py` L38-52
- **来源**: Kiro 发现，Aone Copilot 漏掉
- **问题**: `SemanticRoutingConfig` 定义了 7 个字段，但只有 4 个被使用：

| 字段 | 使用情况 |
|------|----------|
| `enabled` | ✅ `react_agent.py` L393 检查 |
| `encoder` | ✅ `_get_or_create_router` L458 比较 + `SkillRouter` 构造 |
| `top_k` | ✅ `router.py` L63 使用 |
| `min_score` | ✅ `router.py` L73 使用 |
| **`max_tools`** | ❌ **从未使用** |
| **`token_budget`** | ❌ **从未使用** |
| **`mandatory_tools`** | ❌ **从未使用** |

- **风险**: maintainer 会质疑为什么有未使用的配置
- **修复**: 删掉 `max_tools`、`token_budget`、`mandatory_tools`，等 PR2 (MCP tool filtering) 再加

---

### #2 — `__init__.py` 未使用的 `logger`（死代码）

- **文件**: `src/qwenpaw/routing/__init__.py` L13-14
- **来源**: Aone Copilot 发现，Kiro 漏掉
- **问题**: 
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
  定义了但整个文件从未使用
- **修复**: 删除这两行

---

### #3 — `router.py` docstring 提到 "FAISS"（过时注释）

- **文件**: `src/qwenpaw/routing/router.py` L29
- **来源**: 两方均发现
- **问题**: 
  ```python
  persist_dir:
      Optional directory for FAISS index persistence.
  ```
  实际使用 NumPy 持久化（`np.save/np.load`），不是 FAISS
- **修复**: 改为 `Optional directory for index persistence.`

---

### #4 — `_get_or_create_router` 缓存比较不完整

- **文件**: `src/qwenpaw/agents/react_agent.py` L452-460
- **来源**: Aone Copilot 发现，Kiro 漏掉
- **问题**: 只比较了 `top_k`、`min_score`、`encoder`，遗漏其他字段。
  
  **注意**: 如果修复 #1 删掉了 3 个未使用字段，则只剩 4 个字段（enabled 已在上游检查），此时当前的 3 字段比较就是完整的了。**#4 和 #1 联动——修了 #1 后 #4 自动解决。**
  
  如果不删字段，则需要用 `sr_config.model_dump() == cached_cfg.model_dump()` 替代。

---

### #5 — `__getattr__` lazy import 无代码触发

- **文件**: `src/qwenpaw/routing/__init__.py` L50-66
- **来源**: Kiro 发现，Aone Copilot 漏掉
- **问题**: `__getattr__` 定义了 6 个符号的 lazy import，但所有实际使用者都直接 import 子模块。grep 确认 `from qwenpaw.routing import XXX` 出现 0 次。
- **处理**: 这是为外部用户设计的公共 API 入口。**不删**，但加注释说明用途：
  ```python
  def __getattr__(name: str):
      """Lazy import for public API.
  
      Allows ``from qwenpaw.routing import SkillRouter`` etc.
      without loading heavy dependencies at module import time.
      Internal code uses direct sub-module imports instead.
      """
  ```

---

## 🟡 建议修复（4 个）

### #6 — `except Exception: pass` 静默吞异常

- **文件**: `src/qwenpaw/routing/index.py` L66, L123
- **来源**: Aone Copilot 发现
- **问题**: `_get_embedding_config()` 和 `_apply_hf_mirror_if_needed()` 中 `except Exception: pass` 完全静默
- **修复**: 改为 `except Exception: logger.debug("...: %s", exc)`

---

### #7 — 硬编码超时 `timeout=60.0`

- **文件**: `src/qwenpaw/routing/index.py` L93
- **来源**: Aone Copilot 发现
- **问题**: API embedding 请求超时硬编码
- **修复**: 提取为模块常量 `_EMBEDDING_API_TIMEOUT_SECONDS = 60.0`

---

### #8 — `_cleanup_persist` 后未重置内部状态

- **文件**: `src/qwenpaw/routing/index.py` L356-365
- **来源**: Aone Copilot 发现
- **问题**: `load()` 失败后清理文件但未重置 `_vectors/_items/_hash`，可能残留脏数据
- **修复**: 在 `_cleanup_persist()` 后追加：
  ```python
  self._vectors = None
  self._items = []
  self._hash = ""
  ```

---

### #9 — `_skill_meta_cache` 类级别共享，多 workspace 可能冲突

- **文件**: `src/qwenpaw/agents/react_agent.py` L468
- **来源**: 两方均发现
- **问题**: cache key 只用 `name`，多个 workspace 下同名 skill 会互相覆盖
- **当前风险**: 低（QwenPaw 通常单实例）
- **修复**: 改 cache key 为 `f"{skills_dir}:{name}"`，或加注释说明限制

---

## ℹ️ 不需要修复（附理由）

| 审查项 | 结论 | 理由 |
|--------|------|------|
| `load_config()` 每次读磁盘 | 🟢 不改 | 1) 与 upstream 自身模式一致（`runner/utils.py`、`tool_guard` 等多处同样调法）；2) 在 `to_thread` 后台执行不阻塞事件循环；3) config 需要实时生效——用户在 UI 改了 `enabled=false` 后下一次对话就应该生效，缓存反而需要额外的失效机制 |
| 每轮对话计算 embedding | 🟢 设计意图 | query 每次不同，已用 `asyncio.to_thread` 避免阻塞事件循环 |
| `config.py` 的 `try: model_rebuild() except ImportError` | 🟢 可接受 | 防御性编程，虽然几乎不触发 |
| `rebuild_sys_prompt` 与 hint injection 冲突 | 🟢 无冲突 | 通过 memory mark 机制天然隔离 |
| `save()` 的 `indent=2` 性能 | 🟢 可接受 | skill 数量极少 |
| `models.py` 的 `to_dict/from_dict` | 🟢 公共 API | 供外部使用和调试 |

---

## 修复计划

| 优先级 | 问题 | 预计改动 | 说明 |
|--------|------|---------|------|
| **P0** | #1 删 3 个未使用字段 | -18 行 | 删掉后 #4 自动解决 |
| **P0** | #2 删死代码 logger | -2 行 | |
| **P0** | #3 修 FAISS 注释 | 1 行 | |
| **P0** | #5 加 `__getattr__` 注释 | +3 行 | |
| **P1** | #6 改善异常处理 | ~6 行 | |
| **P1** | #7 提取超时常量 | ~3 行 | |
| **P1** | #8 重置脏状态 | +3 行 | |
| **P1** | #9 改 cache key 或加注释 | ~2 行 | |

**总改动量**: 约 20 行净减（删掉 3 个字段 + logger），几行新增。不影响任何功能逻辑。

---

## CI 状态

| Workflow | 最近一次验证 | 结果 |
|----------|-------------|------|
| NPM Format (tsc + prettier) | 2026-04-22 | ✅ PASSED |
| Pre-commit (16 hooks) | 2026-04-22 | ✅ PASSED |
| Tests (pytest) | 2026-04-22 | ✅ 1646 passed, 1 skipped |

> 修复完成后需重新验证 CI。
