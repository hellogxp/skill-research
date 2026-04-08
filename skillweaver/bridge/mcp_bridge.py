#!/usr/bin/env python3
"""SkillWeaver MCP Bridge — exposes SkillWeaver skills as MCP tools to CoPaw.

This lightweight HTTP server speaks MCP-compatible Streamable HTTP protocol.
CoPaw connects to it as an MCP client and sees all SkillWeaver-indexed skills
as callable tools. When CoPaw calls a tool, the bridge logs the call and
returns a simulated result (demo mode).

The bridge also provides a /skillweaver/stats endpoint for the Dashboard
to show real-time filtering metrics.
"""

import json
import logging
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from threading import Lock
from urllib.parse import urlparse
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

SKILLWEAVER_API = "http://127.0.0.1:8740"

# Stats for dashboard
stats_lock = Lock()
stats = {
    "total_requests": 0,
    "last_query": "",
    "last_inject_result": None,
    "history": [],
}


def sw_api(path, payload=None):
    """Call SkillWeaver HTTP API."""
    url = f"{SKILLWEAVER_API}{path}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    else:
        req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_all_skills_as_tools():
    """Fetch all indexed skills from SkillWeaver and convert to MCP tool format.

    Uses multiple broad queries to discover all skills since the search API
    requires a meaningful query string.
    """
    health = sw_api("/health")
    total = health.get("total_skills", 0)

    # Use broad category queries to discover all skills
    seen = {}
    queries = [
        "web scraping API HTTP", "data analysis CSV JSON", "file PDF document",
        "communication notification email", "code development testing",
        "DevOps deployment monitoring", "AI machine learning NLP",
        "image chart visualization", "database SQL query", "security scan",
        "text processing format convert", "automation workflow schedule",
    ]
    for q in queries:
        try:
            result = sw_api("/search", {"query": q, "top_k": 50})
            for s in result.get("results", []):
                sid = s["skill_id"]
                if sid not in seen:
                    seen[sid] = s
        except Exception as e:
            logger.warning("Search query '%s' failed: %s", q, e)

    tools = []
    for s in seen.values():
        tool_name = s["name"].replace(" ", "_").replace("-", "_")
        tools.append({
            "name": tool_name,
            "description": f"[SkillWeaver] {s['description']}",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Input data for this skill"},
                },
            },
        })
    return tools, total


def inject_for_query(query, max_tools=10):
    """Call SkillWeaver /inject to get filtered tools."""
    result = sw_api("/inject", {
        "query": query,
        "max_tools": max_tools,
        "token_budget": 8000,
    })
    return result


def plan_for_query(query):
    """Call SkillWeaver /plan to get execution plan."""
    try:
        result = sw_api("/plan", {
            "query": query,
            "backend": "rule",
            "use_dag": True,
            "sad": False,
        })
        return result
    except Exception as e:
        logger.warning("Plan failed: %s", e)
        return None


class MCPBridgeHandler(BaseHTTPRequestHandler):
    """Handle MCP Streamable HTTP requests + stats endpoint."""

    all_tools = []
    total_skills = 0

    def log_message(self, format, *args):
        logger.info(format, *args)

    def _send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", len(body))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = urlparse(self.path).path

        if path == "/skillweaver/stats":
            with stats_lock:
                self._send_json(stats)
            return

        if path == "/health":
            self._send_json({"status": "ok", "tools": len(self.all_tools)})
            return

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        path = urlparse(self.path).path
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length > 0 else b""

        # MCP JSON-RPC endpoint
        if path == "/mcp" or path == "/":
            try:
                msg = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_json({"error": "invalid json"}, 400)
                return
            self._handle_mcp_rpc(msg)
            return

        # Dashboard query endpoint
        if path == "/skillweaver/query":
            try:
                req = json.loads(body) if body else {}
            except json.JSONDecodeError:
                self._send_json({"error": "invalid json"}, 400)
                return
            self._handle_dashboard_query(req)
            return

        self._send_json({"error": "not found"}, 404)

    def _handle_mcp_rpc(self, msg):
        """Handle MCP JSON-RPC messages."""
        method = msg.get("method", "")
        req_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {"listChanged": False}},
                    "serverInfo": {"name": "skillweaver-bridge", "version": "0.1.0"},
                },
            })
            return

        if method == "notifications/initialized":
            self._send_json({"jsonrpc": "2.0", "id": req_id, "result": {}})
            return

        if method == "tools/list":
            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": self.all_tools},
            })
            return

        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            logger.info("Tool call: %s(%s)", tool_name, json.dumps(arguments)[:100])

            # Record for stats
            with stats_lock:
                stats["total_requests"] += 1

            self._send_json({
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [{
                        "type": "text",
                        "text": f"[SkillWeaver Demo] Tool '{tool_name}' executed successfully with input: {json.dumps(arguments)[:200]}",
                    }],
                },
            })
            return

        # Fallback
        self._send_json({
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"},
        })

    def _handle_dashboard_query(self, req):
        """Handle Dashboard query — calls inject + plan and records stats."""
        query = req.get("query", "")
        if not query:
            self._send_json({"error": "missing query"}, 400)
            return

        inject_result = inject_for_query(query, max_tools=req.get("max_tools", 10))
        plan_result = plan_for_query(query)

        total = inject_result.get("total_available", self.total_skills)
        selected = len(inject_result.get("selected_tools", []))
        tokens_before = total * 400
        tokens_after = inject_result.get("token_estimate", 0)
        savings_pct = (1 - tokens_after / max(tokens_before, 1)) * 100

        record = {
            "time": time.strftime("%H:%M:%S"),
            "query": query,
            "total_tools": total,
            "selected_tools": selected,
            "tokens_before": tokens_before,
            "tokens_after": tokens_after,
            "savings_pct": round(savings_pct, 1),
            "inject_result": inject_result,
            "plan_result": plan_result,
        }

        with stats_lock:
            stats["total_requests"] += 1
            stats["last_query"] = query
            stats["last_inject_result"] = record
            stats["history"].insert(0, {
                "time": record["time"],
                "query": query[:60],
                "before": total,
                "after": selected,
                "savings": f"{savings_pct:.1f}%",
            })
            if len(stats["history"]) > 50:
                stats["history"] = stats["history"][:50]

        self._send_json(record)


def main():
    port = 8743
    logger.info("Loading skills from SkillWeaver API...")
    try:
        tools, total = get_all_skills_as_tools()
        MCPBridgeHandler.all_tools = tools
        MCPBridgeHandler.total_skills = total
        logger.info("Loaded %d tools (%d total skills)", len(tools), total)
    except Exception as e:
        logger.error("Failed to load skills: %s", e)
        MCPBridgeHandler.all_tools = []
        MCPBridgeHandler.total_skills = 0

    server = HTTPServer(("0.0.0.0", port), MCPBridgeHandler)
    logger.info("SkillWeaver MCP Bridge running on port %d", port)
    logger.info("  MCP endpoint: http://0.0.0.0:%d/mcp", port)
    logger.info("  Stats: http://0.0.0.0:%d/skillweaver/stats", port)
    logger.info("  Dashboard query: POST http://0.0.0.0:%d/skillweaver/query", port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()


if __name__ == "__main__":
    main()
