"""
Compositional Query Benchmark Builder v2
Uses LLM to generate realistic multi-skill queries with ground-truth DAGs.
Works with the 11K collected skills.
"""

import json
import random
import logging
import hashlib
from pathlib import Path
from dataclasses import dataclass, asdict, field
from collections import defaultdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_SKILLS_PATH = Path("/mnt/workspace/skill-routing/data/raw_skills/all_skills.jsonl")
BENCHMARK_DIR = Path("/mnt/workspace/skill-routing/data/benchmark")
PROCESSED_DIR = Path("/mnt/workspace/skill-routing/data/processed")


@dataclass
class SkillInfo:
    skill_id: str
    name: str
    description: str
    categories: list[str]
    body_length: int


@dataclass
class SubTask:
    step_index: int
    description: str
    required_category: str
    ground_truth_skill_id: str
    ground_truth_skill_name: str


@dataclass
class Edge:
    from_step: int
    to_step: int
    dependency_type: str  # "sequential", "data_flow", "parallel"


@dataclass
class CompositionalQuery:
    query_id: str
    query: str
    difficulty: str  # "easy"=2, "medium"=3, "hard"=4-5
    num_skills: int
    subtasks: list[SubTask]
    edges: list[Edge]
    category: str
    distractor_skill_ids: list[str]  # negative samples for retrieval


# Realistic compositional task templates
TEMPLATES = [
    # Easy (2 skills)
    {
        "category": "data_export",
        "difficulty": "easy",
        "queries": [
            "Fetch data from the API and export it as a CSV file",
            "Scrape the website content and convert it to markdown",
            "Download the dataset and transform it into JSON format",
            "Read the database records and generate an Excel report",
            "Crawl the webpage and save the results as PDF",
        ],
        "skill_chain": [
            ("data_fetcher", "Fetch or retrieve the raw data from the source"),
            ("format_converter", "Convert the data into the target output format"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "code_review",
        "difficulty": "easy",
        "queries": [
            "Analyze the codebase for issues and generate a test suite",
            "Review the source code and write unit tests for it",
            "Read the repository code and create integration tests",
        ],
        "skill_chain": [
            ("code_reader", "Read and analyze the source code"),
            ("test_generator", "Generate appropriate tests based on the analysis"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "content_translate",
        "difficulty": "easy",
        "queries": [
            "Write a blog post and translate it to Chinese",
            "Draft a technical document and localize it for Japanese readers",
            "Compose a product description and translate it to Spanish",
        ],
        "skill_chain": [
            ("content_writer", "Write the original content"),
            ("translator", "Translate the content to the target language"),
        ],
        "edge_type": "sequential",
    },
    # Medium (3 skills)
    {
        "category": "research_report",
        "difficulty": "medium",
        "queries": [
            "Search for recent papers on LLM agents, summarize the findings, and generate a PDF report",
            "Research the latest trends in AI safety, write an analysis, and export as a formatted document",
            "Find relevant arxiv papers on tool learning, compile a literature review, and create a presentation",
            "Browse the web for market analysis data, write a comprehensive report, and format it as PDF",
        ],
        "skill_chain": [
            ("web_search", "Search and collect information from the web"),
            ("content_writer", "Write a comprehensive summary or report"),
            ("format_converter", "Format and export the final document"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "data_pipeline",
        "difficulty": "medium",
        "queries": [
            "Extract data from the API, clean and transform it, then visualize the results",
            "Fetch the database records, process and filter them, and create charts",
            "Download the CSV dataset, run statistical analysis, and generate visualizations",
        ],
        "skill_chain": [
            ("data_fetcher", "Retrieve raw data from the source"),
            ("data_processor", "Clean, transform, and analyze the data"),
            ("visualizer", "Create charts and visualizations"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "code_workflow",
        "difficulty": "medium",
        "queries": [
            "Read the legacy code, refactor it to modern patterns, and write tests",
            "Analyze the codebase, optimize performance-critical sections, and add test coverage",
            "Review the source code, apply clean code principles, and generate unit tests",
        ],
        "skill_chain": [
            ("code_reader", "Analyze the existing codebase"),
            ("refactorer", "Refactor or optimize the code"),
            ("test_generator", "Write tests for the refactored code"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "deploy_pipeline",
        "difficulty": "medium",
        "queries": [
            "Generate the application code, write tests for it, and deploy to production",
            "Create a web service, add comprehensive tests, and set up CI/CD deployment",
            "Build the microservice, generate integration tests, and deploy with Docker",
        ],
        "skill_chain": [
            ("code_generator", "Generate the application code"),
            ("test_generator", "Create tests for the generated code"),
            ("deployment", "Deploy the application to production"),
        ],
        "edge_type": "sequential",
    },
    # Hard (4-5 skills)
    {
        "category": "full_research",
        "difficulty": "hard",
        "queries": [
            "Search arxiv for papers on skill routing, extract key findings, analyze trends, create visualizations, and compile a PDF report",
            "Research the latest LLM agent papers, parse their abstracts, perform statistical analysis, generate charts, and write a survey document",
            "Browse AI conference proceedings, extract relevant data, run comparative analysis, visualize results, and produce a formatted research report",
        ],
        "skill_chain": [
            ("web_search", "Search and collect papers/information"),
            ("data_processor", "Extract and structure key information"),
            ("analyzer", "Analyze trends and patterns"),
            ("visualizer", "Create charts and visualizations"),
            ("report_generator", "Compile the final formatted report"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "full_app",
        "difficulty": "hard",
        "queries": [
            "Design the API schema, generate the backend code, write comprehensive tests, set up the database, and deploy the service",
            "Create the application architecture, implement the code, add unit and integration tests, configure the database, and deploy to cloud",
        ],
        "skill_chain": [
            ("content_writer", "Design and document the API/architecture"),
            ("code_generator", "Implement the application code"),
            ("test_generator", "Write comprehensive tests"),
            ("database", "Set up and configure the database"),
            ("deployment", "Deploy the complete application"),
        ],
        "edge_type": "sequential",
    },
    {
        "category": "security_audit",
        "difficulty": "hard",
        "queries": [
            "Scan the codebase for vulnerabilities, analyze the security issues, generate fix patches, write tests for the fixes, and create an audit report",
            "Review the code for security flaws, perform threat analysis, implement security improvements, verify with tests, and document findings",
        ],
        "skill_chain": [
            ("security", "Scan for security vulnerabilities"),
            ("analyzer", "Analyze and classify the issues"),
            ("refactorer", "Generate fixes for the vulnerabilities"),
            ("test_generator", "Write tests to verify the fixes"),
            ("report_generator", "Create the security audit report"),
        ],
        "edge_type": "sequential",
    },
    # Hard with parallel branches
    {
        "category": "multilingual_release",
        "difficulty": "hard",
        "queries": [
            "Write a product announcement, translate to 3 languages in parallel, then format all versions as PDF",
            "Draft release notes, translate to Chinese and Japanese simultaneously, then compile into a single formatted document",
        ],
        "skill_chain": [
            ("content_writer", "Write the original content"),
            ("translator", "Translate to target language A"),
            ("translator", "Translate to target language B"),
            ("format_converter", "Compile and format all versions"),
        ],
        "edge_type": "parallel_merge",  # steps 1,2 are parallel, then merge to 3
    },
]


def load_skills() -> list[SkillInfo]:
    """Load and index collected skills."""
    skills = []
    with open(RAW_SKILLS_PATH) as f:
        for line in f:
            if line.strip():
                d = json.loads(line)
                skills.append(SkillInfo(
                    skill_id=d["skill_id"],
                    name=d["name"],
                    description=d.get("description", ""),
                    categories=d.get("categories", ["general"]),
                    body_length=d.get("body_length", len(d.get("body", ""))),
                ))
    return skills


def build_category_index(skills: list[SkillInfo]) -> dict[str, list[SkillInfo]]:
    """Index skills by category."""
    idx = defaultdict(list)
    for s in skills:
        for c in s.categories:
            idx[c].append(s)
    return dict(idx)


def select_skill_for_category(
    category: str,
    cat_index: dict[str, list[SkillInfo]],
    used_ids: set[str],
) -> SkillInfo | None:
    """Select a skill for a category, avoiding duplicates."""
    candidates = cat_index.get(category, [])
    # Prefer skills with descriptions and reasonable body length
    good = [s for s in candidates if s.skill_id not in used_ids and s.description and s.body_length > 100]
    if good:
        return random.choice(good)
    remaining = [s for s in candidates if s.skill_id not in used_ids]
    if remaining:
        return random.choice(remaining)
    # Fallback: allow reuse
    if candidates:
        return random.choice(candidates)
    return None


def get_distractors(
    ground_truth_ids: set[str],
    ground_truth_cats: set[str],
    cat_index: dict[str, list[SkillInfo]],
    n: int = 20,
) -> list[str]:
    """Select distractor skills (hard negatives from same categories + random)."""
    distractors = []

    # Hard negatives: same category but different skill
    for cat in ground_truth_cats:
        candidates = [s for s in cat_index.get(cat, []) if s.skill_id not in ground_truth_ids]
        sampled = random.sample(candidates, min(n // 2, len(candidates)))
        distractors.extend(s.skill_id for s in sampled)

    # Random negatives
    all_cats = list(cat_index.keys())
    while len(distractors) < n:
        cat = random.choice(all_cats)
        candidates = [s for s in cat_index.get(cat, []) if s.skill_id not in ground_truth_ids]
        if candidates:
            distractors.append(random.choice(candidates).skill_id)

    return list(set(distractors))[:n]


def build_edges(template: dict, num_steps: int) -> list[Edge]:
    """Build DAG edges based on template edge type."""
    edges = []
    edge_type = template.get("edge_type", "sequential")

    if edge_type == "sequential":
        for i in range(num_steps - 1):
            edges.append(Edge(from_step=i, to_step=i + 1, dependency_type="sequential"))
    elif edge_type == "parallel_merge":
        # First step fans out, parallel steps merge into last
        edges.append(Edge(from_step=0, to_step=1, dependency_type="data_flow"))
        edges.append(Edge(from_step=0, to_step=2, dependency_type="data_flow"))
        edges.append(Edge(from_step=1, to_step=num_steps - 1, dependency_type="data_flow"))
        edges.append(Edge(from_step=2, to_step=num_steps - 1, dependency_type="data_flow"))

    return edges


def generate_queries(skills: list[SkillInfo], target_count: int = 250) -> list[CompositionalQuery]:
    """Generate the full compositional query benchmark."""
    cat_index = build_category_index(skills)

    # Log available categories
    logger.info("Category index:")
    for cat, cat_skills in sorted(cat_index.items(), key=lambda x: -len(x[1])):
        logger.info(f"  {cat}: {len(cat_skills)} skills")

    queries = []
    query_idx = 0

    # Generate from each template
    rounds = 0
    while len(queries) < target_count and rounds < 100:
        rounds += 1
        for template in TEMPLATES:
            if len(queries) >= target_count:
                break

            for query_text in template["queries"]:
                if len(queries) >= target_count:
                    break

                used_ids = set()
                subtasks = []
                valid = True

                for step_idx, (cat, step_desc) in enumerate(template["skill_chain"]):
                    skill = select_skill_for_category(cat, cat_index, used_ids)
                    if not skill:
                        valid = False
                        break
                    used_ids.add(skill.skill_id)
                    subtasks.append(SubTask(
                        step_index=step_idx,
                        description=step_desc,
                        required_category=cat,
                        ground_truth_skill_id=skill.skill_id,
                        ground_truth_skill_name=skill.name,
                    ))

                if not valid:
                    continue

                gt_ids = {st.ground_truth_skill_id for st in subtasks}
                gt_cats = {st.required_category for st in subtasks}
                distractors = get_distractors(gt_ids, gt_cats, cat_index, n=20)
                edges = build_edges(template, len(subtasks))

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


def save_benchmark(queries: list[CompositionalQuery], skills: list[SkillInfo]):
    """Save the benchmark."""
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

    # Build skill pool for retrieval experiments
    # Collect all ground-truth + distractor skill IDs
    relevant_ids = set()
    for q in queries:
        for st in q.subtasks:
            relevant_ids.add(st.ground_truth_skill_id)
        relevant_ids.update(q.distractor_skill_ids)

    # Save the skill pool
    skill_map = {s.skill_id: s for s in skills}
    pool_file = PROCESSED_DIR / "skill_pool.jsonl"
    pool_count = 0
    with open(RAW_SKILLS_PATH) as fin, open(pool_file, "w") as fout:
        for line in fin:
            d = json.loads(line)
            if d["skill_id"] in relevant_ids:
                fout.write(line)
                pool_count += 1
    logger.info(f"Skill pool: {pool_count} skills saved to {pool_file}")

    # Stats
    stats = {
        "total_queries": len(queries),
        "by_difficulty": {d: sum(1 for q in queries if q.difficulty == d) for d in ["easy", "medium", "hard"]},
        "by_category": {},
        "avg_skills_per_query": sum(q.num_skills for q in queries) / max(len(queries), 1),
        "total_unique_gt_skills": len({st.ground_truth_skill_id for q in queries for st in q.subtasks}),
        "skill_pool_size": pool_count,
        "has_parallel_edges": sum(1 for q in queries if any(e.dependency_type != "sequential" for e in q.edges)),
    }
    for q in queries:
        stats["by_category"][q.category] = stats["by_category"].get(q.category, 0) + 1

    with open(BENCHMARK_DIR / "benchmark_stats.json", "w") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Stats:\n{json.dumps(stats, indent=2)}")


def main():
    random.seed(42)

    logger.info("Loading skills...")
    skills = load_skills()
    logger.info(f"Loaded {len(skills)} skills")

    logger.info("Generating compositional queries...")
    queries = generate_queries(skills, target_count=250)
    logger.info(f"Generated {len(queries)} queries")

    logger.info("Saving benchmark...")
    save_benchmark(queries, skills)
    logger.info("Done!")


if __name__ == "__main__":
    main()
