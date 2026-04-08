"""SkillWeaver MCP integration — Smart Gateway for AI Agents.

This package implements the MCP (Model Context Protocol) proxy that sits
between an AI agent (Claude, Cursor, Qoder, etc.) and the user's real
MCP servers.  It intercepts `tools/list` to return a dynamically filtered
subset, and transparently routes `tools/call` to the correct upstream server.

Architecture:
    Agent  ──stdio──▶  SkillWeaver Proxy  ──stdio──▶  Real MCP Servers
                         │
                         ├─ protocol.py   JSON-RPC 2.0 over stdio
                         ├─ client.py     Connect to upstream MCP servers
                         ├─ registry.py   Unified tool registry
                         ├─ injector.py   Context-aware tool filtering
                         └─ proxy.py      The proxy server itself
"""
