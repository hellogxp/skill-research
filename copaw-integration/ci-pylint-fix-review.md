# CI pylint 修复方案 Review

> 对 ci-pylint-fix-plan.md 的审阅意见
> 日期: 2026-04-21

---

## 总体评价

方案整体正确，5 个问题都找准了。但有 2 个问题的修复方式建议调整。

---

## 逐条审阅

### 问题 1：`__all__` undefined variable — ✅ 同意删除

删除 `__all__` 是最简单干净的方案。`__getattr__` 已经控制了公开 API，`__all__` 多余。

### 问题 2：unused import — ✅ 同意加注释

`# noqa: F401  # pylint: disable=unused-import` 双注释是标准做法，没问题。

### 问题 3：unnecessary lambda — ⚠️ 建议不改

这个报错在 `config.py:1448`，是 upstream 原有代码，不是我们 PR 引入的。改了反而增加 diff，maintainer 可能会问为什么动了不相关的代码。

如果一定要改，方案本身没问题（去掉 lambda 直接传函数引用），但需要确认 `_default_semantic_routing_config` 是无参函数。

### 问题 4：wrong import position — ⚠️ 建议不改，或最小化处理

这些 C0413 警告全部是 upstream 原有的 import（pydantic、shortuuid、agentscope_runtime 等），不是我们的代码有问题。pylint 误判的原因是我们加了 `if TYPE_CHECKING:` 块，导致它认为后面的 import 位置不对。

方案里建议把 `TYPE_CHECKING` 移到所有 import 之后，但这不符合 Python 社区惯例——`TYPE_CHECKING` 通常紧跟在 `from typing import` 之后。

建议：不改。这些 C0413 在 upstream 的 `.pre-commit-config.yaml` 里已经被 `--disable=C0413` 禁用了（检查一下 pylint args）。如果没禁用，加一行 `# pylint: disable=wrong-import-position` 在 TYPE_CHECKING 块后面即可。

### 问题 5：too many return statements — ⚠️ 建议用 disable 注释而非重构

方案里的合并 guard clause 方案可行，但有一个隐患：改变了执行顺序。

原来的逻辑：
1. 先检查 `is_routing_available()`（轻量，不读配置）
2. 通过后才 `load_config()`（读磁盘）
3. 再检查 `sr_config.enabled`

合并后：
1. 先 `load_config()`（读磁盘）
2. 再一起判断所有条件

如果 routing 不可用（比如没装 sentence-transformers），原来的逻辑在第 1 步就返回了，不会读配置。合并后每次都会读配置，增加了不必要的开销。

建议：直接在方法上加 `# pylint: disable=too-many-return-statements`，不改逻辑。多个 early return 的 guard clause 模式本身是好的代码风格，不应该为了满足 pylint 的数量限制而牺牲可读性。

---

## 最终建议

| # | 问题 | 建议操作 |
|---|------|----------|
| 1 | `__all__` undefined | 删除 `__all__` |
| 2 | unused import | 加 `# pylint: disable=unused-import` |
| 3 | unnecessary lambda | 不改（upstream 原有） |
| 4 | wrong import position | 不改（upstream 原有），或确认 pylint args 已禁用 C0413 |
| 5 | too many return | 加 `# pylint: disable=too-many-return-statements` |

只需要改 3 个地方（问题 1、2、5），不动 upstream 原有代码。
