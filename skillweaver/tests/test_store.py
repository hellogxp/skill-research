"""Tests for IndexStore with the enriched Skill model."""

import json

import pytest

from skillweaver.core.models import IOSchema, ParamSchema, ParamType, Skill, SkillFormat
from skillweaver.index.store import IndexStore


@pytest.fixture
def store(tmp_path):
    return IndexStore(store_dir=tmp_path / ".skillweaver")


def _make_skill(name: str, **kwargs) -> Skill:
    defaults = dict(
        skill_id=f"test_{name}",
        name=name,
        description=f"Skill: {name}",
        categories=["test"],
        tags=["unit-test"],
        version="1.0",
        author="tester",
        io_schema=IOSchema(
            inputs=[ParamSchema(name="input", param_type=ParamType.STRING)],
            outputs=[ParamSchema(name="output", param_type=ParamType.STRING)],
        ),
    )
    defaults.update(kwargs)
    return Skill(**defaults)


class TestIndexStore:
    def test_save_and_load_roundtrip(self, store):
        skills = [_make_skill("alpha"), _make_skill("beta")]
        store.save_skills(skills)
        loaded = store.load_skills()
        assert len(loaded) == 2
        assert loaded[0].name == "alpha"
        assert loaded[0].tags == ["unit-test"]
        assert loaded[0].version == "1.0"
        assert len(loaded[0].io_schema.inputs) == 1

    def test_load_empty(self, store):
        assert store.load_skills() == []

    def test_status(self, store):
        store.save_skills([_make_skill("s1", source_format=SkillFormat.MCP)])
        info = store.status()
        assert info["total_skills"] == 1
        assert info["format_counts"]["mcp"] == 1
        assert info["has_faiss_index"] is False

    def test_remove_skill(self, store):
        skills = [_make_skill("a"), _make_skill("b"), _make_skill("c")]
        store.save_skills(skills)
        assert store.remove_skill("test_b") is True
        remaining = store.load_skills()
        assert len(remaining) == 2
        assert all(s.skill_id != "test_b" for s in remaining)

    def test_remove_nonexistent(self, store):
        store.save_skills([_make_skill("x")])
        assert store.remove_skill("test_zzz") is False

    def test_malformed_line_skipped(self, store):
        """Malformed JSONL lines should be skipped without crashing."""
        store.ensure_dir()
        with open(store.skills_file, "w") as f:
            f.write(json.dumps(_make_skill("good").to_dict()) + "\n")
            f.write("THIS IS NOT JSON\n")
            f.write(json.dumps(_make_skill("also_good").to_dict()) + "\n")
        loaded = store.load_skills()
        assert len(loaded) == 2
