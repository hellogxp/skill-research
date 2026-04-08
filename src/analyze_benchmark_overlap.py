"""Analyze text overlap between ground-truth sub-task descriptions and skill descriptions.
Reports ROUGE-L and BLEU scores to assess benchmark bias."""
import sys, json, logging
from pathlib import Path
from collections import Counter

sys.path.insert(0, "/mnt/workspace/skill-routing/src")

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BENCHMARK_PATH = "/mnt/workspace/skill-routing/data/benchmark_v3/compositional_queries.jsonl"
SKILL_POOL_PATH = "/mnt/workspace/skill-routing/data/processed_v3/skill_pool.jsonl"
RESULTS_DIR = Path("/mnt/workspace/skill-routing/results_v3")


def load_data():
    skills = {}
    with open(SKILL_POOL_PATH) as f:
        for line in f:
            s = json.loads(line.strip())
            skills[s["skill_id"]] = s

    queries = []
    with open(BENCHMARK_PATH) as f:
        for line in f:
            queries.append(json.loads(line.strip()))

    return skills, queries


def tokenize(text):
    """Simple whitespace + lowering tokenization."""
    return text.lower().split()


def compute_rouge_l(reference, hypothesis):
    """Compute ROUGE-L F1 score between reference and hypothesis."""
    ref_tokens = tokenize(reference)
    hyp_tokens = tokenize(hypothesis)
    if not ref_tokens or not hyp_tokens:
        return 0.0

    # LCS
    m, n = len(ref_tokens), len(hyp_tokens)
    dp = [[0] * (n + 1) for _ in range(m + 1)]
    for i in range(1, m + 1):
        for j in range(1, n + 1):
            if ref_tokens[i-1] == hyp_tokens[j-1]:
                dp[i][j] = dp[i-1][j-1] + 1
            else:
                dp[i][j] = max(dp[i-1][j], dp[i][j-1])

    lcs_len = dp[m][n]
    if lcs_len == 0:
        return 0.0

    precision = lcs_len / n
    recall = lcs_len / m
    f1 = 2 * precision * recall / (precision + recall)
    return f1


def compute_bleu_1(reference, hypothesis):
    """Compute unigram BLEU (BLEU-1) precision."""
    ref_tokens = tokenize(reference)
    hyp_tokens = tokenize(hypothesis)
    if not hyp_tokens:
        return 0.0

    ref_counts = Counter(ref_tokens)
    hyp_counts = Counter(hyp_tokens)

    clipped = 0
    for token, count in hyp_counts.items():
        clipped += min(count, ref_counts.get(token, 0))

    return clipped / len(hyp_tokens)


def compute_jaccard(text1, text2):
    """Compute Jaccard similarity between two texts."""
    set1 = set(tokenize(text1))
    set2 = set(tokenize(text2))
    if not set1 or not set2:
        return 0.0
    return len(set1 & set2) / len(set1 | set2)


def main():
    skills, queries = load_data()
    logger.info(f"Loaded {len(skills)} skills, {len(queries)} queries")

    rouge_l_scores = []
    bleu_1_scores = []
    jaccard_scores = []
    exact_match = 0
    total_pairs = 0

    for q in queries:
        for subtask in q["subtasks"]:
            gt_desc = subtask["description"]
            gt_skill_id = subtask["ground_truth_skill_id"]

            if gt_skill_id in skills:
                skill_desc = skills[gt_skill_id].get("description", "")
                if not skill_desc:
                    continue

                rl = compute_rouge_l(skill_desc, gt_desc)
                b1 = compute_bleu_1(skill_desc, gt_desc)
                jc = compute_jaccard(skill_desc, gt_desc)

                rouge_l_scores.append(rl)
                bleu_1_scores.append(b1)
                jaccard_scores.append(jc)

                if gt_desc.strip() == skill_desc.strip():
                    exact_match += 1

                total_pairs += 1

    logger.info(f"\nText Overlap Analysis ({total_pairs} sub-task/skill pairs)")
    logger.info(f"=" * 50)

    import numpy as np
    rl = np.array(rouge_l_scores)
    b1 = np.array(bleu_1_scores)
    jc = np.array(jaccard_scores)

    logger.info(f"ROUGE-L F1:  mean={rl.mean():.3f}  median={np.median(rl):.3f}  std={rl.std():.3f}")
    logger.info(f"BLEU-1:      mean={b1.mean():.3f}  median={np.median(b1):.3f}  std={b1.std():.3f}")
    logger.info(f"Jaccard:     mean={jc.mean():.3f}  median={np.median(jc):.3f}  std={jc.std():.3f}")
    logger.info(f"Exact match: {exact_match}/{total_pairs} ({100*exact_match/total_pairs:.1f}%)")

    # Distribution bins
    for name, scores in [("ROUGE-L", rl), ("BLEU-1", b1), ("Jaccard", jc)]:
        bins = [0, 0.2, 0.4, 0.6, 0.8, 1.01]
        hist, _ = np.histogram(scores, bins=bins)
        logger.info(f"\n{name} distribution:")
        for i in range(len(bins)-1):
            logger.info(f"  [{bins[i]:.1f}, {bins[i+1]:.1f}): {hist[i]} ({100*hist[i]/len(scores):.1f}%)")

    # Also check: how were queries generated?
    # Look at the actual sub-task descriptions vs skill descriptions
    logger.info(f"\nSample comparisons (first 5):")
    count = 0
    for q in queries[:10]:
        for subtask in q["subtasks"]:
            gt_desc = subtask["description"][:80]
            gt_skill_id = subtask["ground_truth_skill_id"]
            if gt_skill_id in skills:
                skill_desc = skills[gt_skill_id].get("description", "")[:80]
                rl = compute_rouge_l(skills[gt_skill_id].get("description", ""), subtask["description"])
                logger.info(f"  GT:    {gt_desc}")
                logger.info(f"  Skill: {skill_desc}")
                logger.info(f"  ROUGE-L: {rl:.3f}")
                logger.info(f"  ---")
                count += 1
                if count >= 5:
                    break
        if count >= 5:
            break

    # Save results
    report = {
        "total_pairs": total_pairs,
        "rouge_l": {"mean": float(rl.mean()), "median": float(np.median(rl)), "std": float(rl.std())},
        "bleu_1": {"mean": float(b1.mean()), "median": float(np.median(b1)), "std": float(b1.std())},
        "jaccard": {"mean": float(jc.mean()), "median": float(np.median(jc)), "std": float(jc.std())},
        "exact_match_rate": exact_match / total_pairs,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_DIR / "benchmark_overlap_analysis.json", "w") as f:
        json.dump(report, f, indent=2)
    logger.info(f"\nReport saved to {RESULTS_DIR / 'benchmark_overlap_analysis.json'}")


if __name__ == "__main__":
    main()
