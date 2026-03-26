from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import auth, game, health, packs, settings
from .errors import register_exception_handlers


def create_app() -> FastAPI:
    app = FastAPI(
        title="TextRPG Backend",
        version="0.1.0",
        description="Phase 1 FastAPI shell for the TextRPG application service layer.",
    )
    # Local web development runs Next.js on port 3000 and calls this API on 8000.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:3000",
            "http://localhost:3000",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(game.router)
    app.include_router(packs.router)
    app.include_router(settings.router)
    return app


app = create_app()
