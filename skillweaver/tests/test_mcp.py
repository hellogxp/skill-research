"""Tests for MCP protocol, registry, injector, and proxy."""

from __future__ import annotations

import asyncio
import json
from unittest.mock import MagicMock

from skillweaver.core.models import IOSchema, ParamSchema, ParamType, Skill, SkillFormat
from skillweaver.mcp.client import McpServerConfig, McpTool
from skillweaver.mcp.injector import ToolInjector
from skillweaver.mcp.protocol import (
    JsonRpcRequest,
    JsonRpcResponse,
    StdioTransport,
    make_error,
    parse_message,
)
from skillweaver.mcp.registry import ToolRegistry, _mcp_tool_to_skill


# =========================================================================
# Protocol tests
# =========================================================================
class TestJsonRpcRequest:
    def test_to_dict_with_id(self):
        req = JsonRpcRequest(method="tools/list", params={}, id=1)
        d = req.to_dict()
        assert d["jsonrpc"] == "2.0"
        assert d["method"] == "tools/list"
        assert d["id"] == 1

    def test_notification_has_no_id(self):
        req = JsonRpcRequest(method="notifications/initialized", params={})
        assert req.is_notification
        d = req.to_dict()
        assert "id" not in d

    def test_to_dict_without_params(self):
        req = JsonRpcRequest(method="ping", id=2)
        d = req.to_dict()
        assert "params" not in d


class TestJsonRpcResponse:
    def test_success_response(self):
        resp = JsonRpcResponse(id=1, result={"tools": []})
        d = resp.to_dict()
        assert d["result"] == {"tools": []}
        assert not resp.is_error

    def test_error_response(self):
        resp = make_error(1, -32601, "Method not found")
        assert resp.is_error
        d = resp.to_dict()
        assert d["error"]["code"] == -32601
        assert "Method not found" in d["error"]["message"]


class TestParseMessage:
    def test_parse_request(self):
        raw = {"jsonrpc": "2.0", "method": "tools/list", "params": {}, "id": 1}
        msg = parse_message(raw)
        assert isinstance(msg, JsonRpcRequest)
        assert msg.method == "tools/list"

    def test_parse_response(self):
        raw = {"jsonrpc": "2.0", "id": 1, "result": {"tools": []}}
        msg = parse_message(raw)
        assert isinstance(msg, JsonRpcResponse)
        assert msg.result == {"tools": []}


class TestStdioTransport:
    def test_write_and_read_roundtrip(self):
        import io
        buf = io.BytesIO()
        transport = StdioTransport(reader=None, writer=buf)
        transport.write_message({"jsonrpc": "2.0", "method": "ping", "id": 1})

        # Now read it back
        buf.seek(0)
        reader_transport = StdioTransport(reader=buf)
        msg = reader_transport.read_message()
        assert msg is not None
        assert msg["method"] == "ping"

    def test_read_eof(self):
        import io
        buf = io.BytesIO(b"")
        transport = StdioTransport(reader=buf)
        assert transport.read_message() is None


# =========================================================================
# McpTool → Skill conversion
# =========================================================================
class TestMcpToolToSkill:
    def test_basic_conversion(self):
        tool = McpTool(
            name="read_file",
            description="Read a file from disk",
            input_schema={
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path"},
                },
                "required": ["path"],
            },
            server_name="filesystem",
        )
        skill = _mcp_tool_to_skill(tool, "filesystem")
        assert skill.name == "filesystem/read_file"
        assert skill.source_format == SkillFormat.MCP
        assert skill.server_name == "filesystem"
        assert len(skill.io_schema.inputs) == 1
        assert skill.io_schema.inputs[0].name == "path"
        assert skill.io_schema.inputs[0].required is True

    def test_empty_schema(self):
        tool = McpTool(name="ping", description="Ping server", server_name="test")
        skill = _mcp_tool_to_skill(tool, "test")
        assert skill.io_schema.inputs == []


# =========================================================================
# ToolRegistry tests (sync/unit — no actual server spawning)
# =========================================================================
class TestToolRegistry:
    def test_add_server(self):
        registry = ToolRegistry()
        config = McpServerConfig(name="test", command="echo")
        registry.add_server(config)
        assert registry.server_count == 1

    def test_find_server_for_tool_after_rebuild(self):
        registry = ToolRegistry()
        # Manually inject tools (simulating what start_all does)
        McpServerConfig(name="fs", command="node")
        client = MagicMock()
        client.tools = [
            McpTool(name="read", description="Read file", server_name="fs"),
            McpTool(name="write", description="Write file", server_name="fs"),
        ]
        registry._clients["fs"] = client
        registry._rebuild_index()

        assert registry.tool_count == 2
        assert len(registry.skills) == 2
        assert registry.find_server_for_tool("fs/read") == "fs"
        assert registry.find_server_for_tool("read") == "fs"

    def test_get_all_tool_defs(self):
        registry = ToolRegistry()
        client = MagicMock()
        client.tools = [
            McpTool(name="search", description="Search web",
                    input_schema={"type": "object", "properties": {"q": {"type": "string"}}},
                    server_name="web"),
        ]
        registry._clients["web"] = client
        registry._rebuild_index()

        defs = registry.get_all_tool_defs()
        assert len(defs) == 1
        assert defs[0]["name"] == "web/search"
        assert "inputSchema" in defs[0]


# =========================================================================
# ToolInjector tests
# =========================================================================
class TestToolInjector:
    def _make_skills_and_defs(self, n: int):
        """Create n skills with matching tool defs."""
        skills = []
        defs = []
        for i in range(n):
            name = f"tool_{i}"
            skills.append(Skill(
                skill_id=f"s_{i}",
                name=name,
                description=f"Tool number {i} for testing {'data processing' if i % 2 == 0 else 'image rendering'}",
                source_format=SkillFormat.MCP,
                server_name=f"server_{i % 3}",
                io_schema=IOSchema(
                    inputs=[ParamSchema(name="input", param_type=ParamType.STRING)],
                ),
            ))
            defs.append({
                "name": name,
                "description": f"Tool number {i}",
                "inputSchema": {"type": "object", "properties": {"input": {"type": "string"}}},
            })
        return skills, defs

    def test_select_all_when_no_index(self):
        injector = ToolInjector()
        result = injector.select("anything")
        assert result.total_available == 0
        assert result.selected_tools == []

    def test_select_all_returns_everything(self):
        injector = ToolInjector(max_tools=5)
        skills, defs = self._make_skills_and_defs(3)
        injector._all_skills = skills
        injector._skill_to_tool_def = {s.skill_id: d for s, d in zip(skills, defs)}
        result = injector.select_all()
        assert len(result.selected_tools) == 3
        assert result.total_available == 3

    def test_max_tools_limit(self):
        """With many tools, injector should respect max_tools."""
        injector = ToolInjector(max_tools=5, token_budget=100000)
        skills, defs = self._make_skills_and_defs(50)
        injector.build_index(skills, defs)

        result = injector.select("data processing task")
        assert len(result.selected_tools) <= 5
        assert result.total_available == 50

    def test_token_budget_respected(self):
        """Injector should not exceed token budget."""
        injector = ToolInjector(max_tools=100, token_budget=200)
        skills, defs = self._make_skills_and_defs(50)
        injector.build_index(skills, defs)

        result = injector.select("some task")
        assert result.token_estimate <= 200 + 50  # small margin for rounding

    def test_mandatory_tools_always_included(self):
        injector = ToolInjector(max_tools=3, mandatory_tools=["tool_42"])
        skills, defs = self._make_skills_and_defs(50)
        injector.build_index(skills, defs)

        result = injector.select("unrelated query about images")
        tool_names = [t["name"] for t in result.selected_tools]
        assert "tool_42" in tool_names


# =========================================================================
# McpProxy tests (unit level)
# =========================================================================
class TestMcpProxy:
    def test_handle_initialize(self):
        from skillweaver.mcp.proxy import McpProxy
        proxy = McpProxy(server_configs=[], max_tools=10)

        req = JsonRpcRequest(method="initialize", params={
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1.0"},
        }, id=1)

        resp = asyncio.get_event_loop().run_until_complete(proxy.handle_request(req))
        assert resp is not None
        assert resp.result["serverInfo"]["name"] == "skillweaver-proxy"

    def test_handle_ping(self):
        from skillweaver.mcp.proxy import McpProxy
        proxy = McpProxy(server_configs=[], max_tools=10)

        req = JsonRpcRequest(method="ping", id=2)
        resp = asyncio.get_event_loop().run_until_complete(proxy.handle_request(req))
        assert resp.result == {}

    def test_handle_unknown_method(self):
        from skillweaver.mcp.proxy import McpProxy
        proxy = McpProxy(server_configs=[], max_tools=10)

        req = JsonRpcRequest(method="unknown/method", id=3)
        resp = asyncio.get_event_loop().run_until_complete(proxy.handle_request(req))
        assert resp.is_error

    def test_handle_notification_returns_none(self):
        from skillweaver.mcp.proxy import McpProxy
        proxy = McpProxy(server_configs=[], max_tools=10)

        req = JsonRpcRequest(method="notifications/initialized", params={})
        resp = asyncio.get_event_loop().run_until_complete(proxy.handle_request(req))
        assert resp is None

    def test_tools_list_empty_registry(self):
        from skillweaver.mcp.proxy import McpProxy
        proxy = McpProxy(server_configs=[], max_tools=10)

        req = JsonRpcRequest(method="tools/list", params={}, id=4)
        resp = asyncio.get_event_loop().run_until_complete(proxy.handle_request(req))
        assert resp.result == {"tools": []}

    def test_set_context(self):
        from skillweaver.mcp.proxy import McpProxy
        proxy = McpProxy(server_configs=[], max_tools=10)
        proxy.set_context("analyze CSV data")
        assert proxy._last_query == "analyze CSV data"


# =========================================================================
# Config loading tests
# =========================================================================
class TestConfigLoading:
    def test_parse_claude_config(self, tmp_path):
        from skillweaver.mcp.proxy import load_proxy_configs
        cfg = {
            "mcpServers": {
                "filesystem": {
                    "command": "node",
                    "args": ["dist/index.js", "/tmp"],
                },
                "github": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-github"],
                    "env": {"GITHUB_TOKEN": "test"},
                },
            }
        }
        cfg_file = tmp_path / ".skillweaver.json"
        cfg_file.write_text(json.dumps(cfg))

        configs = load_proxy_configs(cfg_file)
        assert len(configs) == 2
        names = {c.name for c in configs}
        assert names == {"filesystem", "github"}
        gh = next(c for c in configs if c.name == "github")
        assert gh.env == {"GITHUB_TOKEN": "test"}

    def test_empty_config(self, tmp_path):
        from skillweaver.mcp.proxy import load_proxy_configs
        cfg_file = tmp_path / ".skillweaver.json"
        cfg_file.write_text("{}")
        configs = load_proxy_configs(cfg_file)
        assert configs == []

    def test_no_config_found(self, tmp_path):
        from skillweaver.mcp.proxy import load_proxy_configs
        # Pass a nonexistent path
        configs = load_proxy_configs(tmp_path / "does_not_exist.json")
        # Falls back to searching default locations which probably don't exist in CI
        # So we just check it doesn't crash
        assert isinstance(configs, list)
