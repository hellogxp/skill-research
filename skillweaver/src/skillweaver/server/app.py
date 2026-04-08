"""FastAPI application for SkillWeaver HTTP API.

Provides REST endpoints for:
    - /search      — semantic skill search
    - /plan        — decompose + retrieve + compose
    - /inject      — context-aware tool filtering (for MCP proxy)
    - /index/*     — index management (status, add skills)
    - /health      — health check

Start with:
    skillweaver serve
    # or
    uvicorn skillweaver.server.app:create_app --factory
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Optional

from skillweaver.config.settings import Settings, load_settings
from skillweaver.core.models import Skill

logger = logging.getLogger(__name__)


def create_app(settings: Optional[Settings] = None):
    """Application factory — creates and configures the FastAPI app."""
    try:
        from fastapi import FastAPI, HTTPException
        from fastapi.middleware.cors import CORSMiddleware
    except ImportError:
        raise ImportError(
            "FastAPI is required for the server. Install with:\n"
            "  pip install skillweaver[server]"
        )

    from skillweaver.server.schemas import (
        HealthResponse,
        IndexStatusResponse,
        InjectRequest,
        InjectResponse,
        PlanRequest,
        PlanResponse,
        PlanStepResult,
        SearchRequest,
        SearchResponse,
        SkillAddRequest,
        SkillAddResponse,
        SkillResult,
    )

    cfg = settings or load_settings()

    # Shared state
    state: dict[str, Any] = {
        "retriever": None,
        "skills": [],
        "store": None,
        "injector": None,
    }

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        """Startup: load index. Shutdown: cleanup."""
        from skillweaver.core.retriever import SkillRetriever
        from skillweaver.index.store import IndexStore
        from skillweaver.mcp.injector import ToolInjector

        store = IndexStore(store_dir=Path(cfg.store_dir))
        skills = store.load_skills()

        retriever = SkillRetriever(
            encoder_name=cfg.encoder,
            top_k=cfg.top_k,
            use_body=cfg.use_body,
        )
        if skills:
            if store.has_index():
                retriever.load_index(store.index_dir, skills)
            else:
                retriever.build_index(skills)

        # Build injector for /inject endpoint
        injector = ToolInjector(max_tools=cfg.proxy_max_tools)
        if skills:
            tool_defs = [
                {"name": s.name, "description": s.description,
                 "inputSchema": s.io_schema.to_dict()}
                for s in skills
            ]
            injector.build_index(skills, tool_defs)

        state["store"] = store
        state["skills"] = skills
        state["retriever"] = retriever
        state["injector"] = injector

        logger.info("Server ready: %d skills loaded", len(skills))
        yield
        logger.info("Server shutting down")

    app = FastAPI(
        title="SkillWeaver API",
        description="AI Agent skill discovery and compositional workflow orchestration",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # -- Endpoints --------------------------------------------------------

    @app.get("/health", response_model=HealthResponse)
    async def health():
        store = state["store"]
        return HealthResponse(
            version="0.1.0",
            total_skills=len(state["skills"]),
            has_index=store.has_index() if store else False,
        )

    @app.post("/search", response_model=SearchResponse)
    async def search(req: SearchRequest):
        retriever = state["retriever"]
        skills = state["skills"]
        if not retriever or not skills:
            raise HTTPException(status_code=503, detail="Index not loaded")

        matches = retriever.search(req.query, top_k=req.top_k if not req.category else 100)

        # Category filter (post-search)
        if req.category:
            matches = [
                m for m in matches
                if req.category.lower() in [c.lower() for c in m.skill.categories]
            ][:req.top_k]
        results = [
            SkillResult(
                skill_id=m.skill.skill_id,
                name=m.skill.name,
                description=m.skill.description,
                score=round(m.score, 4),
                categories=m.skill.categories,
                tags=m.skill.tags,
                source_format=m.skill.source_format.value,
                server_name=m.skill.server_name,
                estimated_tokens=m.skill.estimated_tokens(),
            )
            for m in matches
        ]
        return SearchResponse(
            query=req.query,
            results=results,
            total_indexed=len(skills),
        )

    @app.post("/plan", response_model=PlanResponse)
    async def plan_endpoint(req: PlanRequest):
        retriever = state["retriever"]
        if not retriever or not state["skills"]:
            raise HTTPException(status_code=503, detail="Index not loaded")

        from skillweaver.core.decomposer import create_decomposer
        from skillweaver.core.pipeline import SkillWeaverPipeline

        kwargs = {}
        if req.model:
            kwargs["model"] = req.model

        try:
            decomposer = create_decomposer(req.backend, **kwargs)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid backend: {e}")

        pipeline = SkillWeaverPipeline(
            decomposer=decomposer,
            retriever=retriever,
            use_dag=req.use_dag,
            sad=req.sad,
            sad_hint_count=req.sad_hint_count,
        )

        try:
            result = pipeline.plan(req.query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Planning failed: {e}")

        steps = [
            PlanStepResult(
                step_index=s.step_index,
                subtask=s.subtask,
                selected_skill=s.selected_skill.name if s.selected_skill else None,
                confidence=round(s.confidence, 4),
                parallel_group=s.parallel_group,
                num_candidates=len(s.candidates),
            )
            for s in result.steps
        ]
        return PlanResponse(
            query=result.query,
            steps=steps,
            edges=[list(e) for e in result.edges],
            avg_confidence=round(result.avg_confidence, 4),
            num_steps=result.num_steps,
        )

    @app.post("/inject", response_model=InjectResponse)
    async def inject(req: InjectRequest):
        injector = state["injector"]
        if not injector:
            raise HTTPException(status_code=503, detail="Injector not loaded")

        result = injector.select(
            query=req.query,
            max_tools=req.max_tools,
            token_budget=req.token_budget,
        )
        return InjectResponse(
            selected_tools=result.selected_tools,
            total_available=result.total_available,
            token_estimate=result.token_estimate,
            query_used=result.query_used,
        )

    @app.get("/index/status", response_model=IndexStatusResponse)
    async def index_status():
        store = state["store"]
        if not store:
            raise HTTPException(status_code=503, detail="Store not initialized")
        info = store.status()
        return IndexStatusResponse(**info)

    @app.post("/index/add", response_model=SkillAddResponse)
    async def index_add(req: SkillAddRequest):
        store = state["store"]
        if not store:
            raise HTTPException(status_code=503, detail="Store not initialized")

        existing = state["skills"]
        existing_ids = {s.skill_id for s in existing}

        new_skills = []
        for d in req.skills:
            try:
                skill = Skill.from_dict(d)
                if skill.skill_id not in existing_ids:
                    new_skills.append(skill)
            except Exception as e:
                logger.warning("Skipping invalid skill: %s", e)

        if new_skills:
            all_skills = existing + new_skills
            store.save_skills(all_skills)
            state["skills"] = all_skills

            if req.rebuild_index:
                retriever = state["retriever"]
                if retriever:
                    retriever.build_index(all_skills)
                    retriever.save_index(store.index_dir)

        return SkillAddResponse(
            added=len(new_skills),
            duplicates_skipped=len(req.skills) - len(new_skills),
            total=len(state["skills"]),
        )

    return app
