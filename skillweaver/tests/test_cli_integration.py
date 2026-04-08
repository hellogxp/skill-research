"""Integration tests for CLI commands using Click's CliRunner."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from click.testing import CliRunner

from skillweaver.cli.main import cli


@pytest.fixture
def runner():
    return CliRunner()


@pytest.fixture
def skill_dir(tmp_path):
    """Create a minimal skill directory for testing."""
    d = tmp_path / "skills" / "test-skill"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        "---\nname: test-skill\ndescription: A test skill\n"
        "categories:\n  - testing\n---\n# Test Skill\nDoes testing.\n"
    )
    d2 = tmp_path / "skills" / "another-skill"
    d2.mkdir(parents=True)
    (d2 / "SKILL.md").write_text(
        "---\nname: another-skill\ndescription: Another test skill\n"
        "categories:\n  - testing\n---\n# Another Skill\nDoes more testing.\n"
    )
    return tmp_path / "skills"


class TestInitCommand:
    def test_init_success(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_STORE_DIR", str(tmp_path / "store"))
        result = runner.invoke(cli, ["init"])
        assert result.exit_code == 0
        assert "initialized" in result.output.lower() or "SkillWeaver" in result.output


class TestIndexCommand:
    @patch("skillweaver.cli.main._rebuild_faiss_index")
    def test_index_skill_md(self, mock_rebuild, runner, skill_dir, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_STORE_DIR", str(tmp_path / "store"))
        (tmp_path / "store").mkdir(parents=True, exist_ok=True)
        result = runner.invoke(cli, ["index", str(skill_dir)])
        assert result.exit_code == 0
        assert "2 new skills" in result.output or "Indexed" in result.output

    @patch("skillweaver.cli.main._rebuild_faiss_index")
    def test_index_no_skills(self, mock_rebuild, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_STORE_DIR", str(tmp_path / "store"))
        (tmp_path / "store").mkdir(parents=True, exist_ok=True)
        empty = tmp_path / "empty"
        empty.mkdir()
        result = runner.invoke(cli, ["index", str(empty)])
        assert result.exit_code == 0
        assert "No skills found" in result.output


class TestStatusCommand:
    def test_status_shows_table(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_STORE_DIR", str(tmp_path / "store"))
        (tmp_path / "store").mkdir(parents=True, exist_ok=True)
        result = runner.invoke(cli, ["status"])
        assert result.exit_code == 0
        assert "SkillWeaver Index Status" in result.output


class TestVersionFlag:
    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output


class TestSearchCommand:
    def test_search_no_index(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_STORE_DIR", str(tmp_path / "store"))
        (tmp_path / "store").mkdir(parents=True, exist_ok=True)
        result = runner.invoke(cli, ["search", "test query"])
        assert result.exit_code != 0 or "No skills indexed" in result.output


class TestPlanCommand:
    def test_plan_no_index(self, runner, tmp_path, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_STORE_DIR", str(tmp_path / "store"))
        (tmp_path / "store").mkdir(parents=True, exist_ok=True)
        result = runner.invoke(cli, ["plan", "do something complex"])
        assert result.exit_code != 0 or "No skills indexed" in result.output
