"""Tests for Hub client, publish, and SkillPack."""

from __future__ import annotations

import json

import pytest

from skillweaver.core.models import Skill
from skillweaver.hub.client import HubClient, SkillPack
from skillweaver.hub.publish import (
    create_pack_from_directory,
    create_pack_from_mcp_config,
    create_pack_from_skills,
)


def _make_skill(name: str, **kw) -> Skill:
    return Skill(skill_id=f"t_{name}", name=name, description=f"Skill: {name}", **kw)


# =========================================================================
# SkillPack
# =========================================================================
class TestSkillPack:
    def test_roundtrip_dict(self):
        pack = SkillPack(
            name="test-pack",
            version="1.0.0",
            description="A test pack",
            author="tester",
            skills=[_make_skill("a"), _make_skill("b")],
            tags=["test"],
        )
        d = pack.to_dict()
        assert d["name"] == "test-pack"
        assert len(d["skills"]) == 2
        assert d["schema_version"] == "1.0"

        restored = SkillPack.from_dict(d)
        assert restored.name == "test-pack"
        assert len(restored.skills) == 2

    def test_save_and_load(self, tmp_path):
        pack = SkillPack(
            name="persist-pack",
            version="2.0.0",
            description="Test persistence",
            author="tester",
            skills=[_make_skill("x"), _make_skill("y"), _make_skill("z")],
        )
        path = tmp_path / "persist-pack.json"
        pack.save(path)
        assert path.exists()

        loaded = SkillPack.load(path)
        assert loaded.name == "persist-pack"
        assert loaded.version == "2.0.0"
        assert len(loaded.skills) == 3


# =========================================================================
# HubClient
# =========================================================================
class TestHubClient:
    @pytest.fixture
    def hub(self, tmp_path):
        return HubClient(local_hub_dir=tmp_path / "hub")

    def test_list_empty(self, hub):
        assert hub.list_packs() == []

    def test_publish_and_list(self, hub):
        pack = SkillPack(
            name="my-pack", version="1.0.0", description="desc",
            author="me", skills=[_make_skill("s1")],
        )
        hub.publish(pack)
        packs = hub.list_packs()
        assert len(packs) == 1
        assert packs[0]["name"] == "my-pack"
        assert packs[0]["skill_count"] == 1
        assert packs[0]["source"] == "local"

    def test_install_local(self, hub):
        pack = SkillPack(
            name="installable", version="1.0.0", description="test",
            author="tester", skills=[_make_skill("t1"), _make_skill("t2")],
        )
        hub.publish(pack)
        installed = hub.install("installable")
        assert installed is not None
        assert installed.name == "installable"
        assert len(installed.skills) == 2

    def test_install_missing(self, hub):
        assert hub.install("nonexistent") is None

    def test_multiple_packs(self, hub):
        for i in range(3):
            pack = SkillPack(
                name=f"pack-{i}", version="1.0.0", description=f"Pack {i}",
                author="tester", skills=[_make_skill(f"s{i}")],
            )
            hub.publish(pack)
        assert len(hub.list_packs()) == 3


# =========================================================================
# Publish helpers
# =========================================================================
class TestPublish:
    def test_from_directory(self, tmp_path):
        # Create SKILL.md files
        for name in ["alpha", "beta"]:
            d = tmp_path / name
            d.mkdir()
            (d / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Skill {name}\n---\n# {name}\n"
            )
        pack = create_pack_from_directory(tmp_path, name="dir-pack", author="test")
        assert pack.name == "dir-pack"
        assert len(pack.skills) == 2

    def test_from_mcp_config(self, tmp_path):
        config = {
            "mcpServers": {
                "srv": {
                    "command": "echo",
                    "tools": [
                        {"name": "t1", "description": "Tool 1"},
                        {"name": "t2", "description": "Tool 2"},
                    ],
                }
            }
        }
        cfg = tmp_path / "mcp.json"
        cfg.write_text(json.dumps(config))
        pack = create_pack_from_mcp_config(cfg, name="mcp-pack")
        assert len(pack.skills) == 2

    def test_from_skills(self):
        skills = [_make_skill("a"), _make_skill("b")]
        pack = create_pack_from_skills(skills, name="manual-pack")
        assert pack.name == "manual-pack"
        assert len(pack.skills) == 2
