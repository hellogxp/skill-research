"""Context-aware tool injector — the brain of the MCP proxy.

Given a user query / conversation context and the full tool registry,
the Injector decides which subset of tools to expose to the agent.

This is where SkillWeaver's core academic contribution (compositional
skill routing) meets the product (MCP gateway).

Filtering pipeline:
    1. Semantic retrieval  — embed query, FAISS search over tool descriptions
    2. Token budget        — respect max_tools and token_budget constraints
    3. Mandatory tools     — always include pinned / recently-used tools
    4. Diversity boost     — ensure coverage across different servers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from skillweaver.core.models import Skill
from skillweaver.core.retriever import SkillRetriever

logger = logging.getLogger(__name__)

# Default token budget — a rough limit on how many tokens the tool
# descriptions should consume in the agent's context window.
DEFAULT_TOKEN_BUDGET = 8000   # ~20 tools × 400 tokens each
DEFAULT_MAX_TOOLS = 20


@dataclass
class InjectionResult:
    """Result of a tool injection decision."""
    selected_tools: list[dict[str, Any]]   # MCP wire-format tool defs
    selected_skills: list[Skill]           # Corresponding Skill objects
    total_available: int                   # How many tools existed in registry
    token_estimate: int                    # Estimated tokens consumed
    query_used: str                        # The query/context used for filtering


class ToolInjector:
    """Decides which tools to inject into the agent's context.

    Uses the SkillRetriever for semantic matching and applies budget
    constraints to keep the context window under control.
    """

    def __init__(
        self,
        max_tools: int = DEFAULT_MAX_TOOLS,
        token_budget: int = DEFAULT_TOKEN_BUDGET,
        mandatory_tools: list[str] | None = None,
    ):
        self.max_tools = max_tools
        self.token_budget = token_budget
        self.mandatory_tools = set(mandatory_tools or [])
        self._retriever: SkillRetriever | None = None
        self._all_skills: list[Skill] = []
        self._skill_to_tool_def: dict[str, dict[str, Any]] = {}

    def build_index(
        self,
        skills: list[Skill],
        tool_defs: list[dict[str, Any]],
    ) -> None:
        """Build the retrieval index from skills + their MCP wire defs.

        Args:
            skills: Unified Skill objects from the registry.
            tool_defs: Corresponding MCP tool definitions (same order).
        """
        self._all_skills = skills
        self._skill_to_tool_def = {
            s.skill_id: td for s, td in zip(skills, tool_defs)
        }
        self._retriever = SkillRetriever(top_k=self.max_tools * 2)
        self._retriever.build_index(skills)
        logger.info("Injector index built: %d tools", len(skills))

    def select(
        self,
        query: str,
        max_tools: int | None = None,
        token_budget: int | None = None,
    ) -> InjectionResult:
        """Select the best tools for a given query/context.

        Args:
            query: The user's message or task description.
            max_tools: Override default max_tools.
            token_budget: Override default token_budget.

        Returns:
            InjectionResult with the filtered tool list.
        """
        if not self._retriever or not self._all_skills:
            # No index — return everything (fallback)
            return InjectionResult(
                selected_tools=[],
                selected_skills=[],
                total_available=0,
                token_estimate=0,
                query_used=query,
            )

        limit = max_tools or self.max_tools
        budget = token_budget or self.token_budget

        # Step 1: Semantic retrieval
        candidates = self._retriever.search(query, top_k=limit * 2)

        # Step 2: Start with mandatory tools
        selected_ids: list[str] = []
        selected_skills: list[Skill] = []
        selected_defs: list[dict[str, Any]] = []
        token_count = 0

        # Add mandatory tools first
        for skill in self._all_skills:
            bare_name = skill.metadata.get("tool", skill.name)
            if bare_name in self.mandatory_tools or skill.name in self.mandatory_tools:
                tool_def = self._skill_to_tool_def.get(skill.skill_id)
                if tool_def and skill.skill_id not in selected_ids:
                    tokens = skill.estimated_tokens()
                    selected_ids.append(skill.skill_id)
                    selected_skills.append(skill)
                    selected_defs.append(tool_def)
                    token_count += tokens

        # Step 3: Add retrieval results within budget
        seen_servers: dict[str, int] = {}  # server_name → count (for diversity)
        for match in candidates:
            if len(selected_skills) >= limit:
                break
            if token_count >= budget:
                break
            if match.skill.skill_id in selected_ids:
                continue

            # Diversity: don't let one server dominate
            server = match.skill.server_name or "unknown"
            server_count = seen_servers.get(server, 0)
            if server_count >= max(limit // 3, 3):
                continue

            tool_def = self._skill_to_tool_def.get(match.skill.skill_id)
            if tool_def is None:
                continue

            tokens = match.skill.estimated_tokens()
            if token_count + tokens > budget:
                continue

            selected_ids.append(match.skill.skill_id)
            selected_skills.append(match.skill)
            selected_defs.append(tool_def)
            token_count += tokens
            seen_servers[server] = server_count + 1

        logger.info(
            "Injector selected %d/%d tools (est. %d tokens) for query: %.60s...",
            len(selected_skills), len(self._all_skills), token_count, query,
        )

        return InjectionResult(
            selected_tools=selected_defs,
            selected_skills=selected_skills,
            total_available=len(self._all_skills),
            token_estimate=token_count,
            query_used=query,
        )

    def select_all(self) -> InjectionResult:
        """Return all tools (no filtering) — used as fallback."""
        all_defs = [
            self._skill_to_tool_def[s.skill_id]
            for s in self._all_skills
            if s.skill_id in self._skill_to_tool_def
        ]
        total_tokens = sum(s.estimated_tokens() for s in self._all_skills)
        return InjectionResult(
            selected_tools=all_defs,
            selected_skills=list(self._all_skills),
            total_available=len(self._all_skills),
            token_estimate=total_tokens,
            query_used="*",
        )
