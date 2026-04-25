# 部署问题记录 - 2026-04-17

## 问题：启动时报 ModuleNotFoundError

### 错误信息

```
ModuleNotFoundError: No module named 'qwenpaw.routing'
```

### 错误位置

文件：`src/qwenpaw/config/config.py`，第 1367 行

```python
from ..routing.config import SemanticRoutingConfig
```

这行代码解析为 `qwenpaw.routing.config`，但 `src/qwenpaw/` 目录下不存在 `routing/` 模块。

### 代码结构现状

```
src/
├── copaw/
│   └── routing/          ← routing 模块在这里
│       ├── __init__.py
│       ├── config.py
│       ├── index.py
│       ├── models.py
│       └── router.py
└── qwenpaw/
    ├── config/
    │   └── config.py     ← 这里引用了 qwenpaw.routing（不存在）
    ├── agents/
    ├── cli/
    └── ...（没有 routing/ 目录）
```

### 问题分析

`qwenpaw/config/config.py` 引用了 `qwenpaw.routing`，但 routing 模块实际位于 `copaw.routing`。

可能原因：
1. rebase 合并冲突时 routing 模块没有被正确合并到 qwenpaw 包
2. import 路径写错了，应该引用 `copaw.routing`

### 建议修复方向

- 确认 routing 模块应该放在 `qwenpaw/routing/` 还是 `copaw/routing/`
- 相应地修改 import 路径或移动模块位置

### 其他错误

启动时还遇到第二个错误：

```
TypeError: BaseModel.model_rebuild() got an unexpected keyword argument '_raise_errors'
```

位置：`src/qwenpaw/config/config.py` 第 1371 行

```python
Config.model_rebuild(_raise_errors=False)
```

Pydantic 2.x 的 `model_rebuild()` 不接受 `_raise_errors` 参数，需要修改为正确的调用方式。
