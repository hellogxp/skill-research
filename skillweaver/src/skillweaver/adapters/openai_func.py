"""Adapter for OpenAI function-calling format.

Converts OpenAI-style function definitions into unified Skill objects.
Supports both the legacy "functions" format and the newer "tools" format.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from skillweaver.core.models import IOSchema, Skill, SkillFormat

logger = logging.getLogger(__name__)


def parse_openai_functions(
    functions: list[dict[str, Any]],
    source_label: str = "openai",
) -> list[Skill]:
    """Convert a list of OpenAI function definitions to Skills.

    Works with both formats:
      - Legacy: [{"name": ..., "description": ..., "parameters": {...}}]
      - Tools:  [{"type": "function", "function": {"name": ..., ...}}]
    """
    skills: list[Skill] = []

    for entry in functions:
        # Handle the "tools" wrapper format
        if "type" in entry and entry["type"] == "function":
            func_def = entry.get("function", {})
        else:
            func_def = entry

        name = func_def.get("name", "")
        if not name:
            continue

        desc = func_def.get("description", "")
        params = func_def.get("parameters", {})

        # Extract I/O schema from parameters
        io_schema = IOSchema.from_json_schema(params) if params else IOSchema()

        sid = hashlib.md5(f"openai_{source_label}_{name}".encode()).hexdigest()[:12]

        skills.append(Skill(
            skill_id=f"openai_{sid}",
            name=name,
            description=desc,
            source_format=SkillFormat.OPENAI_FUNC,
            io_schema=io_schema,
            server_name=source_label,
            metadata={"parameters": params},
        ))

    logger.info("Parsed %d functions from OpenAI format (%s)", len(skills), source_label)
    return skills


def parse_openai_tools(
    tools: list[dict[str, Any]],
    source_label: str = "openai",
) -> list[Skill]:
    """Alias for parse_openai_functions — handles the tools format."""
    return parse_openai_functions(tools, source_label=source_label)
