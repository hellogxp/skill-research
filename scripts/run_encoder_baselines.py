#!/usr/bin/env python3
"""Experiment 3: Encoder Baseline Comparison.

Addresses reviewer weakness (usWc): "retrieval only uses a lightweight encoder
without comprehensive model comparison"

Compares three retrieval strategies:
  1. TF-IDF (sparse, no neural)  — scikit-learn
  2. MiniLM-L6-v2 (dense, small, 384-dim)  — sentence-transformers (paper default)
  3. Qwen2.5-7B-Instruct (dense, large, 4096-dim)  — transformers last hidden state

Uses SAD-decomposed subtask texts from compose eval (no LLM generation needed).

Usage:
    cd /mnt/workspace/skill-research
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 PYTHONPATH=skillweaver/src \
        python3 scripts/run_encoder_baselines.py
"""
import json
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import faiss_shim as _faiss_shim
sys.modules["faiss"] = _faiss_shim

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "results_v4"
MODEL_PATH = "/mnt/workspace/models/Qwen/Qwen2.5-7B-Instruct"
TOP_K = 10


def load_data():
    from skillweaver.core.models import Skill

    skill_path = DATA_DIR / "processed_v3" / "skill_pool.jsonl"
    query_path = DATA_DIR / "benchmark_v3" / "compositional_queries.jsonl"

    skills = []
    with open(skill_path) as f:
        for line in f:
            if line.strip():
                skills.append(Skill.from_dict(json.loads(line.strip())))

    queries = []
    with open(query_path) as f:
        for line in f:
            if line.strip():
                queries.append(json.loads(line.strip()))

    logger.info(f"Loaded {len(skills)} skills, {len(queries)} queries")
    return skills, queries


def load_sad_subtask_texts():
    path = OUTPUT_DIR / "sad_subtask_texts.json"
    if not path.exists():
        logger.error(f"SAD subtask texts not found. Run run_compose_eval.py first.")
        sys.exit(1)
    with open(path) as f:
        items = json.load(f)
    by_query = {}
    for item in items:
        qid = item["query_id"]
        if qid not in by_query:
            by_query[qid] = []
        by_query[qid].append(item["subtask_text"])
    return by_query


# ---------------------------------------------------------------------------
# Strategy 1: TF-IDF (sparse retrieval)
# ---------------------------------------------------------------------------
def run_tfidf(skills, queries, sad_texts):
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity

    logger.info("Building TF-IDF index...")
    texts = [s.to_retrieval_text(use_body=False) for s in skills]
    vectorizer = TfidfVectorizer(max_features=10000, ngram_range=(1, 2), stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(texts)
    logger.info(f"TF-IDF matrix: {tfidf_matrix.shape}")

    skill_id_to_cat = {s.skill_id: s.categories[0] for s in skills if s.categories}

    per_query = []
    t0 = time.time()
    for qi, q in enumerate(queries):
        qid = q.get("query_id", str(qi))
        gt_subtasks = q.get("subtasks", [])
        gt_categories = [
            skill_id_to_cat.get(st.get("ground_truth_skill_id", ""),
                                 st.get("required_category", ""))
            for st in gt_subtasks
        ]
        subtask_texts = sad_texts.get(qid, [st["description"] for st in gt_subtasks])
        if not subtask_texts:
            continue

        q_vec = vectorizer.transform(subtask_texts)
        sims = cosine_similarity(q_vec, tfidf_matrix)  # (n_subtasks, n_skills)

        catr1, catr5, catr10 = 0, 0, 0
        for i, gc in enumerate(gt_categories):
            if i < sims.shape[0]:
                top_indices = np.argsort(-sims[i])[:TOP_K]
                top_cats = [skills[idx].categories for idx in top_indices if skills[idx].categories]
                if top_cats and gc in top_cats[0]:
                    catr1 += 1
                if any(gc in c for c in top_cats[:5]):
                    catr5 += 1
                if any(gc in c for c in top_cats[:10]):
                    catr10 += 1

        n_gt = len(gt_categories) if gt_categories else 1
        per_query.append({"query_id": qid, "catr1": catr1/n_gt, "catr5": catr5/n_gt, "catr10": catr10/n_gt})

    elapsed = time.time() - t0
    return {
        "config": "TF-IDF (sparse)",
        "catr1": round(np.mean([p["catr1"] for p in per_query]), 4),
        "catr5": round(np.mean([p["catr5"] for p in per_query]), 4),
        "catr10": round(np.mean([p["catr10"] for p in per_query]), 4),
        "n_queries": len(per_query),
        "elapsed": round(elapsed, 1),
        "per_query": per_query,
    }


# ---------------------------------------------------------------------------
# Strategy 2: MiniLM (paper default)
# ---------------------------------------------------------------------------
def run_minilm(skills, queries, sad_texts):
    from skillweaver.core.retriever import SkillRetriever

    logger.info("Building MiniLM index...")
    retriever = SkillRetriever(
        encoder_name="sentence-transformers/all-MiniLM-L6-v2",
        use_body=False, top_k=TOP_K,
    )
    retriever.build_index(skills)

    skill_id_to_cat = {s.skill_id: s.categories[0] for s in skills if s.categories}

    per_query = []
    t0 = time.time()
    for qi, q in enumerate(queries):
        qid = q.get("query_id", str(qi))
        gt_subtasks = q.get("subtasks", [])
        gt_categories = [
            skill_id_to_cat.get(st.get("ground_truth_skill_id", ""),
                                 st.get("required_category", ""))
            for st in gt_subtasks
        ]
        subtask_texts = sad_texts.get(qid, [st["description"] for st in gt_subtasks])
        if not subtask_texts:
            continue

        cands = retriever.search_batch(subtask_texts)
        catr1, catr5, catr10 = 0, 0, 0
        for i, gc in enumerate(gt_categories):
            if i < len(cands) and cands[i]:
                top_cats = [m.skill.categories for m in cands[i][:TOP_K] if m.skill.categories]
                if top_cats and gc in top_cats[0]:
                    catr1 += 1
                if any(gc in c for c in top_cats[:5]):
                    catr5 += 1
                if any(gc in c for c in top_cats[:10]):
                    catr10 += 1

        n_gt = len(gt_categories) if gt_categories else 1
        per_query.append({"query_id": qid, "catr1": catr1/n_gt, "catr5": catr5/n_gt, "catr10": catr10/n_gt})

    elapsed = time.time() - t0
    return {
        "config": "MiniLM-L6-v2 (dense, 384-dim)",
        "catr1": round(np.mean([p["catr1"] for p in per_query]), 4),
        "catr5": round(np.mean([p["catr5"] for p in per_query]), 4),
        "catr10": round(np.mean([p["catr10"] for p in per_query]), 4),
        "n_queries": len(per_query),
        "elapsed": round(elapsed, 1),
        "per_query": per_query,
    }


# ---------------------------------------------------------------------------
# Strategy 3: Qwen2.5-7B-Instruct embeddings (last hidden state, mean pooling)
# ---------------------------------------------------------------------------
def run_qwen_embed(skills, queries, sad_texts):
    import torch
    from transformers import AutoModel, AutoTokenizer

    logger.info("Building Qwen2.5-7B embedding index...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH, trust_remote_code=True)
    model = AutoModel.from_pretrained(
        MODEL_PATH, torch_dtype=torch.float16, device_map="cuda:0",
        trust_remote_code=True,
    )
    model.eval()

    def encode_texts(text_list, batch_size=32, max_length=256):
        all_embeddings = []
        for i in range(0, len(text_list), batch_size):
            batch = text_list[i:i+batch_size]
            inputs = tokenizer(batch, padding=True, truncation=True,
                             max_length=max_length, return_tensors="pt").to(model.device)
            with torch.no_grad():
                outputs = model(**inputs)
                # Mean pooling over non-padding tokens
                mask = inputs.attention_mask.unsqueeze(-1).float()
                embeddings = (outputs.last_hidden_state * mask).sum(1) / mask.sum(1)
                # L2 normalize
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
            all_embeddings.append(embeddings.cpu().numpy())
            if (i + batch_size) % 200 == 0:
                logger.info(f"  Encoded {i+batch_size}/{len(text_list)}")
        return np.vstack(all_embeddings).astype(np.float32)

    # Encode skills
    skill_texts = [s.to_retrieval_text(use_body=False) for s in skills]
    logger.info(f"Encoding {len(skill_texts)} skills with Qwen-7B...")
    skill_embs = encode_texts(skill_texts, batch_size=32, max_length=256)
    logger.info(f"Skill embeddings: {skill_embs.shape}")

    skill_id_to_cat = {s.skill_id: s.categories[0] for s in skills if s.categories}

    per_query = []
    t0 = time.time()
    for qi, q in enumerate(queries):
        qid = q.get("query_id", str(qi))
        gt_subtasks = q.get("subtasks", [])
        gt_categories = [
            skill_id_to_cat.get(st.get("ground_truth_skill_id", ""),
                                 st.get("required_category", ""))
            for st in gt_subtasks
        ]
        subtask_texts = sad_texts.get(qid, [st["description"] for st in gt_subtasks])
        if not subtask_texts:
            continue

        q_embs = encode_texts(subtask_texts, batch_size=8, max_length=256)
        sims = q_embs @ skill_embs.T  # (n_subtasks, n_skills)

        catr1, catr5, catr10 = 0, 0, 0
        for i, gc in enumerate(gt_categories):
            if i < sims.shape[0]:
                top_indices = np.argsort(-sims[i])[:TOP_K]
                top_cats = [skills[idx].categories for idx in top_indices if skills[idx].categories]
                if top_cats and gc in top_cats[0]:
                    catr1 += 1
                if any(gc in c for c in top_cats[:5]):
                    catr5 += 1
                if any(gc in c for c in top_cats[:10]):
                    catr10 += 1

        n_gt = len(gt_categories) if gt_categories else 1
        per_query.append({"query_id": qid, "catr1": catr1/n_gt, "catr5": catr5/n_gt, "catr10": catr10/n_gt})

        if (qi + 1) % 50 == 0:
            logger.info(f"  Progress: {qi+1}/{len(queries)}")

    elapsed = time.time() - t0
    dim = skill_embs.shape[1]
    del model
    torch.cuda.empty_cache()
    return {
        "config": f"Qwen2.5-7B-Instruct (dense, {dim}-dim)",
        "catr1": round(np.mean([p["catr1"] for p in per_query]), 4),
        "catr5": round(np.mean([p["catr5"] for p in per_query]), 4),
        "catr10": round(np.mean([p["catr10"] for p in per_query]), 4),
        "n_queries": len(per_query),
        "elapsed": round(elapsed, 1),
        "per_query": per_query,
    }


def main():
    skills, queries = load_data()
    sad_texts = load_sad_subtask_texts()

    all_results = []

    # 1. TF-IDF
    logger.info("=" * 50)
    logger.info("Running TF-IDF baseline...")
    logger.info("=" * 50)
    r1 = run_tfidf(skills, queries, sad_texts)
    all_results.append(r1)
    logger.info(f"  TF-IDF: CatR@1={r1['catr1']:.3f}, CatR@5={r1['catr5']:.3f}, CatR@10={r1['catr10']:.3f}")

    # 2. MiniLM
    logger.info("=" * 50)
    logger.info("Running MiniLM baseline...")
    logger.info("=" * 50)
    r2 = run_minilm(skills, queries, sad_texts)
    all_results.append(r2)
    logger.info(f"  MiniLM: CatR@1={r2['catr1']:.3f}, CatR@5={r2['catr5']:.3f}, CatR@10={r2['catr10']:.3f}")

    # 3. Qwen-7B embeddings
    logger.info("=" * 50)
    logger.info("Running Qwen-7B embedding baseline...")
    logger.info("=" * 50)
    r3 = run_qwen_embed(skills, queries, sad_texts)
    all_results.append(r3)
    logger.info(f"  Qwen-7B: CatR@1={r3['catr1']:.3f}, CatR@5={r3['catr5']:.3f}, CatR@10={r3['catr10']:.3f}")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / "encoder_baselines.json"
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False)
    logger.info(f"Results saved to {out_path}")

    # Print summary
    print("\n" + "=" * 70)
    print("ENCODER BASELINE COMPARISON")
    print("=" * 70)
    print(f"{'Strategy':<45} {'CatR@1':>8} {'CatR@5':>8} {'CatR@10':>8}")
    print("-" * 70)
    for r in all_results:
        print(f"  {r['config']:<43} {r['catr1']:>8.3f} {r['catr5']:>8.3f} {r['catr10']:>8.3f}")
    print("=" * 70)


if __name__ == "__main__":
    main()
