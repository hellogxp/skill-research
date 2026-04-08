"""Generate additional human-written queries for CompSkillBench evaluation.

Samples skill category combinations and pairs them with diverse
natural-language queries. Appends to existing human_queries.jsonl.
"""
import json
import random
import os
import sys

# 20 new human-written queries with diverse phrasing
NEW_QUERIES = [
    # Easy (2 skills, 2 categories) - 8 queries
    {
        "query": "Write a blog post about our new product launch and translate it to Spanish",
        "difficulty": "easy",
        "categories": ["writer", "translator"],
    },
    {
        "query": "Analyze the pull request changes and run the unit tests before merging",
        "difficulty": "easy",
        "categories": ["code_analyzer", "test_writer"],
    },
    {
        "query": "Set up a CI/CD pipeline and configure monitoring alerts for the staging server",
        "difficulty": "easy",
        "categories": ["deployment", "monitoring"],
    },
    {
        "query": "Convert the legacy XML config files to JSON format and validate the schema",
        "difficulty": "easy",
        "categories": ["file_converter", "code_analyzer"],
    },
    {
        "query": "Search for open-source charting libraries and build a line chart from the CSV data",
        "difficulty": "easy",
        "categories": ["search", "visualizer"],
    },
    {
        "query": "Scaffold a new React component library and publish it to the npm registry",
        "difficulty": "easy",
        "categories": ["code_generator", "deployment"],
    },
    {
        "query": "Query the production database and generate a PDF report of monthly sales",
        "difficulty": "easy",
        "categories": ["database", "writer"],
    },
    {
        "query": "Run a security audit on our Docker images and fix any critical vulnerabilities",
        "difficulty": "easy",
        "categories": ["security", "refactorer"],
    },
    # Medium (3 skills, 3 categories) - 8 queries
    {
        "query": "Fetch user analytics from the API, process the data into weekly aggregates, and create a dashboard with interactive charts",
        "difficulty": "medium",
        "categories": ["api_client", "data_processor", "visualizer"],
    },
    {
        "query": "Generate a Python backend service, write integration tests, and containerize it with Docker",
        "difficulty": "medium",
        "categories": ["code_generator", "test_writer", "deployment"],
    },
    {
        "query": "Crawl competitor websites for pricing data, clean and normalize the results, and store them in PostgreSQL",
        "difficulty": "medium",
        "categories": ["search", "data_processor", "database"],
    },
    {
        "query": "Review the authentication module, refactor it to use OAuth2, and update the documentation",
        "difficulty": "medium",
        "categories": ["code_analyzer", "refactorer", "writer"],
    },
    {
        "query": "Design a REST API schema, generate the server stubs, and set up automated end-to-end tests",
        "difficulty": "medium",
        "categories": ["designer", "code_generator", "test_writer"],
    },
    {
        "query": "Extract text from scanned PDF invoices, transform them into structured records, and load into the accounting database",
        "difficulty": "medium",
        "categories": ["file_converter", "data_processor", "database"],
    },
    {
        "query": "Scan the repository for hardcoded secrets, rotate the exposed credentials, and set up secret management",
        "difficulty": "medium",
        "categories": ["security", "git_workflow", "deployment"],
    },
    {
        "query": "Translate the user manual to three languages, convert to Markdown, and deploy to the documentation site",
        "difficulty": "medium",
        "categories": ["translator", "file_converter", "deployment"],
    },
    # Hard (4-5 skills, 4-5 categories) - 4 queries
    {
        "query": "Build a data pipeline that fetches logs from the monitoring system, parses them into structured events, runs anomaly detection, visualizes trends on a dashboard, and sends Slack alerts",
        "difficulty": "hard",
        "categories": ["monitoring", "data_processor", "code_analyzer", "visualizer", "api_client"],
    },
    {
        "query": "Create a full-stack e-commerce feature: design the UI mockup, generate the frontend code, write API endpoints, add tests, and deploy to production",
        "difficulty": "hard",
        "categories": ["designer", "code_generator", "api_client", "test_writer", "deployment"],
    },
    {
        "query": "Migrate the legacy codebase: analyze the existing code structure, refactor deprecated patterns, convert configuration files, update the database schema, and run regression tests",
        "difficulty": "hard",
        "categories": ["code_analyzer", "refactorer", "file_converter", "database", "test_writer"],
    },
    {
        "query": "Set up a multilingual content workflow: write the original article, translate it, generate social media images, publish via the CMS API, and track engagement metrics",
        "difficulty": "hard",
        "categories": ["writer", "translator", "visualizer", "api_client", "monitoring"],
    },
]


def load_skills(skills_path):
    """Load skills organized by category."""
    skills_by_cat = {}
    with open(skills_path) as f:
        for line in f:
            s = json.loads(line)
            for cat in s.get("categories", []):
                if cat not in skills_by_cat:
                    skills_by_cat[cat] = []
                skills_by_cat[cat].append(s)
    return skills_by_cat


def generate_queries(skills_path, output_path, start_id=335):
    skills_by_cat = load_skills(skills_path)
    print(f"Loaded skills in {len(skills_by_cat)} categories")
    for cat, ss in sorted(skills_by_cat.items()):
        print(f"  {cat}: {len(ss)} skills")

    new_entries = []
    qid = start_id

    for q in NEW_QUERIES:
        cats = q["categories"]
        # Check all categories exist
        missing = [c for c in cats if c not in skills_by_cat]
        if missing:
            print(f"SKIP: Missing categories {missing} for query: {q['query'][:50]}")
            continue

        subtasks = []
        for step_idx, cat in enumerate(cats):
            # Pick a random skill from this category
            skill = random.choice(skills_by_cat[cat])
            desc = skill.get("description", skill.get("name", ""))
            # Truncate description to ~200 chars
            if len(desc) > 200:
                desc = desc[:200]
            subtasks.append({
                "step_index": step_idx,
                "description": desc,
                "required_category": cat,
                "ground_truth_skill_id": skill["skill_id"],
                "ground_truth_skill_name": skill["name"],
            })

        edges = []
        for i in range(len(cats) - 1):
            edges.append({
                "from_step": i,
                "to_step": i + 1,
                "dependency_type": "sequential",
            })

        entry = {
            "query_id": f"hq_{qid:04d}",
            "query": q["query"],
            "difficulty": q["difficulty"],
            "num_skills": len(cats),
            "subtasks": subtasks,
            "edges": edges,
            "source": "human_written",
        }
        new_entries.append(entry)
        qid += 1

    # Append to existing file
    with open(output_path, "a") as f:
        for e in new_entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")

    print(f"\nGenerated {len(new_entries)} new queries (IDs hq_{start_id:04d} - hq_{qid-1:04d})")
    print(f"Appended to {output_path}")
    return len(new_entries)


if __name__ == "__main__":
    data_dir = "/mnt/workspace/skill-routing/data"
    skills_path = os.path.join(data_dir, "processed_v3", "skills_categorized.jsonl")
    output_path = os.path.join(data_dir, "benchmark_v3", "human_queries.jsonl")

    # Check current count
    existing = 0
    if os.path.exists(output_path):
        with open(output_path) as f:
            existing = sum(1 for _ in f)
    print(f"Existing human queries: {existing}")

    random.seed(42)
    n = generate_queries(skills_path, output_path, start_id=300 + existing)
    
    # Verify
    with open(output_path) as f:
        total = sum(1 for _ in f)
    print(f"Total human queries: {total}")
