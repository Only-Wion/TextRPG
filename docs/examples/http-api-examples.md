# HTTP API Examples

## Start Game

Request:
```http
POST /game/start
Content-Type: application/json

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

## Step Turn

Request:
```http
POST /game/step
Content-Type: application/json

{
  "input_text": "look around"
}
```

Response:
```json
{
  "result": {
    "narration": "You look around."
  },
  "state_view": {
    "turn_id": 1,
    "chat_history": [
      {
        "role": "user",
        "content": "look around"
      },
      {
        "role": "assistant",
        "content": "You look around."
      }
    ]
  }
}
```

## List Sessions

Request:
```http
GET /game/sessions
```

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
      "location_label": "Unknown",
      "turn_count": 0,
      "updated_label": "2026-03-25 11:42"
    }
  ]
}
```

Notes:
- The response is sourced from the authenticated user's session metadata inventory.
- Missing repository rows are backfilled from local save-slot metadata before the response is returned.

## Enable Pack

Request:
```http
PATCH /packs/starter_kingdom/enabled
Content-Type: application/json

{
  "enabled": true
}
```

Response:
```json
{
  "ok": true
}
```

## Set UI Mode

Request:
```http
PATCH /game/ui-mode
Content-Type: application/json

{
  "mode": "auto"
}
```

Response:
```json
{
  "ok": true
}
```

## Trigger UI Generation

Request:
```http
POST /game/ui/generate
Content-Type: application/json

{
  "force": true
}
```

Response:
```json
{
  "ok": true
}
```

## Read LLM Settings

Request:
```http
GET /settings/llm
```

Response:
```json
{
  "provider": "custom",
  "model_name": "gpt-4o-mini",
  "embedding_model": "text-embedding-3-small",
  "base_url": "",
  "api_key_set": false,
  "use_mock_llm": true,
  "force_fake_embeddings": false
}
```
