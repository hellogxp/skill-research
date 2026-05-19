"""Generate 200 human-style compositional queries using qwen-max API.

Distribution: 80 easy (2 skills) + 80 medium (3 skills) + 40 hard (4-5 skills)
Each query has proper subtask descriptions and correctly assigned ground truth skills.
"""

import json
import random
import time
from pathlib import Path
from openai import OpenAI

# Config
API_BASE = "https://dashscope.aliyuncs.com/compatible-mode/v1"
API_KEY = "sk-ba914ace8a6a42e0b0202e5ca8927418"
MODEL = "qwen-max"
OUTPUT_PATH = Path("data/benchmark_v3/human_queries_v2.jsonl")

client = OpenAI(base_url=API_BASE, api_key=API_KEY)

# Load skill pool
SKILL_POOL_PATH = Path("data/processed_v3/skill_pool.jsonl")
skills_by_category = {}
all_skills = []

for line in open(SKILL_POOL_PATH):
    skill = json.loads(line)
    all_skills.append(skill)
    for cat in skill["categories"]:
        if cat not in skills_by_category:
            skills_by_category[cat] = []
        skills_by_category[cat].append(skill)

CATEGORIES = list(skills_by_category.keys())
print(f"Loaded {len(all_skills)} skills across {len(CATEGORIES)} categories")

# Distribution
DISTRIBUTION = [
    ("easy", 2, 80),
    ("medium", 3, 80),
    ("hard", random.choice([4, 5]), 40),
]

SYSTEM_PROMPT = """You are a creative query generator for a skill-routing benchmark. 
Generate a natural, human-style query that requires EXACTLY {num_skills} different capabilities.

Rules:
1. Write as if you're a real user asking an AI assistant for help
2. NEVER mention tool names, skill names, API names, or MCP server names
3. Each subtask should be a SHORT phrase (5-15 words) describing what needs to be done
4. The query should flow naturally - don't just list tasks, connect them logically
5. Use varied sentence structures (imperatives, questions, conditional requests)
6. Include realistic context (company names, project names, specific details)

The query must combine these {num_skills} capabilities (categories):
{categories}

Respond in JSON format:
{{
  "query": "the full natural language query",
  "subtasks": [
    {{"description": "short subtask phrase", "category": "category_name"}},
    ...
  ]
}}"""


def select_categories(num_skills):
    """Select num_skills distinct categories, weighted by pool size."""
    weights = [len(skills_by_category[c]) for c in CATEGORIES]
    selected = []
    available = list(range(len(CATEGORIES)))
    for _ in range(num_skills):
        pool_weights = [weights[i] for i in available]
        total = sum(pool_weights)
        probs = [w / total for w in pool_weights]
        idx = random.choices(available, weights=probs, k=1)[0]
        selected.append(CATEGORIES[idx])
        available.remove(idx)
    return selected


def pick_ground_truth_skill(category):
    """Pick a random skill from the category as ground truth."""
    candidates = skills_by_category[category]
    skill = random.choice(candidates)
    return skill["skill_id"], skill["name"]


def generate_query(num_skills, difficulty, query_idx):
    """Generate one human-style query via qwen-max."""
    categories = select_categories(num_skills)
    cat_list = "\n".join(f"- {c}" for c in categories)

    prompt = SYSTEM_PROMPT.format(
        num_skills=num_skills, categories=cat_list
    )

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": f"Generate query #{query_idx + 1} (difficulty: {difficulty}, {num_skills} skills needed). Be creative and realistic."}
                ],
                temperature=0.9,
                max_tokens=500,
                response_format={"type": "json_object"},
            )
            content = response.choices[0].message.content
            result = json.loads(content)

            # Validate
            if "query" not in result or "subtasks" not in result:
                raise ValueError("Missing fields")
            if len(result["subtasks"]) != num_skills:
                raise ValueError(f"Expected {num_skills} subtasks, got {len(result['subtasks'])}")

            # Build final record
            subtasks = []
            for i, st in enumerate(result["subtasks"]):
                cat = categories[i]
                skill_id, skill_name = pick_ground_truth_skill(cat)
                subtasks.append({
                    "description": st["description"][:80],
                    "required_category": cat,
                    "ground_truth_skill_id": skill_id,
                    "ground_truth_skill_name": skill_name,
                })

            return {
                "query": result["query"],
                "subtasks": subtasks,
                "difficulty": difficulty,
                "num_skills": num_skills,
                "query_id": f"human_{query_idx:03d}",
            }

        except Exception as e:
            print(f"  Attempt {attempt + 1} failed: {e}")
            time.sleep(2)

    return None


def main():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    results = []
    query_idx = 0
    failed = 0

    for difficulty, num_skills_base, count in DISTRIBUTION:
        print(f"\n=== Generating {count} {difficulty} queries (base {num_skills_base} skills) ===")
        for i in range(count):
            # For hard, randomly choose 4 or 5
            num_skills = num_skills_base if difficulty != "hard" else random.choice([4, 5])

            record = generate_query(num_skills, difficulty, query_idx)
            if record:
                results.append(record)
                if (i + 1) % 10 == 0:
                    print(f"  Progress: {i + 1}/{count}")
            else:
                failed += 1
                print(f"  FAILED query #{query_idx}")

            query_idx += 1
            # Rate limiting
            time.sleep(0.5)

    # Write output
    with open(OUTPUT_PATH, "w") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(f"\n=== Done ===")
    print(f"Generated: {len(results)} queries")
    print(f"Failed: {failed}")
    print(f"Output: {OUTPUT_PATH}")

    # Stats
    by_diff = {}
    for r in results:
        by_diff.setdefault(r["difficulty"], []).append(r)
    for d, qs in by_diff.items():
        print(f"  {d}: {len(qs)} queries")


if __name__ == "__main__":
    random.seed(42)
    main()
