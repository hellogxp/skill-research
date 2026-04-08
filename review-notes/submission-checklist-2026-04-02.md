# ARR / EMNLP 2026 提交清单

**文件名**: `review-notes/submission-checklist-2026-04-02.md`
**提交平台**: OpenReview (ACL Rolling Review)
**Deadline**: 2026-05-25
**Commitment deadline**: 2026-08-02 (commit to EMNLP)

---

## 必须提交

| # | 项目 | 文件 | 状态 |
|---|------|------|------|
| 1 | 论文 PDF | `paper/main.pdf` (11页, 304KB, 正文8页) | ✅ 就绪 |
| 2 | 论文源文件 | `paper/main.tex` + `paper/references.bib` + `paper/figures/` 打包成 zip | ⚠️ 需打包 |
| 3 | Responsible NLP Research checklist | OpenReview 上在线填写 | ⚠️ 需填写 |
| 4 | 作者信息 | OpenReview 上填写（审稿期间匿名） | ⚠️ 需填写 |

## 强烈建议提交

| # | 项目 | 说明 | 状态 |
|---|------|------|------|
| 5 | 补充材料 (Software) | SkillWeaver 代码的匿名化包 | ⚠️ 需匿名化 |

## 补充材料匿名化步骤

提交前需要把 `skillweaver/` 目录做匿名化处理：

1. `pyproject.toml` — 删除或替换 4 行 GitHub URL：
   ```
   Homepage = "https://anonymous"
   Documentation = "https://anonymous"
   Repository = "https://anonymous"
   Issues = "https://anonymous"
   ```

2. `CONTRIBUTING.md` — 删除 clone URL：
   ```
   git clone https://github.com/skillweaver-ai/skillweaver.git  → 删除这行
   ```

3. 删除 `.git/` 目录

4. 打包：`zip -r skillweaver-anonymous.zip skillweaver/ -x "skillweaver/.git/*"`

或者用 anonymous.4open.science 创建匿名仓库镜像。

## 提交前最终确认

| 检查项 | 状态 |
|--------|------|
| PDF 正文 ≤ 8 页 | ✅ 正文8页，References从第9页开始 |
| `\author{Anonymous}` | ✅ |
| 论文中无 GitHub URL / 作者名 | ✅ |
| 所有 \ref 有对应 \label | ✅ 零悬空引用 |
| 所有 \cite 有对应 bib entry | ✅ 30对30完全匹配 |
| BibTeX 零 warning | ✅ |
| Overfull hbox ≤ 12pt | ✅ 肉眼不可见 |
| Limitations section | ✅ |
| Ethics Statement | ✅ |
| 承诺开源 | ✅ "Code, data, and CompSkillBench will be released upon acceptance" |
| 公式符号一致 | ✅ Eq.1 和 Eq.6 的 α 一致 |
| 数字一致（abstract/intro/results/conclusion） | ✅ |
