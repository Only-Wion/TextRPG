from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import os

from .api.routes.auth import router as auth_router
from .api.routes.card_designer import router as card_designer_router
from .api.routes.game import router as game_router
from .api.routes.health import router as health_router
from .api.routes.packs import router as packs_router
from .api.routes.settings import router as settings_router
from .errors import register_exception_handlers


DEFAULT_CORS_ALLOW_ORIGINS = [
    "http://127.0.0.1:3000",
    "http://localhost:3000",
    "http://textrpg.tech",
    "https://textrpg.tech",
    "http://www.textrpg.tech",
    "https://www.textrpg.tech",
]


def get_cors_allow_origins() -> list[str]:
    raw_origins = os.getenv("TEXTRPG_CORS_ALLOW_ORIGINS", "")
    extra_origins = [origin.strip() for origin in raw_origins.split(",") if origin.strip()]
    merged: list[str] = []

    for origin in [*DEFAULT_CORS_ALLOW_ORIGINS, *extra_origins]:
        if origin not in merged:
            merged.append(origin)

    return merged


def create_app() -> FastAPI:
    app = FastAPI(
        title="TextRPG Backend",
        version="0.1.0",
        description="Phase 1 FastAPI shell for the TextRPG application service layer.",
    )
    # Allow both local development and the current production frontend origin.
    # Additional origins can be appended through TEXTRPG_CORS_ALLOW_ORIGINS.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_allow_origins(),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(game_router)
    app.include_router(card_designer_router)
    app.include_router(packs_router)
    app.include_router(settings_router)
    return app


app = create_app()
