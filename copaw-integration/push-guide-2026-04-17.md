# Force Push 操作指南

## 背景

`copaw-upstream` 目录下的 `feat/semantic-skill-routing` 分支已经完成了 rebase（基于最新的 upstream/main），需要 force push 到 fork。

## 前提

- 能访问 GitHub（不在内网限制下）
- 有 git 命令行

## 操作步骤

```bash
cd /Users/xuepinxueping.gxpg.gxp/skill-research/copaw-upstream

# 1. 确认当前状态
git status
# 应该显示：On branch feat/semantic-skill-routing, nothing to commit

git log --oneline -3
# 应该显示：
# a710a523 test: update hint injection assertions for system message mark approach
# fc41411e feat(react-agent): inject skill hint as system message with mark for auto-cleanup
# ef6ac0e5 feat(react-agent): replace tool filtering with KV-cache-friendly hint injection

# 2. Force push
git push origin feat/semantic-skill-routing --force-with-lease
```

## 预期结果

- Push 成功后，PR https://github.com/agentscope-ai/QwenPaw/pull/3117 会自动更新
- 分支基于最新的 upstream/main（d586bc11），共 13 个 commit
- 所有冲突已在 rebase 过程中解决

## 注意

- 必须用 `--force-with-lease`（不要用 `--force`），这样如果远端有别人的新提交不会被覆盖
- 如果报错 `stale info`，先 `git fetch origin` 再重试
