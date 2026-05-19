#!/usr/bin/env python3
"""Build compositional benchmark queries from real skill pool.

Generates queries that require 2-5 skills to complete, with ground truth
skill assignments and difficulty levels.

Strategy:
1. Group skills by category
2. Generate cross-category compositional queries
3. Ensure diverse difficulty distribution (easy=2, medium=3, hard=4-5 skills)
"""
import json
import random
import hashlib
from pathlib import Path
from collections import defaultdict

SKILL_POOL_PATH = Path("data/skill_pool.jsonl")
OUTPUT_DIR = Path("data")
OUTPUT_PATH = OUTPUT_DIR / "compositional_queries.jsonl"

RANDOM_SEED = 42
TARGET_QUERIES = 300  # 150 easy + 100 medium + 50 hard

# Templates for compositional queries
# Each template takes N skill descriptions and composes them
EASY_TEMPLATES = [
    "I need to {verb1} and then {verb2}.",
    "First {verb1}, then {verb2} with the results.",
    "Can you help me {verb1} and afterwards {verb2}?",
    "{verb1} and send the output to {verb2}.",
    "Take the data from {verb1} and use it to {verb2}.",
]

MEDIUM_TEMPLATES = [
    "I want to {verb1}, then {verb2}, and finally {verb3}.",
    "Start by {verb1_ing}, process it with {verb2}, and {verb3} the results.",
    "Help me {verb1}, analyze the output by {verb2_ing}, then {verb3}.",
    "{verb1}, feed the results into {verb2}, and conclude by {verb3_ing}.",
    "First {verb1}, next {verb2}, and then {verb3} everything.",
]

HARD_TEMPLATES = [
    "I need a workflow that {verb1}, {verb2}, {verb3}, and {verb4}.",
    "Build a pipeline: {verb1}, then {verb2}, {verb3} in parallel, and finally {verb4}.",
    "Set up a system to {verb1}, automatically {verb2}, {verb3}, then {verb4}, and {verb5}.",
    "Create an automation: first {verb1}, next {verb2}, then {verb3} and {verb4}.",
    "Help me {verb1}, {verb2} the output, {verb3} the analysis, and {verb4} the results.",
]

# Task verbs by category (used to generate natural queries)
CATEGORY_VERBS = {
    "developer-tools": [
        "lint the codebase", "format the code", "run static analysis",
        "generate API documentation", "set up CI/CD pipeline",
        "create a new project scaffold", "manage dependencies",
        "debug the application", "profile performance",
    ],
    "databases": [
        "query the database", "migrate the schema", "back up the data",
        "run a complex SQL query", "set up replication",
        "analyze query performance", "export data to CSV",
    ],
    "data-processing": [
        "transform the data", "clean the dataset", "aggregate the metrics",
        "run a data pipeline", "validate data quality",
        "merge multiple datasets", "filter outliers",
    ],
    "search-extraction": [
        "scrape the website", "extract structured data", "search the web",
        "crawl the documentation", "parse the HTML content",
        "index the documents", "find relevant articles",
    ],
    "cloud-infrastructure": [
        "deploy to the cloud", "scale the infrastructure",
        "manage containers", "configure the load balancer",
        "set up monitoring alerts", "provision new servers",
    ],
    "communication": [
        "send a notification", "post to Slack", "send an email report",
        "notify the team", "broadcast an announcement",
        "send a message to the channel", "create a group chat",
    ],
    "browser-automation": [
        "automate browser testing", "fill out the web form",
        "take a screenshot of the page", "navigate the website",
        "click through the checkout flow", "extract page content",
    ],
    "security": [
        "scan for vulnerabilities", "check security headers",
        "audit access permissions", "encrypt the data",
        "rotate the API keys", "validate SSL certificates",
    ],
    "monitoring-observability": [
        "check system metrics", "analyze the logs",
        "set up alerting rules", "monitor uptime",
        "track error rates", "create a dashboard",
    ],
    "file-management": [
        "organize the files", "convert the document format",
        "compress the archive", "extract the zip file",
        "rename files in bulk", "manage file permissions",
    ],
    "ai-ml": [
        "generate text with AI", "classify the content",
        "summarize the document", "translate the text",
        "detect sentiment", "extract entities",
    ],
    "knowledge-management": [
        "search the knowledge base", "update the documentation",
        "organize notes", "index research papers",
        "retrieve relevant context", "manage bookmarks",
    ],
    "finance": [
        "fetch stock prices", "analyze financial data",
        "process the payment", "generate an invoice",
        "calculate tax", "track expenses",
    ],
    "productivity": [
        "schedule a meeting", "create a task list",
        "manage the project board", "track time spent",
        "generate a report", "update the spreadsheet",
    ],
    "multimedia": [
        "convert the video format", "resize the images",
        "extract audio from video", "generate thumbnails",
        "compress media files", "add subtitles",
    ],
    "code-execution": [
        "run the script", "execute the test suite",
        "compile the project", "evaluate the code snippet",
        "benchmark the function", "sandbox the execution",
    ],
    "integrations": [
        "connect to the API", "sync data between services",
        "configure the webhook", "integrate with the platform",
        "automate the workflow", "bridge the two systems",
    ],
    "marketing-analytics": [
        "analyze campaign metrics", "track conversion rates",
        "generate marketing reports", "segment the audience",
        "monitor social mentions", "optimize ad spend",
    ],
    "gaming-entertainment": [
        "fetch game stats", "track player progress",
        "generate game content", "analyze match data",
        "manage game inventory", "query game databases",
    ],
    "location-services": [
        "geocode the address", "calculate the route",
        "find nearby places", "get weather data",
        "track the shipment", "map the locations",
    ],
    "science-research": [
        "search PubMed", "analyze protein sequences",
        "visualize molecular structures", "process research data",
        "query scientific databases", "analyze experimental results",
    ],
    "legal-compliance": [
        "check compliance requirements", "review the contract",
        "analyze legal documents", "validate regulatory status",
    ],
    "e-commerce": [
        "process the order", "update inventory",
        "calculate shipping costs", "manage product listings",
        "track delivery status",
    ],
    "data-visualization": [
        "create a chart", "generate a dashboard",
        "visualize the data", "plot the metrics",
    ],
}


def load_skills():
    skills = []
    with open(SKILL_POOL_PATH) as f:
        for line in f:
            if line.strip():
                skills.append(json.loads(line.strip()))
    return skills


def group_by_category(skills):
    groups = defaultdict(list)
    for s in skills:
        for cat in s['categories']:
            groups[cat].append(s)
    return groups


def pick_skill_from_category(cat_skills, used_ids=None):
    """Pick a random skill from a category, avoiding duplicates."""
    if used_ids is None:
        used_ids = set()
    available = [s for s in cat_skills if s['skill_id'] not in used_ids]
    if not available:
        available = cat_skills
    return random.choice(available)


def generate_verb(category):
    """Get a task verb for a category."""
    verbs = CATEGORY_VERBS.get(category, [f"use {category} tools"])
    return random.choice(verbs)


def generate_query(difficulty, categories, cat_skills_map):
    """Generate a compositional query combining skills from different categories."""
    if difficulty == "easy":
        n_skills = 2
        templates = EASY_TEMPLATES
    elif difficulty == "medium":
        n_skills = 3
        templates = MEDIUM_TEMPLATES
    else:
        n_skills = random.choice([4, 5])
        templates = HARD_TEMPLATES

    # Pick n_skills categories (prefer diverse)
    selected_cats = random.sample(categories, min(n_skills, len(categories)))
    while len(selected_cats) < n_skills:
        selected_cats.append(random.choice(categories))

    # Pick skills and generate verbs
    used_ids = set()
    subtasks = []
    for cat in selected_cats:
        skill = pick_skill_from_category(cat_skills_map[cat], used_ids)
        used_ids.add(skill['skill_id'])
        verb = generate_verb(cat)
        subtasks.append({
            "description": verb,
            "required_category": cat,
            "ground_truth_skill_id": skill['skill_id'],
            "ground_truth_skill_name": skill['name'],
        })

    # Build query from template
    template = random.choice(templates)
    verbs = [st['description'] for st in subtasks]

    # Fill template based on number of verbs
    if n_skills == 2:
        query = template.format(
            verb1=verbs[0], verb2=verbs[1],
        )
    elif n_skills == 3:
        query = template.format(
            verb1=verbs[0], verb2=verbs[1], verb3=verbs[2],
            verb1_ing=verbs[0].replace("the ", "").replace("a ", ""),
            verb2_ing=verbs[1].replace("the ", "").replace("a ", ""),
            verb3_ing=verbs[2].replace("the ", "").replace("a ", ""),
        )
    else:
        # For 4-5 skills
        fmt_dict = {}
        for i, v in enumerate(verbs, 1):
            fmt_dict[f'verb{i}'] = v
            fmt_dict[f'verb{i}_ing'] = v.replace("the ", "").replace("a ", "")
        try:
            query = template.format(**fmt_dict)
        except (KeyError, IndexError):
            # Fallback: join with commas
            query = f"I need to: {', '.join(verbs[:-1])}, and finally {verbs[-1]}."

    return {
        "query": query,
        "num_skills": n_skills,
        "difficulty": difficulty,
        "subtasks": subtasks,
    }


def main():
    random.seed(RANDOM_SEED)

    skills = load_skills()
    cat_skills_map = group_by_category(skills)
    categories = [c for c in cat_skills_map if len(cat_skills_map[c]) >= 5]

    print(f"Total skills: {len(skills)}")
    print(f"Categories with ≥5 skills: {len(categories)}")
    print(f"Categories: {', '.join(sorted(categories))}")

    queries = []

    # Easy: 150 queries, 2 skills each
    for i in range(150):
        q = generate_query("easy", categories, cat_skills_map)
        q["query_id"] = f"easy_{i:03d}"
        queries.append(q)

    # Medium: 100 queries, 3 skills each
    for i in range(100):
        q = generate_query("medium", categories, cat_skills_map)
        q["query_id"] = f"med_{i:03d}"
        queries.append(q)

    # Hard: 50 queries, 4-5 skills each
    for i in range(50):
        q = generate_query("hard", categories, cat_skills_map)
        q["query_id"] = f"hard_{i:03d}"
        queries.append(q)

    random.shuffle(queries)

    # Stats
    diff_counts = defaultdict(int)
    skill_counts = defaultdict(int)
    for q in queries:
        diff_counts[q['difficulty']] += 1
        skill_counts[q['num_skills']] += 1

    print(f"\nGenerated {len(queries)} queries:")
    for d, c in sorted(diff_counts.items()):
        print(f"  {d}: {c}")
    print(f"Skills per query: {dict(sorted(skill_counts.items()))}")

    # Save
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, 'w') as f:
        for q in queries:
            f.write(json.dumps(q, ensure_ascii=False) + '\n')
    print(f"\nSaved to {OUTPUT_PATH}")

    # Show examples
    print("\nExamples:")
    for q in queries[:3]:
        print(f"  [{q['difficulty']}] {q['query']}")
        for st in q['subtasks']:
            print(f"    -> {st['required_category']}: {st['ground_truth_skill_name']}")


if __name__ == "__main__":
    main()
