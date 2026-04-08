"""Unified tool registry — aggregates tools from multiple MCP servers.

The Registry is the single source of truth for all available tools.
It tracks which tool belongs to which server and converts MCP tool
definitions into SkillWeaver's unified Skill model for retrieval.
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from skillweaver.core.models import IOSchema, Skill, SkillFormat
from skillweaver.mcp.client import McpClient, McpServerConfig, McpTool

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Aggregates tools from multiple MCP servers into a unified registry.

    Responsibilities:
        - Manage MCP client lifecycles
        - Discover and cache tool definitions from all servers
        - Convert McpTool → Skill for retrieval/filtering
        - Route tool calls to the correct upstream server
    """

    def __init__(self) -> None:
        self._clients: dict[str, McpClient] = {}  # server_name → client
        self._tools: dict[str, McpTool] = {}       # tool_name → tool
        self._skills: list[Skill] = []
        self._tool_to_server: dict[str, str] = {}  # tool_name → server_name

    @property
    def server_count(self) -> int:
        return len(self._clients)

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def skills(self) -> list[Skill]:
        return list(self._skills)

    def add_server(self, config: McpServerConfig) -> None:
        """Register an MCP server (does not start it yet)."""
        client = McpClient(config)
        self._clients[config.name] = client
        logger.info("Registered server: %s", config.name)

    async def start_all(self) -> dict[str, int]:
        """Start all registered servers and discover their tools.

        Returns:
            Dict mapping server_name → number of tools discovered.
        """
        import asyncio

        results: dict[str, int] = {}

        async def _start_one(name: str, client: McpClient) -> tuple[str, int]:
            try:
                await client.start()
                tools = await client.list_tools()
                return name, len(tools)
            except Exception as e:
                logger.error("Failed to start server %s: %s", name, e)
                return name, 0

        tasks = [_start_one(n, c) for n, c in self._clients.items()]
        for coro in asyncio.as_completed(tasks):
            name, count = await coro
            results[name] = count

        # Rebuild unified index
        self._rebuild_index()
        return results

    async def stop_all(self) -> None:
        """Stop all running MCP servers."""
        import asyncio
        await asyncio.gather(
            *(c.stop() for c in self._clients.values()),
            return_exceptions=True,
        )

    def _rebuild_index(self) -> None:
        """Rebuild the unified tool index from all clients."""
        self._tools.clear()
        self._tool_to_server.clear()
        self._skills.clear()

        for name, client in self._clients.items():
            for tool in client.tools:
                # Use server_name/tool_name as unique key
                full_name = f"{name}/{tool.name}"
                self._tools[full_name] = tool
                self._tool_to_server[full_name] = name
                # Also register bare tool name for routing
                self._tool_to_server[tool.name] = name

                # Convert to Skill
                self._skills.append(_mcp_tool_to_skill(tool, name))

        logger.info(
            "Registry rebuilt: %d servers, %d tools",
            self.server_count, self.tool_count,
        )

    def get_skill_by_tool_name(self, tool_name: str) -> Skill | None:
        """Find a Skill by its tool name (bare or full)."""
        for skill in self._skills:
            if skill.name == tool_name or skill.metadata.get("tool") == tool_name:
                return skill
        return None

    def find_server_for_tool(self, tool_name: str) -> str | None:
        """Find which server owns a given tool."""
        return self._tool_to_server.get(tool_name)

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Route a tools/call to the correct upstream server."""
        server_name = self.find_server_for_tool(tool_name)
        if server_name is None:
            raise ValueError(f"Unknown tool: {tool_name}")

        client = self._clients.get(server_name)
        if client is None or not client.is_running:
            raise RuntimeError(f"Server {server_name} is not running")

        # Use bare tool name for the actual call
        bare_name = tool_name.split("/", 1)[-1] if "/" in tool_name else tool_name
        return await client.call_tool(bare_name, arguments)

    def get_all_tool_defs(self) -> list[dict[str, Any]]:
        """Return all tools in MCP wire format (for unfiltered tools/list)."""
        result = []
        for full_name, tool in self._tools.items():
            result.append({
                "name": full_name,
                "description": tool.description,
                "inputSchema": tool.input_schema,
            })
        return result

    def get_tool_def(self, tool_name: str) -> dict[str, Any] | None:
        """Get a single tool definition in MCP wire format."""
        tool = self._tools.get(tool_name)
        if tool is None:
            # Try bare name lookup
            for full_name, t in self._tools.items():
                if t.name == tool_name:
                    tool = t
                    tool_name = full_name
                    break
        if tool is None:
            return None
        return {
            "name": tool_name,
            "description": tool.description,
            "inputSchema": tool.input_schema,
        }


def _mcp_tool_to_skill(tool: McpTool, server_name: str) -> Skill:
    """Convert an MCP tool definition to a SkillWeaver Skill."""
    full_name = f"{server_name}/{tool.name}"
    sid = hashlib.md5(f"mcp_{full_name}".encode()).hexdigest()[:12]
    io_schema = IOSchema.from_json_schema(tool.input_schema) if tool.input_schema else IOSchema()

    return Skill(
        skill_id=f"mcp_{sid}",
        name=full_name,
        description=tool.description,
        source_format=SkillFormat.MCP,
        io_schema=io_schema,
        server_name=server_name,
        metadata={"server": server_name, "tool": tool.name},
    )
