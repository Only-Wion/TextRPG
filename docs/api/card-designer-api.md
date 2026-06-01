# Card Designer API

This document defines the backend contract for the authenticated Card Designer workbench.

Status:
- Current implementation: local-development backend contract
- Current storage backing: local sqlite + file storage
- Target production backing: PostgreSQL + file storage
- Pack content storage is OSS-only and requires `TEXTRPG_PACK_STORAGE_BACKEND=oss` with `TEXTRPG_OSS_*` environment variables.

Authentication:
- Every route below requires `Authorization: Bearer <token>`

## `GET /card-designer/packs`

Purpose:
- List packs available to the Card Designer workbench.

Response:
- Same pack inventory shape returned by `GET /packs`

Notes:
- This route is editing-oriented and is intended for the Card Designer page.
- Pack files are persisted in OSS directly; backend card read/write no longer depends on persistent local pack caches.
- OSS object namespace is user-scoped: `<oss_prefix>/users/<user_id>/packs/<pack_id>/<version>/<cards_root>/...`.

## `POST /card-designer/packs`

Purpose:
- Create a new pack manifest and directory structure.

Request body:
```json
{
  "pack_id": "mystery_hotel",
  "name": "Mystery Hotel",
  "version": "0.1.0",
  "author": "Only-Wion",
  "description": "Narrative mystery pack"
}
```

Notes:
- `cards_root` is now backend-managed and defaults to `cards`.

Response:
- Echoes the created manifest payload.

## `GET /card-designer/packs/{pack_id}/card-types`

Purpose:
- Return available card types for the selected pack.

Response:
```json
["character", "location", "quest"]
```

## `GET /card-designer/packs/{pack_id}/cards`

Purpose:
- List cards for one pack in the Card Designer library panel.

Query parameters:
- `category` optional
- `keyword` optional

Response shape:
```json
[
  {
    "path": "characters/bartender.md",
    "folder_path": "",
    "card_id": "bartender",
    "card_type": "character",
    "category": "characters",
    "title": "Bartender"
  }
]
```

Notes:
- This endpoint reads card files from OSS user-scoped object keys, not from a PostgreSQL card table.
- In `postgres` backend mode, PostgreSQL persists user/session metadata; pack/card content remains file-backed.
- In OSS mode, object storage is the only source of truth for pack files.

## `GET /card-designer/packs/{pack_id}/cards/{card_path}`

Purpose:
- Load a single card payload for editing.

Response shape:
```json
{
  "path": "characters/bartender.md",
  "folder_path": "",
  "pack_id": "starter_kingdom",
  "card_type": "character",
  "card_id": "bartender",
  "frontmatter": {},
  "body": "..."
}
```

## `POST /card-designer/packs/{pack_id}/cards/template`

Purpose:
- Generate a default template payload for one card type.

Request body:
```json
{
  "card_type": "character"
}
```

## `POST /card-designer/packs/{pack_id}/cards`

Purpose:
- Create or save a card file inside one pack.

Request body:
```json
{
  "card_type": "character",
  "card_id": "bartender",
  "folder_path": "main_story/chapter_01",
  "frontmatter_text": "{\n  \"id\": \"bartender\",\n  \"type\": \"character\"\n}",
  "body": "Card body markdown",
  "original_path": "characters/old_bartender.md"
}
```

Response:
- Returns the saved card payload in the same shape as `GET card`

Notes:
- The current frontend sends `frontmatter_text` so the browser does not need a YAML dependency.
- The backend also accepts structured `frontmatter` for future clients.
- `folder_path` is optional and represents a nested directory under the type directory.
  Example final path: `events/main_story/chapter_01/event-a.md`.
- If `folder_path` is omitted while editing an existing card (`original_path` provided), backend keeps the card in its original nested folder by default.

## `GET /card-designer/packs/{pack_id}/canvas-state`

Purpose:
- Load the pack's designer canvas state.

Response shape:
```json
{
  "canvas_nodes": [],
  "canvas_edges": [],
  "canvas_offset": { "x": 0, "y": 0 },
  "canvas_scale": 1,
  "selected_node_id": null,
  "selected_edge_id": null,
  "connect_source_id": null,
  "entry_events": ["event_logic_overflow_grey_gift"]
}
```

## `PUT /card-designer/packs/{pack_id}/canvas-state`

Purpose:
- Persist the pack's designer canvas state.

Notes:
- The payload now includes `entry_events`, which the Card Designer page uses to mark the current entry card.
- Runtime reads the same `canvas_state.json` file when building pack entry points.

## `POST /card-designer/cards/validate`

Purpose:
- Validate card content before saving.

Request body:
```json
{
  "frontmatter_text": "{\n  \"id\": \"bartender\"\n}",
  "body": "Card body markdown"
}
```

Response:
```json
{
  "ok": true
}
```

## `DELETE /card-designer/packs/{pack_id}/cards/{card_path}`

Purpose:
- Delete a card file from one pack.

Response:
```json
{
  "ok": true
}
```

## `POST /card-designer/agent/sessions`

Purpose:
- Create a persisted Card Designer AI session for one authenticated user.

Request body:
```json
{
  "pack_id": "starter_kingdom"
}
```

Response shape:
```json
{
  "session_id": "uuid",
  "selected_pack_id": "starter_kingdom",
  "mode": "edit",
  "state": {
    "history": [],
    "memory": "",
    "question_mode": true,
    "creation_started": false,
    "selected_pack_id": "starter_kingdom"
  },
  "updated_at": "2026-03-26 10:20:00"
}
```

## `GET /card-designer/agent/sessions/{session_id}`

Purpose:
- Load a previously created Card Designer AI session.

Response:
- Same shape as `POST /card-designer/agent/sessions`

## `POST /card-designer/agent/sessions/{session_id}/messages`

Purpose:
- Send one message to the Pack Builder Agent and persist the updated designer state.

Request body:
```json
{
  "message": "Create a mystery hotel pack with a receptionist and a missing guest quest."
}
```

Response shape:
```json
{
  "session_id": "uuid",
  "assistant": "I'll start by planning the pack structure.",
  "tool_logs": [
    "create_pack -> mystery_hotel"
  ],
  "selected_pack_id": "mystery_hotel",
  "state": {}
}
```

Behavior notes:
- Write tools (for example `save_card` / `batch_save_cards`) are confirmation-gated. The assistant first returns a pending-write plan and waits for user confirmation.
- When writes are executed, `selected_pack_id` in response is synchronized to the actual write target pack.
- Agent execution now uses the authenticated user's LLM runtime settings for each message (same user-scoped settings source as Play flow).

## Current local-development note

- Card files and pack manifests live in filesystem storage.
- Designer AI/draft session state is persisted in the active auth repository backend (`sqlite` or `postgres`).
- Current production path is PostgreSQL for user/session/settings metadata + filesystem storage for pack/card files.
