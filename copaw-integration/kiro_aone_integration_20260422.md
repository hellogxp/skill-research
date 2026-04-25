# PR #3117 综合代码审查报告

> 合并自 Kiro Review (2026-04-22 21:20) + Aone Review (2026-04-22 21:20)
> PR 分支: `feat/semantic-skill-routing`
> 范围: 14 个文件, +1125 insertions, -10 deletions

---

## 🔴 必须修复（4 个）

### 1. 死代码：`__init__.py` 未使用的 `logger`
- 来源: Aone
- 文件: `src/qwenpaw/routing/__init__.py` L13-14
- 问题: `logger = logging.getLogger(__name__)` 定义后从未使用
- 修复: 删除 `import logging` 和 `logger = ...` 两行

### 2. 死代码：`config.py` 中 3 个配置字段从未使用
- 来源: Kiro
- 文件: `src/qwenpaw/routing/config.py`
- 问题: `max_tools`、`token_budget`、`mandatory_tools` 没有任何代码引用，是 PR2 的预留字段
- 修复: 删掉这 3 个字段，等 PR2 再加

### 3. 注释错误：`router.py` docstring 提到 "FAISS"
- 来源: Kiro + Aone
- 文件: `src/qwenpaw/routing/router.py` L29
- 问题: `Optional directory for FAISS index persistence` — FAISS 已删，用的是 numpy
- 修复: 改为 `Optional directory for index persistence.`

### 4. 缓存比较不完整（如果保留问题 2 的字段）
- 来源: Aone
- 文件: `src/qwenpaw/agents/react_agent.py` L452-460
- 问题: `_get_or_create_router` 只比较 `top_k`/`min_score`/`encoder`，漏了其他字段
- 修复: 如果删掉问题 2 的 3 个字段，这个问题自动消失。如果保留，改用 `cached_cfg.model_dump() == sr_config.model_dump()`

---

## 🟡 建议修复（5 个）

### 5. 异常处理过于宽泛 — `except Exception: pass`
- 来源: Aone
- 文件: `routing/index.py` L66-67, L122-123
- 问题: `_get_embedding_config()` 和 `_apply_hf_mirror_if_needed()` 静默吞掉所有异常
- 修复: 加 `logger.debug("...: %s", exc)`

### 6. 硬编码超时 `timeout=60.0`
- 来源: Aone
- 文件: `routing/index.py` L93
- 修复: 提取为模块级常量 `_EMBEDDING_API_TIMEOUT_SECONDS = 60.0`

### 7. `_cleanup_persist` 后未重置内部状态
- 来源: Aone
- 文件: `routing/index.py` `load()` 方法的 except 分支
- 问题: 删除文件后 `_vectors`/`_items`/`_hash` 可能残留脏数据
- 修复: cleanup 后加 `self._vectors = None; self._items = []; self._hash = ""`

### 8. `__getattr__` lazy import 未被使用
- 来源: Kiro
- 文件: `routing/__init__.py` L50-68
- 问题: 所有使用 SkillRouter 等的地方都直接 import 子模块，不走 `__getattr__`
- 修复: 删掉或加注释说明是公开 API

### 9. `_skill_meta_cache` 类变量多实例共享
- 来源: Kiro
- 文件: `react_agent.py` L479
- 问题: 多 agent 实例不同 workspace 时，同名 skill 的 cache 会互相覆盖
- 风险: 低（当前只有单实例）
- 修复: 改 cache key 为 `(skills_dir, name)` 或加注释说明限制

---

## 🟢 无需修改

| 项目 | 结论 |
|------|------|
| `_build_skill_hint` 每次调 `load_config()` | Kiro 提出，需确认是否有内部缓存。如果有则无需改 |
| `routing/models.py` 的 `to_dict/from_dict` | Aone 确认是公共 API，不是死代码 |
| `_skill_meta_cache` 内存泄漏 | Aone 确认 skill 数量 < 50，可忽略 |
| hint injection 的 memory mark 机制 | 两方确认正确，finally 块确保清理 |
| `config.py` 的 `try: model_rebuild() except: pass` | Aone 确认防御性编程合理 |

---

## 修复优先级

| 优先级 | 问题 | 改动量 |
|--------|------|--------|
| P0 | #1 删 logger 死代码 | 2 行 |
| P0 | #2 删 3 个未使用字段 | ~15 行 |
| P0 | #3 改 FAISS docstring | 1 行 |
| P0 | #4 缓存比较（如果保留字段） | ~5 行 |
| P1 | #5 改善异常处理 | ~6 行 |
| P1 | #6 提取超时常量 | ~3 行 |
| P1 | #7 重置脏状态 | ~3 行 |
| P2 | #8 清理 `__getattr__` | ~20 行 |
| P2 | #9 cache key 改进 | ~3 行 |

总改动量约 50 行，全部是代码质量改进，不影响功能逻辑。
