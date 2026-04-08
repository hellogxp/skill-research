"""JSON-RPC 2.0 protocol helpers for MCP communication.

MCP uses the LSP-style transport: Content-Length headers over stdio.
This module handles low-level message framing, parsing, and construction.
"""

from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from typing import Any, BinaryIO

logger = logging.getLogger(__name__)

JSONRPC_VERSION = "2.0"


# ---------------------------------------------------------------------------
# Message types
# ---------------------------------------------------------------------------
@dataclass
class JsonRpcRequest:
    """A JSON-RPC 2.0 request."""
    method: str
    params: dict[str, Any] | list | None = None
    id: int | str | None = None  # None = notification

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        if self.id is not None:
            d["id"] = self.id
        return d

    @property
    def is_notification(self) -> bool:
        return self.id is None


@dataclass
class JsonRpcResponse:
    """A JSON-RPC 2.0 response."""
    id: int | str | None
    result: Any = None
    error: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": JSONRPC_VERSION, "id": self.id}
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d

    @property
    def is_error(self) -> bool:
        return self.error is not None


@dataclass
class JsonRpcError:
    """Standard JSON-RPC error codes."""
    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


def make_error(id: int | str | None, code: int, message: str, data: Any = None) -> JsonRpcResponse:
    """Create an error response."""
    err: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return JsonRpcResponse(id=id, error=err)


# ---------------------------------------------------------------------------
# Message parsing
# ---------------------------------------------------------------------------
def parse_message(raw: dict[str, Any]) -> JsonRpcRequest | JsonRpcResponse:
    """Parse a raw JSON dict into a typed message."""
    if "method" in raw:
        return JsonRpcRequest(
            method=raw["method"],
            params=raw.get("params"),
            id=raw.get("id"),
        )
    else:
        return JsonRpcResponse(
            id=raw.get("id"),
            result=raw.get("result"),
            error=raw.get("error"),
        )


# ---------------------------------------------------------------------------
# Stdio transport (LSP-style Content-Length framing)
# ---------------------------------------------------------------------------
class StdioTransport:
    """Read/write JSON-RPC messages over stdio with Content-Length framing."""

    def __init__(
        self,
        reader: BinaryIO | None = None,
        writer: BinaryIO | None = None,
    ):
        self._reader = reader or sys.stdin.buffer
        self._writer = writer or sys.stdout.buffer

    def read_message(self) -> dict[str, Any] | None:
        """Read one message from the transport. Returns None on EOF."""
        # Read headers
        content_length = -1
        while True:
            line = self._reader.readline()
            if not line:
                return None  # EOF
            line_str = line.decode("utf-8", errors="replace").strip()
            if not line_str:
                break  # End of headers
            if line_str.lower().startswith("content-length:"):
                try:
                    content_length = int(line_str.split(":", 1)[1].strip())
                except ValueError:
                    logger.warning("Invalid Content-Length: %s", line_str)
                    return None

        if content_length < 0:
            # Try reading as bare JSON line (some MCP servers don't use headers)
            line = self._reader.readline()
            if not line:
                return None
            try:
                return json.loads(line.decode("utf-8", errors="replace"))
            except json.JSONDecodeError:
                return None

        # Read body
        body = self._reader.read(content_length)
        if len(body) < content_length:
            return None  # Incomplete read
        try:
            return json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as e:
            logger.warning("Failed to parse JSON body: %s", e)
            return None

    def write_message(self, msg: dict[str, Any]) -> None:
        """Write one message to the transport."""
        body = json.dumps(msg, ensure_ascii=False).encode("utf-8")
        header = f"Content-Length: {len(body)}\r\n\r\n".encode("utf-8")
        self._writer.write(header + body)
        self._writer.flush()

    def send_request(self, request: JsonRpcRequest) -> None:
        self.write_message(request.to_dict())

    def send_response(self, response: JsonRpcResponse) -> None:
        self.write_message(response.to_dict())
