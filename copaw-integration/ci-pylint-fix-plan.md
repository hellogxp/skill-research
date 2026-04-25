# CI pylint 修复方案

> CI 链接: https://github.com/agentscope-ai/QwenPaw/actions/runs/24674726742/job/72252735533?pr=3117
> 当前 commit: `3a04987e`
> 日期: 2026-04-21

---

## CI 结果概览

Pre-commit Checks 中，除 pylint 外全部通过：

| Hook | 结果 |
|------|------|
| check python ast | ✅ Passed |
| check yaml/xml/toml/json | ✅ Passed |
| check docstring is first | ✅ Passed |
| fix python encoding pragma | ✅ Passed |
| detect private key | ✅ Passed |
| trim trailing whitespace | ✅ Passed |
| Add trailing commas | ✅ Passed |
| mypy | ✅ Passed |
| black | ✅ Passed |
| flake8 | ✅ Passed |
| prettier | ✅ Passed |
| **pylint** | ❌ **Failed** |

pylint 评分: **9.99/10**

---

## pylint 报错详情 & 修复方案（共 5 个问题）

### 问题 1：`routing/__init__.py:50-55` — E0603 Undefined variable in `__all__`

**报错**:
```
src/qwenpaw/routing/__init__.py:50:4: E0603: Undefined variable name 'SemanticRoutingConfig' in __all__
src/qwenpaw/routing/__init__.py:51:4: E0603: Undefined variable name 'IndexItem' in __all__
src/qwenpaw/routing/__init__.py:52:4: E0603: Undefined variable name 'SearchHit' in __all__
src/qwenpaw/routing/__init__.py:53:4: E0603: Undefined variable name 'RoutingResult' in __all__
src/qwenpaw/routing/__init__.py:54:4: E0603: Undefined variable name 'SemanticIndex' in __all__
src/qwenpaw/routing/__init__.py:55:4: E0603: Undefined variable name 'SkillRouter' in __all__
```

**原因**: 我们用了 `__getattr__` 懒加载模式，`__all__` 里声明的名字在模块级别没有直接定义，pylint 不理解这个模式。

**当前代码** (`routing/__init__.py:47-56`):
```python
__all__ = [
    "is_routing_available",
    "SemanticRoutingConfig",
    "IndexItem",
    "SearchHit",
    "RoutingResult",
    "SemanticIndex",
    "SkillRouter",
]
```

**修复方案**: 直接删除 `__all__`。因为 `__getattr__` 已经控制了模块的公开 API，`__all__` 在这里是多余的。

**替代方案**: 如果要保留 `__all__`，可以在定义前加 `# pylint: disable=undefined-all-variable`。

---

### 问题 2：`routing/index.py:187` — W0611 Unused import

**报错**:
```
src/qwenpaw/routing/index.py:187:12: W0611: Unused import sentence_transformers (unused-import)
```

**原因**: 这个 import 只是用来检测 `sentence_transformers` 是否可用（feature detection），不是真正使用它。已经加了 `# noqa: F401`（flake8 认），但 pylint 不认 noqa 注释。

**当前代码** (`index.py:187`):
```python
import sentence_transformers  # noqa: F401
```

**修复方案**: 加 pylint 的 disable 注释：
```python
import sentence_transformers  # noqa: F401  # pylint: disable=unused-import
```

---

### 问题 3：`config.py:1448` — W0108 Unnecessary lambda

**报错**:
```
src/qwenpaw/config/config.py:1448:24: W0108: Lambda may not be necessary (unnecessary-lambda)
```

**当前代码** (`config.py:1448`):
```python
semantic_routing: "SemanticRoutingConfig" = Field(
    default_factory=lambda: _default_semantic_routing_config(),
    ...
)
```

**修复方案**: 去掉 lambda 包装，直接传函数引用：
```python
semantic_routing: "SemanticRoutingConfig" = Field(
    default_factory=_default_semantic_routing_config,
    ...
)
```

**注意**: 需要确认 `_default_semantic_routing_config` 函数存在且无参数。

---

### 问题 4：`config.py:22-35` — C0413 Wrong import position

**报错**:
```
src/qwenpaw/config/config.py:22:0: C0413: Import "from pydantic import ..." should be placed at the top of the module
src/qwenpaw/config/config.py:29:0: C0413: Import "import shortuuid" should be placed at the top
src/qwenpaw/config/config.py:30:0: C0413: Import "from agentscope_runtime..." should be placed at the top
src/qwenpaw/config/config.py:34:0: C0413: Import "from .timezone import ..." should be placed at the top
src/qwenpaw/config/config.py:35:0: C0413: Import "from ..constant import ..." should be placed at the top
```

**原因**: 我们 PR 在第 8 行加了 `TYPE_CHECKING` import 块（第 18-20 行），导致后面第 22 行开始的 import 被 pylint 认为位置不对。upstream/main 原始代码没有 `TYPE_CHECKING` 块，所以没有这个问题。

**当前代码** (`config.py:1-35`):
```python
from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import (
    Optional, Union, Dict, List, Literal, Any, Set,
    TYPE_CHECKING,
)

if TYPE_CHECKING:
    from ..routing.config import SemanticRoutingConfig   # <-- 这个块导致后面的 import 被认为位置不对

from pydantic import (          # <-- pylint 认为这应该在 TYPE_CHECKING 块之前
    BaseModel, Field, ...
)
import shortuuid               # <-- 同上
...
```

**修复方案**: 把 `TYPE_CHECKING` 块移到所有 import 之后（但在类定义之前）：

```python
from __future__ import annotations

import os
import json
import re
from pathlib import Path
from typing import Optional, Union, Dict, List, Literal, Any, Set

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
import shortuuid
from agentscope_runtime.engine.schemas.exception import ConfigurationException
from .timezone import detect_system_timezone
from ..constant import ...

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from ..routing.config import SemanticRoutingConfig
```

**替代方案**: 在 `TYPE_CHECKING` 块前加 `# pylint: disable=wrong-import-position`，但这不太优雅。

---

### 问题 5：`react_agent.py:350` — R0911 Too many return statements

**报错**:
```
src/qwenpaw/agents/react_agent.py:350:4: R0911: Too many return statements (7/6) (too-many-return-statements)
```

**原因**: 我们新增的 `_build_skill_hint()` 方法有 7 个 return 语句，pylint 默认限制是 6 个。

**当前代码中的 7 个 return**:
```python
def _build_skill_hint(self, query: str) -> str:
    try:
        if not is_routing_available():
            return ""                    # return 1
        ...
        if sr_config is None or not sr_config.enabled:
            return ""                    # return 2
        ...
        if not skill_names or skills_dir is None:
            return ""                    # return 3
        ...
        if result.bypassed:
            return ""                    # return 4
        ...
        if not hints:
            return ""                    # return 5
        ...
        return hint_text                 # return 6
    except Exception:
        ...
        return ""                        # return 7
```

**修复方案**: 合并前 3 个 guard clause 为一个条件判断：

```python
def _build_skill_hint(self, query: str) -> str:
    try:
        from ..routing import is_routing_available
        from ..config.utils import load_config

        config = load_config()
        sr_config = getattr(config, "semantic_routing", None)

        # Guard: check all preconditions
        if (
            not is_routing_available()
            or sr_config is None
            or not sr_config.enabled
        ):
            return ""                    # return 1 (merged)

        skill_names = getattr(self, "_effective_skill_names", [])
        skills_dir = getattr(self, "_working_skills_dir", None)
        if not skill_names or skills_dir is None:
            return ""                    # return 2
        ...
        if result.bypassed:
            return ""                    # return 3
        ...
        if not hints:
            return ""                    # return 4
        ...
        return hint_text                 # return 5
    except Exception:
        return ""                        # return 6
```

这样从 7 个减少到 6 个，刚好满足 pylint 限制。

**替代方案**: 在方法上加 `# pylint: disable=too-many-return-statements`。

---

## 修复优先级

| # | 问题 | 风险 | 建议 |
|---|------|------|------|
| 1 | `__all__` undefined variable | 低 | 删除 `__all__` |
| 2 | unused import | 低 | 加 pylint disable 注释 |
| 3 | unnecessary lambda | 低 | 去掉 lambda |
| 4 | wrong import position | 中 | 移动 TYPE_CHECKING 块到所有 import 之后 |
| 5 | too many return statements | 中 | 合并 guard clause |

修复后需要：
1. 本地再跑一次 `pre-commit run --all-files` 确认不引入新问题
2. Commit + force push
3. 等 CI 重新跑
