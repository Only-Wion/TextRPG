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
- Manage one authenticated user's game session lifecycle and turn progression.

Methods:

### `start_new_game(user_id, save_slot, pack_ids=None, language=None) -> None`

Behavior:
- Enables the requested packs for the session bootstrap path.
- Builds the runtime session.
- Resets the persisted user-scoped chat history for the target slot.
- Schedules UI generation for the new session.

Inputs:
- `user_id: str`
- `save_slot: str`
- `pack_ids: list[str] | None`
- `language: str | None`
- `ui_template_id: str | None` (optional)

Raises:
- `ValueError` for invalid user input.
- `RuntimeError` for unrecoverable startup issues.

### `load_game(user_id, save_slot, language=None) -> None`

Behavior:
- Loads an existing save slot into the active runtime session.
- Rehydrates chat history from the user-scoped repository when available.
- Backfills the user-scoped chat history repository from legacy local save data when needed.
- Rehydrates cached UI panel definitions.

Inputs:
- `user_id: str`
- `save_slot: str`
- `language: str | None`

Raises:
- `ValueError`
- `RuntimeError`

### `step(user_id, input_text) -> dict`

Behavior:
- Advances the game by one turn.
- Updates runtime state.
- Persists chat history into the user-scoped chat-history repository.
- Persists current session summary metadata.
- Refreshes world facts.
- Refreshes or schedules UI panel updates depending on UI mode.

Inputs:
- `user_id: str`
- `input_text: str`

Returns:
- Turn result payload including narration, validated ops, and any graph output fields.

Raises:
- `RuntimeError` when no session has been started or loaded.

### `get_current_state_view(user_id) -> dict`

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
- `ui_template_id`
- `ui_variable_values`
- `ui_panel_visibility`
- `save_slot`
- `ui_generation_status`
- `ui_update_status`
- `ui_update_mode`
- `ui_auto_update_every`
- `enabled_packs`
- `location_label`
- `storage_backend_label`

### `list_sessions(user_id) -> dict`

Behavior:
- Returns the session inventory view used by the `/sessions` page.
- Reads database-backed session summaries when available.
- Falls back to filesystem-derived summaries only for slots that have not been synchronized yet.
- Filters the session inventory to slots owned by the authenticated user.

Returns canonical fields:
- `selected_slot`
- `backend_status`
- `storage_backend`
- `last_sync_label`
- `sessions`

### `duplicate_session(user_id, source_slot, target_slot=None) -> dict`

Behavior:
- Copies a save slot to a new slot directory.
- Auto-generates a target slot id when `target_slot` is omitted.
- Returns the refreshed session inventory view with the new slot selected.

Inputs:
- `user_id: str`
- `source_slot: str`
- `target_slot: str | None`

### `archive_session(user_id, save_slot) -> dict`

Behavior:
- Moves a save slot out of the active saves directory into the local archives directory.
- Releases active runtime resources before archiving the currently loaded slot.
- Clears the active in-memory session when archiving the currently loaded slot.
- Returns the refreshed session inventory view after removal.

Inputs:
- `user_id: str`
- `save_slot: str`

### `set_language(user_id, language) -> None`

Behavior:
- Updates language preference on the active session state.

### `set_ui_update_mode(user_id, mode) -> None`

Behavior:
- Sets UI update strategy to `manual` or `auto`.

### `set_ui_auto_update_every(user_id, turns) -> None`

Behavior:
- Sets the turn interval for auto UI updates.

### `trigger_ui_generation(user_id, force=False) -> None`

Behavior:
- Triggers asynchronous UI panel generation.

### `trigger_ui_update(user_id) -> None`

Behavior:
- Triggers asynchronous UI panel update.

### `set_ui_panel_visibility(user_id, panel_id, visible) -> None`

Behavior:
- Updates one panel visibility flag for the active session and persists binding state.

### `bind_session_ui_template(user_id, save_slot, pack_id, template_id) -> dict`

Behavior:
- Applies selected pack UI template to target session and persists session binding.

### `list_pack_ui_templates(user_id, pack_id) -> list[dict]`
### `create_pack_ui_template(user_id, pack_id, name, template_payload=None, variable_template=None) -> dict`
### `delete_pack_ui_template(user_id, pack_id, template_id) -> None`

## AuthService

Purpose:
- Manage account registration, login, token lookup, and logout.

Methods:

### `register(email, username, password) -> dict`

Returns:
- `user`
- `access_token`
- `token_type`

### `login(email_or_username, password) -> dict`

Returns:
- `user`
- `access_token`
- `token_type`

### `get_current_user(token) -> dict`

Behavior:
- Resolves the authenticated user from the bearer token.

### `logout(token) -> None`

Behavior:
- Revokes the current token.

## PackService

Purpose:
- Manage pack lifecycle and pack content from the application layer.

Methods:

### `list_packs(user_id) -> list[dict]`

Returns pack records with:
- `pack_id`
- `name`
- `version`
- `author`
- `description`
- `cards_root`
- `enabled`
- `source`

Notes:
- `enabled` is resolved from the authenticated user's default pack-state repository.

### `install_pack_from_url(url) -> dict`
### `install_pack_from_zip(path) -> dict`
### `remove_pack(pack_id) -> None`
### `enable_pack(user_id, pack_id, enabled) -> None`
### `export_pack(pack_id, output_path) -> None`
### `export_pack_to_runtime_exports(pack_id) -> dict`
### `create_pack(manifest) -> None`
### `export_pack_manifest(data) -> None`

Notes:
- For Card Designer create-pack workflows, callers no longer need to provide `cards_root`.
- The backend normalizes `cards_root` to `cards` when omitted.

Notes:
- `remove_pack(pack_id)` rejects builtin packs.
- `export_pack_to_runtime_exports(pack_id)` writes a ZIP to the local runtime exports directory
  and returns:
  - `ok`
  - `pack_id`
  - `export_path`
- `enable_pack(user_id, pack_id, enabled)` updates the authenticated user's default pack set.

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

UI template methods:
- `list_ui_templates(user_id, pack_id) -> list[dict]`
- `create_ui_template(user_id, pack_id, name, template_payload, variable_template) -> dict`
- `delete_ui_template(user_id, pack_id, template_id) -> None`

## CardDesignerService

Purpose:
- Provide the authenticated Card Designer workbench use case boundary.

Methods:

### `list_packs(user_id) -> list[dict]`
### `create_pack(user_id, manifest) -> dict`
### `list_card_types(user_id, pack_id) -> list[str]`
### `list_cards(user_id, pack_id, category=None, keyword=None) -> list[dict]`
### `load_card(user_id, pack_id, card_path) -> dict`
### `get_card_template(user_id, card_type) -> dict`
### `save_card(user_id, pack_id, card_type, card_id, frontmatter, body, original_path=None) -> dict`
### `validate_card(user_id, frontmatter, body) -> None`
### `delete_card(user_id, pack_id, card_path) -> None`

AI session methods:
- `create_agent_session(user_id, pack_id=None) -> dict`
- `get_agent_session(user_id, session_id) -> dict`
- `send_agent_message(user_id, session_id, message) -> dict`

Behavior notes:
- Pack and card files remain filesystem-backed.
- Card Designer AI/draft session state is persisted through the designer-session repository.
- The current implementation reuses the existing Pack Builder Agent state shape and tool loop.
- `send_agent_message` binds the authenticated user's runtime LLM settings for each call before invoking the Pack Builder Agent.
- Agent write actions (`save_card` / `batch_save_cards`) synchronize `state.selected_pack_id` to the resolved write target pack so UI refreshes query the correct pack.

## SettingsService

Purpose:
- Manage runtime LLM-related settings.

Methods:

### `get_llm_settings(user_id) -> dict`

Returns public settings fields only:
- `provider`
- `model_name`
- `embedding_model`
- `base_url`
- `api_key_set`
- `use_mock_llm`
- `force_fake_embeddings`

### `update_llm_settings(user_id, payload) -> dict`

Behavior:
- Validates and persists runtime LLM settings for one authenticated user.
- Returns the public projection of the active settings.

## Transitional Ownership

Current code ownership:
- `SessionService` wraps the session-related methods of `GameService`
- `PackService` wraps the pack-related methods of `GameService`
- `SettingsService` wraps the settings-related methods of `GameService`

Transition rule:
- New API code must depend on these service contracts, not on `GameService` directly.
