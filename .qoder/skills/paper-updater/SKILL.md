---
name: paper-updater
description: >
  EMNLP 2026 论文自动化更新 skill。在论文修改后自动执行远程编译、页数验证、
  PDF 下载、数据一致性检查、变更日志生成，可选触发审稿和 GitHub 推送。
  覆盖 paper/main.tex 从修改到发布的完整工作流。
tags:
  - paper
  - latex
  - compilation
  - EMNLP
  - ARR
  - workflow
version: "1.0"
author: anonymous
---

# Paper Updater Skill

## 角色定位

你是一个论文工程助手，负责 EMNLP 2026 论文 (ACL Rolling Review) 的编译、验证和发布自动化。
你严格按照以下流程执行，确保每次论文修改后 PDF 是正确编译的、页数合规的、数据一致的。

## 适用场景

在以下任何一种情况下触发此 skill：
- 用户修改了 `paper/main.tex` 或 `paper/references.bib`
- 用户要求"编译论文"、"更新论文"、"生成 PDF"
- 用户要求"检查页数"、"验证论文"
- 用户完成了一轮论文修改并需要完整的 compile-verify-download 流程

## 用户输入

```text
$ARGUMENTS
```

可选参数（在用户消息中识别）：
- `--review`：编译完成后触发 paper-reviewer skill 进行完整审稿
- `--push`：编译完成后推送更新到 GitHub
- `--skip-verify`：跳过页数验证（用于草稿阶段快速迭代）
- `--changelog-only`：仅生成变更日志，不编译

## 基础配置

### 远程编译服务器

- **主机**: `120.55.88.46`
- **端口**: `24`
- **用户**: `root`
- **SSH 密钥**: `~/.ssh/pai_dsw_rsa`
- **SSH 命令前缀**: `ssh -o ConnectTimeout=10 -o StrictHostKeyChecking=no -i ~/.ssh/pai_dsw_rsa -p 24 root@120.55.88.46`
- **远程工作目录**: `/tmp/paper/`
- **ACL 样式文件**: 已预装于 `/tmp/paper/acl.sty` 和 `/tmp/paper/acl_natbib.bst`

### 本地路径

| 用途 | 路径 |
|------|------|
| LaTeX 源文件 | `paper/main.tex` |
| 参考文献 | `paper/references.bib` |
| 编译后 PDF | `paper/main.pdf` |
| TikZ 图源 | `paper/figure1_tikz.tex`（如被引用） |
| 审稿笔记 | `review-notes/` |
| 审稿 Skill | `.kiro/skills/paper-reviewer/SKILL.md` |

### GitHub 仓库（Phase 8 使用）

- **Owner/Repo**: `hellogxp/skillweaver`
- **PAT 环境变量**: `GITHUB_TOKEN`
- **推送方式**: GitHub REST API（Git Data API），不使用 git push（内部网络限制）

### ARR 格式约束

- **正文页数限制**: ≤ 8 页（不含 references、limitations、ethics、appendix）
- **Limitations / Ethics Statement**: 放在 `\bibliography{}` 之后，不计入正文页数
- **Appendix**: 放在 Limitations/Ethics 之后
- **文档格式**: `\documentclass[11pt]{article}` + `\usepackage[hyperref]{acl}`

## 执行流程

### Phase 0：变更检测

在开始编译前，先确定本次有什么变化：

1. 读取 `paper/main.tex` 的当前内容
2. 识别用户本次修改的内容（如果是在本次会话中修改的，从会话上下文获取；否则询问用户）
3. 记录变更摘要，供 Phase 6 变更日志使用
4. 如果用户指定了 `--changelog-only`，跳到 Phase 6

### Phase 1：文件上传

将本地文件上传到远程编译服务器。**使用 cat 管道模式**（scp 在此环境不可靠）：

1. **上传 main.tex**：
   ```bash
   cat paper/main.tex | ssh [SSH前缀] 'cat > /tmp/paper/main.tex'
   ```
   验证：`ssh [SSH前缀] 'wc -l /tmp/paper/main.tex'` 与本地行数对比

2. **上传 references.bib**：
   ```bash
   cat paper/references.bib | ssh [SSH前缀] 'cat > /tmp/paper/references.bib'
   ```

3. **检测并生成 dummy figures**：
   - 在 main.tex 中搜索所有 `\includegraphics` 引用的文件路径
   - 确保远程 `figures/` 目录存在：`ssh [SSH前缀] 'mkdir -p /tmp/paper/figures'`
   - 对每个被引用但不存在于远程的图片文件，生成空白 PDF 占位：
     ```bash
     ssh [SSH前缀] 'python3 -c "
     from PIL import Image
     img = Image.new(\"RGB\", (800, 400), \"white\")
     img.save(\"/tmp/paper/figures/[文件名]\", \"PDF\")
     "'
     ```

**失败处理**: SSH 连接超时或上传验证失败 → 重试 1 次 → 仍失败则报告错误并停止

### Phase 2：远程编译

在远程服务器上执行完整的 LaTeX 编译序列：

```bash
ssh [SSH前缀] 'cd /tmp/paper && \
  pdflatex -interaction=nonstopmode main.tex && \
  bibtex main && \
  pdflatex -interaction=nonstopmode main.tex && \
  pdflatex -interaction=nonstopmode main.tex'
```

编译结果检查：
- 确认 `main.pdf` 已生成且大小 > 0
- 如果编译失败，获取错误日志：`ssh [SSH前缀] 'tail -50 /tmp/paper/main.log'`
- 向用户报告具体的 LaTeX 错误行号和类型
- 常见错误的快速修复建议：
  - `Undefined control sequence` → 检查 `\usepackage`
  - `File not found` → 检查图片/输入文件路径
  - `Missing $ inserted` → 数学模式错误
  - `Citation undefined` → bibtex 未运行或 .bib 文件问题

**失败处理**: 报告编译错误详情，给出修复建议，停止后续 Phase

### Phase 3：页数验证

验证论文正文是否符合 ARR ≤ 8 页限制：

1. **提取文本并按页分割**：
   ```bash
   ssh [SSH前缀] 'cd /tmp/paper && pdftotext main.pdf -'
   ```
   按 `\f`（form feed）分割输出得到各页内容

2. **识别正文结束位置**：
   - 在每页文本中搜索 References / Bibliography 标题的首次出现
   - References 之前的页码 = 正文页数
   - 同时报告各 section 的页面分布

3. **判定并报告**：
   - ≤ 8 页 → `正文 X 页，符合 ARR 要求`
   - = 8 页 → `正文恰好 8 页，无余量，注意后续修改`
   - > 8 页 → `正文 X 页，超出限制 Y 页`，建议压缩策略：
     - 将 Difficulty Analysis (Table 4) 移到 Appendix
     - 缩小表格字号（`\small` → `\footnotesize`）
     - 压缩 Discussion 段落

如果用户指定了 `--skip-verify`，仅报告总页数，不做合规判定

### Phase 4：PDF 下载

将编译好的 PDF 下载到本地：

```bash
ssh [SSH前缀] 'cat /tmp/paper/main.pdf' > paper/main.pdf
```

验证：
- 本地文件大小 > 0
- 与远程文件大小一致（`ssh [SSH前缀] 'wc -c /tmp/paper/main.pdf'`）
- 如不一致，重试 1 次

### Phase 5：数据一致性检查

读取 `paper/main.tex`，验证以下关键数据点在各位置是否一致：

| 数据项 | 预期值 | 检查位置 |
|--------|--------|----------|
| 技能库规模 | 2,595 | abstract, Section 5.1 |
| 查询数量 | 300 | abstract, Section 5.1 |
| 类别数量 | 17 | abstract, Section 5.1 |
| Human query 数量 | 55 | Section 7.4 |
| Oracle R@1 | 99.5% | abstract, Section 7.1 |
| Vanilla CatR@1 | 33.9% | abstract, Section 7.1, Discussion |
| SAD CatR@1 | 54.2% | abstract, Section 7.3, Discussion |
| SAD 提升幅度 | +60% | abstract, Section 7.3 |
| GitHub 仓库数 | 212 | Section 5.1 |
| Context window 节省 | >99% | abstract, Section 7.5 |

交叉验证：
- SAD 提升 = (54.2 - 33.9) / 33.9 ≈ 60%（验证计算正确性）
- 表格中的数值与正文描述一致
- Abstract 中的每个 claim 在 Results 或 Discussion 中有对应证据
- Text Overlap Disclosure 中引用的人类评估数据与 SAD Results 一致

报告格式：
- 一致项：简要列出
- 不一致项：标注具体位置（行号）和冲突值，标红
- 仅单次出现的关键数据：建议增加交叉引用

### Phase 6：变更日志

生成结构化变更日志，保存到 `review-notes/changelog-YYYY-MM-DD-HHMM.md`：

```markdown
# 论文变更日志 — YYYY-MM-DD HH:MM

## 修改摘要
[一句话概括本次修改的目的]

## 具体变更
| 位置 | 变更类型 | 描述 |
|------|----------|------|
| Section X, Line Y | 新增/修改/删除 | 具体描述 |

## 编译状态
- 编译结果: 成功 / 失败
- 正文页数: X 页
- 页数合规: 是 / 否

## 数据一致性
- 检查结果: 全部一致 / 有 N 处不一致
- [不一致项详情]

## 待办事项
- [ ] 后续需要修复的问题（如有）
```

### Phase 7：审稿（可选，需 `--review`）

仅在用户指定 `--review` 或明确要求审稿时执行：

1. 读取 `.kiro/skills/paper-reviewer/SKILL.md` 中的审稿框架
2. 基于最新的 `paper/main.tex` 执行完整 10 维度审稿
3. 将审稿报告保存到 `review-notes/review-YYYY-MM-DD-HHMM.md`
4. 在报告中标注本次是第几轮审稿，以及相比上轮的分数变化

### Phase 8：GitHub 推送（可选，需 `--push`）

仅在用户指定 `--push` 或明确要求推送时执行：

1. **检查环境变量**：确认 `GITHUB_TOKEN` 已设置
2. **确定要推送的文件**：
   - `paper/main.tex`
   - `paper/references.bib`
   - `paper/main.pdf`（base64 编码）
   - `review-notes/` 下本次新生成的文件
3. **GitHub REST API 推送流程**：
   - `GET /repos/hellogxp/skillweaver/git/ref/heads/main` → 获取最新 commit SHA
   - `GET /repos/hellogxp/skillweaver/git/commits/{sha}` → 获取 base tree SHA
   - 为每个文件 `POST /repos/hellogxp/skillweaver/git/blobs` → 创建 blob
   - `POST /repos/hellogxp/skillweaver/git/trees` → 创建 tree（base_tree 合并）
   - `POST /repos/hellogxp/skillweaver/git/commits` → 创建 commit，message: `paper: [变更摘要]`
   - `PATCH /repos/hellogxp/skillweaver/git/refs/heads/main` → 更新分支指针
4. **报告**：显示 commit SHA 和仓库 URL

## 输出格式

每次执行完成后，输出以下汇总报告：

```
## 论文更新报告

### 编译
- 状态: 成功 / 失败
- 远程服务器: 120.55.88.46:24
- PDF 大小: XXX KB

### 页数验证
- 总页数: X 页
- 正文页数: X 页
- ARR 合规: 符合（≤ 8 页） / 超出 Y 页

### 数据一致性
- 状态: 全部一致 / N 处不一致
- [不一致项详情]

### 本地 PDF
- 路径: paper/main.pdf

### 变更日志
- 路径: review-notes/changelog-YYYY-MM-DD-HHMM.md

### 可选操作
- 审稿: 使用 --review 触发
- 推送: 使用 --push 触发
```

## 错误恢复

| 错误场景 | 处理方式 |
|----------|----------|
| SSH 连接超时 | 重试 1 次，仍失败则报告网络问题，停止 |
| 文件上传大小不匹配 | 重试 1 次 |
| LaTeX 编译失败 | 报告错误日志和修复建议，停止后续 Phase |
| pdftotext 不可用 | 用 `pdfinfo main.pdf` 获取总页数作为 fallback |
| PDF 下载失败 | 重试 1 次 |
| GITHUB_TOKEN 未设置 | 提醒用户设置环境变量，跳过推送 |
| 页数超限 | 给出压缩建议，不自动修改论文 |

## 注意事项

1. **绝不自动修改论文内容** — 此 skill 只负责编译、验证和报告，不会自动修改 main.tex
2. **编译前确认文件已保存** — 如果在会话中修改了 main.tex，确保修改已写入磁盘再触发
3. **dummy figure 仅用于编译通过** — 如论文引用了尚未生成的图片，创建空白 PDF 占位
4. **SSH 密钥路径不得泄露** — `~/.ssh/pai_dsw_rsa` 不出现在 commit、日志或变更记录中
5. **GitHub 推送用 API** — 内部网络限制，不使用 git push
