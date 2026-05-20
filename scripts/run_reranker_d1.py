"""D1: LLM-based listwise reranker on top of SAD pipeline.

For each (sub-task, top-10 candidate skills), prompt Qwen2.5-7B to pick
the best matching skill by listwise scoring. Compare reranked CatR@1
against SAD baseline CatR@1.

Closes the @1-vs-@10 gap noted as future work in the paper.

Run on PAI-DSW V100. Outputs JSON to /mnt/workspace/skill-research/results_v4/
"""

from __future__ import annotations
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, "/mnt/workspace/skill-research/skillweaver/src")

from skillweaver.core.decomposer import LocalDecomposer
from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever
from skillweaver.core.pipeline import build_hint_set

MODEL_7B = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
ENCODER_MINILM = "/mnt/workspace/models/sentence-transformers/all-MiniLM-L6-v2"
SKILLS_PATH = "/mnt/workspace/skill-research/data/processed_v3/skill_pool.jsonl"
QUERIES_PATH = "/mnt/workspace/skill-research/data/benchmark_v3/compositional_queries.jsonl"
RESULTS_DIR = Path("/mnt/workspace/skill-research/results_v4")
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

H = 15
TOP_K = 10
N_QUERIES = 100  # subset for time budget


# ---------- Reranker prompt ----------
RERANK_USER_TEMPLATE = """You are selecting the single best skill for a sub-task from a list of candidates.

Sub-task: {subtask}

Candidate skills (each is `[index] name: description (categories)`):
{candidates_block}

Task: Output ONLY the integer index (0 to {max_idx}) of the SINGLE best matching skill. Do not explain. Do not output anything else.

Answer:"""


def _format_candidate(idx: int, match) -> str:
    sk = match.skill
    desc = (sk.description or "").replace("\n", " ").strip()[:140]
    cats = ", ".join(sk.categories[:3]) if sk.categories else "n/a"
    return f"[{idx}] {sk.name}: {desc} ({cats})"


def llm_rerank(decomposer: LocalDecomposer, subtask_desc: str, candidates) -> int:
    """Return reranked top-1 index (0..len(candidates)-1)."""
    if not candidates:
        return 0
    block = "\n".join(_format_candidate(i, c) for i, c in enumerate(candidates))
    prompt = RERANK_USER_TEMPLATE.format(
        subtask=subtask_desc.strip(),
        candidates_block=block,
        max_idx=len(candidates) - 1,
    )
    messages = [
        {"role": "system", "content": "You are a precise skill-selection assistant. Output ONLY a single integer index."},
        {"role": "user", "content": prompt},
    ]
    text = decomposer._generate(messages).strip()
    # Extract first integer
    m = re.search(r"\d+", text)
    if not m:
        return 0
    idx = int(m.group(0))
    if idx < 0 or idx >= len(candidates):
        return 0
    return idx


# ---------- Metrics ----------
def cat_r1(reranked_top, gt_cats, n_eval):
    hits = 0
    for i in range(n_eval):
        gc = gt_cats[i]
        if gc is None or i >= len(reranked_top):
            continue
        sk = reranked_top[i]
        if sk and gc in (sk.categories or []):
            hits += 1
    return hits / n_eval if n_eval else 0.0


def cat_r10(cands, gt_cats, n_eval):
    hits = 0
    for i in range(n_eval):
        gc = gt_cats[i]
        if gc is None or i >= len(cands) or not cands[i]:
            continue
        for m in cands[i][:10]:
            if gc in (m.skill.categories or []):
                hits += 1
                break
    return hits / n_eval if n_eval else 0.0


def main():
    # Load skills + queries
    skills = []
    for line in open(SKILLS_PATH):
        d = json.loads(line)
        skills.append(Skill.from_dict(d))
    print(f"Loaded {len(skills)} skills")

    queries = [json.loads(line) for line in open(QUERIES_PATH)][:N_QUERIES]
    print(f"Loaded {len(queries)} queries (subset)")

    # MiniLM retriever
    print("Building MiniLM retriever...")
    retriever = SkillRetriever(encoder_name=ENCODER_MINILM, use_body=False, top_k=TOP_K)
    retriever.build_index(skills)

    # 7B decomposer (also reused as reranker LLM)
    print("Loading Qwen2.5-7B-Instruct (decomposer + reranker)...")
    decomposer = LocalDecomposer(model_path=MODEL_7B, temperature=0.1)

    print("\n" + "=" * 60)
    print(f"D1: LLM-listwise reranker on SAD top-10 ({N_QUERIES} queries)")
    print("=" * 60)

    sad_r1_total = 0
    rerank_r1_total = 0
    r10_total = 0
    n_steps_total = 0
    per_query = []

    t0 = time.time()
    for qi, q in enumerate(queries):
        query_text = q["query"]
        gt_subs = q["subtasks"]
        gt_cats = [s["required_category"] for s in gt_subs]
        n_eval = len(gt_subs)

        # SAD pipeline (Pass-1 vanilla -> hints -> Pass-2 SAD)
        try:
            pass1 = decomposer.decompose(query_text)
            pass1_cands = retriever.search_batch([s.description for s in pass1])
            hints = build_hint_set(pass1_cands, H)
            subtasks = decomposer.decompose_with_hints(query_text, hints)
            cands = retriever.search_batch([s.description for s in subtasks], top_k=TOP_K)
        except Exception as e:
            print(f"  [{qi+1}] SAD failed: {e}")
            continue

        # SAD baseline top-1 per step (encoder top-1)
        sad_top1 = [c[0].skill if c else None for c in cands]
        # CatR@1 / @10 for SAD
        n_use = min(n_eval, len(cands))
        sad_r1 = cat_r1(sad_top1, gt_cats, n_use)
        r10 = cat_r10(cands, gt_cats, n_use)

        # LLM reranking on top-10 -> reranked top-1
        rerank_top1 = []
        for si in range(min(n_eval, len(cands))):
            if not cands[si]:
                rerank_top1.append(None)
                continue
            idx = llm_rerank(decomposer, subtasks[si].description, cands[si])
            rerank_top1.append(cands[si][idx].skill)
        rerank_r1 = cat_r1(rerank_top1, gt_cats, n_use)

        sad_r1_total += sad_r1 * n_use
        rerank_r1_total += rerank_r1 * n_use
        r10_total += r10 * n_use
        n_steps_total += n_use
        per_query.append({
            "qi": qi,
            "n_steps": n_use,
            "sad_r1": sad_r1,
            "rerank_r1": rerank_r1,
            "r10": r10,
        })

        if (qi + 1) % 10 == 0:
            sad_avg = sum(p["sad_r1"] * p["n_steps"] for p in per_query) / max(1, sum(p["n_steps"] for p in per_query))
            rerank_avg = sum(p["rerank_r1"] * p["n_steps"] for p in per_query) / max(1, sum(p["n_steps"] for p in per_query))
            print(f"  [{qi+1}/{len(queries)}] SAD@1={sad_avg:.3f}  Rerank@1={rerank_avg:.3f}", flush=True)

    elapsed = time.time() - t0

    # Aggregate (step-weighted)
    if n_steps_total:
        sad_r1_w = sad_r1_total / n_steps_total
        rerank_r1_w = rerank_r1_total / n_steps_total
        r10_w = r10_total / n_steps_total
    else:
        sad_r1_w = rerank_r1_w = r10_w = 0.0

    summary = {
        "n_queries": len(per_query),
        "n_steps_total": n_steps_total,
        "sad_cat_r1": sad_r1_w,
        "rerank_cat_r1": rerank_r1_w,
        "sad_cat_r10": r10_w,
        "absolute_gain": rerank_r1_w - sad_r1_w,
        "relative_gain": (rerank_r1_w - sad_r1_w) / max(1e-9, sad_r1_w),
        "elapsed_sec": elapsed,
        "per_query": per_query,
    }
    out_path = RESULTS_DIR / "llm_rerank_d1.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nFinal:")
    print(f"  SAD @1     = {sad_r1_w:.4f}")
    print(f"  + Rerank@1 = {rerank_r1_w:.4f}")
    print(f"  CatR@10    = {r10_w:.4f}")
    print(f"  Abs gain   = {rerank_r1_w - sad_r1_w:+.4f}  ({(rerank_r1_w - sad_r1_w)/max(1e-9,sad_r1_w)*100:+.1f}%)")
    print(f"  Elapsed    = {elapsed/60:.1f} min")
    print(f"  Saved -> {out_path}")


if __name__ == "__main__":
    main()
