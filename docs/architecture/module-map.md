# Module Map

This file maps the current repository modules to the target layered architecture.

## Mapping Table

| Current module | Target layer | Status | Notes |
| --- | --- | --- | --- |
| `game/core/graph.py` | core | keep | Main turn pipeline and orchestration graph. |
| `game/core/rule_engine.py` | core | keep | Domain validation and derived actions. |
| `game/core/card_repository.py` | core | keep for now | Domain-facing card loading and search. |
| `game/core/admin.py` | core | keep | Admin command to ops parsing. |
| `game/core/snapshot.py` | core | keep for now | Runtime snapshot output. May move later. |
| `game/state.py` | core | keep | Turn state contract. |
| `game/ops.py` | core | keep | Ops contract models. |
| `game/packs/validator.py` | core | keep | Manifest and card validation rules. |
| `game/packs/card_editor.py` | core | keep | Card parsing, rendering, and validation helpers. |
| `game/service/api.py` | application | transitional facade | Central legacy facade now wrapped by application services. |
| `game/application/services.py` | application | keep | Thin service boundary for API-facing use cases. |
| `game/service/ui_agents.py` | application | keep for now | UI panel business workflow. |
| `game/packs/manager.py` | application + infrastructure | split later | Mixes use case logic with filesystem operations. |
| `game/infrastructure/postgres/stores.py::PostgresWorldStore` | infrastructure | keep | PostgreSQL-backed world attribute implementation. |
| `game/infrastructure/postgres/stores.py::PostgresKGStore` | infrastructure | keep | PostgreSQL-backed KG edge implementation. |
| `game/core/rag_store.py` | infrastructure | relocate later | Chroma-backed implementation. |
| `game/packs/registry.py` | infrastructure | relocate later | JSON registry implementation. |
| `game/infrastructure/contracts.py` | infrastructure | keep | Canonical store contracts for application-layer dependencies. |
| `game/infrastructure/session_files.py` | infrastructure | keep | Filesystem chat history and UI panel cache stores. |
| `game/infrastructure/store_factory.py` | infrastructure | keep | Session-scoped store creation boundary for future PostgreSQL swaps. |
| `game/infrastructure/postgres/stores.py` | infrastructure | keep | PostgreSQL store implementations for world, KG, and RAG (RAG currently uses SQL keyword fallback). |
| `game/infrastructure/postgres/session_files.py` | infrastructure | keep | PostgreSQL store implementations for chat history and UI panels. |
| `game/llm.py` | infrastructure | split later | Mixes prompts with client wiring. |
| `game/main.py` | entrypoint | keep | CLI/debug entrypoint. |
| `ui/*` | legacy frontend | keep during transition | Transitional Streamlit UI. |

## Phase 1 Focus

Phase 1 is the FastAPI shell and contract phase.

Keep stable:
- `game/core/graph.py`
- `game/core/rule_engine.py`
- `game/state.py`
- `game/ops.py`
- `game/packs/validator.py`
- `game/packs/card_editor.py`

Wrap without rewriting:
- `game/service/api.py`
- `game/packs/manager.py`
- `game/llm.py`

Treat as infrastructure even before moving files:
- `game/infrastructure/postgres/stores.py::PostgresWorldStore`
- `game/infrastructure/postgres/stores.py::PostgresKGStore`
- `game/core/rag_store.py`
- `game/packs/registry.py`

## Target Service Split

The current `game/service/api.py` facade will eventually split into:

- `SessionService`
- `PackService`
- `SettingsService`
- `UIPanelService` or a private UI workflow module behind `SessionService`
