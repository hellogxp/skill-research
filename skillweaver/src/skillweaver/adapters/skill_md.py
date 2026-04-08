"""Adapter for Anthropic SKILL.md format.

Parses SKILL.md files (YAML frontmatter + markdown body) into unified Skill objects.
Extracts tags, version, author, and auth metadata when available.
"""

from __future__ import annotations

import hashlib
import logging
import re
from pathlib import Path

import yaml

from skillweaver.core.models import Skill, SkillFormat

logger = logging.getLogger(__name__)


def parse_skill_md(path: Path) -> Skill | None:
    """Parse a single SKILL.md file into a Skill object."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        logger.warning(f"Failed to read {path}: {e}")
        return None

    # Extract YAML frontmatter
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if fm_match:
        try:
            frontmatter = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            frontmatter = {}
        body = text[fm_match.end() :].strip()
    else:
        frontmatter = {}
        body = text.strip()

    name = frontmatter.get("name", "") or path.parent.name
    description = frontmatter.get("description", "")

    if not name:
        return None

    # Generate stable ID from path
    skill_id = hashlib.md5(str(path.resolve()).encode()).hexdigest()[:12]

    return Skill(
        skill_id=f"skill_md_{skill_id}",
        name=name,
        description=description,
        body=body,
        categories=frontmatter.get("categories", []),
        tags=frontmatter.get("tags", []),
        source_format=SkillFormat.SKILL_MD,
        source_path=str(path),
        version=str(frontmatter.get("version", "")),
        author=frontmatter.get("author", ""),
        auth_required=bool(frontmatter.get("auth_required", False)),
        auth_type=frontmatter.get("auth_type", ""),
        metadata=frontmatter,
    )


def scan_directory(root: Path, recursive: bool = True) -> list[Skill]:
    """Scan a directory for SKILL.md files and parse them."""
    pattern = "**/SKILL.md" if recursive else "SKILL.md"
    skills = []

    for path in sorted(root.glob(pattern)):
        skill = parse_skill_md(path)
        if skill:
            skills.append(skill)

    logger.info(f"Found {len(skills)} skills in {root}")
    return skills
