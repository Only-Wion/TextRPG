# Game Session Data Contracts

This file defines the canonical shape of game-session-related payloads exposed across
application and API boundaries.

## StartGameRequest

```json
{
  "save_slot": "slot_001",
  "pack_ids": ["starter_kingdom"],
  "language": "zh"
}
```

Fields:
- `save_slot: string`
- `pack_ids: string[] | null`
- `language: string | null`

## LoadGameRequest

```json
{
  "save_slot": "slot_001",
  "language": "zh"
}
```

## DuplicateSessionRequest

```json
{
  "target_slot": "slot_001_copy_01"
}
```

Field notes:
- `target_slot` is optional.
- When omitted, the backend generates the next available copy slot id.

## StepRequest

```json
{
  "input_text": "check inventory"
}
```

## ChatMessage

```json
{
  "role": "user",
  "content": "check inventory"
}
```

Fields:
- `role: "user" | "assistant"`
- `content: string`

Storage notes:
- The authenticated user's active chat history is persisted in a user-scoped chat-history repository.
- Local save-slot files remain a compatibility fallback while the runtime is still in transitional storage mode.

## WorldFacts

```json
{
  "attrs": {
    "player": {
      "hp": "10"
    }
  },
  "edges": [
    {
      "subject_id": "player",
      "relation": "at",
      "object_id": "tavern",
      "ts": 1710000000,
      "confidence": 0.9,
      "source": "bootstrap"
    }
  ]
}
```

## StateView

This is the canonical frontend-safe session projection.

```json
{
  "turn_id": 1,
  "recent_messages": [],
  "chat_history": [],
  "narration": "",
  "world_facts": {
    "attrs": {},
    "edges": []
  },
  "allowed_actions": [],
  "retrieved_cards": [],
  "validated_ops": [],
  "errors": [],
  "custom_ui_panels": [],
  "save_slot": "slot_001",
  "ui_generation_status": "idle",
  "ui_update_status": "idle",
  "ui_update_mode": "manual",
  "ui_auto_update_every": 1,
  "enabled_packs": ["starter_kingdom"],
  "location_label": "Tavern",
  "storage_backend_label": "local"
}
```

Field notes:
- `retrieved_cards` is a list of card ids in the current state view, not full card objects.
- `validated_ops` is the validated and possibly rule-adjusted ops list.
- `errors` contains non-fatal validation and processing messages for the turn.
- `custom_ui_panels` is frontend-facing panel data, not raw planner prompts.
- `enabled_packs` is the active pack list for the loaded runtime session.
- `location_label` is a display-friendly location derived from world facts.
- `storage_backend_label` reflects the current runtime storage backend.

## SessionSummary

```json
{
  "slot_id": "slot_001",
  "language": "zh",
  "enabled_packs": ["starter_kingdom"],
  "location_label": "Tavern",
  "turn_count": 18,
  "updated_label": "2026-03-25 11:42"
}
```

Field notes:
- Session summaries are persisted in a user-scoped session metadata repository.
- The stored repository payload mirrors this API shape closely so `/game/sessions` stays stable across storage migrations.

## SessionManagerResponse

```json
{
  "selected_slot": "slot_001",
  "backend_status": "online",
  "storage_backend": "local",
  "last_sync_label": "just now",
  "sessions": []
}
```

Field notes:
- `selected_slot` points at the slot that should remain focused after the last session-management action.
- After duplicate, this is typically the newly created slot.
- After archive, this is the next available active slot or `slot_001` when none remain.

## StepResponse

```json
{
  "result": {
    "narration": "You look around the tavern."
  },
  "state_view": {
    "turn_id": 1
  }
}
```

## UiModeRequest

```json
{
  "mode": "manual"
}
```

Allowed values:
- `manual`
- `auto`

## UiAutoUpdateRequest

```json
{
  "turns": 1
}
```

## TriggerUiGenerationRequest

```json
{
  "force": true
}
```
