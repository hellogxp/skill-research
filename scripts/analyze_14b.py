import json
from pathlib import Path
from collections import Counter

results_dir = Path("/mnt/workspace/skill-routing/results_v3")

for fname in ["qwen14b_vanilla.json", "qwen14b_sad_hints15.json",
              "skill_aware_qwen7b_hints15.json"]:
    fpath = results_dir / fname
    if not fpath.exists():
        print(f"{fname}: NOT FOUND")
        continue
    with open(fpath) as f:
        data = json.load(f)

    preds = data.get("predictions", [])
    m = data.get("metrics", {})
    total = len(preds)
    if total == 0:
        continue

    subtask_counts = [len(p["decomposed_subtasks"]) for p in preds]
    avg_subs = sum(subtask_counts) / total
    single = sum(1 for c in subtask_counts if c == 1)
    long_decomp = sum(1 for c in subtask_counts if c > 5)

    da = m.get("decomposition_accuracy", "?")
    cr = m.get("cat_recall_at_1", "?")

    print(f"\n{fname}:")
    print(f"  Total: {total}, DA={da}, CR@1={cr}")
    print(f"  Avg subtasks: {avg_subs:.1f}")
    print(f"  Single subtask (fallback): {single} ({100*single/total:.1f}%)")
    print(f"  >5 subtasks (over-decomp): {long_decomp} ({100*long_decomp/total:.1f}%)")
    dist = Counter(subtask_counts)
    print(f"  Subtask dist: {dict(sorted(dist.items()))}")
    # Show 3 examples
    print("  Examples:")
    for p in preds[:3]:
        subs = p["decomposed_subtasks"]
        q = p["query"][:60]
        print(f"    Q: {q}...")
        print(f"    -> {len(subs)} subs: {[s[:40] for s in subs[:4]]}")
