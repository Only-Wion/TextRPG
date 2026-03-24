# PostgreSQL Storage Model

This document defines the planned PostgreSQL-side storage model for TextRPG. It is a
contract and migration target, not a claim that PostgreSQL persistence is active today.

## Status

- Current active backend: `local`
- Planned backend: `postgres`
- PostgreSQL code path currently exists as skeletons only

## Session Identity

Canonical session identity:
- `session_key`

Current derivation rule:
- `session_key == save_slot`

Current helper:
- `game/infrastructure/postgres/session_key.py::session_key_from_slot_dir`

Why this exists:
- The local implementation is slot-directory-based.
- PostgreSQL storage needs a stable key that is independent of filesystem paths.

## Planned Tables

### `game_sessions`

Purpose:
- Root table for session-scoped persistence.

Fields:
- `session_key`
- `save_slot`
- `language`
- `created_at`
- `updated_at`

### `world_attrs`

Purpose:
- Dynamic world attributes keyed by session and entity.

Primary key:
- `(session_key, entity_id, key)`

### `kg_edges`

Purpose:
- Session-scoped world relations.

Important fields:
- `session_key`
- `sub`
- `rel`
- `obj`
- `ts`
- `confidence`
- `source`

### `chat_messages`

Purpose:
- Ordered chat history for one session.

Primary key:
- `(session_key, message_index)`

### `ui_panel_defs`

Purpose:
- Persist generated UI panel definitions as JSON.

Primary key:
- `(session_key, panel_id)`

### `memory_entries`

Purpose:
- Semantic memory store.

Current planned fields:
- `memory_id`
- `session_key`
- `text`
- `tags`
- `metadata`
- `created_at`

Future extension:
- vector embedding column for `pgvector`

## Canonical SQL Draft

Reference file:
- `game/infrastructure/postgres/schema.sql`

This SQL file is the authoritative draft schema for the PostgreSQL migration path.
