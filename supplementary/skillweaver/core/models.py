"""SkillWeaver core data models.

Defines the universal Skill representation and execution-plan data structures.
Designed to unify skills from MCP, SKILL.md, OpenAI functions, LangChain tools,
and any other format into a single interoperable model.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class SkillFormat(str, Enum):
    """Supported skill specification formats."""

    SKILL_MD = "skill_md"       # Anthropic SKILL.md
    MCP = "mcp"                 # Model Context Protocol
    OPENAI_FUNC = "openai_func" # OpenAI function calling
    LANGCHAIN = "langchain"     # LangChain tool
    GENERIC = "generic"         # Generic key-value


class ParamType(str, Enum):
    """Canonical parameter types for I/O schema."""

    STRING = "string"
    INTEGER = "integer"
    NUMBER = "number"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"
    FILE = "file"
    IMAGE = "image"
    ANY = "any"


# ---------------------------------------------------------------------------
# I/O Schema
# ---------------------------------------------------------------------------
@dataclass
class ParamSchema:
    """Schema for a single input or output parameter."""

    name: str
    param_type: ParamType = ParamType.STRING
    description: str = ""
    required: bool = False
    default: Any = None
    enum: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "type": self.param_type.value,
        }
        if self.description:
            d["description"] = self.description
        if self.required:
            d["required"] = True
        if self.default is not None:
            d["default"] = self.default
        if self.enum:
            d["enum"] = self.enum
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ParamSchema":
        return cls(
            name=d["name"],
            param_type=ParamType(d.get("type", "string")),
            description=d.get("description", ""),
            required=d.get("required", False),
            default=d.get("default"),
            enum=d.get("enum"),
        )


@dataclass
class IOSchema:
    """Input/output schema for a skill — enables compositional type checking."""

    inputs: list[ParamSchema] = field(default_factory=list)
    outputs: list[ParamSchema] = field(default_factory=list)

    @property
    def input_types(self) -> set[ParamType]:
        return {p.param_type for p in self.inputs}

    @property
    def output_types(self) -> set[ParamType]:
        return {p.param_type for p in self.outputs}

    def to_dict(self) -> dict[str, Any]:
        return {
            "inputs": [p.to_dict() for p in self.inputs],
            "outputs": [p.to_dict() for p in self.outputs],
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "IOSchema":
        return cls(
            inputs=[ParamSchema.from_dict(p) for p in d.get("inputs", [])],
            outputs=[ParamSchema.from_dict(p) for p in d.get("outputs", [])],
        )

    @classmethod
    def from_json_schema(cls, schema: dict[str, Any]) -> "IOSchema":
        """Convert a JSON Schema (e.g. MCP inputSchema) to IOSchema."""
        inputs: list[ParamSchema] = []
        props = schema.get("properties", {})
        required_set = set(schema.get("required", []))
        for name, prop in props.items():
            raw_type = prop.get("type", "string")
            try:
                ptype = ParamType(raw_type)
            except ValueError:
                ptype = ParamType.ANY
            inputs.append(ParamSchema(
                name=name,
                param_type=ptype,
                description=prop.get("description", ""),
                required=name in required_set,
                default=prop.get("default"),
                enum=prop.get("enum"),
            ))
        return cls(inputs=inputs)


# ---------------------------------------------------------------------------
# Skill
# ---------------------------------------------------------------------------
@dataclass
class Skill:
    """A unified skill representation, regardless of source format.

    This is the central data model of SkillWeaver.  Every adapter converts
    its native format (MCP tool, SKILL.md, OpenAI function, etc.) into this
    structure so that retrieval, compatibility scoring and planning all work
    the same way.
    """

    skill_id: str
    name: str
    description: str
    body: str = ""
    categories: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    source_format: SkillFormat = SkillFormat.GENERIC
    source_path: str = ""
    version: str = ""
    author: str = ""
    io_schema: IOSchema = field(default_factory=IOSchema)
    auth_required: bool = False
    auth_type: str = ""            # "oauth2", "api_key", "bearer", ""
    server_name: str = ""          # originating MCP server / adapter name
    metadata: dict[str, Any] = field(default_factory=dict)

    # -- Display helpers --------------------------------------------------

    @property
    def display_text(self) -> str:
        """Short display string for CLI output."""
        return f"{self.name}: {self.description[:80]}"

    def to_retrieval_text(self, use_body: bool = False) -> str:
        """Text representation for embedding and retrieval.

        Includes tags for better semantic matching.
        """
        parts = [self.name, self.description]
        if self.tags:
            parts.append("Tags: " + ", ".join(self.tags))
        if self.categories:
            parts.append("Categories: " + ", ".join(self.categories))
        if use_body and self.body:
            parts.append(self.body[:2000])
        return "\n".join(parts)

    # -- Serialization ----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a plain dict (suitable for JSON/JSONL)."""
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "body": self.body,
            "categories": self.categories,
            "tags": self.tags,
            "source_format": self.source_format.value,
            "source_path": self.source_path,
            "version": self.version,
            "author": self.author,
            "io_schema": self.io_schema.to_dict(),
            "auth_required": self.auth_required,
            "auth_type": self.auth_type,
            "server_name": self.server_name,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Skill":
        """Deserialize from a plain dict."""
        io_raw = d.get("io_schema")
        io_schema = IOSchema.from_dict(io_raw) if io_raw else IOSchema()
        return cls(
            skill_id=d["skill_id"],
            name=d["name"],
            description=d.get("description", ""),
            body=d.get("body", ""),
            categories=d.get("categories", []),
            tags=d.get("tags", []),
            source_format=SkillFormat(d.get("source_format", "generic")),
            source_path=d.get("source_path", ""),
            version=d.get("version", ""),
            author=d.get("author", ""),
            io_schema=io_schema,
            auth_required=d.get("auth_required", False),
            auth_type=d.get("auth_type", ""),
            server_name=d.get("server_name", ""),
            metadata=d.get("metadata", {}),
        )

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    # -- Token estimation (for context-window budgeting) ------------------

    def estimated_tokens(self) -> int:
        """Rough token estimate for this skill's description in an LLM context.

        Uses the ~4-chars-per-token heuristic.  Useful for the MCP proxy to
        decide how many tools to inject.
        """
        text = f"Tool: {self.name}\nDescription: {self.description}"
        if self.io_schema.inputs:
            text += "\nParameters:\n"
            for p in self.io_schema.inputs:
                text += f"  - {p.name} ({p.param_type.value}): {p.description}\n"
        return len(text) // 4


# ---------------------------------------------------------------------------
# Sub-task / Plan data structures
# ---------------------------------------------------------------------------
@dataclass
class SubTask:
    """A single atomic sub-task from query decomposition."""

    step_index: int
    description: str
    required_input_types: set[ParamType] = field(default_factory=set)
    expected_output_types: set[ParamType] = field(default_factory=set)


@dataclass
class SkillMatch:
    """A skill matched to a sub-task, with score."""

    skill: Skill
    score: float
    compatibility_score: float = 0.0  # set by planner


@dataclass
class PlanStep:
    """One step in an execution plan."""

    step_index: int
    subtask: str
    selected_skill: Skill | None = None
    candidates: list[SkillMatch] = field(default_factory=list)
    confidence: float = 0.0
    parallel_group: int | None = None  # steps in the same group can run in parallel


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "steps": [
                {
                    "step_index": s.step_index,
                    "subtask": s.subtask,
                    "selected_skill": s.selected_skill.name if s.selected_skill else None,
                    "confidence": round(s.confidence, 4),
                    "parallel_group": s.parallel_group,
                    "num_candidates": len(s.candidates),
                }
                for s in self.steps
            ],
            "edges": self.edges,
            "avg_confidence": round(self.avg_confidence, 4),
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)
