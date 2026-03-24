from __future__ import annotations

from fastapi import FastAPI

from .api.routes import game, health, packs, settings
from .errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="TextRPG Backend",
        version="0.1.0",
        description="Phase 1 FastAPI shell for the TextRPG application service layer.",
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(game.router)
    app.include_router(packs.router)
    app.include_router(settings.router)
    return app


app = create_app()
