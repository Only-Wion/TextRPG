# Repository and Store Contracts

This document defines the storage-facing contracts the application layer relies on.
Current implementations are transitional and in some cases still live under `game/core/`.

## Rules

- Application services depend on behavior, not storage technology.
- Concrete SQLite, JSON, filesystem, and Chroma implementations are infrastructure details.
- Future PostgreSQL migration should preserve these contracts where possible.
- Canonical storage contracts live in `game/infrastructure/contracts.py`.
- Session-scoped concrete store creation is centralized in `game/infrastructure/store_factory.py`.

## User Repository

Purpose:
- Persist accounts, password hashes, bearer tokens, and user lookup.

Canonical operations:

### `create_user(email, username, password) -> dict`
### `authenticate(email_or_username, password) -> dict`
### `get_user_by_id(user_id) -> dict | None`
### `issue_token(user_id) -> str`
### `get_user_by_token(token) -> dict | None`
### `revoke_token(token) -> None`

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UserRepositoryProtocol`

## User Session Ownership Repository

Purpose:
- Map save-slot ids to the owning authenticated user.

Canonical operations:

### `bind_session(user_id, save_slot) -> None`
### `list_session_slots(user_id) -> list[str]`
### `user_owns_session(user_id, save_slot) -> bool`
### `clone_binding(user_id, source_slot, target_slot) -> None`
### `archive_binding(user_id, save_slot) -> None`

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UserSessionIndexProtocol`

## User Settings Repository

Purpose:
- Persist runtime LLM settings for one authenticated user.

Canonical operations:

### `get_llm_settings(user_id) -> dict`
### `update_llm_settings(user_id, payload) -> dict`

Behavior:
- Returns the effective per-user runtime settings.
- Preserves the stored API key when the incoming payload leaves `api_key` blank.

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UserSettingsRepositoryProtocol`

## User Pack State Repository

Purpose:
- Persist the default enabled-pack set for one authenticated user.

Canonical operations:

### `list_enabled_pack_ids(user_id) -> list[str]`
### `set_pack_enabled(user_id, pack_id, enabled) -> None`
### `replace_enabled_pack_ids(user_id, pack_ids) -> None`

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UserPackStateRepositoryProtocol`

## User Session Metadata Repository

Purpose:
- Persist per-user session summary metadata used by `/game/sessions`.

Canonical operations:

### `save_session_metadata(user_id, save_slot, payload) -> None`
### `list_session_summaries(user_id) -> list[dict]`
### `delete_session_metadata(user_id, save_slot) -> None`

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UserSessionMetadataRepositoryProtocol`

## User Chat History Repository

Purpose:
- Persist per-user chat history for one save slot.

Canonical operations:

### `load_chat_history(user_id, save_slot) -> list[dict]`
### `save_chat_history(user_id, save_slot, history) -> None`
### `delete_chat_history(user_id, save_slot) -> None`

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UserChatHistoryRepositoryProtocol`

## Card Designer Session Repository

Purpose:
- Persist the authenticated user's Card Designer AI/draft workspace state.

Canonical operations:

### `create_designer_session(user_id, pack_id=None) -> dict`
### `get_designer_session(user_id, session_id) -> dict | None`
### `save_designer_session(user_id, session_id, payload) -> dict`
### `delete_designer_session(user_id, session_id) -> None`

Current implementation:
- `game/infrastructure/auth_sqlite.py::SqliteAuthRepository` (local backend)
- `game/infrastructure/postgres/auth_repository.py::PostgresAuthRepository` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::CardDesignerSessionRepositoryProtocol`

Notes:
- Current local implementation stores the designer agent state JSON in sqlite.
- Target production design remains PostgreSQL for the designer session state and file storage
  for pack/card files.

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
- `game/infrastructure/postgres/stores.py::PostgresWorldStore` (postgres backend)

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
- `game/infrastructure/postgres/stores.py::PostgresKGStore` (postgres backend)

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
- `game/core/rag_store.py` (local backend)
- `game/infrastructure/postgres/stores.py::PostgresRAGStore` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::RAGStoreProtocol`

Current postgres note:
- The current PostgreSQL implementation uses keyword matching fallback in SQL.
- A future `pgvector` upgrade should preserve the same search payload contract for the
  application layer.

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

Backend switch note:
- `SessionStoreFactory` switches by `TEXTRPG_STORAGE_BACKEND`.
- `local` uses sqlite/chroma implementations.
- `postgres` uses PostgreSQL-backed world/kg/rag implementations.
- `TEXTRPG_POSTGRES_DSN` is required when backend is `postgres`.

## Chat History Store

Purpose:
- Persist chat history for a save slot.

Canonical operations:

### `load(path) -> list[ChatMessage]`
### `save(path, history) -> None`

Current implementation:
- `game/infrastructure/session_files.py::ChatHistoryStore` (local backend)
- `game/infrastructure/postgres/session_files.py::PostgresChatHistoryStore` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::ChatHistoryStoreProtocol`

Current note:
- `GameService` delegates chat history persistence to this store and selects
  the concrete implementation by backend.

## UI Panel Cache Store

Purpose:
- Persist generated UI panel definitions for a save slot.

Canonical operations:

### `load(path) -> list[dict]`
### `save(path, panels) -> None`

Current implementation:
- `game/infrastructure/session_files.py::UIPanelStore` (local backend)
- `game/infrastructure/postgres/session_files.py::PostgresUIPanelStore` (postgres backend)

Contract:
- `game/infrastructure/contracts.py::UIPanelStoreProtocol`

Current note:
- `GameService` delegates UI panel cache persistence to this store and selects
  the concrete implementation by backend.

## Transaction Boundary

Current state:
- There is no cross-store transaction boundary.
- A turn may write attrs, edges, memories, snapshots, and chat history independently.

Migration note:
- When PostgreSQL is introduced, document whether:
  - turn writes become transactional, or
  - memory and snapshot writes remain eventually consistent side effects.
