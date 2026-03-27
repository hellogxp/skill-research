"""
Compositional Query Benchmark Builder v3

Key fixes over v2:
1. Deduplicate skills by name (many repos fork the same skills)
2. Strict categorization using name+description only (not body keywords)
3. Build queries FROM actual skill descriptions (no semantic gap)
4. Category-level evaluation support
5. Proper skill pool with guaranteed GT presence
"""

import json
import random
import logging
import hashlib
import re
from pathlib import Path
from dataclasses import dataclass, asdict, field
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_SKILLS_PATH = Path("/mnt/workspace/skill-routing/data/raw_skills/all_skills.jsonl")
BENCHMARK_DIR = Path("/mnt/workspace/skill-routing/data/benchmark_v3")
PROCESSED_DIR = Path("/mnt/workspace/skill-routing/data/processed_v3")


# ============================================================
# Strict category definitions (name+description keywords only)
# ============================================================

CATEGORY_RULES = {
    "api_client": {
        "keywords": ["api", "rest", "http", "endpoint", "request", "fetch data", "graphql"],
        "anti_keywords": ["test", "document", "write"],
        "description": "Fetch data from APIs or web services",
    },
    "web_scraper": {
        "keywords": ["scrape", "crawl", "spider", "extract from web", "parse html", "browser"],
        "anti_keywords": ["test"],
        "description": "Scrape or crawl web pages",
    },
    "file_converter": {
        "keywords": ["convert", "transform", "csv", "json", "excel", "pdf", "export format", "markdown"],
        "anti_keywords": ["test", "review"],
        "description": "Convert data between file formats",
    },
    "code_analyzer": {
        "keywords": ["analyze code", "code review", "lint", "static analysis", "code quality"],
        "anti_keywords": [],
        "description": "Analyze or review source code",
    },
    "code_generator": {
        "keywords": ["generate code", "scaffold", "boilerplate", "create component", "code generation"],
        "anti_keywords": ["test", "review"],
        "description": "Generate source code or components",
    },
    "test_writer": {
        "keywords": ["test", "unittest", "pytest", "jest", "spec", "test suite", "testing"],
        "anti_keywords": [],
        "description": "Write or generate tests",
    },
    "documentation": {
        "keywords": ["document", "readme", "docstring", "jsdoc", "api doc", "documentation"],
        "anti_keywords": ["test"],
        "description": "Generate documentation",
    },
    "database": {
        "keywords": ["database", "sql", "query", "migration", "schema", "postgres", "mysql", "mongodb"],
        "anti_keywords": [],
        "description": "Database operations and queries",
    },
    "deployment": {
        "keywords": ["deploy", "docker", "kubernetes", "ci/cd", "pipeline", "container", "cloud"],
        "anti_keywords": [],
        "description": "Deploy applications or manage infrastructure",
    },
    "security": {
        "keywords": ["security", "vulnerability", "audit", "scan", "penetration", "auth"],
        "anti_keywords": [],
        "description": "Security analysis and vulnerability scanning",
    },
    "data_processor": {
        "keywords": ["process data", "clean data", "transform data", "etl", "pipeline", "normalize"],
        "anti_keywords": ["test", "deploy"],
        "description": "Process, clean, or transform data",
    },
    "translator": {
        "keywords": ["translate", "locali", "i18n", "multilingual", "language translation"],
        "anti_keywords": [],
        "description": "Translate content between languages",
    },
    "visualizer": {
        "keywords": ["chart", "graph", "plot", "visualization", "dashboard", "diagram"],
        "anti_keywords": [],
        "description": "Create visualizations and charts",
    },
    "git_ops": {
        "keywords": ["git", "commit", "branch", "merge", "pull request", "version control"],
        "anti_keywords": [],
        "description": "Git operations and version control",
    },
    "refactorer": {
        "keywords": ["refactor", "optimize", "improve code", "clean code", "restructure"],
        "anti_keywords": [],
        "description": "Refactor or optimize code",
    },
    "search": {
        "keywords": ["search", "find", "lookup", "query", "research", "browse"],
        "anti_keywords": ["test", "code"],
        "description": "Search for information",
    },
    "writer": {
        "keywords": ["write", "compose", "draft", "author", "blog", "article", "content"],
        "anti_keywords": ["test", "code", "unit"],
        "description": "Write content or articles",
    },
}


@dataclass
class SkillInfo:
    skill_id: str
    name: str
    description: str
    body: str
    category: str  # Single primary category
    body_length: int


@dataclass
class SubTask:
    step_index: int
    description: str  # Now uses actual skill description
    required_category: str
    ground_truth_skill_id: str
    ground_truth_skill_name: str


@dataclass
class Edge:
    from_step: int
    to_step: int
    dependency_type: str


@dataclass
class CompositionalQuery:
    query_id: str
    query: str
    difficulty: str
    num_skills: int
    subtasks: list
    edges: list
    category: str
    distractor_skill_ids: list


def strict_categorize(name: str, description: str) -> str | None:
    """Categorize skill using ONLY name + description (not body). Returns single best category."""
    text = f"{name} {description}".lower()

    best_cat = None
    best_score = 0

    for cat, rules in CATEGORY_RULES.items():
        # Check anti-keywords first
        if any(kw in text for kw in rules.get("anti_keywords", [])):
            continue

        score = sum(1 for kw in rules["keywords"] if kw in text)
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat if best_score >= 1 else None


def load_and_curate_skills() -> list[SkillInfo]:
    """Load, deduplicate, and properly categorize skills."""
    raw_skills = []
    with open(RAW_SKILLS_PATH) as f:
        for line in f:
            if line.strip():
                raw_skills.append(json.loads(line))

    logger.info(f"Loaded {len(raw_skills)} raw skills")

    # Deduplicate by name (keep the one with longest description)
    name_map = {}
    for d in raw_skills:
        name = d["name"].strip().lower()
        desc = d.get("description", "")
        if name not in name_map or len(desc) > len(name_map[name].get("description", "")):
            name_map[name] = d

    logger.info(f"After deduplication by name: {len(name_map)} unique skills")

    # Filter and categorize
    skills = []
    for name, d in name_map.items():
        desc = d.get("description", "")
        body = d.get("body", "")

        # Filter: must have meaningful description
        if len(desc) < 20:
            continue
        if len(body) < 50:
            continue

        # Strict categorization
        category = strict_categorize(d["name"], desc)
        if not category:
            continue

        skills.append(SkillInfo(
            skill_id=d["skill_id"],
            name=d["name"],
            description=desc,
            body=body,
            category=category,
            body_length=len(body),
        ))

    logger.info(f"After filtering and categorization: {len(skills)} skills")

    # Log category distribution
    cat_counts = defaultdict(int)
    for s in skills:
        cat_counts[s.category] += 1
    for cat, count in sorted(cat_counts.items(), key=lambda x: -x[1]):
        logger.info(f"  {cat}: {count}")

    return skills


# ============================================================
# Compositional Query Templates (using real skill categories)
# ============================================================

QUERY_TEMPLATES = [
    # Easy (2 skills) - clear 2-step pipelines
    {
        "category": "api_to_format",
        "difficulty": "easy",
        "skill_categories": ["api_client", "file_converter"],
        "query_template": "Use {skill_0_name} to fetch the data, then use {skill_1_name} to convert it to the target format",
        "fallback_queries": [
            "Fetch data from the API and export it as a formatted file",
            "Retrieve data from the web service and convert it to CSV",
            "Download data from the endpoint and transform it into JSON",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "code_and_test",
        "difficulty": "easy",
        "skill_categories": ["code_analyzer", "test_writer"],
        "query_template": "Use {skill_0_name} to analyze the codebase, then use {skill_1_name} to generate tests",
        "fallback_queries": [
            "Analyze the codebase for issues and generate a test suite",
            "Review the source code and write unit tests",
            "Read the repository code and create integration tests",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "write_and_translate",
        "difficulty": "easy",
        "skill_categories": ["writer", "translator"],
        "query_template": "Use {skill_0_name} to write the content, then use {skill_1_name} to translate it",
        "fallback_queries": [
            "Write a blog post and translate it to another language",
            "Draft a document and localize it for international readers",
            "Compose a description and translate it to the target language",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "code_and_docs",
        "difficulty": "easy",
        "skill_categories": ["code_generator", "documentation"],
        "query_template": "Use {skill_0_name} to generate the code, then use {skill_1_name} to document it",
        "fallback_queries": [
            "Generate the application code and create documentation",
            "Scaffold the component and write API documentation",
            "Create the module code and generate docstrings",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "scrape_and_process",
        "difficulty": "easy",
        "skill_categories": ["web_scraper", "data_processor"],
        "query_template": "Use {skill_0_name} to scrape the web data, then use {skill_1_name} to process it",
        "fallback_queries": [
            "Scrape the website and clean the extracted data",
            "Crawl the web pages and process the content",
            "Extract web data and transform it for analysis",
        ],
        "edge_type": "sequential",
    },
    # Medium (3 skills)
    {
        "category": "research_pipeline",
        "difficulty": "medium",
        "skill_categories": ["search", "writer", "file_converter"],
        "query_template": "Use {skill_0_name} to search for information, {skill_1_name} to write a report, then {skill_2_name} to format it",
        "fallback_queries": [
            "Search for papers, write a summary report, and export as PDF",
            "Research the topic, compile findings, and format the document",
            "Find relevant sources, write an analysis, and export as formatted document",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "data_pipeline",
        "difficulty": "medium",
        "skill_categories": ["api_client", "data_processor", "visualizer"],
        "query_template": "Use {skill_0_name} to fetch data, {skill_1_name} to process it, then {skill_2_name} to visualize results",
        "fallback_queries": [
            "Fetch data from the API, process and analyze it, then create visualizations",
            "Retrieve records, run statistical analysis, and generate charts",
            "Download the dataset, transform it, and create visual reports",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "code_workflow",
        "difficulty": "medium",
        "skill_categories": ["code_analyzer", "refactorer", "test_writer"],
        "query_template": "Use {skill_0_name} to analyze code, {skill_1_name} to refactor it, then {skill_2_name} to write tests",
        "fallback_queries": [
            "Analyze the legacy code, refactor it, and write tests",
            "Review code quality, optimize performance, and add test coverage",
            "Read the codebase, apply clean code patterns, and generate tests",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "deploy_pipeline",
        "difficulty": "medium",
        "skill_categories": ["code_generator", "test_writer", "deployment"],
        "query_template": "Use {skill_0_name} to generate code, {skill_1_name} to test it, then {skill_2_name} to deploy",
        "fallback_queries": [
            "Generate the application code, write tests, and deploy to production",
            "Create the service, add tests, and set up deployment",
            "Build the microservice, generate tests, and deploy with containers",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "db_workflow",
        "difficulty": "medium",
        "skill_categories": ["database", "data_processor", "file_converter"],
        "query_template": "Use {skill_0_name} to query the database, {skill_1_name} to process results, then {skill_2_name} to export",
        "fallback_queries": [
            "Query the database, process the results, and export as CSV",
            "Fetch database records, transform the data, and generate a report file",
            "Run SQL queries, clean the results, and convert to JSON",
        ],
        "edge_type": "sequential",
    },
    # Hard (4-5 skills)
    {
        "category": "full_research",
        "difficulty": "hard",
        "skill_categories": ["search", "data_processor", "visualizer", "writer", "file_converter"],
        "query_template": "Use {skill_0_name} to search, {skill_1_name} to process data, {skill_2_name} to visualize, {skill_3_name} to write, then {skill_4_name} to format",
        "fallback_queries": [
            "Research papers, extract data, create charts, write analysis, and format as PDF",
            "Search for sources, process findings, visualize trends, write report, and export document",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "full_app",
        "difficulty": "hard",
        "skill_categories": ["code_generator", "test_writer", "database", "deployment"],
        "query_template": "Use {skill_0_name} to generate code, {skill_1_name} to test, {skill_2_name} for database, then {skill_3_name} to deploy",
        "fallback_queries": [
            "Generate backend code, write tests, set up the database, and deploy the service",
            "Create the application, add test coverage, configure database, and deploy to cloud",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "security_audit",
        "difficulty": "hard",
        "skill_categories": ["security", "code_analyzer", "refactorer", "test_writer"],
        "query_template": "Use {skill_0_name} to scan, {skill_1_name} to analyze, {skill_2_name} to fix, then {skill_3_name} to verify",
        "fallback_queries": [
            "Scan for vulnerabilities, analyze security issues, implement fixes, and write verification tests",
            "Run security audit, review findings, apply patches, and add regression tests",
        ],
        "edge_type": "sequential",
    },
    {
        "category": "full_git_workflow",
        "difficulty": "hard",
        "skill_categories": ["code_analyzer", "refactorer", "test_writer", "git_ops"],
        "query_template": "Use {skill_0_name} to review, {skill_1_name} to refactor, {skill_2_name} to test, then {skill_3_name} to commit",
        "fallback_queries": [
            "Review the code, refactor problematic areas, write tests, and commit changes",
            "Analyze code quality, optimize code, add tests, and create a pull request",
        ],
        "edge_type": "sequential",
    },
]


def generate_queries(skills: list[SkillInfo], target_count: int = 300) -> list[CompositionalQuery]:
    """Generate compositional queries from actual skill combinations."""
    # Build category index
    cat_index = defaultdict(list)
    for s in skills:
        cat_index[s.category].append(s)

    queries = []
    query_idx = 0
    rounds = 0

    while len(queries) < target_count and rounds < 200:
        rounds += 1
        random.shuffle(QUERY_TEMPLATES)

        for template in QUERY_TEMPLATES:
            if len(queries) >= target_count:
                break

            required_cats = template["skill_categories"]

            # Check all required categories have skills
            if not all(cat in cat_index and len(cat_index[cat]) >= 1 for cat in required_cats):
                continue

            # For each fallback query, create a benchmark entry
            for query_text in template["fallback_queries"]:
                if len(queries) >= target_count:
                    break

                # Select skills for each step
                used_ids = set()
                subtasks = []
                valid = True

                for step_idx, cat in enumerate(required_cats):
                    # Pick a random skill from this category
                    candidates = [s for s in cat_index[cat] if s.skill_id not in used_ids]
                    if not candidates:
                        candidates = cat_index[cat]  # Allow reuse as fallback

                    skill = random.choice(candidates)
                    used_ids.add(skill.skill_id)

                    # Use the skill's actual description as the subtask description
                    subtasks.append(asdict(SubTask(
                        step_index=step_idx,
                        description=skill.description[:200],  # Actual skill description
                        required_category=cat,
                        ground_truth_skill_id=skill.skill_id,
                        ground_truth_skill_name=skill.name,
                    )))

                if not valid:
                    continue

                # Build edges
                num_steps = len(subtasks)
                edges = []
                if template["edge_type"] == "sequential":
                    for i in range(num_steps - 1):
                        edges.append(asdict(Edge(from_step=i, to_step=i+1, dependency_type="sequential")))
                elif template["edge_type"] == "parallel_merge":
                    edges.append(asdict(Edge(from_step=0, to_step=1, dependency_type="data_flow")))
                    edges.append(asdict(Edge(from_step=0, to_step=2, dependency_type="data_flow")))
                    edges.append(asdict(Edge(from_step=1, to_step=num_steps-1, dependency_type="data_flow")))
                    edges.append(asdict(Edge(from_step=2, to_step=num_steps-1, dependency_type="data_flow")))

                # Select distractors
                gt_ids = {st["ground_truth_skill_id"] for st in subtasks}
                gt_cats = {st["required_category"] for st in subtasks}
                distractors = select_distractors(gt_ids, gt_cats, cat_index, n=15)

                queries.append(CompositionalQuery(
                    query_id=f"cq_{query_idx:04d}",
                    query=query_text,
                    difficulty=template["difficulty"],
                    num_skills=len(subtasks),
                    subtasks=subtasks,
                    edges=edges,
                    category=template["category"],
                    distractor_skill_ids=distractors,
                ))
                query_idx += 1

    return queries


def select_distractors(gt_ids, gt_cats, cat_index, n=15):
    """Select hard negative distractors."""
    distractors = []

    # Hard negatives from same categories
    for cat in gt_cats:
        candidates = [s.skill_id for s in cat_index.get(cat, []) if s.skill_id not in gt_ids]
        distractors.extend(random.sample(candidates, min(n // 3, len(candidates))))

    # Random from other categories
    all_cats = list(cat_index.keys())
    while len(distractors) < n:
        cat = random.choice(all_cats)
        candidates = [s.skill_id for s in cat_index[cat] if s.skill_id not in gt_ids]
        if candidates:
            distractors.append(random.choice(candidates).skill_id if hasattr(random.choice(candidates), 'skill_id') else random.choice(candidates))

    return list(set(distractors))[:n]


def save_benchmark(queries: list[CompositionalQuery], skills: list[SkillInfo]):
    """Save benchmark and skill pool."""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    # Save queries
    output_file = BENCHMARK_DIR / "compositional_queries.jsonl"
    with open(output_file, "w") as f:
        for q in queries:
            f.write(json.dumps(asdict(q), ensure_ascii=False) + "\n")
    logger.info(f"Saved {len(queries)} queries to {output_file}")

    # Split by difficulty
    for diff in ["easy", "medium", "hard"]:
        subset = [q for q in queries if q.difficulty == diff]
        with open(BENCHMARK_DIR / f"queries_{diff}.jsonl", "w") as f:
            for q in subset:
                f.write(json.dumps(asdict(q), ensure_ascii=False) + "\n")
        logger.info(f"  {diff}: {len(subset)} queries")

    # Build skill pool: GT skills + distractors + random sample for diversity
    relevant_ids = set()
    for q in queries:
        for st in q.subtasks:
            relevant_ids.add(st["ground_truth_skill_id"])
        relevant_ids.update(q.distractor_skill_ids)

    # Add all skills from the curated set as pool
    skill_pool = {s.skill_id: s for s in skills}

    pool_file = PROCESSED_DIR / "skill_pool.jsonl"
    pool_count = 0

    # Write pool from raw skills file (to preserve full data including body)
    pool_ids = set(skill_pool.keys())
    with open(RAW_SKILLS_PATH) as fin, open(pool_file, "w") as fout:
        seen_ids = set()
        for line in fin:
            d = json.loads(line)
            sid = d["skill_id"]
            if sid in pool_ids and sid not in seen_ids:
                # Add proper category
                skill_info = skill_pool.get(sid)
                if skill_info:
                    d["categories"] = [skill_info.category]
                fout.write(json.dumps(d, ensure_ascii=False) + "\n")
                seen_ids.add(sid)
                pool_count += 1

    logger.info(f"Skill pool: {pool_count} skills saved to {pool_file}")

    # Stats
    gt_skills = set()
    for q in queries:
        for st in q.subtasks:
            gt_skills.add(st["ground_truth_skill_id"])

    stats = {
        "total_queries": len(queries),
        "by_difficulty": {d: sum(1 for q in queries if q.difficulty == d) for d in ["easy", "medium", "hard"]},
        "by_category": {},
        "avg_skills_per_query": sum(q.num_skills for q in queries) / max(len(queries), 1),
        "total_unique_gt_skills": len(gt_skills),
        "skill_pool_size": pool_count,
        "gt_in_pool": len(gt_skills & set(skill_pool.keys())),
    }
    for q in queries:
        stats["by_category"][q.category] = stats["by_category"].get(q.category, 0) + 1

    with open(BENCHMARK_DIR / "benchmark_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Stats:\n{json.dumps(stats, indent=2)}")


def main():
    random.seed(42)

    logger.info("Loading and curating skills...")
    skills = load_and_curate_skills()
    logger.info(f"Curated {len(skills)} skills")

    logger.info("Generating compositional queries...")
    queries = generate_queries(skills, target_count=300)
    logger.info(f"Generated {len(queries)} queries")

    logger.info("Saving benchmark...")
    save_benchmark(queries, skills)
    logger.info("Done!")


if __name__ == "__main__":
    main()
