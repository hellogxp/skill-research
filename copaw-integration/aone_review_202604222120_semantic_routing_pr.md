# Semantic Skill Routing PR — 代码审查报告

**日期**: 2026-04-22 21:20  
**审查人**: Aone Copilot  
**PR 分支**: `feat/semantic-skill-routing`  
**Base**: `upstream/main` @ `6a7a01c1`  
**Commit**: `248cd754`  
**Diff**: 14 files, +1125 insertions, -10 deletions  

---

## 审查范围

本次审查覆盖 PR 引入的全部 14 个文件：

| 类别 | 文件 |
|------|------|
| **routing 新模块** | `routing/__init__.py`, `routing/config.py`, `routing/index.py`, `routing/models.py`, `routing/router.py` |
| **核心集成** | `agents/react_agent.py`, `config/config.py`, `app/routers/config.py` |
| **前端 UI** | `SemanticRoutingCard.tsx`, `components/index.ts`, `Config/index.tsx` |
| **i18n** | `locales/en.json`, `locales/zh.json` |
| **配置** | `pyproject.toml` |

**所有问题均经 `git diff upstream/main HEAD` 确认为本 PR 引入，不存在 upstream 遗留问题。**

---

## 🔴 必须修复（3 个）

### 1. 死代码：`__init__.py` 未使用的 `logger`

- **文件**: `src/qwenpaw/routing/__init__.py` L13-14
- **问题**: 定义了 `logger = logging.getLogger(__name__)` 但整个文件从未使用
- **严重程度**: 🔴 必须修复（死代码）
- **当前代码**:
  ```python
  import logging
  logger = logging.getLogger(__name__)
  ```
- **修复建议**: 删除这两行。如果 `is_routing_available()` 或 `__getattr__` 未来需要日志，再加回来。

---

### 2. 注释错误：`router.py` 提到 "FAISS"

- **文件**: `src/qwenpaw/routing/router.py` L29
- **问题**: docstring 写了 `Optional directory for FAISS index persistence`，但实际实现用的是 NumPy 持久化（`np.save/np.load`），不是 FAISS
- **严重程度**: 🔴 必须修复（误导性注释）
- **当前代码**:
  ```python
  persist_dir:
      Optional directory for FAISS index persistence.
  ```
- **修复建议**: 改为 `Optional directory for index persistence.`

---

### 3. `_get_or_create_router` 缓存比较不完整

- **文件**: `src/qwenpaw/agents/react_agent.py` L452-460
- **问题**: 只比较了 `top_k`、`min_score`、`encoder` 三个字段来判断是否复用缓存的 router。但 `SemanticRoutingConfig` 还有 `max_tools`、`token_budget`、`mandatory_tools` 字段。如果用户只修改了这些字段，缓存不会失效，导致 router 使用过时配置。
- **严重程度**: 🔴 必须修复（逻辑缺陷）
- **当前代码**:
  ```python
  if (
      cached_cfg is not None
      and cached_cfg.top_k == sr_config.top_k
      and cached_cfg.min_score == sr_config.min_score
      and cached_cfg.encoder == sr_config.encoder
  ):
      return cached
  ```
- **修复建议**: 直接比较整个 config 对象：
  ```python
  if (
      cached_cfg is not None
      and cached_cfg.model_dump() == sr_config.model_dump()
  ):
      return cached
  ```
  或者显式补全所有字段比较。

---

## 🟡 建议修复（3 个）

### 4. 异常处理过于宽泛 — 多处 `except Exception: pass`

- **文件与行号**:
  - `routing/index.py` L66-67 (`_get_embedding_config`): `except Exception: pass`
  - `routing/index.py` L122-123 (`_apply_hf_mirror_if_needed`): `except Exception: pass`
  - `routing/router.py` L79-84 (`route` 方法): `except Exception as exc` 有 warning 日志 ✅
- **问题**: 前两处静默吞掉所有异常，配置错误时完全无法排查
- **严重程度**: 🟡 建议修复
- **修复建议**: 至少添加 `logger.debug("...: %s", exc)` 记录异常详情

---

### 5. 硬编码超时 `timeout=60.0`

- **文件**: `src/qwenpaw/routing/index.py` L93
- **问题**: API embedding 请求超时硬编码为 60 秒
- **严重程度**: 🟡 建议修复
- **当前代码**:
  ```python
  resp = httpx.post(url, json=payload, headers=headers, timeout=60.0)
  ```
- **修复建议**: 提取为模块级常量：
  ```python
  _EMBEDDING_API_TIMEOUT_SECONDS = 60.0
  ```

---

### 6. `_cleanup_persist` 后未重置内部状态

- **文件**: `src/qwenpaw/routing/index.py` L356-365（`load` 方法的 except 分支）
- **问题**: `load()` 失败后调用 `_cleanup_persist()` 删除文件，但没有重置 `_vectors`、`_items`、`_hash`。如果 `json.loads` 成功但 `np.load` 失败，`_items` 可能残留部分加载的脏数据。
- **严重程度**: 🟡 建议修复
- **当前代码**:
  ```python
  except Exception as exc:
      logger.warning("Failed to load semantic index: %s. Will rebuild.", exc)
      self._cleanup_persist()
      return False
  ```
- **修复建议**: 在 cleanup 后重置状态：
  ```python
  except Exception as exc:
      logger.warning("Failed to load semantic index: %s. Will rebuild.", exc)
      self._cleanup_persist()
      self._vectors = None
      self._items = []
      self._hash = ""
      return False
  ```

---

## 🟢 已审查无问题（确认通过）

| 文件 | 审查结论 |
|------|---------|
| `routing/config.py` | ✅ Pydantic 模型定义规范，所有字段有默认值和约束 |
| `routing/models.py` | ✅ dataclass 定义清晰，`to_dict/from_dict` 是公共 API 不是死代码 |
| `routing/index.py`（主体） | ✅ 双后端检测、缓存、持久化逻辑正确 |
| `react_agent.py`（hint injection） | ✅ KV-cache-friendly 设计，memory mark 机制正确，finally 块确保清理 |
| `react_agent.py`（`_read_skill_metas`） | ✅ mtime 缓存策略合理 |
| `config.py`（`semantic_routing` 字段） | ✅ 前向引用 + `model_rebuild()` 模式正确 |
| `app/routers/config.py` | ✅ import 正确（black 格式化已修复） |
| `SemanticRoutingCard.tsx` | ✅ 表单绑定正确，条件渲染合理，i18n 覆盖完整 |
| `components/index.ts` | ✅ 导出正确 |
| `Config/index.tsx` | ✅ Tab 注册在 `baseTabs` 末尾，与 upstream `dynamicTabs` 机制兼容 |
| `locales/en.json` / `zh.json` | ✅ i18n key 一一对应 |
| `pyproject.toml` | ✅ `semantic` 可选依赖配置合理 |

---

## 不需要修复的审查项（附理由）

| 审查项 | 结论 | 理由 |
|--------|------|------|
| `_skill_meta_cache` 类级别静态 dict 内存泄漏 | 🟢 可接受 | skill 数量通常 < 50，内存占用可忽略 |
| 每轮对话都计算 embedding | 🟢 设计意图 | query 每次不同，embedding 计算不可避免；已用 `asyncio.to_thread` 避免阻塞事件循环 |
| `config.py` 的 `try: model_rebuild() except ImportError: pass` | 🟢 可接受 | 虽然 `ImportError` 几乎不触发，但作为防御性编程是合理的 |
| `rebuild_sys_prompt` 与 hint injection 冲突 | 🟢 无冲突 | `rebuild_sys_prompt` 只更新第一个 system 消息，hint 是带 mark 的独立 system 消息，通过 `break` 天然隔离 |
| `save()` 的 `indent=2` 性能 | 🟢 可接受 | skill 数量小，JSON 文件大小不构成瓶颈 |
| API Key 安全 | 🟢 可接受 | 遵循 QwenPaw 现有的 `EmbeddingConfig` 模式，API Key 来自配置文件而非用户输入 |

---

## CI 验证状态

| Workflow | 状态 | 结果 |
|----------|------|------|
| NPM Format (tsc + prettier) | ✅ PASSED | 零错误 |
| Pre-commit (16 hooks) | ✅ PASSED | black/flake8/pylint/mypy 全通过 |
| Tests (pytest) | ✅ PASSED | 1646 passed, 1 skipped |

---

## 修复优先级建议

| 优先级 | 问题 # | 预计改动量 |
|--------|--------|-----------|
| **P0 — 提交前必须修** | #1 删除死代码 logger | 2 行 |
| **P0 — 提交前必须修** | #2 修正 FAISS 注释 | 1 行 |
| **P0 — 提交前必须修** | #3 完善缓存比较 | ~5 行 |
| **P1 — 强烈建议修** | #4 改善异常处理 | ~6 行 |
| **P1 — 强烈建议修** | #5 提取超时常量 | ~3 行 |
| **P1 — 强烈建议修** | #6 重置脏状态 | ~3 行 |

**总改动量**: 约 20 行，不影响任何功能逻辑，全部是代码质量改进。
