# Card Designer Data Contracts

This document defines the canonical payload shapes used by the Card Designer workbench.

Status:
- Current implementation: local-development contract
- Current persistence mix: sqlite transition repository + file storage
- Target production persistence: PostgreSQL + file storage

## Designer Card Summary

Used by:
- `GET /card-designer/packs/{pack_id}/cards`
- future frontend card library panel

Shape:
```json
{
  "path": "characters/bartender.md",
  "card_id": "bartender",
  "card_type": "character",
  "category": "characters",
  "title": "Bartender"
}
```

## Designer Card Payload

Used by:
- `GET /card-designer/packs/{pack_id}/cards/{card_path}`
- `POST /card-designer/packs/{pack_id}/cards`

Shape:
```json
{
  "path": "characters/bartender.md",
  "pack_id": "starter_kingdom",
  "card_type": "character",
  "card_id": "bartender",
  "frontmatter": {
    "id": "bartender",
    "type": "character"
  },
  "body": "Markdown content"
}
```

## Card Validation Response

Shape:
```json
{
  "ok": true
}
```

## Designer Session Payload

Used by:
- `POST /card-designer/agent/sessions`
- `GET /card-designer/agent/sessions/{session_id}`

Shape:
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

Notes:
- `state` is intentionally agent-runtime-shaped because the current implementation reuses the old Pack Builder Agent state machine.
- The current local store persists this as JSON.
- The target PostgreSQL model should preserve the same logical payload, likely in JSONB.

## Designer Agent Message Response

Used by:
- `POST /card-designer/agent/sessions/{session_id}/messages`

Shape:
```json
{
  "session_id": "uuid",
  "assistant": "I created the pack scaffold.",
  "tool_logs": [
    "create_pack -> mystery_hotel",
    "save_card -> mystery_hotel/character/receptionist"
  ],
  "selected_pack_id": "mystery_hotel",
  "state": {}
}
```

## Storage split

Current and target design:
- Pack manifest and card files: file storage
- Designer AI session state: database-backed repository

This split is intentional and should remain true when the project migrates from the local sqlite transition repository to PostgreSQL.
