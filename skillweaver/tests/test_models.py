"""Tests for core models — Skill, IOSchema, ParamSchema, Plan."""

from skillweaver.core.models import (
    IOSchema,
    ParamSchema,
    ParamType,
    Plan,
    PlanStep,
    Skill,
)


# ---------------------------------------------------------------------------
# ParamSchema
# ---------------------------------------------------------------------------
class TestParamSchema:
    def test_to_dict_minimal(self):
        p = ParamSchema(name="query", param_type=ParamType.STRING)
        d = p.to_dict()
        assert d == {"name": "query", "type": "string"}

    def test_to_dict_full(self):
        p = ParamSchema(
            name="format",
            param_type=ParamType.STRING,
            description="Output format",
            required=True,
            default="json",
            enum=["json", "csv"],
        )
        d = p.to_dict()
        assert d["required"] is True
        assert d["default"] == "json"
        assert d["enum"] == ["json", "csv"]

    def test_roundtrip(self):
        original = ParamSchema(
            name="count",
            param_type=ParamType.INTEGER,
            description="Number of items",
            required=True,
        )
        restored = ParamSchema.from_dict(original.to_dict())
        assert restored.name == original.name
        assert restored.param_type == original.param_type
        assert restored.required == original.required


# ---------------------------------------------------------------------------
# IOSchema
# ---------------------------------------------------------------------------
class TestIOSchema:
    def test_empty(self):
        schema = IOSchema()
        assert schema.input_types == set()
        assert schema.output_types == set()

    def test_types(self):
        schema = IOSchema(
            inputs=[
                ParamSchema(name="url", param_type=ParamType.STRING),
                ParamSchema(name="depth", param_type=ParamType.INTEGER),
            ],
            outputs=[
                ParamSchema(name="data", param_type=ParamType.OBJECT),
            ],
        )
        assert schema.input_types == {ParamType.STRING, ParamType.INTEGER}
        assert schema.output_types == {ParamType.OBJECT}

    def test_from_json_schema(self):
        raw = {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results"},
            },
            "required": ["query"],
        }
        schema = IOSchema.from_json_schema(raw)
        assert len(schema.inputs) == 2
        names = {p.name for p in schema.inputs}
        assert names == {"query", "limit"}
        query_param = next(p for p in schema.inputs if p.name == "query")
        assert query_param.required is True
        assert query_param.param_type == ParamType.STRING

    def test_roundtrip(self):
        original = IOSchema(
            inputs=[ParamSchema(name="x", param_type=ParamType.NUMBER)],
            outputs=[ParamSchema(name="y", param_type=ParamType.STRING)],
        )
        restored = IOSchema.from_dict(original.to_dict())
        assert len(restored.inputs) == 1
        assert len(restored.outputs) == 1
        assert restored.inputs[0].name == "x"


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------
class TestSkill:
    def _make_skill(self, **kwargs):
        defaults = {
            "skill_id": "test_001",
            "name": "web-scraper",
            "description": "Scrapes web pages and extracts content",
            "categories": ["data", "web"],
            "tags": ["scraping", "html"],
        }
        defaults.update(kwargs)
        return Skill(**defaults)

    def test_display_text(self):
        s = self._make_skill()
        assert "web-scraper" in s.display_text

    def test_to_retrieval_text_includes_tags(self):
        s = self._make_skill()
        text = s.to_retrieval_text()
        assert "Tags: scraping, html" in text
        assert "Categories: data, web" in text

    def test_roundtrip(self):
        original = self._make_skill(
            version="1.2.0",
            author="test-user",
            auth_required=True,
            auth_type="api_key",
            server_name="test-server",
        )
        d = original.to_dict()
        restored = Skill.from_dict(d)
        assert restored.skill_id == original.skill_id
        assert restored.name == original.name
        assert restored.categories == original.categories
        assert restored.tags == original.tags
        assert restored.version == "1.2.0"
        assert restored.auth_required is True
        assert restored.auth_type == "api_key"

    def test_estimated_tokens(self):
        s = self._make_skill()
        tokens = s.estimated_tokens()
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_to_json(self):
        import json
        s = self._make_skill()
        parsed = json.loads(s.to_json())
        assert parsed["name"] == "web-scraper"

    def test_from_dict_legacy_format(self):
        """Ensure backward compat with old JSONL records that lack new fields."""
        d = {
            "skill_id": "old_001",
            "name": "old-tool",
            "description": "An old tool",
            "source_format": "generic",
        }
        s = Skill.from_dict(d)
        assert s.tags == []
        assert s.io_schema.inputs == []
        assert s.auth_required is False


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
class TestPlan:
    def test_basic_plan(self):
        s1 = Skill(skill_id="s1", name="fetch", description="Fetch data")
        s2 = Skill(skill_id="s2", name="parse", description="Parse data")
        plan = Plan(
            query="fetch and parse data",
            steps=[
                PlanStep(step_index=0, subtask="fetch data", selected_skill=s1, confidence=0.8),
                PlanStep(step_index=1, subtask="parse data", selected_skill=s2, confidence=0.7),
            ],
            edges=[(0, 1)],
        )
        assert plan.num_steps == 2
        assert plan.skill_chain == ["fetch", "parse"]
        assert 0.7 < plan.avg_confidence < 0.8

    def test_to_dict(self):
        plan = Plan(query="test", steps=[], edges=[])
        d = plan.to_dict()
        assert d["query"] == "test"
        assert d["steps"] == []
