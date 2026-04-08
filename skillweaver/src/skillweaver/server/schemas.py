"""Pydantic models for the SkillWeaver HTTP API.

Defines request/response schemas for all API endpoints.
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------
class SearchRequest(BaseModel):
    query: str = Field(..., description="Natural language query")
    top_k: int = Field(10, ge=1, le=100, description="Max results to return")
    category: Optional[str] = Field(None, description="Filter by category")


class SkillResult(BaseModel):
    skill_id: str
    name: str
    description: str
    score: float
    categories: list[str] = []
    tags: list[str] = []
    source_format: str = "generic"
    server_name: str = ""
    estimated_tokens: int = 0


class SearchResponse(BaseModel):
    query: str
    results: list[SkillResult]
    total_indexed: int


# ---------------------------------------------------------------------------
# Plan
# ---------------------------------------------------------------------------
class PlanRequest(BaseModel):
    query: str = Field(..., description="Complex task to decompose and plan")
    top_k: int = Field(10, ge=1, le=100, description="Candidates per step")
    backend: str = Field("rule", description="Decomposer backend: rule, ollama, openai")
    use_dag: bool = Field(True, description="Use DAG planner with parallel detection")
    model: Optional[str] = Field(None, description="LLM model name for decomposition")
    sad: bool = Field(False, description="Enable Skill-Aware Decomposition (two-pass feedback)")
    sad_hint_count: int = Field(15, ge=1, le=100, description="Number of skill-name hints for SAD")


class PlanStepResult(BaseModel):
    step_index: int
    subtask: str
    selected_skill: Optional[str] = None
    confidence: float = 0.0
    parallel_group: Optional[int] = None
    num_candidates: int = 0


class PlanResponse(BaseModel):
    query: str
    steps: list[PlanStepResult]
    edges: list[list[int]]
    avg_confidence: float
    num_steps: int


# ---------------------------------------------------------------------------
# Inject (for MCP proxy / tool filtering)
# ---------------------------------------------------------------------------
class InjectRequest(BaseModel):
    query: str = Field(..., description="Current task context for tool filtering")
    max_tools: int = Field(20, ge=1, le=200)
    token_budget: int = Field(8000, ge=100, le=100000)


class InjectResponse(BaseModel):
    selected_tools: list[dict[str, Any]]
    total_available: int
    token_estimate: int
    query_used: str


# ---------------------------------------------------------------------------
# Index management
# ---------------------------------------------------------------------------
class IndexStatusResponse(BaseModel):
    total_skills: int
    has_faiss_index: bool
    store_dir: str
    format_counts: dict[str, int]


class SkillAddRequest(BaseModel):
    skills: list[dict[str, Any]] = Field(..., description="List of skill dicts to add")
    rebuild_index: bool = Field(True, description="Rebuild FAISS index after adding")


class SkillAddResponse(BaseModel):
    added: int
    duplicates_skipped: int
    total: int


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    total_skills: int
    has_index: bool
