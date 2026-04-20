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

Authentication note:
- Account routes are defined separately in `docs/api/auth-api.md`.
- Game/session routes below now assume a valid bearer token unless stated otherwise.
- Card Designer routes are documented separately in `docs/api/card-designer-api.md`.

### `POST /game/start`

Purpose:
- Start a new game session for a save slot.

Request body:
```json
{
  "save_slot": "slot_001",
  "pack_ids": ["starter_kingdom"],
  "language": "zh",
  "ui_template_id": "tpl_hero_dashboard"
}
```

Field notes:
- `ui_template_id` is optional.
- If provided, backend attempts to bind and apply that UI template for the newly started session.

Response:
```json
{
  "ok": true
}
```

Authentication:
- `Authorization: Bearer <token>`

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

Authentication:
- `Authorization: Bearer <token>`

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
- The turn updates the authenticated user's persisted chat history for the active save slot.
- Turn execution now uses split branches:
  - narration branch runs every turn.
  - ops branch (`plan_ops -> validate_ops -> apply_updates`) runs every N turns.
- N is controlled by environment variable `TEXTRPG_OPS_EVERY_N_TURNS` (default `3`).
- On turns where ops is skipped, `result.validated_ops` and `result.errors` may keep the latest values from the most recent ops turn.

Authentication:
- `Authorization: Bearer <token>`

### `POST /game/step/stream`

Purpose:
- Execute one turn with Server-Sent Events (SSE) incremental narration output.

Request body:
```json
{
  "input_text": "look around the tavern"
}
```

Response shape:
- `text/event-stream` with these event types:
  - `narration_delta`
  - `done`
  - `error`

Event payloads:
```text
event: narration_delta
data: {"delta":"You "}

event: narration_delta
data: {"delta":"look around the tavern."}

event: done
data: {"result": {"narration": "You look around the tavern."}, "state_view": {}}
```

Error event payload:
```text
event: error
data: {"detail":"stream step failed"}
```

Notes:
- `done` payload is equivalent to the `POST /game/step` response shape.
- Streaming and non-streaming turns share the same split turn architecture.
- `narration_delta` is emitted from narration branch immediately.
- ops branch may run in parallel and only triggers every N turns (`TEXTRPG_OPS_EVERY_N_TURNS`).

Authentication:
- `Authorization: Bearer <token>`

### `GET /game/state`

Purpose:
- Fetch the current frontend-safe session state.

Response:
- Matches `StateView` contract in `docs/data-contracts/game-session.md`.

Authentication:
- `Authorization: Bearer <token>`

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
- Session summaries are read from a user-scoped metadata repository first.
- Older save slots without synchronized metadata are backfilled from local save-slot metadata and then persisted.
- Only sessions bound to the authenticated user are returned.
- Loading a session also rehydrates the authenticated user's chat history for that slot from the repository when available.

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
- The source session must belong to the authenticated user.

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
- The archived session must belong to the authenticated user.

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

### `PATCH /game/ui/visibility`

Purpose:
- Toggle visibility for one generated UI panel in the active session.

Request body:
```json
{
  "panel_id": "player_status_1",
  "visible": false
}
```

### `POST /game/ui/template/bind`

Purpose:
- Bind one existing pack UI template to a target session.

Request body:
```json
{
  "save_slot": "slot_001",
  "pack_id": "starter_kingdom",
  "template_id": "tpl_hero_dashboard"
}
```

Response shape:
- Returns persisted session UI binding payload.

### `GET /packs`

Purpose:
- List installed packs.

Authentication:
- `Authorization: Bearer <token>`

Notes:
- Returned `enabled` flags are scoped to the authenticated user's default pack set.
- Pack metadata and content are resolved from user-scoped namespace `data/user_packs/<user_id>/`.

### `PATCH /packs/{pack_id}/enabled`

Purpose:
- Enable or disable a pack.

Request body:
```json
{
  "enabled": true
}
```

Authentication:
- `Authorization: Bearer <token>`

Notes:
- Updates the authenticated user's default enabled-pack set.
- Existing save slots keep their own persisted pack list until they are loaded or restarted.

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
- Authenticated access is still required.

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
- Authenticated access is required.

### `GET /packs/{pack_id}/ui-templates`

Purpose:
- List UI templates scoped to authenticated user and selected pack.

Response item additions:
- `sessions_in_use: number` indicates how many active session bindings currently reference this template.

### `POST /packs/{pack_id}/ui-templates`

Purpose:
- Create or update a user-scoped UI template for selected pack.

Request body:
```json
{
  "name": "Hero Dashboard",
  "template": {
    "panels": []
  },
  "variable_template": {
    "variables": []
  }
}
```

### `DELETE /packs/{pack_id}/ui-templates/{template_id}`

Purpose:
- Delete one UI template.

Notes:
- Deletion is rejected when any active session binding currently references the template.
- Validation detail includes active binding count, for example: `template is currently used by 2 active session(s)`.

### `GET /packs/market/public`
### `GET /packs/market/public/{public_pack_id}`
### `POST /packs/{pack_id}/market/publish`
### `POST /packs/market/public/{public_pack_id}/download`

Purpose:
- Reserved marketplace interfaces for future pack publication and distribution.

Current behavior:
- All endpoints return `501 Not Implemented` until marketplace implementation is introduced.

### `GET /settings/llm`
### `PUT /settings/llm`

Purpose:
- Read and update runtime LLM settings.

Authentication:
- `Authorization: Bearer <token>`

Notes:
- Settings are now stored per authenticated user.
- Sending an empty `api_key` preserves the previously stored key for that user.

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
  - `http://textrpg.tech`
  - `https://textrpg.tech`
  - `http://www.textrpg.tech`
  - `https://www.textrpg.tech`

Production note:
- Additional frontend origins can be appended with the `TEXTRPG_CORS_ALLOW_ORIGINS`
  environment variable.
- The variable accepts a comma-separated list, for example:
  `TEXTRPG_CORS_ALLOW_ORIGINS=https://preview.textrpg.tech,https://admin.textrpg.tech`

Notes:
- Without this CORS allowance, browser-triggered write requests such as `POST /game/start`,
  `POST /game/step`, `PATCH /packs/{pack_id}/enabled`, and `PUT /settings/llm` will fail in
  local development with a generic `Failed to fetch` error.
- The same browser symptom will also appear in production when the deployed frontend origin is
  missing from the backend CORS allowlist.

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
