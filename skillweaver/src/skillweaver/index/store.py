"""Local index store for SkillWeaver.

Manages the persistent skill index at ~/.skillweaver/
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from skillweaver.core.models import Skill, SkillFormat

logger = logging.getLogger(__name__)

DEFAULT_STORE_DIR = Path.home() / ".skillweaver"


class IndexStore:
    """Manages persistent skill storage and FAISS index."""

    def __init__(self, store_dir: Path | None = None):
        self.store_dir = store_dir or DEFAULT_STORE_DIR
        self.skills_file = self.store_dir / "skills.jsonl"
        self.index_dir = self.store_dir / "faiss_index"

    def ensure_dir(self):
        self.store_dir.mkdir(parents=True, exist_ok=True)

    def save_skills(self, skills: list[Skill]) -> None:
        """Save skills to JSONL file."""
        self.ensure_dir()
        with open(self.skills_file, "w") as f:
            for s in skills:
                record = {
                    "skill_id": s.skill_id,
                    "name": s.name,
                    "description": s.description,
                    "body": s.body,
                    "categories": s.categories,
                    "source_format": s.source_format.value,
                    "source_path": s.source_path,
                }
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(skills)} skills to {self.skills_file}")

    def load_skills(self) -> list[Skill]:
        """Load skills from JSONL file."""
        if not self.skills_file.exists():
            return []
        skills = []
        with open(self.skills_file) as f:
            for line in f:
                d = json.loads(line)
                skills.append(Skill(
                    skill_id=d["skill_id"],
                    name=d["name"],
                    description=d.get("description", ""),
                    body=d.get("body", ""),
                    categories=d.get("categories", []),
                    source_format=SkillFormat(d.get("source_format", "generic")),
                    source_path=d.get("source_path", ""),
                ))
        logger.info(f"Loaded {len(skills)} skills from index")
        return skills

    def has_index(self) -> bool:
        """Check if a FAISS index exists."""
        return (self.index_dir / "index.faiss").exists()

    def status(self) -> dict:
        """Return index status info."""
        skills = self.load_skills()
        format_counts: dict[str, int] = {}
        for s in skills:
            fmt = s.source_format.value
            format_counts[fmt] = format_counts.get(fmt, 0) + 1

        return {
            "total_skills": len(skills),
            "has_faiss_index": self.has_index(),
            "store_dir": str(self.store_dir),
            "format_counts": format_counts,
        }
