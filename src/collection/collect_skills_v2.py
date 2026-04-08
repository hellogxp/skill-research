"""
Skill Data Collection Pipeline v2
Clone public repos and extract SKILL.md files locally. No API token needed.
"""

import os
import json
import re
import hashlib
import logging
import subprocess
import shutil
from pathlib import Path
from dataclasses import dataclass, asdict

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

CLONE_DIR = Path("/mnt/workspace/skill-routing/data/repos")
OUTPUT_DIR = Path("/mnt/workspace/skill-routing/data/raw_skills")

# Curated list of repos known to contain SKILL.md files
SKILL_REPOS = [
    "https://github.com/anthropics/skills.git",
    "https://github.com/VoltAgent/awesome-agent-skills.git",
    "https://github.com/skillmatic-ai/awesome-agent-skills.git",
    "https://github.com/heilcheng/awesome-agent-skills.git",
    "https://github.com/gmh5225/awesome-skills.git",
    "https://github.com/ComposioHQ/awesome-claude-skills.git",
    "https://github.com/InternScience/Awesome-Scientific-Skills.git",
    "https://github.com/abubakarsiddik31/claude-skills-collection.git",
    "https://github.com/libukai/awesome-agent-skills.git",
    "https://github.com/BehiSecc/awesome-claude-skills.git",
]


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    body: str
    source_repo: str
    source_path: str
    files: dict
    metadata: dict
    body_length: int
    has_code: bool
    categories: list


def parse_skill_md(content: str) -> dict:
    """Parse SKILL.md content to extract frontmatter and body."""
    result = {"name": "", "description": "", "frontmatter": {}, "instructions": ""}

    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    if fm_match:
        fm_text, body = fm_match.group(1), fm_match.group(2)
        for line in fm_text.strip().split("\n"):
            if ":" in line:
                key, val = line.split(":", 1)
                result["frontmatter"][key.strip()] = val.strip().strip('"').strip("'")
        result["name"] = result["frontmatter"].get("name", "")
        result["description"] = result["frontmatter"].get("description", "")
        result["instructions"] = body.strip()
    else:
        heading = re.match(r"^#\s+(.+)", content)
        if heading:
            result["name"] = heading.group(1).strip()
        result["instructions"] = content.strip()

    return result


def detect_categories(name: str, desc: str, body: str) -> list[str]:
    """Auto-detect skill categories based on content."""
    text = f"{name} {desc} {body}".lower()
    cats = []
    keyword_map = {
        "data_fetcher": ["fetch", "scrape", "crawl", "download", "api call", "http request", "web request"],
        "data_processor": ["process", "transform", "parse", "clean", "filter", "extract data", "etl"],
        "format_converter": ["convert", "export", "pdf", "csv", "json", "xlsx", "markdown", "docx", "pptx"],
        "web_search": ["search", "web browse", "google", "arxiv", "bing"],
        "content_writer": ["write", "draft", "compose", "generate text", "blog", "article", "essay"],
        "code_reader": ["read code", "analyze code", "code review", "understand code", "codebase"],
        "code_generator": ["generate code", "write code", "implement", "scaffold", "boilerplate"],
        "refactorer": ["refactor", "optimize code", "improve code", "clean code", "modernize"],
        "test_generator": ["test", "unit test", "pytest", "jest", "spec", "coverage"],
        "git_operator": ["git", "commit", "pull request", "branch", "merge", "github"],
        "document_parser": ["parse document", "extract text", "ocr", "read pdf", "read doc"],
        "translator": ["translate", "language", "i18n", "localize", "multilingual"],
        "formatter": ["format", "style", "template", "layout", "typeset", "prettier"],
        "analyzer": ["analyze", "statistics", "metrics", "evaluate", "benchmark", "profil"],
        "visualizer": ["chart", "plot", "graph", "visualize", "diagram", "dashboard"],
        "report_generator": ["report", "summary", "document generation", "presentation"],
        "database": ["database", "sql", "query", "mongodb", "postgres", "mysql"],
        "deployment": ["deploy", "docker", "kubernetes", "ci/cd", "vercel", "aws"],
        "security": ["security", "vulnerability", "audit", "scan", "encrypt"],
        "communication": ["email", "slack", "notification", "message", "webhook"],
    }
    for cat, keywords in keyword_map.items():
        if any(kw in text for kw in keywords):
            cats.append(cat)
    if not cats:
        cats.append("general")
    return cats


def clone_repo(url: str) -> Path | None:
    """Shallow clone a repository."""
    repo_name = url.split("/")[-1].replace(".git", "")
    repo_path = CLONE_DIR / repo_name

    if repo_path.exists():
        logger.info(f"  Already cloned: {repo_name}")
        return repo_path

    try:
        result = subprocess.run(
            ["git", "clone", "--depth", "1", url, str(repo_path)],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode == 0:
            logger.info(f"  Cloned: {repo_name}")
            return repo_path
        else:
            logger.warning(f"  Clone failed: {repo_name}: {result.stderr[:200]}")
            return None
    except subprocess.TimeoutExpired:
        logger.warning(f"  Clone timeout: {repo_name}")
        return None


def extract_linked_repos(repo_path: Path) -> list[str]:
    """Extract GitHub repo links from README and other markdown files."""
    links = []
    for md_file in repo_path.rglob("*.md"):
        try:
            content = md_file.read_text(errors="ignore")
            pattern = r"https?://github\.com/([\w\-\.]+/[\w\-\.]+)"
            matches = re.findall(pattern, content)
            for match in matches:
                clean = match.rstrip("/").rstrip(".")
                url = f"https://github.com/{clean}.git"
                if url not in links and "awesome" not in clean.lower():
                    links.append(url)
        except Exception:
            continue
    return links


def extract_skills_from_repo(repo_path: Path, repo_url: str) -> list[Skill]:
    """Find and parse all SKILL.md files in a repo."""
    skills = []
    repo_name = repo_url.split("github.com/")[-1].replace(".git", "")

    for skill_md in repo_path.rglob("SKILL.md"):
        try:
            content = skill_md.read_text(errors="ignore")
            if len(content) < 10:
                continue

            parsed = parse_skill_md(content)
            skill_dir = skill_md.parent
            rel_path = str(skill_md.relative_to(repo_path).parent)

            # Collect companion files
            files = {}
            for f in skill_dir.iterdir():
                if f.is_file() and f.name != "SKILL.md":
                    try:
                        fc = f.read_text(errors="ignore")
                        if len(fc) < 50000:
                            files[f.name] = fc
                    except Exception:
                        pass

            skill_id = hashlib.md5(f"{repo_name}/{rel_path}".encode()).hexdigest()[:12]
            name = parsed["name"] or skill_dir.name
            desc = parsed["description"]
            body = content

            skills.append(Skill(
                skill_id=skill_id,
                name=name,
                description=desc,
                body=body,
                source_repo=repo_name,
                source_path=rel_path,
                files=files,
                metadata=parsed["frontmatter"],
                body_length=len(body),
                has_code=bool(re.search(r"```\w+\n", body)),
                categories=detect_categories(name, desc, body),
            ))
        except Exception as e:
            logger.warning(f"  Error parsing {skill_md}: {e}")

    return skills


def main():
    CLONE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    all_skills = []
    seen_ids = set()

    # Phase 1: Clone and extract from known repos
    logger.info("=== Phase 1: Known repositories ===")
    for url in SKILL_REPOS:
        logger.info(f"Processing {url}...")
        repo_path = clone_repo(url)
        if repo_path:
            skills = extract_skills_from_repo(repo_path, url)
            for s in skills:
                if s.skill_id not in seen_ids:
                    all_skills.append(s)
                    seen_ids.add(s.skill_id)
            logger.info(f"  Extracted {len(skills)} skills")

    # Phase 2: Follow links from awesome lists
    logger.info("=== Phase 2: Following links from awesome lists ===")
    linked_urls = set()
    for url in SKILL_REPOS:
        repo_name = url.split("/")[-1].replace(".git", "")
        repo_path = CLONE_DIR / repo_name
        if repo_path.exists() and "awesome" in repo_name.lower():
            links = extract_linked_repos(repo_path)
            linked_urls.update(links)
            logger.info(f"  Found {len(links)} linked repos in {repo_name}")

    logger.info(f"Total linked repos to process: {len(linked_urls)}")
    processed = 0
    for url in list(linked_urls)[:300]:
        processed += 1
        if processed % 20 == 0:
            logger.info(f"  Progress: {processed}/{min(len(linked_urls), 300)}")
        repo_path = clone_repo(url)
        if repo_path:
            skills = extract_skills_from_repo(repo_path, url)
            for s in skills:
                if s.skill_id not in seen_ids:
                    all_skills.append(s)
                    seen_ids.add(s.skill_id)

    # Phase 3: Also search for standalone SKILL.md patterns (markdown skill definitions)
    logger.info("=== Phase 3: Extracting inline skill definitions from awesome lists ===")
    for url in SKILL_REPOS:
        repo_name = url.split("/")[-1].replace(".git", "")
        repo_path = CLONE_DIR / repo_name
        if not repo_path.exists():
            continue

        for md_file in repo_path.rglob("*.md"):
            if md_file.name == "SKILL.md":
                continue
            try:
                content = md_file.read_text(errors="ignore")
                # Find inline skill definitions in markdown
                # Pattern: ### Skill Name\n```\n---\nname: ...\n---\n```
                blocks = re.findall(
                    r"```(?:markdown|md|yaml)?\s*\n(---\s*\n.*?name:.*?\n---.*?)```",
                    content, re.DOTALL,
                )
                for block in blocks:
                    parsed = parse_skill_md(block)
                    if parsed["name"]:
                        skill_id = hashlib.md5(block.encode()).hexdigest()[:12]
                        if skill_id not in seen_ids:
                            all_skills.append(Skill(
                                skill_id=skill_id,
                                name=parsed["name"],
                                description=parsed["description"],
                                body=block,
                                source_repo=repo_name,
                                source_path=str(md_file.relative_to(repo_path)),
                                files={},
                                metadata=parsed["frontmatter"],
                                body_length=len(block),
                                has_code=bool(re.search(r"```\w+\n", block)),
                                categories=detect_categories(parsed["name"], parsed["description"], block),
                            ))
                            seen_ids.add(skill_id)
            except Exception:
                continue

    # Save results
    logger.info(f"\n{'='*50}")
    logger.info(f"Total skills collected: {len(all_skills)}")
    logger.info(f"Unique source repos: {len(set(s.source_repo for s in all_skills))}")

    output_file = OUTPUT_DIR / "all_skills.jsonl"
    with open(output_file, "w") as f:
        for skill in all_skills:
            f.write(json.dumps(asdict(skill), ensure_ascii=False) + "\n")
    logger.info(f"Saved to {output_file}")

    # Category distribution
    cat_dist = {}
    for s in all_skills:
        for c in s.categories:
            cat_dist[c] = cat_dist.get(c, 0) + 1

    stats = {
        "total_skills": len(all_skills),
        "unique_repos": len(set(s.source_repo for s in all_skills)),
        "with_description": sum(1 for s in all_skills if s.description),
        "with_companion_files": sum(1 for s in all_skills if s.files),
        "with_code_blocks": sum(1 for s in all_skills if s.has_code),
        "avg_body_length": sum(s.body_length for s in all_skills) / max(len(all_skills), 1),
        "category_distribution": dict(sorted(cat_dist.items(), key=lambda x: -x[1])),
    }
    stats_file = OUTPUT_DIR / "collection_stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    logger.info(f"Stats:\n{json.dumps(stats, indent=2)}")

    # Cleanup cloned repos to save disk
    logger.info("Cleaning up cloned repos...")
    shutil.rmtree(CLONE_DIR, ignore_errors=True)
    logger.info("Done!")


if __name__ == "__main__":
    main()
