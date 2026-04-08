"""MCP upstream client — spawns and communicates with real MCP servers.

Each McpClient manages a single upstream MCP server process.
Communication uses JSON-RPC 2.0 over stdio (Content-Length framing).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class McpServerConfig:
    """Configuration for one upstream MCP server."""
    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None

    @classmethod
    def from_dict(cls, name: str, d: dict[str, Any]) -> "McpServerConfig":
        return cls(
            name=name,
            command=d.get("command", ""),
            args=d.get("args", []),
            env=d.get("env", {}),
            cwd=d.get("cwd"),
        )


@dataclass
class McpTool:
    """A tool definition as returned by an MCP server."""
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)
    server_name: str = ""  # which server this tool belongs to


class McpClient:
    """Client for a single upstream MCP server.

    Manages the server process lifecycle and provides async methods
    to call MCP protocol methods (initialize, tools/list, tools/call).
    """

    def __init__(self, config: McpServerConfig):
        self.config = config
        self._process: asyncio.subprocess.Process | None = None
        self._request_id = 0
        self._pending: dict[int, asyncio.Future] = {}
        self._reader_task: asyncio.Task | None = None
        self._tools: list[McpTool] = []
        self._initialized = False

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def tools(self) -> list[McpTool]:
        return list(self._tools)

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def start(self) -> None:
        """Spawn the MCP server process and initialize the connection."""
        if self.is_running:
            return

        import os
        env = {**os.environ, **self.config.env}

        logger.info("Starting MCP server: %s (%s %s)",
                     self.config.name, self.config.command, " ".join(self.config.args))

        self._process = await asyncio.create_subprocess_exec(
            self.config.command,
            *self.config.args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
            cwd=self.config.cwd,
        )

        # Start background reader
        self._reader_task = asyncio.create_task(self._read_loop())

        # MCP initialize handshake
        result = await self._send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "skillweaver-proxy", "version": "0.1.0"},
        })
        logger.debug("Server %s initialized: %s", self.name, result)

        # Send initialized notification
        await self._send_notification("notifications/initialized", {})

        self._initialized = True

    async def stop(self) -> None:
        """Gracefully stop the MCP server."""
        if not self.is_running:
            return
        try:
            self._process.stdin.close()
            await asyncio.wait_for(self._process.wait(), timeout=5.0)
        except (asyncio.TimeoutError, ProcessLookupError):
            self._process.kill()
        finally:
            if self._reader_task:
                self._reader_task.cancel()
            self._process = None
            self._initialized = False
            # Cancel pending futures
            for fut in self._pending.values():
                if not fut.done():
                    fut.cancel()
            self._pending.clear()

    async def list_tools(self) -> list[McpTool]:
        """Call tools/list and cache the result."""
        result = await self._send_request("tools/list", {})
        raw_tools = result.get("tools", []) if isinstance(result, dict) else []
        self._tools = [
            McpTool(
                name=t.get("name", ""),
                description=t.get("description", ""),
                input_schema=t.get("inputSchema", {}),
                server_name=self.name,
            )
            for t in raw_tools
            if t.get("name")
        ]
        logger.info("Server %s has %d tools", self.name, len(self._tools))
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> Any:
        """Call tools/call on the upstream server."""
        result = await self._send_request("tools/call", {
            "name": tool_name,
            "arguments": arguments,
        })
        return result

    # -- Internal transport ------------------------------------------------

    async def _send_request(self, method: str, params: dict[str, Any]) -> Any:
        """Send a request and wait for the response."""
        if not self._process or not self._process.stdin:
            raise RuntimeError(f"Server {self.name} is not running")

        self._request_id += 1
        req_id = self._request_id
        msg = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params,
        }

        future: asyncio.Future = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future

        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._process.stdin.write(header + body)
        await self._process.stdin.drain()

        try:
            result = await asyncio.wait_for(future, timeout=30.0)
        except asyncio.TimeoutError:
            self._pending.pop(req_id, None)
            raise TimeoutError(f"Request {method} to {self.name} timed out")

        return result

    async def _send_notification(self, method: str, params: dict[str, Any]) -> None:
        """Send a notification (no response expected)."""
        if not self._process or not self._process.stdin:
            return
        msg = {
            "jsonrpc": "2.0",
            "method": method,
            "params": params,
        }
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._process.stdin.write(header + body)
        await self._process.stdin.drain()

    async def _read_loop(self) -> None:
        """Background task that reads responses from the server."""
        assert self._process and self._process.stdout

        reader = self._process.stdout
        try:
            while True:
                # Read headers
                content_length = -1
                while True:
                    line = await reader.readline()
                    if not line:
                        return  # EOF
                    line_str = line.decode("utf-8", errors="replace").strip()
                    if not line_str:
                        break
                    if line_str.lower().startswith("content-length:"):
                        try:
                            content_length = int(line_str.split(":", 1)[1].strip())
                        except ValueError:
                            pass

                if content_length < 0:
                    continue

                body = await reader.readexactly(content_length)
                try:
                    msg = json.loads(body.decode("utf-8"))
                except json.JSONDecodeError:
                    continue

                # Dispatch
                msg_id = msg.get("id")
                if msg_id is not None and msg_id in self._pending:
                    future = self._pending.pop(msg_id)
                    if "error" in msg:
                        future.set_exception(
                            RuntimeError(f"MCP error: {msg['error']}")
                        )
                    else:
                        future.set_result(msg.get("result"))
                elif "method" in msg:
                    # Server-initiated notification/request — log and ignore for now
                    logger.debug("Server %s notification: %s", self.name, msg.get("method"))

        except (asyncio.CancelledError, asyncio.IncompleteReadError):
            pass
        except Exception as e:
            logger.error("Read loop error for %s: %s", self.name, e)
