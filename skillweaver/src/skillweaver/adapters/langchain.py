"""Adapter for LangChain tools.

Converts LangChain BaseTool instances into unified Skill objects.
Works with LangChain, LangChain-community, and LangGraph tools.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from skillweaver.core.models import IOSchema, ParamSchema, ParamType, Skill, SkillFormat

logger = logging.getLogger(__name__)

# Mapping from Python/Pydantic types to our ParamType
_TYPE_MAP: dict[str, ParamType] = {
    "str": ParamType.STRING,
    "string": ParamType.STRING,
    "int": ParamType.INTEGER,
    "integer": ParamType.INTEGER,
    "float": ParamType.NUMBER,
    "number": ParamType.NUMBER,
    "bool": ParamType.BOOLEAN,
    "boolean": ParamType.BOOLEAN,
    "list": ParamType.ARRAY,
    "array": ParamType.ARRAY,
    "dict": ParamType.OBJECT,
    "object": ParamType.OBJECT,
}


def parse_langchain_tools(
    tools: list[Any],
    source_label: str = "langchain",
) -> list[Skill]:
    """Convert LangChain BaseTool instances to Skills.

    Each tool is expected to have at minimum:
      - name: str
      - description: str
    And optionally:
      - args_schema: Pydantic model class
      - args: dict (schema dict)
    """
    skills: list[Skill] = []

    for tool in tools:
        name = getattr(tool, "name", "")
        if not name:
            continue

        desc = getattr(tool, "description", "")
        io_schema = _extract_io_schema(tool)

        sid = hashlib.md5(f"lc_{source_label}_{name}".encode()).hexdigest()[:12]

        skills.append(Skill(
            skill_id=f"lc_{sid}",
            name=name,
            description=desc,
            source_format=SkillFormat.LANGCHAIN,
            io_schema=io_schema,
            server_name=source_label,
            metadata={"tool_class": type(tool).__name__},
        ))

    logger.info("Parsed %d tools from LangChain format (%s)", len(skills), source_label)
    return skills


def _extract_io_schema(tool: Any) -> IOSchema:
    """Try to extract IOSchema from a LangChain tool."""
    inputs: list[ParamSchema] = []

    # Try args_schema (Pydantic model)
    args_schema = getattr(tool, "args_schema", None)
    if args_schema is not None:
        try:
            # Pydantic v2
            if hasattr(args_schema, "model_json_schema"):
                schema = args_schema.model_json_schema()
            # Pydantic v1
            elif hasattr(args_schema, "schema"):
                schema = args_schema.schema()
            else:
                schema = {}
            return IOSchema.from_json_schema(schema)
        except Exception:
            pass

    # Try args dict
    args_dict = getattr(tool, "args", None)
    if isinstance(args_dict, dict):
        return IOSchema.from_json_schema(args_dict)

    return IOSchema(inputs=inputs)
