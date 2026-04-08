"""Tests for config/settings.py."""

from pathlib import Path

import pytest
import yaml

from skillweaver.config.settings import (
    _merge,
    load_settings,
    reset_settings_cache,
)


@pytest.fixture(autouse=True)
def _clean_cache():
    """Reset settings cache before each test."""
    reset_settings_cache()
    yield
    reset_settings_cache()


class TestDefaults:
    def test_defaults_loaded(self):
        s = load_settings(use_cache=False)
        assert s.encoder == "sentence-transformers/all-MiniLM-L6-v2"
        assert s.top_k == 10
        assert s.alpha == 0.7
        assert s.proxy_port == 5173
        assert s.decomposer_backend == "rule"

    def test_store_path(self):
        s = load_settings(use_cache=False)
        assert isinstance(s.store_path, Path)


class TestOverrides:
    def test_explicit_overrides(self):
        s = load_settings(overrides={"top_k": 20, "alpha": 0.5}, use_cache=False)
        assert s.top_k == 20
        assert s.alpha == 0.5

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("SKILLWEAVER_TOP_K", "50")
        monkeypatch.setenv("SKILLWEAVER_ALPHA", "0.3")
        monkeypatch.setenv("SKILLWEAVER_USE_BODY", "true")
        s = load_settings(use_cache=False)
        assert s.top_k == 50
        assert s.alpha == 0.3
        assert s.use_body is True


class TestProjectConfig:
    def test_project_config_file(self, tmp_path):
        cfg = tmp_path / ".skillweaver.yaml"
        cfg.write_text(yaml.dump({"top_k": 42, "encoder": "custom/model"}))
        s = load_settings(project_dir=tmp_path, use_cache=False)
        assert s.top_k == 42
        assert s.encoder == "custom/model"

    def test_override_beats_project_config(self, tmp_path):
        cfg = tmp_path / ".skillweaver.yaml"
        cfg.write_text(yaml.dump({"top_k": 42}))
        s = load_settings(
            project_dir=tmp_path,
            overrides={"top_k": 99},
            use_cache=False,
        )
        assert s.top_k == 99


class TestMerge:
    def test_merge_skips_none(self):
        base = {"a": 1, "b": 2}
        patch = {"a": None, "b": 3}
        assert _merge(base, patch) == {"a": 1, "b": 3}


class TestCache:
    def test_cache_returns_same_object(self):
        s1 = load_settings(use_cache=True)
        s2 = load_settings(use_cache=True)
        assert s1 is s2

    def test_overrides_bypass_cache(self):
        s1 = load_settings(use_cache=True)
        s2 = load_settings(overrides={"top_k": 77}, use_cache=True)
        assert s1.top_k != 77
        assert s2.top_k == 77
