"""Quick analysis of pipeline predictions."""
import json
import sys

result_file = sys.argv[1] if len(sys.argv) > 1 else "/mnt/workspace/skill-routing/results_v3/full_pipeline_metadata_v3.json"

with open(result_file) as f:
    data = json.load(f)

preds = data["predictions"]
print(f"Total predictions: {len(preds)}")

# Analyze decomposition patterns
decomp_counts = {}
for p in preds:
    n = len(p["decomposed_subtasks"])
    decomp_counts[n] = decomp_counts.get(n, 0) + 1
print(f"\nDecomposition count distribution:")
for k in sorted(decomp_counts.keys()):
    print(f"  {k} subtasks: {decomp_counts[k]} queries ({decomp_counts[k]/len(preds)*100:.1f}%)")

# Load benchmark for GT comparison
with open("/mnt/workspace/skill-routing/data/benchmark_v3/compositional_queries.jsonl") as f:
    benchmark = [json.loads(line) for line in f]
gt_map = {q["query_id"]: q for q in benchmark}

# Sample predictions
print("\n--- Sample Predictions ---")
for i in [0, 10, 50, 100, 200]:
    if i >= len(preds):
        break
    p = preds[i]
    gt = gt_map.get(p["query_id"], {})
    gt_subtasks = gt.get("subtasks", [])
    gt_skills = [st["ground_truth_skill_id"] for st in gt_subtasks]
    gt_cats = [st.get("required_category", "") for st in gt_subtasks]

    print(f"\nQ{i}: {p['query'][:120]}")
    print(f"  GT steps: {len(gt_subtasks)}, Pred steps: {len(p['decomposed_subtasks'])}")
    for j, st in enumerate(p["decomposed_subtasks"][:5]):
        sel_name = p["predictions"][j]["selected_skill_name"] if j < len(p["predictions"]) else "N/A"
        gt_cat = gt_cats[j] if j < len(gt_cats) else "N/A"
        print(f"  [{j}] subtask: {st[:80]}")
        print(f"       -> selected: {sel_name[:60]} | GT cat: {gt_cat}")

# Analyze Llama results too
llama_file = "/mnt/workspace/skill-routing/results_v3/decomposer_llama_31_8b_instruct.json"
try:
    with open(llama_file) as f:
        llama_data = json.load(f)
    llama_preds = llama_data["predictions"]
    llama_counts = {}
    for p in llama_preds:
        n = len(p["decomposed_subtasks"])
        llama_counts[n] = llama_counts.get(n, 0) + 1
    print(f"\n--- Llama Decomposition Distribution ---")
    for k in sorted(llama_counts.keys()):
        print(f"  {k} subtasks: {llama_counts[k]} queries ({llama_counts[k]/len(llama_preds)*100:.1f}%)")
except:
    pass
