"""SkillWeaver configuration management.

Supports layered configuration:
  1. Built-in defaults
  2. Project-level  .skillweaver.yaml / skillweaver.yaml
  3. User-level     ~/.skillweaver/config.yaml
  4. Environment    SKILLWEAVER_*  (uppercase, underscores replace dots)
  5. CLI flags      (highest priority, handled at call-site)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default values
# ---------------------------------------------------------------------------
_DEFAULTS: dict[str, Any] = {
    # Core engine
    "encoder": "sentence-transformers/all-MiniLM-L6-v2",
    "encoder_fallback": "sentence-transformers/all-MiniLM-L6-v2",
    "top_k": 10,
    "use_body": False,
    "alpha": 0.7,  # retrieval vs compatibility weight

    # Decomposer
    "decomposer_backend": "rule",
    "decomposer_model": None,
    "decomposer_base_url": None,
    "decomposer_api_key": None,

    # Store
    "store_dir": str(Path.home() / ".skillweaver"),

    # MCP proxy
    "proxy_host": "127.0.0.1",
    "proxy_port": 5173,
    "proxy_max_tools": 20,

    # Server (FastAPI)
    "server_host": "0.0.0.0",
    "server_port": 8740,

    # HuggingFace
    "hf_endpoint": None,   # auto-detect if None
    "hf_mirrors": ["https://hf-mirror.com"],

    # Logging
    "log_level": "WARNING",
}

# Config file search paths (project → user)
_CONFIG_FILENAMES = [
    ".skillweaver.yaml",
    "skillweaver.yaml",
]
_USER_CONFIG = Path.home() / ".skillweaver" / "config.yaml"


# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------
@dataclass
class Settings:
    """Immutable snapshot of resolved configuration."""

    # Core engine
    encoder: str = _DEFAULTS["encoder"]
    encoder_fallback: str = _DEFAULTS["encoder_fallback"]
    top_k: int = _DEFAULTS["top_k"]
    use_body: bool = _DEFAULTS["use_body"]
    alpha: float = _DEFAULTS["alpha"]

    # Decomposer
    decomposer_backend: str = _DEFAULTS["decomposer_backend"]
    decomposer_model: str | None = _DEFAULTS["decomposer_model"]
    decomposer_base_url: str | None = _DEFAULTS["decomposer_base_url"]
    decomposer_api_key: str | None = _DEFAULTS["decomposer_api_key"]

    # Store
    store_dir: str = _DEFAULTS["store_dir"]

    # MCP proxy
    proxy_host: str = _DEFAULTS["proxy_host"]
    proxy_port: int = _DEFAULTS["proxy_port"]
    proxy_max_tools: int = _DEFAULTS["proxy_max_tools"]

    # Server
    server_host: str = _DEFAULTS["server_host"]
    server_port: int = _DEFAULTS["server_port"]

    # HuggingFace
    hf_endpoint: str | None = _DEFAULTS["hf_endpoint"]
    hf_mirrors: list[str] = field(default_factory=lambda: list(_DEFAULTS["hf_mirrors"]))

    # Logging
    log_level: str = _DEFAULTS["log_level"]

    @property
    def store_path(self) -> Path:
        return Path(self.store_dir)


# ---------------------------------------------------------------------------
# Loading helpers
# ---------------------------------------------------------------------------
def _find_project_config(start: Path | None = None) -> Path | None:
    """Walk upward from *start* looking for a project config file."""
    cwd = start or Path.cwd()
    for d in [cwd, *cwd.parents]:
        for name in _CONFIG_FILENAMES:
            candidate = d / name
            if candidate.is_file():
                return candidate
    return None


def _load_yaml(path: Path) -> dict[str, Any]:
    """Load a YAML file; return empty dict on failure."""
    try:
        with open(path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception as exc:
        logger.debug("Failed to read config %s: %s", path, exc)
        return {}


def _env_overrides() -> dict[str, Any]:
    """Read SKILLWEAVER_* environment variables."""
    prefix = "SKILLWEAVER_"
    overrides: dict[str, Any] = {}
    for key, val in os.environ.items():
        if key.startswith(prefix):
            setting_key = key[len(prefix):].lower()
            if setting_key in _DEFAULTS:
                # Coerce to the same type as the default
                default = _DEFAULTS[setting_key]
                if isinstance(default, bool):
                    overrides[setting_key] = val.lower() in ("1", "true", "yes")
                elif isinstance(default, int):
                    try:
                        overrides[setting_key] = int(val)
                    except ValueError:
                        pass
                elif isinstance(default, float):
                    try:
                        overrides[setting_key] = float(val)
                    except ValueError:
                        pass
                else:
                    overrides[setting_key] = val
    return overrides


def _merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    """Shallow merge *patch* onto *base*, skipping None values in patch."""
    merged = dict(base)
    for k, v in patch.items():
        if v is not None:
            merged[k] = v
    return merged


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
_cached_settings: Settings | None = None


def load_settings(
    project_dir: Path | None = None,
    overrides: dict[str, Any] | None = None,
    *,
    use_cache: bool = True,
) -> Settings:
    """Load settings from all config layers.

    Resolution order (later wins):
        defaults → user config → project config → env vars → explicit overrides
    """
    global _cached_settings
    if use_cache and _cached_settings is not None and overrides is None:
        return _cached_settings

    resolved = dict(_DEFAULTS)

    # Layer 2: user config
    if _USER_CONFIG.is_file():
        resolved = _merge(resolved, _load_yaml(_USER_CONFIG))

    # Layer 3: project config
    proj_cfg = _find_project_config(project_dir)
    if proj_cfg:
        resolved = _merge(resolved, _load_yaml(proj_cfg))
        logger.debug("Loaded project config: %s", proj_cfg)

    # Layer 4: environment
    resolved = _merge(resolved, _env_overrides())

    # Layer 5: explicit overrides
    if overrides:
        resolved = _merge(resolved, overrides)

    settings = Settings(**{k: resolved[k] for k in Settings.__dataclass_fields__})

    if use_cache and overrides is None:
        _cached_settings = settings
    return settings


def reset_settings_cache() -> None:
    """Clear cached settings (useful for testing)."""
    global _cached_settings
    _cached_settings = None
