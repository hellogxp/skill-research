# CI pylint 修复 — 实际改动详情

> 日期: 2026-04-21
> 基于 commit: `3a04987e`
> 本地 pre-commit 验证: ✅ 我们 PR 引入的 5 个 pylint 问题全部消除

---

## 改动总览

共修改 **4 个文件**，改动极小（净减少 10 行）：

| 文件 | 改动类型 | 行数变化 |
|------|----------|----------|
| `routing/__init__.py` | 删除 `__all__` 块 | -12 行 |
| `routing/index.py` | 加 1 行 pylint 注释 | +1 行 |
| `config/config.py` | 加 1 行 pylint 注释 + 去掉 lambda | +1 行, ~1 行 |
| `agents/react_agent.py` | 加 1 行 pylint 注释 | +1 行 |

---

## 逐文件改动

### 1. `src/qwenpaw/routing/__init__.py` — 删除 `__all__`

**问题**: E0603 Undefined variable name in `__all__`（6 处）

**原因**: `__getattr__` 懒加载模式下，`__all__` 里声明的名字在模块级别没有直接定义，pylint 不理解这个模式。

**改动**: 删除整个 `__all__` 块。`__getattr__` 已经控制了模块的公开 API，`__all__` 多余。

```diff
     return False
 
 
-# Lazy public API
-__all__ = [
-    "is_routing_available",
-    "SemanticRoutingConfig",
-    "IndexItem",
-    "SearchHit",
-    "RoutingResult",
-    "SemanticIndex",
-    "SkillRouter",
-]
-
-
 def __getattr__(name: str):
```

**影响**: 无功能影响。`__all__` 只影响 `from routing import *` 的行为，而项目中没有使用 `import *`。`__getattr__` 仍然正常工作。

---

### 2. `src/qwenpaw/routing/index.py` — 加 pylint disable 注释

**问题**: W0611 Unused import sentence_transformers

**原因**: 这个 import 只用于检测 `sentence_transformers` 是否可用（feature detection），不是真正使用它。已有 `# noqa: F401`（flake8 认），但 pylint 不认 noqa。

**改动**: 在 import 上方加 `# pylint: disable-next=unused-import`。

```diff
         # Priority 2: Local sentence-transformers
         try:
+            # pylint: disable-next=unused-import
             import sentence_transformers  # noqa: F401
```

**为什么不放同一行**: 双注释会超过 79 字符的 flake8 行长限制。`disable-next` 作用于下一行，效果等价。

**影响**: 无功能影响，纯注释。

---

### 3. `src/qwenpaw/config/config.py` — 两处改动

#### 3a. 加 `# pylint: disable=wrong-import-position`

**问题**: C0413 Import should be placed at the top of the module（4 处）

**原因**: 我们 PR 在 import 区域加了 `if TYPE_CHECKING:` 块，导致后面的 pydantic、shortuuid 等 import 被 pylint 认为位置不对。

**改动**: 在 `TYPE_CHECKING` 块后、pydantic import 前加一行 disable 注释。

```diff
 if TYPE_CHECKING:
     from ..routing.config import SemanticRoutingConfig
 
+# pylint: disable=wrong-import-position
 from pydantic import (
     BaseModel,
     Field,
```

**为什么用 `disable` 而不是 `disable-next`**: `disable` 作用于后续所有行，可以一次性覆盖后面的 shortuuid、agentscope_runtime 等多个 import。`disable-next` 只作用于下一行。

**影响**: 无功能影响，纯注释。

#### 3b. 去掉 unnecessary lambda

**问题**: W0108 Lambda may not be necessary

**改动**: 去掉 lambda 包装，直接传函数引用。

```diff
     semantic_routing: "SemanticRoutingConfig" = Field(
-        default_factory=lambda: _default_semantic_routing_config(),
+        default_factory=_default_semantic_routing_config,
         description="Semantic skill routing configuration. "
```

**影响**: 功能等价。`default_factory` 接受一个无参 callable，`_default_semantic_routing_config` 本身就是无参函数，不需要 lambda 包装。

---

### 4. `src/qwenpaw/agents/react_agent.py` — 加 pylint disable 注释

**问题**: R0911 Too many return statements (7/6)

**原因**: `_build_skill_hint()` 方法有 7 个 return 语句（6 个 early return + 1 个正常 return），pylint 默认限制是 6 个。

**改动**: 在方法定义上方加 `# pylint: disable-next=too-many-return-statements`。

```diff
+    # pylint: disable-next=too-many-return-statements
     def _build_skill_hint(self, query: str) -> str:
         """Build a skill routing hint for the given user query.
```

**为什么不重构减少 return**: 多个 early return 的 guard clause 模式是好的代码风格。如果合并 guard clause 会改变执行顺序（原来先检查 `is_routing_available()` 轻量操作，通过后才 `load_config()` 读磁盘），增加不必要的开销。

**影响**: 无功能影响，纯注释。

---

## 本地验证结果

```
check python ast ............... Passed
check docstring is first ....... Passed
fix python encoding pragma ..... Passed
detect private key ............. Passed
trim trailing whitespace ....... Passed
Add trailing commas ............ Passed
black .......................... Passed  ✅
flake8 ......................... Passed  ✅
pylint ......................... 仅剩 upstream 原有的 E1131（Python 3.9 不支持 X|Y 语法）  ✅
```

pylint 评分从 9.56 提升到 **9.60/10**。

剩余的 mypy 和 pylint E1131 错误全部是 upstream 原有的 `X | Y` 语法问题（Python 3.9 不支持），CI 使用 Python 3.10 不会有这些问题。
