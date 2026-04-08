"""Local index store for SkillWeaver.

Manages the persistent skill index at ~/.skillweaver/
Uses JSONL for skill metadata and FAISS for vector search.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from skillweaver.core.models import Skill

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
        """Save skills to JSONL file using Skill.to_dict()."""
        self.ensure_dir()
        with open(self.skills_file, "w") as f:
            for s in skills:
                f.write(json.dumps(s.to_dict(), ensure_ascii=False) + "\n")
        logger.info(f"Saved {len(skills)} skills to {self.skills_file}")

    def load_skills(self) -> list[Skill]:
        """Load skills from JSONL file using Skill.from_dict()."""
        if not self.skills_file.exists():
            return []
        skills = []
        with open(self.skills_file) as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    d = json.loads(line)
                    skills.append(Skill.from_dict(d))
                except (json.JSONDecodeError, KeyError) as e:
                    logger.warning("Skipping malformed line %d: %s", line_num, e)
        logger.info(f"Loaded {len(skills)} skills from index")
        return skills

    def has_index(self) -> bool:
        """Check if a FAISS index exists."""
        return (self.index_dir / "index.faiss").exists()

    def remove_skill(self, skill_id: str) -> bool:
        """Remove a skill by ID. Returns True if found and removed."""
        skills = self.load_skills()
        before = len(skills)
        skills = [s for s in skills if s.skill_id != skill_id]
        if len(skills) < before:
            self.save_skills(skills)
            return True
        return False

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
