# HTTP API Contract

This document defines the Phase 1 FastAPI shell that wraps the existing application
services.

## Design Rules

- Routes are thin wrappers over application services.
- Route handlers do not build stores, graphs, or repositories directly.
- Error mapping is centralized.
- Response bodies should be stable even if internal implementation changes.

## Implemented Routes

### `GET /health`

Purpose:
- Health and readiness probe for the backend process.

Response:
```json
{
  "status": "ok"
}
```

Notes:
- The concrete implementation returns `{"ok": true, "status": "ok"}`.

### `POST /game/start`

Purpose:
- Start a new game session for a save slot.

Request body:
```json
{
  "save_slot": "slot_001",
  "pack_ids": ["starter_kingdom"],
  "language": "zh"
}
```

Response:
```json
{
  "ok": true
}
```

### `POST /game/load`

Purpose:
- Load an existing game session from a save slot.

Request body:
```json
{
  "save_slot": "slot_001",
  "language": "zh"
}
```

Response:
```json
{
  "ok": true
}
```

### `POST /game/step`

Purpose:
- Execute one turn against the active session.

Request body:
```json
{
  "input_text": "look around the tavern"
}
```

Response shape:
```json
{
  "result": {},
  "state_view": {}
}
```

Notes:
- `result` is the direct turn output from the application service.
- `state_view` is the frontend-safe projection after the turn completes.

### `GET /game/state`

Purpose:
- Fetch the current frontend-safe session state.

Response:
- Matches `StateView` contract in `docs/data-contracts/game-session.md`.

### `GET /game/sessions`

Purpose:
- Fetch session inventory data for the Sessions page.

Response:
```json
{
  "selected_slot": "slot_001",
  "backend_status": "online",
  "storage_backend": "local",
  "last_sync_label": "just now",
  "sessions": [
    {
      "slot_id": "slot_001",
      "language": "zh",
      "enabled_packs": ["starter_kingdom"],
      "location_label": "Tavern",
      "turn_count": 18,
      "updated_label": "2026-03-25 11:42"
    }
  ]
}
```

Notes:
- Session summaries are read from local save-slot metadata when present.
- Older save slots without metadata are backfilled from filesystem timestamps plus safe defaults.

### `PATCH /game/ui-mode`

Purpose:
- Update UI panel refresh mode.

Request body:
```json
{
  "mode": "manual"
}
```

### `PATCH /game/ui-auto-update`

Purpose:
- Update UI auto-refresh turn interval.

Request body:
```json
{
  "turns": 1
}
```

### `POST /game/ui/generate`

Purpose:
- Trigger UI panel generation.

Request body:
```json
{
  "force": true
}
```

### `POST /game/ui/update`

Purpose:
- Trigger UI panel update.

Response:
```json
{
  "ok": true
}
```

### `GET /packs`

Purpose:
- List installed packs.

### `PATCH /packs/{pack_id}/enabled`

Purpose:
- Enable or disable a pack.

Request body:
```json
{
  "enabled": true
}
```

### `GET /settings/llm`
### `PUT /settings/llm`

Purpose:
- Read and update runtime LLM settings.

## FastAPI Shell Layout

The current shell is implemented in:

- `backend/main.py`
- `backend/deps.py`
- `backend/errors.py`
- `backend/api/routes/*.py`
- `backend/schemas/*.py`

## Error Mapping

| Condition | HTTP status | Notes |
| --- | --- | --- |
| Validation failure | 400 | Includes invalid input and malformed payload. |
| Session not started | 409 | Returned when turn or UI actions are requested without an active session. |
| Resource not found | 404 | Pack or file path not found, when applicable. |
| Unexpected runtime failure | 500 | Internal error. |

## Transitional Runtime Constraint

- The shell currently uses a singleton `GameService`.
- Session state is therefore process-local and single-runtime in Phase 1.

## Phase Boundary

Phase 1 does not solve:
- multi-user isolation
- process-safe session storage
- PostgreSQL persistence
- auth

Those concerns will be introduced in later phases without changing the HTTP surface more
than necessary.
