"""
Compositional Query Benchmark Builder
Generates multi-skill queries and ground-truth skill DAGs for evaluation.
"""

import json
import random
import logging
from pathlib import Path
from dataclasses import dataclass, asdict, field

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

RAW_SKILLS_PATH = Path("/mnt/workspace/skill-routing/data/raw_skills/all_skills.jsonl")
BENCHMARK_DIR = Path("/mnt/workspace/skill-routing/data/benchmark")


@dataclass
class SkillNode:
    """A node in the skill DAG."""
    skill_id: str
    skill_name: str
    subtask: str
    step_index: int


@dataclass
class SkillEdge:
    """An edge in the skill DAG (data dependency)."""
    from_step: int
    to_step: int
    dependency_type: str  # "sequential", "data_flow", "conditional"


@dataclass
class CompositionalQuery:
    """A query that requires multiple skills to complete."""
    query_id: str
    query: str
    difficulty: str  # "easy" (2 skills), "medium" (3 skills), "hard" (4-5 skills)
    subtasks: list[str]
    ground_truth_skills: list[SkillNode]
    edges: list[SkillEdge]
    category: str


# Templates for generating compositional queries
COMPOSITIONAL_TEMPLATES = {
    "data_pipeline": {
        "pattern": "Fetch {source}, process it with {transform}, and output as {format}",
        "skill_types": ["data_fetcher", "data_processor", "format_converter"],
        "difficulty": "easy",
    },
    "content_creation": {
        "pattern": "Research {topic}, write a {doc_type}, and convert to {format}",
        "skill_types": ["web_search", "content_writer", "format_converter"],
        "difficulty": "medium",
    },
    "analysis_report": {
        "pattern": "Collect {data} from {source}, analyze with {method}, visualize, and generate report",
        "skill_types": ["data_collector", "analyzer", "visualizer", "report_generator"],
        "difficulty": "hard",
    },
    "code_workflow": {
        "pattern": "Read {code_source}, refactor using {pattern}, add tests, and create PR",
        "skill_types": ["code_reader", "refactorer", "test_generator", "git_operator"],
        "difficulty": "hard",
    },
    "document_processing": {
        "pattern": "Extract text from {input_format}, translate to {language}, format as {output_format}",
        "skill_types": ["document_parser", "translator", "formatter"],
        "difficulty": "medium",
    },
}


def load_skills() -> list[dict]:
    """Load collected skills."""
    skills = []
    if RAW_SKILLS_PATH.exists():
        with open(RAW_SKILLS_PATH) as f:
            for line in f:
                if line.strip():
                    skills.append(json.loads(line))
    return skills


def categorize_skills(skills: list[dict]) -> dict[str, list[dict]]:
    """Categorize skills by their functionality."""
    categories = {
        "data_fetcher": [], "data_processor": [], "format_converter": [],
        "web_search": [], "content_writer": [], "code_reader": [],
        "refactorer": [], "test_generator": [], "git_operator": [],
        "document_parser": [], "translator": [], "formatter": [],
        "analyzer": [], "visualizer": [], "report_generator": [],
        "general": [],
    }

    keyword_map = {
        "data_fetcher": ["fetch", "scrape", "crawl", "download", "api", "request"],
        "data_processor": ["process", "transform", "parse", "clean", "filter", "extract"],
        "format_converter": ["convert", "export", "pdf", "csv", "json", "xlsx", "markdown"],
        "web_search": ["search", "web", "browse", "google", "arxiv"],
        "content_writer": ["write", "draft", "compose", "generate text", "blog", "article"],
        "code_reader": ["read code", "analyze code", "review", "understand"],
        "refactorer": ["refactor", "optimize", "improve code", "clean code"],
        "test_generator": ["test", "unit test", "pytest", "jest", "spec"],
        "git_operator": ["git", "commit", "pull request", "branch", "merge"],
        "document_parser": ["parse", "extract text", "ocr", "read pdf", "read doc"],
        "translator": ["translate", "language", "i18n", "localize"],
        "formatter": ["format", "style", "template", "layout", "typeset"],
        "analyzer": ["analyze", "statistics", "metrics", "evaluate", "benchmark"],
        "visualizer": ["chart", "plot", "graph", "visualize", "diagram"],
        "report_generator": ["report", "summary", "document", "presentation"],
    }

    for skill in skills:
        text = f"{skill.get('name', '')} {skill.get('description', '')}".lower()
        categorized = False
        for cat, keywords in keyword_map.items():
            if any(kw in text for kw in keywords):
                categories[cat].append(skill)
                categorized = True
                break
        if not categorized:
            categories["general"].append(skill)

    return categories


def build_compositional_query(
    template_name: str,
    template: dict,
    categorized_skills: dict[str, list[dict]],
    query_idx: int,
) -> CompositionalQuery | None:
    """Build a single compositional query from a template."""
    skill_types = template["skill_types"]
    selected_skills = []

    for i, stype in enumerate(skill_types):
        candidates = categorized_skills.get(stype, [])
        if not candidates:
            candidates = categorized_skills.get("general", [])
        if not candidates:
            return None
        skill = random.choice(candidates)
        selected_skills.append(
            SkillNode(
                skill_id=skill["skill_id"],
                skill_name=skill["name"],
                subtask=stype,
                step_index=i,
            )
        )

    # Build sequential edges
    edges = []
    for i in range(len(selected_skills) - 1):
        edges.append(SkillEdge(
            from_step=i,
            to_step=i + 1,
            dependency_type="sequential",
        ))

    return CompositionalQuery(
        query_id=f"cq_{query_idx:04d}",
        query=template["pattern"],
        difficulty=template["difficulty"],
        subtasks=[s.subtask for s in selected_skills],
        ground_truth_skills=selected_skills,
        edges=edges,
        category=template_name,
    )


def generate_benchmark(skills: list[dict], n_queries: int = 200) -> list[CompositionalQuery]:
    """Generate the full compositional benchmark."""
    categorized = categorize_skills(skills)

    # Log category distribution
    for cat, cat_skills in categorized.items():
        if cat_skills:
            logger.info(f"  Category '{cat}': {len(cat_skills)} skills")

    queries = []
    templates = list(COMPOSITIONAL_TEMPLATES.items())
    idx = 0

    while len(queries) < n_queries:
        template_name, template = templates[idx % len(templates)]
        query = build_compositional_query(template_name, template, categorized, len(queries))
        if query:
            queries.append(query)
        idx += 1
        if idx > n_queries * 10:  # safety break
            break

    return queries


def save_benchmark(queries: list[CompositionalQuery]):
    """Save benchmark to disk."""
    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)

    # Save as JSONL
    output_file = BENCHMARK_DIR / "compositional_queries.jsonl"
    with open(output_file, "w") as f:
        for q in queries:
            data = asdict(q)
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    # Split by difficulty
    for diff in ["easy", "medium", "hard"]:
        subset = [q for q in queries if q.difficulty == diff]
        subset_file = BENCHMARK_DIR / f"queries_{diff}.jsonl"
        with open(subset_file, "w") as f:
            for q in subset:
                f.write(json.dumps(asdict(q), ensure_ascii=False) + "\n")
        logger.info(f"  {diff}: {len(subset)} queries")

    # Stats
    stats = {
        "total_queries": len(queries),
        "by_difficulty": {d: sum(1 for q in queries if q.difficulty == d) for d in ["easy", "medium", "hard"]},
        "by_category": {},
        "avg_skills_per_query": sum(len(q.ground_truth_skills) for q in queries) / max(len(queries), 1),
    }
    for q in queries:
        stats["by_category"][q.category] = stats["by_category"].get(q.category, 0) + 1

    stats_file = BENCHMARK_DIR / "benchmark_stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Benchmark stats: {json.dumps(stats, indent=2)}")


def main():
    logger.info("Loading skills...")
    skills = load_skills()
    logger.info(f"Loaded {len(skills)} skills")

    if not skills:
        logger.error("No skills found. Run collect_skills.py first.")
        return

    logger.info("Generating compositional benchmark...")
    queries = generate_benchmark(skills, n_queries=200)
    logger.info(f"Generated {len(queries)} compositional queries")

    logger.info("Saving benchmark...")
    save_benchmark(queries)
    logger.info("Done!")


if __name__ == "__main__":
    main()
