# Skill Routing Paper -- Submission Timeline & Strategy

## Target Venues (Dual Track)

### Track 1: COLM 2026
- Abstract submitted: 2026-03-26 (done)
- Full paper deadline: 2026-03-31
- Conference: Oct 6-9, 2026, San Francisco
- Status: CCF 未收录 (too new), Tier 1.5
- Note: 不走 ARR 系统，独立投稿

### Track 2: EMNLP 2026 (Primary Target)
- ARR submission deadline: 2026-05-25
- Commitment deadline: 2026-08-02
- Conference: Oct 24-29, 2026
- Status: CCF-A, Tier 1.5, NLP 第二会议
- Note: 走 ARR 系统

### Backup: NAACL 2027
- ARR submission deadline: ~2026-08-03
- Commitment deadline: ~2026-11
- Conference: ~2027-04
- Status: CCF-B

## Execution Plan

```
3/26 (done)  COLM 摘要提交
    |
3/31         COLM 全文截止 → 先交一版
    |
4月-5月       花 2 个月打磨论文
              - 加深方法贡献（蒸馏框架 / 新方向）
              - 跑完所有实验 + 消融
              - 精写论文
    |
5/25         投 ARR → commit 到 EMNLP 2026
    |
8/02         EMNLP commitment deadline
    |
~8月         如果 COLM 中了 → 选更好的发
             如果 COLM 被拒 → EMNLP 兜底
             如果都被拒 → 改进后投 NAACL 2027 ARR (8/03)
```

## Key Principle
- COLM 和 EMNLP 不冲突（不同投稿系统）
- COLM 先交占位，EMNLP 做精做深
- 最大化中稿概率

## Compute Resources
- 4 x NVIDIA A100-SXM4-80GB (320GB total VRAM)
- 64-core Intel Xeon Platinum 8369B
- 491GB RAM
- PyTorch 2.7.1 + CUDA 12.6
- Workspace: /mnt/workspace (57GB free)
- SSH: ssh -i ~/.ssh/pai_dsw_rsa root@120.55.88.46 -p 24
