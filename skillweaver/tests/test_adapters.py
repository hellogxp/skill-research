"""Tests for adapters — OpenAI functions, MCP config, SKILL.md."""

import json

from skillweaver.adapters.mcp import parse_mcp_config
from skillweaver.adapters.openai_func import parse_openai_functions
from skillweaver.adapters.skill_md import parse_skill_md
from skillweaver.core.models import ParamType, SkillFormat


class TestOpenAIAdapter:
    def test_legacy_format(self):
        funcs = [
            {
                "name": "get_weather",
                "description": "Get the current weather",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {"type": "string", "description": "City name"},
                        "unit": {"type": "string", "enum": ["celsius", "fahrenheit"]},
                    },
                    "required": ["location"],
                },
            }
        ]
        skills = parse_openai_functions(funcs)
        assert len(skills) == 1
        s = skills[0]
        assert s.name == "get_weather"
        assert s.source_format == SkillFormat.OPENAI_FUNC
        assert len(s.io_schema.inputs) == 2
        loc = next(p for p in s.io_schema.inputs if p.name == "location")
        assert loc.required is True
        assert loc.param_type == ParamType.STRING

    def test_tools_format(self):
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "search",
                    "description": "Search the web",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string"},
                        },
                    },
                },
            }
        ]
        skills = parse_openai_functions(tools)
        assert len(skills) == 1
        assert skills[0].name == "search"

    def test_empty_list(self):
        assert parse_openai_functions([]) == []

    def test_missing_name_skipped(self):
        funcs = [{"description": "no name here"}]
        assert parse_openai_functions(funcs) == []


class TestMCPAdapter:
    def test_parse_with_tools(self, tmp_path):
        config = {
            "mcpServers": {
                "filesystem": {
                    "command": "node",
                    "args": ["server.js"],
                    "tools": [
                        {
                            "name": "read_file",
                            "description": "Read a file from disk",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string", "description": "File path"},
                                },
                                "required": ["path"],
                            },
                        },
                        {
                            "name": "write_file",
                            "description": "Write content to a file",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "path": {"type": "string"},
                                    "content": {"type": "string"},
                                },
                                "required": ["path", "content"],
                            },
                        },
                    ],
                }
            }
        }
        cfg_file = tmp_path / "mcp.json"
        cfg_file.write_text(json.dumps(config))

        skills = parse_mcp_config(cfg_file)
        assert len(skills) == 2
        assert skills[0].name == "filesystem/read_file"
        assert skills[0].source_format == SkillFormat.MCP
        assert skills[0].server_name == "filesystem"
        # Check I/O schema extraction
        assert len(skills[0].io_schema.inputs) == 1
        assert skills[0].io_schema.inputs[0].name == "path"

    def test_parse_without_tools(self, tmp_path):
        config = {
            "mcpServers": {
                "my-server": {
                    "command": "python",
                    "description": "A custom server",
                }
            }
        }
        cfg_file = tmp_path / "mcp.json"
        cfg_file.write_text(json.dumps(config))

        skills = parse_mcp_config(cfg_file)
        assert len(skills) == 1
        assert skills[0].name == "my-server"


class TestSkillMDAdapter:
    def test_parse_with_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text(
            "---\n"
            "name: data-fetcher\n"
            "description: Fetches data from APIs\n"
            "categories:\n"
            "  - data\n"
            "  - web\n"
            "tags:\n"
            "  - api\n"
            "  - http\n"
            "version: '2.0'\n"
            "author: test-user\n"
            "auth_required: true\n"
            "auth_type: api_key\n"
            "---\n"
            "# Data Fetcher\n\n"
            "This skill fetches data.\n"
        )

        skill = parse_skill_md(skill_file)
        assert skill is not None
        assert skill.name == "data-fetcher"
        assert skill.categories == ["data", "web"]
        assert skill.tags == ["api", "http"]
        assert skill.version == "2.0"
        assert skill.author == "test-user"
        assert skill.auth_required is True
        assert skill.auth_type == "api_key"
        assert "Data Fetcher" in skill.body

    def test_parse_without_frontmatter(self, tmp_path):
        skill_dir = tmp_path / "plain-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("# Just a skill\n\nNo frontmatter here.\n")

        skill = parse_skill_md(skill_file)
        assert skill is not None
        assert skill.name == "plain-skill"  # falls back to parent dir name
