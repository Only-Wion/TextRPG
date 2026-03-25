# Application Service Contracts

This document defines the stable use-case interfaces that the API layer is allowed to
call.

Current implementation:
- API routes depend on `game/application/services.py`
- Those services currently delegate to the transitional `game/service/api.py`
- Future code changes should move internal logic out of `GameService` without changing
  the service contracts below

## General Rules

- API handlers call application services only.
- Application services return plain Python data structures or typed DTOs.
- Application services do not expose FastAPI request or response objects.
- When a method signature changes here, `docs/data-contracts/` and `docs/examples/`
  must be updated in the same change.

## SessionService

Purpose:
- Manage one game session lifecycle and turn progression.

Methods:

### `start_new_game(save_slot, pack_ids=None, language=None) -> None`

Behavior:
- Enables the requested packs for the session bootstrap path.
- Builds the runtime session.
- Schedules UI generation for the new session.

Inputs:
- `save_slot: str`
- `pack_ids: list[str] | None`
- `language: str | None`

Raises:
- `ValueError` for invalid user input.
- `RuntimeError` for unrecoverable startup issues.

### `load_game(save_slot, language=None) -> None`

Behavior:
- Loads an existing save slot into the active runtime session.
- Rehydrates chat history and cached UI panel definitions.

Inputs:
- `save_slot: str`
- `language: str | None`

Raises:
- `ValueError`
- `RuntimeError`

### `step(input_text) -> dict`

Behavior:
- Advances the game by one turn.
- Updates runtime state.
- Persists chat history.
- Refreshes world facts.
- Refreshes or schedules UI panel updates depending on UI mode.

Inputs:
- `input_text: str`

Returns:
- Turn result payload including narration, validated ops, and any graph output fields.

Raises:
- `RuntimeError` when no session has been started or loaded.

### `get_current_state_view() -> dict`

Behavior:
- Returns a frontend-safe session state view.
- Omits internal store handles and graph objects.

Returns canonical fields:
- `turn_id`
- `recent_messages`
- `chat_history`
- `narration`
- `world_facts`
- `allowed_actions`
- `retrieved_cards`
- `validated_ops`
- `errors`
- `custom_ui_panels`
- `save_slot`
- `ui_generation_status`
- `ui_update_status`
- `ui_update_mode`
- `ui_auto_update_every`
- `enabled_packs`
- `location_label`
- `storage_backend_label`

### `list_sessions() -> dict`

Behavior:
- Returns the session inventory view used by the `/sessions` page.
- Reads save-slot metadata when available.
- Falls back to filesystem timestamps and defaults for older save slots.

Returns canonical fields:
- `selected_slot`
- `backend_status`
- `storage_backend`
- `last_sync_label`
- `sessions`

### `duplicate_session(source_slot, target_slot=None) -> dict`

Behavior:
- Copies a save slot to a new slot directory.
- Auto-generates a target slot id when `target_slot` is omitted.
- Returns the refreshed session inventory view with the new slot selected.

Inputs:
- `source_slot: str`
- `target_slot: str | None`

### `archive_session(save_slot) -> dict`

Behavior:
- Moves a save slot out of the active saves directory into the local archives directory.
- Clears the active in-memory session when archiving the currently loaded slot.
- Returns the refreshed session inventory view after removal.

Inputs:
- `save_slot: str`

### `set_language(language) -> None`

Behavior:
- Updates language preference on the active session state.

### `set_ui_update_mode(mode) -> None`

Behavior:
- Sets UI update strategy to `manual` or `auto`.

### `set_ui_auto_update_every(turns) -> None`

Behavior:
- Sets the turn interval for auto UI updates.

### `trigger_ui_generation(force=False) -> None`

Behavior:
- Triggers asynchronous UI panel generation.

### `trigger_ui_update() -> None`

Behavior:
- Triggers asynchronous UI panel update.

## PackService

Purpose:
- Manage pack lifecycle and pack content from the application layer.

Methods:

### `list_packs() -> list[dict]`

Returns pack records with:
- `pack_id`
- `name`
- `version`
- `author`
- `description`
- `cards_root`
- `enabled`
- `source`

### `install_pack_from_url(url) -> dict`
### `install_pack_from_zip(path) -> dict`
### `remove_pack(pack_id) -> None`
### `enable_pack(pack_id, enabled) -> None`
### `export_pack(pack_id, output_path) -> None`
### `export_pack_to_runtime_exports(pack_id) -> dict`
### `create_pack(manifest) -> None`
### `export_pack_manifest(data) -> None`

Notes:
- `remove_pack(pack_id)` rejects builtin packs.
- `export_pack_to_runtime_exports(pack_id)` writes a ZIP to the local runtime exports directory
  and returns:
  - `ok`
  - `pack_id`
  - `export_path`

Card editing methods currently exposed through the same facade:
- `list_pack_card_types(pack_id) -> list[str]`
- `list_pack_cards(pack_id) -> list[path]`
- `load_card(path) -> dict`
- `create_card(pack_id, card_type, card_id, frontmatter, body) -> path`
- `save_card(pack_id, card_type, card_id, frontmatter, body, original_path=None) -> path`
- `update_card(path, frontmatter, body) -> None`
- `validate_card(frontmatter, body) -> None`
- `delete_card(pack_id, path) -> None`
- `get_card_template(card_type) -> dict`

## SettingsService

Purpose:
- Manage runtime LLM-related settings.

Methods:

### `get_llm_settings() -> dict`

Returns public settings fields only:
- `provider`
- `model_name`
- `embedding_model`
- `base_url`
- `api_key_set`
- `use_mock_llm`
- `force_fake_embeddings`

### `update_llm_settings(payload) -> dict`

Behavior:
- Validates and persists runtime LLM settings.
- Returns the public projection of the active settings.

## Transitional Ownership

Current code ownership:
- `SessionService` wraps the session-related methods of `GameService`
- `PackService` wraps the pack-related methods of `GameService`
- `SettingsService` wraps the settings-related methods of `GameService`

Transition rule:
- New API code must depend on these service contracts, not on `GameService` directly.
