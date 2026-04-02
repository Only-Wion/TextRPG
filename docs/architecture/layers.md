# Layer Architecture

## Goal

Reshape the current TextRPG project into a backend that fits `Next.js + FastAPI +
TextRPG + PostgreSQL` without rewriting core gameplay logic up front.

## Layers

### 1. Core

Purpose:
- Pure game and domain logic.
- No dependency on FastAPI, Streamlit, or frontend code.
- Avoid dependence on concrete storage technologies where possible.

Contains:
- LangGraph game flow.
- Rules engine.
- Card parsing and card search logic.
- Ops and state models.
- Admin command parsing.
- Runtime snapshot logic.

Rules:
- `core` must not depend on `api`.
- `core` must not depend on frontend modules.
- `core` should express domain behavior, not delivery concerns.

### 2. Application

Purpose:
- Organize use cases.
- Coordinate sessions, packs, settings, and UI panel workflows.
- Serve as the only layer called by the API layer.

Contains:
- Session start and load.
- Turn progression.
- Pack management use cases.
- LLM settings use cases.
- UI panel generation and refresh use cases.

Rules:
- `application` may depend on `core`.
- `application` may depend on `infrastructure`.
- `application` must not know about HTTP request or response objects.
- `application` owns orchestration, not delivery formatting.

### 3. Infrastructure

Purpose:
- Concrete implementations for storage and external integrations.
- Encapsulate SQLite, JSON files, Chroma, filesystem, and future PostgreSQL adapters.

Contains:
- SQLite world store.
- SQLite KG store.
- Chroma RAG store.
- Filesystem-based pack registry and pack storage.
- Pack content storage now has an abstraction seam; the default backend remains local filesystem, and OSS-ready settings are read from `TEXTRPG_PACK_STORAGE_BACKEND` / `TEXTRPG_OSS_*`.
- JSON persistence for chat history and UI panel cache.
- Session store factory used by the application layer to resolve concrete store implementations.
- PostgreSQL infrastructure implementations for server-side persistence.
- LLM client wiring and embedding client wiring.

Rules:
- `infrastructure` may use third-party libraries and the filesystem.
- `infrastructure` must not own business use cases.
- `infrastructure` must not expose framework-specific HTTP behavior.

### 4. API

Purpose:
- FastAPI application entrypoint.
- Request validation.
- Response serialization.
- Error mapping.
- Dependency injection and auth hooks.

Contains:
- Route handlers.
- API schemas.
- Exception handlers.
- Dependency providers.

Rules:
- `api` calls `application`, not `core` directly for use cases.
- `api` must not orchestrate storage objects directly.
- `api` must keep controller logic thin.

## Dependency Direction

Allowed:
- `api -> application`
- `application -> core`
- `application -> infrastructure`
- `infrastructure -> core`

Forbidden:
- `core -> api`
- `core -> ui`
- `api -> infrastructure` for business orchestration
- frontend code calling `core` or `application` Python objects directly in the target architecture

## Transitional Notes

- Streamlit remains a transitional UI entrypoint for now.
- `game.service.api.GameService` is a transitional application-layer facade.
- Several concrete storage implementations currently live under `game/core/`; they will
  be treated as infrastructure during migration even before the files move.
