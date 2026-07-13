from __future__ import annotations

from fastapi import FastAPI

from backend.app.api.routers import events, workflows
from backend.app.core.container import build_container


def create_app() -> FastAPI:
    app = FastAPI(title="AI QA Copilot", version="0.1.0")
    app.state.container = build_container()

    app.include_router(workflows.router)
    app.include_router(events.router)

    @app.get("/health")
    def health() -> dict:
        container = app.state.container
        return {"status": "ok", "agents": container.agent_registry.list_agents()}

    return app


app = create_app()
