# PR #3117 CI 失败分析与修复报告

## 1. CI 失败概况

**PR**: [feat/semantic-skill-routing #3117](https://github.com/agentscope-ai/QwenPaw/pull/3117)
**失败的 CI Run**: `24728166763` (commit `69054f57`)
**涉及 Workflows**: Tests, NPM Format (website & console)

### 失败 Job 清单

| Job 名称 | 失败步骤 | 错误信息 |
|----------|---------|---------|
| Unit Tests - py3.10 - macos-latest | Build console frontend | `'SemanticRoutingPage' is declared but its value is never read.` |
| Unit Tests - py3.10 - ubuntu-latest | Build console frontend | 同上 |
| Unit Tests - py3.10 - windows-latest | Build console frontend | 同上 |
| Unit Tests - py3.13 - ubuntu-latest | Build console frontend | 同上 |
| Integrated Tests - py3.10 - macos-latest | Build console frontend | 同上 |
| Integrated Tests - py3.10 - ubuntu-latest | Build console frontend | 同上 |
| Integrated Tests - py3.10 - windows-latest | Build console frontend | 同上 |
| Integrated Tests - py3.13 - ubuntu-latest | Build console frontend | 同上 |
| Coverage Report | Build console frontend | 同上 |
| Test Summary | Check test results | 前置 job 全部失败 |
| console format check (NPM Format) | Run format check | 同上（`tsc -b --noEmit` 编译失败） |

**关键结论**: 所有 11 个失败 Job 的**唯一根因**是 TypeScript 编译错误，Python 单元测试**根本没有执行到**（被 skip 了）。

---

## 2. 根因分析

### 2.1 错误来源

`console/src/layouts/MainLayout/index.tsx` 第 41 行：

```typescript
const SemanticRoutingPage = lazyImportWithRetry(
  "../../pages/Settings/SemanticRouting",
);
```

这个声明引用了一个**不存在的页面模块** `pages/Settings/SemanticRouting`，且声明后**未在任何 Route 中使用**，导致 TypeScript 编译报错：

> `TS6133: 'SemanticRoutingPage' is declared but its value is never read.`

### 2.2 为什么这个声明不应该存在

在 PR 的开发历史中，`SemanticRouting` 的 UI 经历了一次**架构重构**：

| Commit | 操作 |
|--------|------|
| `6d99e12c` feat(routing): HF mirror, min_score filter, optional deps, and console UI | 初始实现：创建了独立的 `pages/Settings/SemanticRouting/` 页面，并在 `MainLayout` 中添加了路由 |
| `0cd012f6` feat(routing): add API embedding support and refactor UI | **重构 UI**：删除了独立页面（-201 行），改为 `SemanticRoutingCard` 组件嵌入 Agent Config 页面（+53 行） |
| `85b05b88` fix: remove stale semantic-routing route and fix Pydantic forward ref | **清理路由**：从 `MainLayout` 中删除了 `/semantic-routing` 路由和 Sidebar 菜单项 |

### 2.3 为什么 rebase 后又出现了

在 rebase 到最新的 `upstream/main` 时，upstream 有一个改动将 `lazyWithRetry` 重命名为 `lazyImportWithRetry`（commit `713a2cb7`）。这导致 `MainLayout/index.tsx` 产生了 rebase 冲突。

在解决冲突时，upstream 的新版本文件中包含了所有 lazy import 声明（使用新的 `lazyImportWithRetry` 函数名），而我们的分支在 commit `85b05b88` 中已经删除了 `SemanticRoutingPage` 的声明。冲突解决时，**错误地保留了 upstream 模板中的 `SemanticRoutingPage` 声明**，导致这个已被删除的声明又被带回来了。

---

## 3. 修复内容

### 修复 Commit: `ed200c98`

**文件**: `console/src/layouts/MainLayout/index.tsx`

**改动**: 删除 3 处多余代码（共 -4 行）

#### 3.1 删除 lazy import 声明（第 42-44 行）

```diff
 const BackupsPage = lazyImportWithRetry("../../pages/Settings/Backups");
-const SemanticRoutingPage = lazyImportWithRetry(
-  "../../pages/Settings/SemanticRouting",
-);
```

#### 3.2 删除多余空行（prettier 格式修复）

```diff
 const BackupsPage = lazyImportWithRetry("../../pages/Settings/Backups");
-
 const { Content } = Layout;
```

**修复后效果**: `MainLayout/index.tsx` 与 `upstream/main` **完全一致**（`git diff upstream/main -- console/src/layouts/MainLayout/index.tsx` 输出为空），即我们的 PR 对该文件不再有任何改动。

---

## 4. SemanticRouting UI 的正确位置

修复后，SemanticRouting 的 UI 以 `SemanticRoutingCard` 组件的形式嵌入在 **Agent Config 页面**中，而非独立页面：

| 文件 | 作用 |
|------|------|
| `console/src/pages/Agent/Config/components/SemanticRoutingCard.tsx` | 组件实现（新增 53 行） |
| `console/src/pages/Agent/Config/components/index.ts` | 导出组件 |
| `console/src/pages/Agent/Config/index.tsx` | 在 Tabs 中使用 `<SemanticRoutingCard />` |

---

## 5. 本地验证结果

在 push 前，已对所有 CI 检查项进行了本地验证：

### 5.1 前端检查

| 检查项 | 命令 | 结果 |
|--------|------|------|
| TypeScript 编译 | `npx tsc -b --noEmit` | ✅ 通过（exit code 0） |
| Prettier 格式 | `npx prettier --check <所有前端改动文件>` | ✅ 通过 |
| ESLint | `npx eslint <所有前端改动文件>` | ✅ 通过 |
| npm run build | `npm run build` (console 目录) | ✅ 构建成功 |

### 5.2 Python 检查

| 检查项 | 命令 | 结果 |
|--------|------|------|
| Black 格式 (v23.3.0) | `black --check --line-length=79 <8个Python文件>` | ✅ 通过 |
| Flake8 | `flake8 --extend-ignore=E203 --max-line-length=79 <8个Python文件>` | ✅ 通过 |
| Pylint | `pylint --disable=<完整disable列表> <8个Python文件>` | ✅ 通过（E1131/R0917 是 Python 3.9 本地环境误报，CI 用 3.10+） |
| Python 语法 | `python3 -c "import ast; ast.parse(...)"` (5个新增文件) | ✅ 通过 |
| Trailing whitespace | `grep -rn ' $' <8个Python文件>` | ✅ 通过 |

### 5.3 Git 状态

| 检查项 | 结果 |
|--------|------|
| 工作区状态 | clean（`nothing to commit, working tree clean`） |
| PR 改动文件数 | 14 个文件（vs upstream/main） |
| 无多余改动 | ✅ `MainLayout/index.tsx` 不再出现在 diff 中 |

---

## 6. PR 改动文件总览

```
 console/src/locales/en.json                        |   8 +    (i18n 翻译)
 console/src/locales/zh.json                        |   8 +    (i18n 翻译)
 .../Config/components/SemanticRoutingCard.tsx       |  53 +++ (新增组件)
 console/src/pages/Agent/Config/components/index.ts |   1 +    (导出组件)
 console/src/pages/Agent/Config/index.tsx           |  14 +    (使用组件)
 pyproject.toml                                     |   5 +-   (添加 [semantic] 依赖组)
 src/qwenpaw/agents/react_agent.py                  | 186 +   (hint 注入逻辑)
 src/qwenpaw/app/routers/config.py                  |  27 +   (API 路由)
 src/qwenpaw/config/config.py                       |  43 +-  (配置模型)
 src/qwenpaw/routing/__init__.py                    |  65 +++ (路由模块入口)
 src/qwenpaw/routing/config.py                      |  58 +++ (路由配置)
 src/qwenpaw/routing/index.py                       | 414 +++ (索引实现)
 src/qwenpaw/routing/models.py                      |  85 +++ (数据模型)
 src/qwenpaw/routing/router.py                      | 161 +++ (路由器)
 14 files changed, 1120 insertions(+), 8 deletions(-)
```

---

## 7. 本地完整复现 CI Workflows

以下是按照官方 GitHub CI 的完整步骤在本地复现的结果。

### 7.1 Workflow 1: NPM Format (`npm-format.yml`)

CI 命令：`cd console && npm ci && npm run format:check`
（format:check = `tsc -b --noEmit && prettier --check .`）

```
本地复现：
  1. rm -rf node_modules && npm ci     → ✅ 成功
  2. tsc -b --noEmit                   → ✅ 通过（exit code 0，无 TS 错误）
  3. prettier --check .                → ⚠️ 51 files have style issues
```

> **注**：prettier 报出的 51 个文件全部是 `dist/` 目录下的构建产物和 `registerHostModules.ts`（自动生成文件），
> **不是我们 PR 改动的文件**。CI 环境从干净的 checkout 开始，没有 `dist/` 目录，所以不会有这个问题。
> 我们所有改动的前端文件单独检查全部通过：
> `prettier --check SemanticRoutingCard.tsx index.ts index.tsx en.json zh.json MainLayout/index.tsx` → ✅ All matched files use Prettier code style!

### 7.2 Workflow 2: Pre-commit Checks (`pre-commit.yml`)

CI 命令：`pip install -e ".[dev]" && pre-commit run --all-files`
（包含 black 23.3.0 / flake8 6.1.0 / pylint v3.0.2 / mypy v1.7.0 等）

对 PR 改动的 8 个 Python 文件逐项验证：

| 检查项 | 命令 | 结果 |
|--------|------|------|
| **Black** (v23.3.0, `--line-length=79`) | `black --check --line-length=79 <8 files>` | ✅ `8 files would be left unchanged` |
| **Flake8** (`--extend-ignore=E203 --max-line-length=79`) | `flake8 <8 files>` | ✅ 无输出（0 个错误） |
| **Pylint** (带 CI 完整 disable 列表) | `pylint --disable=... <8 files>` | ✅ 9.69/10（仅 E1131/R0917，见下文） |
| **check-ast** (Python 语法) | `python3 -c "import ast; ast.parse(...)"` | ✅ 8 个文件全部通过 |
| **trailing-whitespace** | `grep -rn ' $' <8 files>` | ✅ 无行尾空格 |

> **关于 Pylint E1131/R0917**：
> - E1131 `unsupported operand type(s) for |` — 因为本地 Python 3.9 不支持 `str | None` 类型联合语法（PEP 604），CI 使用 Python 3.10+ 不会触发
> - R0917 `too-many-positional-arguments` — 存在于 upstream 原有代码中（非 PR 引入），且 CI 的 pylint v3.0.2 不含此规则（v3.2+ 才有）
> - 这两类错误均为本地 Python 3.9 环境的误报，**不影响 CI 通过**

## 7. 严格对照官方 CI 完整复现（2026-04-22 第二轮验证）

> **本轮验证严格按照 `.github/workflows/` 中三个 Workflow 的每一个步骤、每一个依赖版本执行，确保与 CI 完全一致。**

### 7.1 环境信息

| 项 | 本地 | CI |
|----|------|-----|
| Node.js | v25.8.1 | v20 (LTS) |
| npm | 11.11.0 | npm ci |
| Python | 3.10.20 (brew, 独立 venv) | 3.10 / 3.13 |
| OS | macOS arm64 (Darwin 24.5.0) | ubuntu / macos / windows |

> **Node.js 版本差异说明**：本地 v25.8.1 > CI v20，向下兼容，对 tsc 编译和 prettier 检查无影响。

### 7.2 Workflow 1: NPM Format (`npm-format.yml`)

**CI 步骤对照**：
```
checkout → setup-node@20 → npm ci → npm run format:check
format:check = "tsc -b --noEmit && prettier --check ."
```

**本地严格复现**：
```bash
cd copaw-upstream/console
rm -rf dist                    # CI 是 fresh checkout，不会有 dist/
npm ci                         # ✅ added 1022 packages in 1m
npm run format:check           # 包含 tsc + prettier
```

| 步骤 | 结果 |
|------|------|
| `tsc -b --noEmit` | ✅ exit code 0，零错误 |
| `prettier --check .` | ✅ All matched files use Prettier code style! |

**✅ Workflow 1: NPM Format PASSED**

### 7.3 Workflow 2: Pre-commit Checks (`pre-commit.yml`)

**CI 步骤对照**：
```
checkout → setup-python@3.10
→ pip install setuptools==68.2.2 wheel==0.41.2     ← 特定版本！
→ pip install -q -e ".[dev]"
→ pre-commit install
→ pre-commit run --all-files
```

**本地严格复现**：
```bash
cd copaw-upstream
python3.10 -m venv .venv-precommit        # 独立 venv
source .venv-precommit/bin/activate
pip install setuptools==68.2.2 wheel==0.41.2   # ✅ 与 CI 完全一致
pip install -q -e ".[dev]"                      # ✅ 安装成功
pre-commit install                              # ✅ installed
pre-commit run --all-files                      # ✅ 全部通过
```

| 检查项 | 结果 |
|--------|------|
| check python ast | ✅ Passed |
| sort simple yaml files | ⏭️ Skipped (no files) |
| check yaml | ✅ Passed |
| check xml | ✅ Passed |
| check toml | ✅ Passed |
| check docstring is first | ✅ Passed |
| check json | ✅ Passed |
| fix python encoding pragma | ✅ Passed |
| detect private key | ✅ Passed |
| trim trailing whitespace | ✅ Passed |
| Add trailing commas | ✅ Passed |
| mypy | ✅ Passed |
| black | ✅ Passed |
| flake8 | ✅ Passed |
| pylint | ✅ Passed |
| prettier | ✅ Passed |

**✅ Workflow 2: Pre-commit Checks PASSED（全部 16 项）**

### 7.4 Workflow 3: Tests (`tests.yml`)

**CI 步骤对照**：
```
checkout
→ setup-node@20 → cd console && npm ci && npm run build
→ rm -rf src/qwenpaw/console/* && mkdir -p src/qwenpaw/console && cp -R console/dist/* src/qwenpaw/console/
→ setup-python@3.10 → pip install --upgrade pip → pip install -e ".[dev,full]"
→ pytest tests/unit -v
```

**本地严格复现**：
```bash
# Step 1: Build console frontend
cd copaw-upstream/console && npm ci && npm run build   # ✅ built in 15.61s

# Step 2: Copy console build into package（与 CI 命令 100% 一致）
cd copaw-upstream
rm -rf src/qwenpaw/console/*
mkdir -p src/qwenpaw/console
cp -R console/dist/* src/qwenpaw/console/              # ✅ copied

# Step 3: 独立 venv + 安装依赖
python3.10 -m venv .venv-tests
source .venv-tests/bin/activate
pip install --upgrade pip                               # ✅ pip 26.0.1
pip install -e ".[dev,full]"                            # ✅ 安装成功

# Step 4: 运行单元测试
pytest tests/unit -v                                    # ✅ 全部通过
```

| 步骤 | CI 命令 | 本地结果 |
|------|---------|---------|
| Build console frontend | `cd console && npm ci && npm run build` | ✅ built in 15.61s |
| Copy console build | `rm -rf ... && cp -R console/dist/* src/qwenpaw/console/` | ✅ 复制完成 |
| Install dependencies | `pip install -e ".[dev,full]"` | ✅ 安装成功（Python 3.10.20 venv） |
| Run unit tests | `pytest tests/unit -v` | ✅ **1641 passed, 1 skipped, 52 warnings (78.92s)** |

> **Integrated Tests 说明**：CI 中 `tests/integrated` 目录不存在（实际目录为 `tests/integration`），CI 的 `compgen -G "tests/integrated/*.py"` 检查会返回 `has_tests=false`，该 job 会被跳过。本地已确认目录不存在。

**✅ Workflow 3: Tests PASSED**

### 7.5 复现总结

| Workflow | CI 文件 | 状态 | 关键结果 |
|----------|---------|------|---------|
| NPM Format | `npm-format.yml` | ✅ **PASSED** | tsc 零错误，prettier 格式全部通过 |
| Pre-commit Checks | `pre-commit.yml` | ✅ **PASSED** | 16/16 hooks 通过（含 setuptools==68.2.2 特定版本） |
| Tests (unit) | `tests.yml` | ✅ **PASSED** | 1641 passed, 1 skipped, 52 warnings |
| Tests (integrated) | `tests.yml` | ⏭️ **SKIPPED** | `tests/integrated` 目录不存在（CI 也会 skip） |

### 7.6 与之前验证的差异说明

| 差异点 | 之前（第一轮） | 本次（第二轮） |
|--------|---------------|---------------|
| setuptools 版本 | 未特别指定 | ✅ 严格安装 `setuptools==68.2.2 wheel==0.41.2` |
| console build copy | 未执行 | ✅ 严格按 CI 执行 `rm -rf + cp -R` |
| venv 隔离 | 共用环境 | ✅ 每个 workflow 独立 venv |
| dist/ 目录影响 | 未注意 | ✅ 确认 CI 无 dist/，删除后重新验证 |
| prettier 检查 | 含 dist/ 假阳性失败 | ✅ 删除 dist/ 后通过 |

---

## 8. 第三轮：Rebase 到最新 upstream/main（2026-04-22）

### 8.1 背景

upstream/main 从 `713a2cb7` 前进到 `6a7a01c1`，新增 22 个 commit，包含多个与我们 PR 文件重叠的变更：
- `#3548` feat(memory): rebuild memory & context — `react_agent.py` 大改
- `#3696` refactor(plugins): switch to dynamic module registration — `registerHostModules.ts` 重构
- `#3599` feat(agents): add per-agent model assignment — Agent Config 页面变更
- `#3676` chore(console): add `.prettierignore`
- `#3692` chore(console): comment out vitePatchable plugin

### 8.2 Rebase 冲突解决

共 3 个冲突文件，均在 commit 6/18 (`0cd012f6`) 中出现：

| 文件 | 冲突原因 | 解决方式 |
|------|---------|---------|
| `console/src/pages/Agent/Config/components/index.ts` | upstream 删除旧组件、新增 `LightContextCard`/`ReMeLightMemoryCard`；我们新增 `SemanticRoutingCard` | 保留 upstream 新组件 + 我们的 `SemanticRoutingCard`；移除不存在的 `EmbeddingConfigCard` |
| `console/src/pages/Agent/Config/index.tsx` | upstream 改用 `dynamicTabs`（backend mapping 动态生成）；我们的旧代码是硬编码 tabs | 采用 upstream 的 `dynamicTabs` 结构，在 `baseTabs` 末尾追加 `semanticRouting` tab |
| `src/qwenpaw/app/routers/config.py` | upstream 新增 `SIPChannelConfig`；我们新增 `SemanticRoutingConfig` | 两个都保留 |

### 8.3 额外修复

- **black 格式化修复**：`sed` 替换导致 `config.py` 中两个 import 被挤到同一行，black 自动修复后重新 commit

### 8.4 Rebase 后验证结果

| Workflow | 状态 | 关键结果 |
|----------|------|---------|
| NPM Format | ✅ **PASSED** | tsc 零错误，prettier 全部通过 |
| Pre-commit Checks | ✅ **PASSED** | 16/16 hooks 通过（含 setuptools==68.2.2） |
| Tests (unit) | ✅ **PASSED** | **1646 passed**, 1 skipped, 52 warnings (78.88s) |

> 测试数量从 1641 → 1646（upstream 新增 5 个测试），全部通过。

### 8.5 当前状态

- **最新 commit**: `248cd754` 已 force push
- **base**: `6a7a01c1` (upstream/main 最新)
- **diff**: 14 files, +1125 insertions, -10 deletions
- **CI**: 等待 maintainer approve 新的 CI run

---

## 附录 A: CI Workflow 结构速览

```
┌─ NPM Format (npm-format.yml) ─────────────────────┐
│  console format check:                              │
│    npm ci → tsc -b --noEmit → prettier --check .    │
└─────────────────────────────────────────────────────┘

┌─ Pre-commit Checks (pre-commit.yml) ───────────────┐
│  Python 3.10, ubuntu-latest:                        │
│    pip install setuptools==68.2.2 wheel==0.41.2     │
│    pip install -e ".[dev]"                          │
│    pre-commit run --all-files                       │
│      ├─ check-ast, trailing-whitespace              │
│      ├─ add-trailing-comma                          │
│      ├─ mypy (v1.7.0)                              │
│      ├─ black (v23.3.0, --line-length=79)           │
│      ├─ flake8 (v6.1.0, --extend-ignore=E203)      │
│      ├─ pylint (v3.0.2, 大量 disable)               │
│      └─ prettier (仅 .tsx，排除 console/)            │
└─────────────────────────────────────────────────────┘

┌─ Tests (tests.yml) ────────────────────────────────┐
│  需要 Maintainer Approval                           │
│  Python 3.10/3.13, ubuntu/macos/windows:            │
│    npm ci → npm run build → cp dist/                │
│    pip install -e ".[dev,full]"                     │
│    pytest tests/unit -v                             │
│    pytest tests/integrated -v (if exists → skip)    │
└─────────────────────────────────────────────────────┘
```

## 附录 B: 依赖配置 (`pyproject.toml`)

```toml
requires-python = ">=3.10,<3.14"

[project.optional-dependencies]
dev = [
    "pytest>=8.3.5",
    "pytest-asyncio>=0.23.0",
    "pre-commit>=4.2.0",
    "pytest-cov>=6.2.1",
    "hypothesis>=6.0.0",
]
local = ["huggingface_hub>=0.20.0"]
semantic = ["sentence-transformers>=2.2"]
whisper = ["openai-whisper>=20231117"]
full = ["qwenpaw[local,whisper,semantic]"]
```
