"""Tests for the FastAPI server and Python SDK."""

from __future__ import annotations

import json

import pytest

from skillweaver.core.models import (
    Plan,
    Skill,
    SkillMatch,
)
from skillweaver.sdk.client import SkillWeaverClient


# =========================================================================
# Server schema tests
# =========================================================================
class TestServerSchemas:
    def test_search_request(self):
        from skillweaver.server.schemas import SearchRequest
        req = SearchRequest(query="web scraping", top_k=5)
        assert req.query == "web scraping"
        assert req.top_k == 5

    def test_plan_request_defaults(self):
        from skillweaver.server.schemas import PlanRequest
        req = PlanRequest(query="complex task")
        assert req.backend == "rule"
        assert req.use_dag is True

    def test_inject_request(self):
        from skillweaver.server.schemas import InjectRequest
        req = InjectRequest(query="analyze data", max_tools=10)
        assert req.token_budget == 8000

    def test_health_response(self):
        from skillweaver.server.schemas import HealthResponse
        h = HealthResponse(version="0.1.0", total_skills=42, has_index=True)
        assert h.status == "ok"

    def test_skill_add_request(self):
        from skillweaver.server.schemas import SkillAddRequest
        req = SkillAddRequest(
            skills=[{"skill_id": "s1", "name": "t1", "description": "d1"}],
            rebuild_index=False,
        )
        assert len(req.skills) == 1
        assert req.rebuild_index is False


# =========================================================================
# SDK local mode tests
# =========================================================================
class TestSDKLocalMode:
    @pytest.fixture
    def client(self, tmp_path):
        """Create a SDK client with a temp store."""
        from skillweaver.config.settings import Settings
        settings = Settings(store_dir=str(tmp_path / ".skillweaver"))
        return SkillWeaverClient(settings=settings)

    def test_initial_state(self, client):
        assert client.skill_count == 0
        assert client.skills == []

    def test_add_skill(self, client):
        skill = Skill(
            skill_id="test_1",
            name="test-skill",
            description="A test skill",
        )
        client.add_skill(skill)
        assert client.skill_count == 1

    def test_load_from_directory(self, client, tmp_path):
        # Create a SKILL.md file
        skill_dir = tmp_path / "my-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(
            "---\nname: demo-skill\ndescription: A demo\ncategories:\n  - test\n---\n# Demo\n"
        )
        added = client.load_skills_from_directory(str(tmp_path))
        assert added == 1
        assert client.skill_count == 1

    def test_load_from_mcp_config(self, client, tmp_path):
        config = {
            "mcpServers": {
                "test-server": {
                    "command": "echo",
                    "tools": [
                        {"name": "tool1", "description": "Test tool"},
                    ],
                }
            }
        }
        cfg_file = tmp_path / "mcp.json"
        cfg_file.write_text(json.dumps(config))
        added = client.load_skills_from_mcp_config(cfg_file)
        assert added == 1

    def test_load_from_openai_functions(self, client):
        funcs = [
            {"name": "get_weather", "description": "Get weather", "parameters": {}},
            {"name": "search", "description": "Search web", "parameters": {}},
        ]
        added = client.load_skills_from_openai_functions(funcs)
        assert added == 2
        assert client.skill_count == 2

    def test_search(self, client):
        # Add some skills first
        for i in range(5):
            client.add_skill(Skill(
                skill_id=f"s_{i}",
                name=f"tool-{i}",
                description=f"Tool {i} for {'data processing' if i < 3 else 'image rendering'}",
            ))
        results = client.search("data processing")
        assert len(results) > 0
        assert all(isinstance(r, SkillMatch) for r in results)

    def test_plan(self, client):
        for i in range(5):
            client.add_skill(Skill(
                skill_id=f"s_{i}",
                name=f"tool-{i}",
                description=f"Tool {i} for data tasks",
            ))
        plan = client.plan("fetch data, then analyze it", backend="rule")
        assert isinstance(plan, Plan)
        assert plan.num_steps >= 1

    def test_filter_tools(self, client):
        for i in range(30):
            client.add_skill(Skill(
                skill_id=f"s_{i}",
                name=f"tool-{i}",
                description=f"Tool {i} for {'data' if i % 2 == 0 else 'images'}",
            ))
        tools = client.filter_tools("data analysis", max_tools=5)
        assert len(tools) <= 5

    def test_duplicate_skills_not_added(self, client):
        skill = Skill(skill_id="dup", name="dup-skill", description="Dup")
        client.add_skill(skill)
        client.add_skill(skill)  # Same ID
        assert client.skill_count == 1


# =========================================================================
# Server app creation test (no actual HTTP — just verify app factory)
# =========================================================================
class TestServerApp:
    def test_create_app(self):
        """Verify the app factory doesn't crash."""
        try:
            from skillweaver.server.app import create_app
            app = create_app()
            # Just check it has routes
            routes = [r.path for r in app.routes]
            assert "/health" in routes
            assert "/search" in routes
            assert "/plan" in routes
            assert "/inject" in routes
            assert "/index/status" in routes
            assert "/index/add" in routes
        except ImportError:
            pytest.skip("FastAPI not installed")
