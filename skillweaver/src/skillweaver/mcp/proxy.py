"""SkillWeaver MCP Proxy — the zero-config smart gateway.

This is the killer feature: a transparent MCP proxy that sits between
an AI agent and the user's real MCP servers.  The agent connects to
SkillWeaver as if it were a normal MCP server, but behind the scenes
SkillWeaver:

    1. Connects to ALL configured upstream MCP servers
    2. Aggregates their tools into a unified registry
    3. On `tools/list` → returns a SMART FILTERED subset
    4. On `tools/call` → routes to the correct upstream server

The agent gets fewer, better-targeted tools → better selection accuracy,
less context window usage, faster responses.

Usage:
    skillweaver proxy                    # stdio mode (for Claude/Cursor config)
    skillweaver proxy --mode http        # HTTP/SSE mode (for programmatic use)
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

from skillweaver.mcp.client import McpServerConfig
from skillweaver.mcp.injector import ToolInjector
from skillweaver.mcp.protocol import (
    JsonRpcError,
    JsonRpcRequest,
    JsonRpcResponse,
    make_error,
    parse_message,
)
from skillweaver.mcp.registry import ToolRegistry

logger = logging.getLogger(__name__)


class McpProxy:
    """MCP Proxy server — sits between agent and real MCP servers.

    Lifecycle:
        1. Load upstream server configs
        2. Start all upstream servers, discover tools
        3. Build retrieval index for smart filtering
        4. Serve MCP protocol to the downstream agent
    """

    def __init__(
        self,
        server_configs: list[McpServerConfig],
        max_tools: int = 20,
        token_budget: int = 8000,
        mandatory_tools: list[str] | None = None,
    ):
        self.registry = ToolRegistry()
        self.injector = ToolInjector(
            max_tools=max_tools,
            token_budget=token_budget,
            mandatory_tools=mandatory_tools,
        )
        self._server_configs = server_configs
        self._last_query: str = ""
        self._initialized = False

        for cfg in server_configs:
            self.registry.add_server(cfg)

    async def start(self) -> dict[str, int]:
        """Start all upstream servers and build the injection index."""
        results = await self.registry.start_all()

        # Build injector index from registry
        skills = self.registry.skills
        tool_defs = self.registry.get_all_tool_defs()
        if skills:
            self.injector.build_index(skills, tool_defs)

        logger.info(
            "Proxy ready: %d servers, %d tools indexed",
            self.registry.server_count, self.registry.tool_count,
        )
        return results

    async def stop(self) -> None:
        """Stop all upstream servers."""
        await self.registry.stop_all()

    # -- MCP protocol handler ---------------------------------------------

    async def handle_request(self, request: JsonRpcRequest) -> JsonRpcResponse | None:
        """Handle an incoming JSON-RPC request from the downstream agent."""
        method = request.method
        params = request.params or {}

        if method == "initialize":
            return self._handle_initialize(request)
        elif method == "notifications/initialized":
            return None  # Notification, no response
        elif method == "tools/list":
            return await self._handle_tools_list(request, params)
        elif method == "tools/call":
            return await self._handle_tools_call(request, params)
        elif method == "ping":
            return JsonRpcResponse(id=request.id, result={})
        else:
            logger.debug("Unhandled method: %s", method)
            return make_error(
                request.id,
                JsonRpcError.METHOD_NOT_FOUND,
                f"Method not found: {method}",
            )

    def _handle_initialize(self, request: JsonRpcRequest) -> JsonRpcResponse:
        """Handle MCP initialize handshake."""
        self._initialized = True
        return JsonRpcResponse(
            id=request.id,
            result={
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {"listChanged": True},
                },
                "serverInfo": {
                    "name": "skillweaver-proxy",
                    "version": "0.1.0",
                },
            },
        )

    async def _handle_tools_list(
        self,
        request: JsonRpcRequest,
        params: dict[str, Any],
    ) -> JsonRpcResponse:
        """Handle tools/list — this is where the magic happens.

        If we have a query context, return filtered tools.
        Otherwise return all tools (standard MCP behavior).
        """
        # Check if the agent provided a cursor or context hint
        query = self._last_query

        if query and self.injector._retriever:
            # Smart filtering mode
            result = self.injector.select(query)
            logger.info(
                "Smart filter: %d/%d tools (saved %d tokens)",
                len(result.selected_tools),
                result.total_available,
                result.total_available * 400 - result.token_estimate,
            )
            return JsonRpcResponse(
                id=request.id,
                result={"tools": result.selected_tools},
            )
        else:
            # Pass-through mode
            all_tools = self.registry.get_all_tool_defs()
            return JsonRpcResponse(
                id=request.id,
                result={"tools": all_tools},
            )

    async def _handle_tools_call(
        self,
        request: JsonRpcRequest,
        params: dict[str, Any],
    ) -> JsonRpcResponse:
        """Handle tools/call — route to the correct upstream server."""
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        if not tool_name:
            return make_error(
                request.id,
                JsonRpcError.INVALID_PARAMS,
                "Missing 'name' parameter",
            )

        try:
            result = await self.registry.call_tool(tool_name, arguments)
            return JsonRpcResponse(id=request.id, result=result)
        except ValueError as e:
            return make_error(request.id, JsonRpcError.INVALID_PARAMS, str(e))
        except Exception as e:
            logger.error("Tool call failed: %s — %s", tool_name, e)
            return make_error(request.id, JsonRpcError.INTERNAL_ERROR, str(e))

    def set_context(self, query: str) -> None:
        """Update the current query context for smart filtering.

        This can be called externally (e.g., from a conversation hook)
        to inform the proxy about what the user is working on.
        """
        self._last_query = query

    # -- Stdio server loop ------------------------------------------------

    async def serve_stdio(self) -> None:
        """Run the proxy as a stdio MCP server.

        This is the main entry point for use in Claude/Cursor MCP config:
            {
                "mcpServers": {
                    "skillweaver": {
                        "command": "skillweaver",
                        "args": ["proxy"]
                    }
                }
            }
        """
        # Use asyncio streams for non-blocking stdio
        reader = asyncio.StreamReader()
        protocol = asyncio.StreamReaderProtocol(reader)
        await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)

        writer_transport, writer_protocol = await asyncio.get_event_loop().connect_write_pipe(
            asyncio.streams.FlowControlMixin, sys.stdout
        )
        writer = asyncio.StreamWriter(writer_transport, writer_protocol, None, asyncio.get_event_loop())

        logger.info("SkillWeaver proxy serving on stdio")

        try:
            while True:
                msg = await _read_message_async(reader)
                if msg is None:
                    break

                parsed = parse_message(msg)
                if isinstance(parsed, JsonRpcRequest):
                    response = await self.handle_request(parsed)
                    if response is not None:
                        body = json.dumps(response.to_dict(), ensure_ascii=False).encode("utf-8")
                        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
                        writer.write(header + body)
                        await writer.drain()
        except (asyncio.CancelledError, KeyboardInterrupt):
            pass
        finally:
            await self.stop()


async def _read_message_async(reader: asyncio.StreamReader) -> dict[str, Any] | None:
    """Read one JSON-RPC message from an async stream reader."""
    content_length = -1
    while True:
        line = await reader.readline()
        if not line:
            return None
        line_str = line.decode("utf-8", errors="replace").strip()
        if not line_str:
            break
        if line_str.lower().startswith("content-length:"):
            try:
                content_length = int(line_str.split(":", 1)[1].strip())
            except ValueError:
                pass

    if content_length < 0:
        return None

    body = await reader.readexactly(content_length)
    try:
        return json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        return None


# ---------------------------------------------------------------------------
# Config loading helpers
# ---------------------------------------------------------------------------
def load_proxy_configs(config_path: Path | None = None) -> list[McpServerConfig]:
    """Load MCP server configs from a JSON file.

    Searches (in order):
        1. Explicit config_path
        2. .skillweaver.json in cwd
        3. Claude Desktop config
        4. Cursor config
    """
    search_paths = []
    if config_path:
        search_paths.append(config_path)

    search_paths.extend([
        Path.cwd() / ".skillweaver.json",
        Path.home() / "Library/Application Support/Claude/claude_desktop_config.json",
        Path.home() / ".config/claude/claude_desktop_config.json",
        Path.home() / ".cursor" / "mcp.json",
    ])

    for p in search_paths:
        if p.is_file():
            logger.info("Loading MCP config from: %s", p)
            return _parse_config_file(p)

    return []


def _parse_config_file(path: Path) -> list[McpServerConfig]:
    """Parse a config file into McpServerConfig list."""
    try:
        data = json.loads(path.read_text())
    except Exception as e:
        logger.error("Failed to parse config %s: %s", path, e)
        return []

    servers = data.get("mcpServers", data.get("servers", {}))
    configs = []
    for name, cfg in servers.items():
        command = cfg.get("command", "")
        if not command:
            continue
        configs.append(McpServerConfig.from_dict(name, cfg))

    return configs
