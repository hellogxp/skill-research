#!/usr/bin/env python3
"""Build the SkillWeaver benchmark v3 from raw SKILL.md files.

Steps:
1. Scan skillweaver/demo-skills/ for all SKILL.md files (raw skills)
2. Parse into unified Skill objects and export as skill_pool.jsonl
3. Generate compositional queries (easy/medium/hard) with ground truth
4. Generate difficulty-stratified query files
5. Export collection stats
"""

import json
import random
import sys
from pathlib import Path

# Add skillweaver to path
WORKSPACE = Path("/mnt/workspace")
sys.path.insert(0, str(WORKSPACE / "skillweaver" / "src"))

from skillweaver.adapters.skill_md import scan_directory
from skillweaver.core.models import Skill

random.seed(42)

# Paths
SKILLS_DIR = WORKSPACE / "skillweaver" / "demo-skills"
DATA_DIR = WORKSPACE / "skill-research" / "data"
RAW_DIR = DATA_DIR / "raw_skills"
PROCESSED_DIR = DATA_DIR / "processed_v3"
BENCH_DIR = DATA_DIR / "benchmark_v3"

for d in [RAW_DIR, PROCESSED_DIR, BENCH_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# Step 1: Scan and collect raw skills
print("Step 1: Scanning raw skills from SKILL.md files...")
skills = scan_directory(SKILLS_DIR, recursive=True)
print(f"  Found {len(skills)} skills")

# Step 2: Export raw skills
print("Step 2: Exporting raw skills...")
with open(RAW_DIR / "all_skills.jsonl", "w") as f:
    for skill in skills:
        f.write(json.dumps(skill.to_dict(), ensure_ascii=False) + "\n")

# Collect stats
category_counts = {}
for skill in skills:
    for cat in skill.categories:
        category_counts[cat] = category_counts.get(cat, 0) + 1

stats = {
    "total_skills": len(skills),
    "categories": category_counts,
    "num_categories": len(category_counts),
    "avg_skills_per_category": round(len(skills) / max(len(category_counts), 1), 1),
}
with open(RAW_DIR / "collection_stats.json", "w") as f:
    json.dump(stats, f, indent=2)
print(f"  Categories: {category_counts}")

# Step 3: Build skill pool (processed)
print("Step 3: Building processed skill pool...")
with open(PROCESSED_DIR / "skill_pool.jsonl", "w") as f:
    for skill in skills:
        f.write(json.dumps(skill.to_dict(), ensure_ascii=False) + "\n")

# Step 4: Generate compositional queries
print("Step 4: Generating compositional queries...")

# Group skills by category
cat_skills: dict[str, list] = {}
for skill in skills:
    for cat in skill.categories:
        cat_skills.setdefault(cat, []).append(skill)

categories = list(cat_skills.keys())


def generate_query_template(skill_combo, difficulty):
    """Generate a natural-language compositional query from a skill combination."""
    descriptions = [s.description.lower().rstrip(".") for s in skill_combo]
    if len(descriptions) == 2:
        connectors = ["and then", "and", "followed by"]
        return f"{descriptions[0]} {random.choice(connectors)} {descriptions[1]}"
    elif len(descriptions) == 3:
        return f"{descriptions[0]}, then {descriptions[1]}, and finally {descriptions[2]}"
    else:
        middle = ", ".join(descriptions[1:-1])
        return f"{descriptions[0]}, {middle}, and finally {descriptions[-1]}"


queries = []
query_id = 0

# Easy: 2 skills (150 queries)
print("  Generating easy queries (2 skills)...")
for _ in range(150):
    cats = random.sample(categories, min(2, len(categories)))
    skill_combo = [random.choice(cat_skills[c]) for c in cats]
    query_text = generate_query_template(skill_combo, "easy")
    subtasks = []
    for i, skill in enumerate(skill_combo):
        subtasks.append({
            "step_index": i,
            "description": skill.description,
            "required_category": skill.categories[0] if skill.categories else "",
            "ground_truth_skill_id": skill.skill_id,
            "ground_truth_skill_name": skill.name,
        })
    edges = [
        {"from_step": i, "to_step": i + 1, "dependency_type": "sequential"}
        for i in range(len(skill_combo) - 1)
    ]
    queries.append({
        "query_id": f"cq_{query_id:04d}",
        "query": query_text,
        "difficulty": "easy",
        "num_skills": 2,
        "subtasks": subtasks,
        "edges": edges,
        "source": "template_generated",
    })
    query_id += 1

# Medium: 3 skills (100 queries)
print("  Generating medium queries (3 skills)...")
for _ in range(100):
    cats = random.sample(categories, min(3, len(categories)))
    skill_combo = [random.choice(cat_skills[c]) for c in cats]
    query_text = generate_query_template(skill_combo, "medium")
    subtasks = []
    for i, skill in enumerate(skill_combo):
        subtasks.append({
            "step_index": i,
            "description": skill.description,
            "required_category": skill.categories[0] if skill.categories else "",
            "ground_truth_skill_id": skill.skill_id,
            "ground_truth_skill_name": skill.name,
        })
    edges = [
        {"from_step": i, "to_step": i + 1, "dependency_type": "sequential"}
        for i in range(len(skill_combo) - 1)
    ]
    queries.append({
        "query_id": f"cq_{query_id:04d}",
        "query": query_text,
        "difficulty": "medium",
        "num_skills": 3,
        "subtasks": subtasks,
        "edges": edges,
        "source": "template_generated",
    })
    query_id += 1

# Hard: 4-5 skills (50 queries)
print("  Generating hard queries (4-5 skills)...")
for _ in range(50):
    n = random.choice([4, 5])
    cats = random.sample(categories, min(n, len(categories)))
    skill_combo = [random.choice(cat_skills[c]) for c in cats]
    query_text = generate_query_template(skill_combo, "hard")
    subtasks = []
    for i, skill in enumerate(skill_combo):
        subtasks.append({
            "step_index": i,
            "description": skill.description,
            "required_category": skill.categories[0] if skill.categories else "",
            "ground_truth_skill_id": skill.skill_id,
            "ground_truth_skill_name": skill.name,
        })
    edges = [
        {"from_step": i, "to_step": i + 1, "dependency_type": "sequential"}
        for i in range(len(skill_combo) - 1)
    ]
    queries.append({
        "query_id": f"cq_{query_id:04d}",
        "query": query_text,
        "difficulty": "hard",
        "num_skills": n,
        "subtasks": subtasks,
        "edges": edges,
        "source": "template_generated",
    })
    query_id += 1

# Step 5: Export benchmark files
print("Step 5: Exporting benchmark files...")
with open(BENCH_DIR / "compositional_queries.jsonl", "w") as f:
    for q in queries:
        f.write(json.dumps(q, ensure_ascii=False) + "\n")

# Split by difficulty
for diff in ["easy", "medium", "hard"]:
    subset = [q for q in queries if q["difficulty"] == diff]
    with open(BENCH_DIR / f"queries_{diff}.jsonl", "w") as f:
        for q in subset:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")

# Benchmark stats
bench_stats = {
    "total_queries": len(queries),
    "easy": sum(1 for q in queries if q["difficulty"] == "easy"),
    "medium": sum(1 for q in queries if q["difficulty"] == "medium"),
    "hard": sum(1 for q in queries if q["difficulty"] == "hard"),
    "total_skills": len(skills),
    "num_categories": len(categories),
    "categories": categories,
    "avg_skills_per_query": round(
        sum(q["num_skills"] for q in queries) / len(queries), 2
    ),
}
with open(BENCH_DIR / "benchmark_stats.json", "w") as f:
    json.dump(bench_stats, f, indent=2)

print(f"\nDone! Benchmark v3 built successfully.")
print(f"  Total queries: {len(queries)}")
print(f"  Easy: {bench_stats['easy']}, Medium: {bench_stats['medium']}, Hard: {bench_stats['hard']}")
print(f"  Total skills: {len(skills)}, Categories: {len(categories)}")
