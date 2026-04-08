"""Adapter for Model Context Protocol (MCP) server configurations.

Parses MCP server config files and converts tool definitions into Skill objects.
Now extracts I/O schemas from MCP inputSchema for type-aware compatibility scoring.
"""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path

from skillweaver.core.models import IOSchema, Skill, SkillFormat

logger = logging.getLogger(__name__)


def parse_mcp_config(config_path: Path) -> list[Skill]:
    """Parse an MCP server configuration file.

    Supports both Claude Desktop format and generic MCP config.

    Expected format (Claude Desktop):
    {
        "mcpServers": {
            "server-name": {
                "command": "...",
                "args": [...],
                "tools": [
                    {"name": "tool_name", "description": "...", "inputSchema": {...}}
                ]
            }
        }
    }
    """
    try:
        data = json.loads(config_path.read_text())
    except Exception as e:
        logger.warning(f"Failed to parse MCP config {config_path}: {e}")
        return []

    skills = []
    servers = data.get("mcpServers", data.get("servers", {}))

    for server_name, server_config in servers.items():
        tools = server_config.get("tools", [])

        if not tools:
            # If no tools listed, create a single skill for the server
            desc = server_config.get("description", f"MCP server: {server_name}")
            sid = hashlib.md5(f"mcp_{server_name}".encode()).hexdigest()[:12]
            skills.append(Skill(
                skill_id=f"mcp_{sid}",
                name=server_name,
                description=desc,
                source_format=SkillFormat.MCP,
                source_path=str(config_path),
                server_name=server_name,
                metadata={"server": server_name},
            ))
            continue

        for tool in tools:
            tool_name = tool.get("name", "")
            if not tool_name:
                continue
            full_name = f"{server_name}/{tool_name}"
            desc = tool.get("description", "")

            # Extract I/O schema from inputSchema
            input_schema_raw = tool.get("inputSchema", {})
            io_schema = IOSchema.from_json_schema(input_schema_raw) if input_schema_raw else IOSchema()

            schema_str = json.dumps(input_schema_raw, indent=2)

            sid = hashlib.md5(f"mcp_{full_name}".encode()).hexdigest()[:12]
            skills.append(Skill(
                skill_id=f"mcp_{sid}",
                name=full_name,
                description=desc,
                body=f"Input schema:\n{schema_str}" if schema_str != "{}" else "",
                source_format=SkillFormat.MCP,
                source_path=str(config_path),
                io_schema=io_schema,
                server_name=server_name,
                metadata={"server": server_name, "tool": tool_name},
            ))

    logger.info(f"Parsed {len(skills)} tools from MCP config: {config_path.name}")
    return skills
