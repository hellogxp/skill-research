"""Pack publisher — create skill packs from various sources.

Helpers for curating and packaging skills for sharing.
"""

from __future__ import annotations

import logging
from pathlib import Path

from skillweaver.core.models import Skill
from skillweaver.hub.client import SkillPack

logger = logging.getLogger(__name__)


def create_pack_from_directory(
    path: Path,
    name: str,
    version: str = "1.0.0",
    author: str = "",
    description: str = "",
    tags: list[str] | None = None,
) -> SkillPack:
    """Create a skill pack from a directory of SKILL.md files."""
    from skillweaver.adapters.skill_md import scan_directory

    skills = scan_directory(path)
    return SkillPack(
        name=name,
        version=version,
        description=description or f"Skills from {path.name}",
        author=author,
        skills=skills,
        tags=tags or [],
    )


def create_pack_from_mcp_config(
    config_path: Path,
    name: str,
    version: str = "1.0.0",
    author: str = "",
    description: str = "",
    tags: list[str] | None = None,
) -> SkillPack:
    """Create a skill pack from an MCP config file."""
    from skillweaver.adapters.mcp import parse_mcp_config

    skills = parse_mcp_config(config_path)
    return SkillPack(
        name=name,
        version=version,
        description=description or f"MCP tools from {config_path.name}",
        author=author,
        skills=skills,
        tags=tags or [],
    )


def create_pack_from_skills(
    skills: list[Skill],
    name: str,
    version: str = "1.0.0",
    author: str = "",
    description: str = "",
    tags: list[str] | None = None,
) -> SkillPack:
    """Create a skill pack from an explicit list of skills."""
    return SkillPack(
        name=name,
        version=version,
        description=description,
        author=author,
        skills=skills,
        tags=tags or [],
    )
