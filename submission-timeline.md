# Skill Routing Paper -- Submission Timeline & Strategy

> 最后更新: 2026-04-03

## 投稿计划（2026年4月修订）

### 主投：EMNLP 2026 via ARR（Primary Target）
- ARR submission deadline: **2026-05-25**
- Commitment deadline: 2026-08-02
- Conference: Oct 24-29, 2026
- Status: CCF-B（实际影响力接近 A）
- Note: 走 ARR 系统，被拒可转 ACL Findings
- 格式: ACL 格式，已就绪

### 保底会议

#### NLPCC 2026（推荐保底）
- Paper submission deadline: **2026-05-26**
- Conference: 2026年11月, 澳门
- Status: CCF C
- Note: 国内 NLP 主要会议，方向匹配，录取率较高，接受 ACL 格式
- 与 ARR 截止日期仅差 1 天，可同时投

#### PRICAI 2026（第二保底）
- Paper submission deadline: **2026-06-13**
- Conference: 2026年11月, 广州
- Status: CCF C
- Note: 环太平洋 AI 会议，国内认可度不错

#### WISE 2026（第三保底）
- Paper submission deadline: **2026-06-17**
- Conference: 预计 2026 秋季
- Status: CCF C
- Note: Web 信息系统方向，可从 agent+tool 角度投

### 冲高选项
- **NeurIPS 2026**: Abstract 5/4, Paper 5/6, CCF A, 12月 Atlanta
  - 需改为 NeurIPS 格式，调整 framing 强调方法通用性

### 已过截止 / 已放弃
- COLM 2026: 3/31 已过
- ECML-PKDD 2026: 3/12 已过
- EACL 2026: 12/14 (2025) 已过
- ACL 2026 commitment: 3/14 已过
- IJCAI-ECAI 2026: 1/19 已过

## 执行计划

```
4月初 (now)   打磨论文
              - SAD 两遍反馈循环代码已实现 (done)
              - 跑完所有实验 + 消融
              - 精写论文
    |
5/25         投 ARR → commit 到 EMNLP 2026
5/26         同时投 NLPCC 2026 保底
    |
6/13         如需要，投 PRICAI 2026（第二保底）
6/17         如需要，投 WISE 2026（第三保底）
    |
8/02         EMNLP commitment deadline
    |
秋季          等结果
              - EMNLP 中了 → 发 EMNLP
              - EMNLP 被拒但审稿可以 → 转 Findings
              - NLPCC/PRICAI/WISE 中了 → 保底发表
              - 都被拒 → 改进后投 ARR 8/03 → NAACL 2027
```

## 关键提醒日期
- **5月4日**: NeurIPS abstract 截止（如果决定冲高）
- **5月25日**: ARR → EMNLP 截止 ⚠️ 最重要
- **5月26日**: NLPCC 截止
- **6月13日**: PRICAI 截止
- **6月17日**: WISE 截止

## Compute Resources
- 4 x NVIDIA A100-SXM4-80GB (320GB total VRAM)
- 64-core Intel Xeon Platinum 8369B
- 491GB RAM
- PyTorch 2.7.1 + CUDA 12.6
- Workspace: /mnt/workspace (57GB free)
- SSH: ssh -i ~/.ssh/pai_dsw_rsa root@120.55.88.46 -p 24
