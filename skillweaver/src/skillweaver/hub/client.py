"""Hub client — discover, download, and publish shared skill packs.

The Hub is a lightweight registry where the community can share
curated collections of skills ("skill packs").  Each pack is a
JSON manifest with skill definitions, metadata, and version info.

Hub modes:
    1. Local file hub  — a directory of .json pack files (for testing / air-gapped)
    2. Remote HTTP hub — a hosted registry API (future: hub.skillweaver.dev)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from skillweaver.core.models import Skill

logger = logging.getLogger(__name__)

PACK_SCHEMA_VERSION = "1.0"


@dataclass
class SkillPack:
    """A shareable collection of skills with metadata."""
    name: str
    version: str
    description: str
    author: str
    skills: list[Skill]
    tags: list[str] = field(default_factory=list)
    homepage: str = ""
    license: str = "Apache-2.0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": PACK_SCHEMA_VERSION,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "homepage": self.homepage,
            "license": self.license,
            "skills": [s.to_dict() for s in self.skills],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "SkillPack":
        return cls(
            name=d["name"],
            version=d.get("version", "0.0.0"),
            description=d.get("description", ""),
            author=d.get("author", ""),
            tags=d.get("tags", []),
            homepage=d.get("homepage", ""),
            license=d.get("license", "Apache-2.0"),
            skills=[Skill.from_dict(s) for s in d.get("skills", [])],
        )

    def save(self, path: Path) -> None:
        """Save pack to a JSON file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)
        logger.info("Saved pack '%s' v%s (%d skills) to %s",
                     self.name, self.version, len(self.skills), path)

    @classmethod
    def load(cls, path: Path) -> "SkillPack":
        """Load pack from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return cls.from_dict(data)


class HubClient:
    """Client for discovering and installing skill packs.

    Supports local file-based hub and remote HTTP hub.
    """

    def __init__(
        self,
        local_hub_dir: Path | None = None,
        remote_url: str | None = None,
    ):
        self._local_dir = local_hub_dir or (Path.home() / ".skillweaver" / "hub")
        self._remote_url = remote_url
        self._local_dir.mkdir(parents=True, exist_ok=True)

    def list_packs(self) -> list[dict[str, Any]]:
        """List all available packs."""
        packs = []
        # Local packs
        for p in sorted(self._local_dir.glob("*.json")):
            try:
                pack = SkillPack.load(p)
                packs.append({
                    "name": pack.name,
                    "version": pack.version,
                    "description": pack.description,
                    "author": pack.author,
                    "skill_count": len(pack.skills),
                    "source": "local",
                    "path": str(p),
                })
            except Exception as e:
                logger.warning("Skipping invalid pack %s: %s", p, e)

        # Remote packs (if configured)
        if self._remote_url:
            try:
                remote_packs = self._fetch_remote_list()
                packs.extend(remote_packs)
            except Exception as e:
                logger.warning("Failed to fetch remote packs: %s", e)

        return packs

    def install(self, pack_name: str) -> SkillPack | None:
        """Install a pack by name.

        First checks local, then remote.  Returns the pack or None.
        """
        # Check local
        local_path = self._local_dir / f"{pack_name}.json"
        if local_path.exists():
            return SkillPack.load(local_path)

        # Try remote
        if self._remote_url:
            return self._fetch_remote_pack(pack_name)

        return None

    def publish(self, pack: SkillPack) -> Path:
        """Publish a pack to the local hub directory.

        For remote publishing, use the web interface (future).
        """
        path = self._local_dir / f"{pack.name}.json"
        pack.save(path)
        return path

    def _fetch_remote_list(self) -> list[dict[str, Any]]:
        """Fetch pack list from remote hub."""
        import httpx
        resp = httpx.get(f"{self._remote_url}/packs", timeout=10)
        resp.raise_for_status()
        return resp.json().get("packs", [])

    def _fetch_remote_pack(self, name: str) -> SkillPack | None:
        """Download and cache a remote pack."""
        import httpx
        try:
            resp = httpx.get(f"{self._remote_url}/packs/{name}", timeout=30)
            resp.raise_for_status()
            data = resp.json()
            pack = SkillPack.from_dict(data)
            # Cache locally
            pack.save(self._local_dir / f"{name}.json")
            return pack
        except Exception as e:
            logger.error("Failed to download pack '%s': %s", name, e)
            return None
