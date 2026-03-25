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

### `POST /game/sessions/{slot_id}/duplicate`

Purpose:
- Duplicate an existing save slot into a new slot.

Request body:
```json
{
  "target_slot": "slot_001_copy_01"
}
```

Notes:
- `target_slot` is optional.
- When omitted, the backend auto-generates a unique copy slot id.
- Response matches `SessionManagerResponse`.

### `POST /game/sessions/{slot_id}/archive`

Purpose:
- Archive an existing save slot out of the active session inventory.

Request body:
```json
{}
```

Notes:
- Archived slots are moved from `data/saves/` to `data/archives/`.
- Response matches `SessionManagerResponse`.

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

### `DELETE /packs/{pack_id}`

Purpose:
- Remove a local pack from the installed-pack inventory.

Response:
```json
{
  "ok": true
}
```

Notes:
- Builtin packs are protected and return a validation error when removal is requested.

### `POST /packs/{pack_id}/export`

Purpose:
- Export a pack into the local runtime exports directory.

Response:
```json
{
  "ok": true,
  "pack_id": "starter_kingdom",
  "export_path": "E:/TextRPG/data/exports/starter_kingdom-0.1.0.zip"
}
```

Notes:
- This is currently a local-development convenience endpoint.
- It does not stream a download yet; it returns the generated file path.

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

## Local Web Development

- The Next.js frontend runs on `http://127.0.0.1:3000` during local development.
- The FastAPI backend runs on `http://127.0.0.1:8000`.
- `backend/main.py` enables CORS for:
  - `http://127.0.0.1:3000`
  - `http://localhost:3000`

Notes:
- Without this CORS allowance, browser-triggered write requests such as `POST /game/start`,
  `POST /game/step`, `PATCH /packs/{pack_id}/enabled`, and `PUT /settings/llm` will fail in
  local development with a generic `Failed to fetch` error.

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
