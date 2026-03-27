"""
Skill Data Collection Pipeline
Collects SKILL.md files and full skill bodies from public GitHub repositories.
"""

import os
import json
import time
import re
import hashlib
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

import requests

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path("/mnt/workspace/skill-routing/data/raw_skills")
GITHUB_API = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")

HEADERS = {"Accept": "application/vnd.github.v3+json"}
if GITHUB_TOKEN:
    HEADERS["Authorization"] = f"token {GITHUB_TOKEN}"


@dataclass
class Skill:
    skill_id: str
    name: str
    description: str
    body: str  # full SKILL.md content
    source_repo: str
    source_path: str
    files: dict  # other files in the skill directory
    metadata: dict  # parsed YAML frontmatter


def parse_skill_md(content: str) -> dict:
    """Parse SKILL.md content to extract frontmatter and body."""
    result = {"name": "", "description": "", "frontmatter": {}, "instructions": ""}

    # Parse YAML frontmatter
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
        # No frontmatter, try to extract name from first heading
        heading = re.match(r"^#\s+(.+)", content)
        if heading:
            result["name"] = heading.group(1).strip()
        result["instructions"] = content.strip()

    return result


def github_api_get(url: str, params: dict = None) -> Optional[dict]:
    """Make a GitHub API request with rate limit handling."""
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, params=params, timeout=30)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code == 403:
                reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                wait = max(reset_time - time.time(), 60)
                logger.warning(f"Rate limited. Waiting {wait:.0f}s...")
                time.sleep(wait)
                continue
            if resp.status_code == 404:
                return None
            logger.warning(f"GitHub API {resp.status_code}: {url}")
        except requests.RequestException as e:
            logger.warning(f"Request failed (attempt {attempt+1}): {e}")
            time.sleep(5)
    return None


def get_raw_content(repo: str, path: str, ref: str = "main") -> Optional[str]:
    """Get raw file content from GitHub."""
    for branch in [ref, "master", "main"]:
        url = f"https://raw.githubusercontent.com/{repo}/{branch}/{path}"
        try:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 200:
                return resp.text
        except requests.RequestException:
            continue
    return None


def collect_from_repo(repo: str, skill_dir: str = "") -> list[Skill]:
    """Collect all skills from a GitHub repository."""
    skills = []

    # Search for SKILL.md files in the repo
    url = f"{GITHUB_API}/search/code"
    params = {"q": f"filename:SKILL.md repo:{repo}", "per_page": 100}
    result = github_api_get(url, params)

    if not result or "items" not in result:
        # Try direct directory listing
        url = f"{GITHUB_API}/repos/{repo}/contents/{skill_dir}"
        contents = github_api_get(url)
        if not contents or not isinstance(contents, list):
            return skills

        for item in contents:
            if item["type"] == "dir":
                sub_skills = collect_skill_directory(repo, item["path"])
                if sub_skills:
                    skills.append(sub_skills)
        return skills

    for item in result.get("items", []):
        path = item["path"]
        dir_path = str(Path(path).parent)
        skill = collect_skill_directory(repo, dir_path)
        if skill:
            skills.append(skill)

    return skills


def collect_skill_directory(repo: str, dir_path: str) -> Optional[Skill]:
    """Collect a single skill from its directory."""
    # Get SKILL.md
    skill_md_path = f"{dir_path}/SKILL.md" if dir_path else "SKILL.md"
    content = get_raw_content(repo, skill_md_path)
    if not content:
        return None

    parsed = parse_skill_md(content)
    skill_id = hashlib.md5(f"{repo}/{dir_path}".encode()).hexdigest()[:12]

    # Get other files in the directory
    files = {}
    url = f"{GITHUB_API}/repos/{repo}/contents/{dir_path}"
    dir_contents = github_api_get(url)
    if dir_contents and isinstance(dir_contents, list):
        for item in dir_contents:
            if item["type"] == "file" and item["name"] != "SKILL.md":
                file_content = get_raw_content(repo, item["path"])
                if file_content and len(file_content) < 50000:  # skip very large files
                    files[item["name"]] = file_content

    return Skill(
        skill_id=skill_id,
        name=parsed["name"],
        description=parsed["description"],
        body=content,
        source_repo=repo,
        source_path=dir_path,
        files=files,
        metadata=parsed["frontmatter"],
    )


def search_github_skill_repos() -> list[str]:
    """Search GitHub for repositories containing SKILL.md files."""
    repos = set()
    queries = [
        "SKILL.md in:path",
        "agent skill SKILL.md",
        "claude skill SKILL.md",
        "agent-skills SKILL.md",
    ]

    for query in queries:
        url = f"{GITHUB_API}/search/repositories"
        params = {"q": query, "sort": "stars", "per_page": 100}
        result = github_api_get(url, params)
        if result and "items" in result:
            for item in result["items"]:
                repos.add(item["full_name"])
        time.sleep(2)  # rate limit

    return list(repos)


# Curated list of known skill repositories
KNOWN_REPOS = [
    ("anthropics/skills", "skills"),
    ("anthropics/courses", ""),
    ("VoltAgent/awesome-agent-skills", ""),
    ("skillmatic-ai/awesome-agent-skills", ""),
    ("heilcheng/awesome-agent-skills", ""),
    ("gmh5225/awesome-skills", ""),
    ("ComposioHQ/awesome-claude-skills", ""),
    ("InternScience/Awesome-Scientific-Skills", ""),
]


def extract_skill_links_from_awesome(repo: str) -> list[tuple[str, str]]:
    """Extract links to skill repos from awesome-* repositories."""
    links = []
    readme = get_raw_content(repo, "README.md")
    if not readme:
        return links

    # Match GitHub repo links
    pattern = r"https?://github\.com/([\w\-\.]+/[\w\-\.]+)"
    matches = re.findall(pattern, readme)
    for match in matches:
        clean = match.rstrip("/").rstrip(".")
        if clean != repo and "awesome" not in clean.lower():
            links.append((clean, ""))

    return links


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    all_skills = []
    seen_ids = set()

    # Phase 1: Collect from known repos
    logger.info("=== Phase 1: Collecting from known repositories ===")
    for repo, skill_dir in KNOWN_REPOS:
        logger.info(f"Collecting from {repo}...")
        skills = collect_from_repo(repo, skill_dir)
        for s in skills:
            if s.skill_id not in seen_ids:
                all_skills.append(s)
                seen_ids.add(s.skill_id)
        logger.info(f"  Found {len(skills)} skills")
        time.sleep(1)

    # Phase 2: Extract linked repos from awesome lists
    logger.info("=== Phase 2: Extracting from awesome lists ===")
    linked_repos = set()
    for repo, _ in KNOWN_REPOS:
        if "awesome" in repo.lower():
            links = extract_skill_links_from_awesome(repo)
            for link_repo, link_dir in links:
                linked_repos.add((link_repo, link_dir))
            logger.info(f"  Found {len(links)} linked repos in {repo}")

    for repo, skill_dir in list(linked_repos)[:200]:  # limit to avoid rate limit
        logger.info(f"Collecting from linked repo {repo}...")
        skills = collect_from_repo(repo, skill_dir)
        for s in skills:
            if s.skill_id not in seen_ids:
                all_skills.append(s)
                seen_ids.add(s.skill_id)
        time.sleep(1)

    # Phase 3: GitHub code search
    logger.info("=== Phase 3: GitHub code search for SKILL.md ===")
    discovered_repos = search_github_skill_repos()
    logger.info(f"  Discovered {len(discovered_repos)} repos via search")

    for repo in discovered_repos:
        if repo not in {r for r, _ in KNOWN_REPOS} and repo not in {r for r, _ in linked_repos}:
            logger.info(f"Collecting from discovered repo {repo}...")
            skills = collect_from_repo(repo)
            for s in skills:
                if s.skill_id not in seen_ids:
                    all_skills.append(s)
                    seen_ids.add(s.skill_id)
            time.sleep(1)

    # Save results
    logger.info(f"\n=== Total skills collected: {len(all_skills)} ===")

    # Save as JSONL
    output_file = OUTPUT_DIR / "all_skills.jsonl"
    with open(output_file, "w") as f:
        for skill in all_skills:
            f.write(json.dumps(asdict(skill), ensure_ascii=False) + "\n")
    logger.info(f"Saved to {output_file}")

    # Save summary stats
    stats = {
        "total_skills": len(all_skills),
        "unique_repos": len(set(s.source_repo for s in all_skills)),
        "with_description": sum(1 for s in all_skills if s.description),
        "with_files": sum(1 for s in all_skills if s.files),
        "avg_body_length": sum(len(s.body) for s in all_skills) / max(len(all_skills), 1),
    }
    stats_file = OUTPUT_DIR / "collection_stats.json"
    with open(stats_file, "w") as f:
        json.dump(stats, f, indent=2)
    logger.info(f"Stats: {json.dumps(stats, indent=2)}")


if __name__ == "__main__":
    main()
