"""SkillWeaver core data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class SkillFormat(str, Enum):
    """Supported skill specification formats."""

    SKILL_MD = "skill_md"  # Anthropic SKILL.md
    MCP = "mcp"  # Model Context Protocol
    OPENAI_FUNC = "openai_func"  # OpenAI function calling
    LANGCHAIN = "langchain"  # LangChain tool
    GENERIC = "generic"  # Generic key-value


@dataclass
class Skill:
    """A unified skill representation, regardless of source format."""

    skill_id: str
    name: str
    description: str
    body: str = ""
    categories: list[str] = field(default_factory=list)
    source_format: SkillFormat = SkillFormat.GENERIC
    source_path: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def display_text(self) -> str:
        """Short display string for CLI output."""
        return f"{self.name}: {self.description[:80]}"

    def to_retrieval_text(self, use_body: bool = False) -> str:
        """Text representation for embedding and retrieval."""
        text = f"{self.name}\n{self.description}"
        if use_body and self.body:
            text += f"\n{self.body[:2000]}"
        return text


@dataclass
class SubTask:
    """A single atomic sub-task from query decomposition."""

    step_index: int
    description: str


@dataclass
class SkillMatch:
    """A skill matched to a sub-task, with score."""

    skill: Skill
    score: float


@dataclass
class PlanStep:
    """One step in an execution plan."""

    step_index: int
    subtask: str
    selected_skill: Skill | None = None
    candidates: list[SkillMatch] = field(default_factory=list)
    confidence: float = 0.0


@dataclass
class Plan:
    """A complete execution plan: decomposition + skill assignments + DAG."""

    query: str
    steps: list[PlanStep] = field(default_factory=list)
    edges: list[tuple[int, int]] = field(default_factory=list)  # (from_step, to_step)

    @property
    def num_steps(self) -> int:
        return len(self.steps)

    @property
    def skill_chain(self) -> list[str]:
        """Names of selected skills in order."""
        return [s.selected_skill.name for s in self.steps if s.selected_skill]

    @property
    def avg_confidence(self) -> float:
        if not self.steps:
            return 0.0
        return sum(s.confidence for s in self.steps) / len(self.steps)
