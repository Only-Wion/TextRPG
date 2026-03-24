# Repository and Store Contracts

This document defines the storage-facing contracts the application layer relies on.
Current implementations are transitional and in some cases still live under `game/core/`.

## Rules

- Application services depend on behavior, not storage technology.
- Concrete SQLite, JSON, filesystem, and Chroma implementations are infrastructure details.
- Future PostgreSQL migration should preserve these contracts where possible.
- Canonical storage contracts live in `game/infrastructure/contracts.py`.
- Session-scoped concrete store creation is centralized in `game/infrastructure/store_factory.py`.

## World Attribute Store

Purpose:
- Persist dynamic entity attributes.

Canonical operations:

### `set_attr(entity_id, key, value, source, ts) -> None`

Behavior:
- Upserts a single attribute value for one entity and key.

### `all_attrs() -> dict[str, dict[str, str]]`

Behavior:
- Returns all attributes grouped by entity id.

Current implementation:
- `game/core/world_store.py`
- PostgreSQL skeleton: `game/infrastructure/postgres/stores.py::PostgresWorldStore`

Contract:
- `game/infrastructure/contracts.py::WorldStoreProtocol`

Future note:
- PostgreSQL implementation should preserve the grouped return shape used by the session
  state view.

## Knowledge Graph Store

Purpose:
- Persist world relations as edges.

Canonical operations:

### `add_edge(sub, rel, obj, confidence, source) -> None`
### `remove_edge(sub, rel, obj) -> None`
### `all_edges() -> list[dict]`

Current implementation:
- `game/core/kg_store.py`
- PostgreSQL skeleton: `game/infrastructure/postgres/stores.py::PostgresKGStore`

Contract:
- `game/infrastructure/contracts.py::KGStoreProtocol`

Return shape requirement:
- Each edge must expose:
  - `subject_id`
  - `relation`
  - `object_id`
  - `ts`
  - `confidence`
  - `source`

## RAG Memory Store

Purpose:
- Persist and search semantic memories.

Canonical operations:

### `add_memory(text, tags) -> None`
### `search(query, k) -> list[dict]`

Search result shape:
- `text`
- `metadata`

Current implementation:
- `game/core/rag_store.py`
- PostgreSQL skeleton: `game/infrastructure/postgres/stores.py::PostgresRAGStore`

Contract:
- `game/infrastructure/contracts.py::RAGStoreProtocol`

Future note:
- A `pgvector`-based implementation should preserve the same search payload contract for
  the application layer.

## Pack Registry Store

Purpose:
- Persist installed pack metadata and enabled state.

Canonical operations:

### `list() -> list[PackRecord]`
### `get(pack_id) -> PackRecord | None`
### `upsert(record) -> None`
### `remove(pack_id) -> None`
### `set_enabled(pack_id, enabled) -> None`

Current implementation:
- `game/packs/registry.py`

## Session Store Factory

Purpose:
- Centralize construction of persistence implementations for one save slot.

Canonical operation:

### `create(world_db_path, kg_db_path, rag_dir) -> SessionStores`

Behavior:
- Returns a bundle containing `world`, `kg`, and `rag` store implementations.

Current implementation:
- `game/infrastructure/store_factory.py::SessionStoreFactory`

Current bundle type:
- `game/infrastructure/store_factory.py::SessionStores`

Session identity rule:
- The PostgreSQL path uses a canonical `session_key`.
- Current derivation is documented in `docs/data-contracts/postgres-storage-model.md`.

Future note:
- PostgreSQL migration should swap implementations behind this factory before changing
  application services.
- The factory now recognizes `TEXTRPG_STORAGE_BACKEND=postgres`, but the PostgreSQL
  implementations are still skeletons and raise `NotImplementedError`.

## Chat History Store

Purpose:
- Persist chat history for a save slot.

Canonical operations:

### `load(path) -> list[ChatMessage]`
### `save(path, history) -> None`

Current implementation:
- `game/infrastructure/session_files.py::ChatHistoryStore`
- PostgreSQL skeleton: `game/infrastructure/postgres/session_files.py::PostgresChatHistoryStore`

Contract:
- `game/infrastructure/contracts.py::ChatHistoryStoreProtocol`

Future note:
- `GameService` currently delegates chat history persistence to this store.
- A PostgreSQL-backed implementation should preserve the same load and save behavior.

## UI Panel Cache Store

Purpose:
- Persist generated UI panel definitions for a save slot.

Canonical operations:

### `load(path) -> list[dict]`
### `save(path, panels) -> None`

Current implementation:
- `game/infrastructure/session_files.py::UIPanelStore`
- PostgreSQL skeleton: `game/infrastructure/postgres/session_files.py::PostgresUIPanelStore`

Contract:
- `game/infrastructure/contracts.py::UIPanelStoreProtocol`

Future note:
- `GameService` currently delegates UI panel cache persistence to this store.

## Transaction Boundary

Current state:
- There is no cross-store transaction boundary.
- A turn may write attrs, edges, memories, snapshots, and chat history independently.

Migration note:
- When PostgreSQL is introduced, document whether:
  - turn writes become transactional, or
  - memory and snapshot writes remain eventually consistent side effects.
