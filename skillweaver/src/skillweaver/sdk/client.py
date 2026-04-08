"""SkillWeaver Python SDK — programmatic access to skill routing.

Usage:
    from skillweaver.sdk.client import SkillWeaverClient

    sw = SkillWeaverClient()
    sw.load_skills_from_directory("./skills")

    # Search
    results = sw.search("web scraping")

    # Plan
    plan = sw.plan("fetch data from API, then parse it, then store in DB")

    # Filter tools for an agent
    tools = sw.filter_tools("data analysis task", max_tools=10)

For remote server mode:
    sw = SkillWeaverClient(server_url="http://localhost:8740")
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from skillweaver.config.settings import Settings, load_settings
from skillweaver.core.models import Plan, Skill, SkillMatch

logger = logging.getLogger(__name__)


class SkillWeaverClient:
    """High-level SDK client for SkillWeaver.

    Works in two modes:
        - Local mode (default): everything runs in-process
        - Remote mode: delegates to a SkillWeaver HTTP server
    """

    def __init__(
        self,
        server_url: str | None = None,
        settings: Settings | None = None,
    ):
        self._server_url = server_url
        self._settings = settings or load_settings()
        self._skills: list[Skill] = []
        self._retriever = None
        self._store = None
        self._initialized = False

    # -- Initialization ---------------------------------------------------

    def _ensure_local(self) -> None:
        """Lazy-initialize local mode components."""
        if self._initialized:
            return
        from skillweaver.core.retriever import SkillRetriever
        from skillweaver.index.store import IndexStore

        self._store = IndexStore(store_dir=Path(self._settings.store_dir))
        self._skills = self._store.load_skills()
        self._retriever = SkillRetriever(
            encoder_name=self._settings.encoder,
            top_k=self._settings.top_k,
            use_body=self._settings.use_body,
        )
        if self._skills:
            if self._store.has_index():
                self._retriever.load_index(self._store.index_dir, self._skills)
            else:
                self._retriever.build_index(self._skills)
        self._initialized = True

    # -- Skill loading ----------------------------------------------------

    def load_skills_from_directory(self, path: str | Path) -> int:
        """Scan a directory for SKILL.md files and add to index."""
        from skillweaver.adapters.skill_md import scan_directory

        skills = scan_directory(Path(path))
        return self._add_skills(skills)

    def load_skills_from_mcp_config(self, path: str | Path) -> int:
        """Parse an MCP config file and add tools to index."""
        from skillweaver.adapters.mcp import parse_mcp_config

        skills = parse_mcp_config(Path(path))
        return self._add_skills(skills)

    def load_skills_from_openai_functions(
        self,
        functions: list[dict[str, Any]],
        label: str = "openai",
    ) -> int:
        """Add OpenAI function definitions to index."""
        from skillweaver.adapters.openai_func import parse_openai_functions

        skills = parse_openai_functions(functions, source_label=label)
        return self._add_skills(skills)

    def load_skills_from_langchain_tools(
        self,
        tools: list[Any],
        label: str = "langchain",
    ) -> int:
        """Add LangChain tools to index."""
        from skillweaver.adapters.langchain import parse_langchain_tools

        skills = parse_langchain_tools(tools, source_label=label)
        return self._add_skills(skills)

    def add_skill(self, skill: Skill) -> None:
        """Add a single skill to the index."""
        self._add_skills([skill])

    def _add_skills(self, new_skills: list[Skill]) -> int:
        """Internal: merge new skills and rebuild index."""
        self._ensure_local()
        existing_ids = {s.skill_id for s in self._skills}
        unique = [s for s in new_skills if s.skill_id not in existing_ids]
        if unique:
            self._skills.extend(unique)
            self._store.save_skills(self._skills)
            self._retriever.build_index(self._skills)
            self._retriever.save_index(self._store.index_dir)
        return len(unique)

    # -- Search -----------------------------------------------------------

    def search(
        self,
        query: str,
        top_k: int | None = None,
    ) -> list[SkillMatch]:
        """Search for skills matching a query.

        Args:
            query: Natural language description.
            top_k: Max results (default from settings).

        Returns:
            List of SkillMatch with skill and score.
        """
        if self._server_url:
            return self._remote_search(query, top_k)
        self._ensure_local()
        return self._retriever.search(query, top_k=top_k or self._settings.top_k)

    # -- Plan -------------------------------------------------------------

    def plan(
        self,
        query: str,
        backend: str | None = None,
        use_dag: bool = True,
        top_k: int | None = None,
    ) -> Plan:
        """Decompose a task and compose a skill execution plan.

        Args:
            query: Complex task description.
            backend: Decomposer backend (rule, ollama, openai).
            use_dag: Use DAG planner with parallel detection.
            top_k: Candidates per step.

        Returns:
            A Plan with steps, skills, edges, and confidence scores.
        """
        if self._server_url:
            return self._remote_plan(query, backend, use_dag, top_k)
        self._ensure_local()

        from skillweaver.core.decomposer import create_decomposer
        from skillweaver.core.pipeline import SkillWeaverPipeline

        decomposer = create_decomposer(backend or self._settings.decomposer_backend)
        pipeline = SkillWeaverPipeline(
            decomposer=decomposer,
            retriever=self._retriever,
            use_dag=use_dag,
        )
        return pipeline.plan(query)

    # -- Tool filtering (for agent integration) ---------------------------

    def filter_tools(
        self,
        query: str,
        max_tools: int = 20,
        token_budget: int = 8000,
    ) -> list[dict[str, Any]]:
        """Filter tools for an agent based on current context.

        This is the programmatic equivalent of the MCP proxy's
        smart filtering.  Returns MCP-compatible tool definitions.

        Args:
            query: Current task context.
            max_tools: Max tools to return.
            token_budget: Max tokens for tool descriptions.

        Returns:
            List of tool definitions (MCP wire format).
        """
        if self._server_url:
            return self._remote_inject(query, max_tools, token_budget)
        self._ensure_local()

        from skillweaver.mcp.injector import ToolInjector

        injector = ToolInjector(max_tools=max_tools, token_budget=token_budget)
        tool_defs = [
            {"name": s.name, "description": s.description,
             "inputSchema": s.io_schema.to_dict()}
            for s in self._skills
        ]
        injector.build_index(self._skills, tool_defs)
        result = injector.select(query)
        return result.selected_tools

    # -- Properties -------------------------------------------------------

    @property
    def skills(self) -> list[Skill]:
        """All indexed skills."""
        self._ensure_local()
        return list(self._skills)

    @property
    def skill_count(self) -> int:
        self._ensure_local()
        return len(self._skills)

    # -- Remote mode helpers ----------------------------------------------

    def _remote_search(self, query: str, top_k: int | None) -> list[SkillMatch]:
        import httpx
        resp = httpx.post(
            f"{self._server_url}/search",
            json={"query": query, "top_k": top_k or 10},
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        return [
            SkillMatch(
                skill=Skill(
                    skill_id=r["skill_id"],
                    name=r["name"],
                    description=r["description"],
                ),
                score=r["score"],
            )
            for r in data["results"]
        ]

    def _remote_plan(
        self, query: str, backend: str | None, use_dag: bool, top_k: int | None,
    ) -> Plan:
        import httpx
        resp = httpx.post(
            f"{self._server_url}/plan",
            json={
                "query": query,
                "backend": backend or "rule",
                "use_dag": use_dag,
                "top_k": top_k or 10,
            },
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()
        from skillweaver.core.models import PlanStep
        steps = [
            PlanStep(
                step_index=s["step_index"],
                subtask=s["subtask"],
                selected_skill=Skill(
                    skill_id="", name=s["selected_skill"] or "", description=""
                ) if s.get("selected_skill") else None,
                confidence=s["confidence"],
                parallel_group=s.get("parallel_group"),
            )
            for s in data["steps"]
        ]
        return Plan(
            query=data["query"],
            steps=steps,
            edges=[tuple(e) for e in data["edges"]],
        )

    def _remote_inject(
        self, query: str, max_tools: int, token_budget: int,
    ) -> list[dict[str, Any]]:
        import httpx
        resp = httpx.post(
            f"{self._server_url}/inject",
            json={"query": query, "max_tools": max_tools, "token_budget": token_budget},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["selected_tools"]
