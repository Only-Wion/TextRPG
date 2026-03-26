# User And Auth Data Contract

This document defines the current account, token, and user-session ownership data model.

## User

Canonical fields:
- `id`
- `email`
- `username`

Password handling:
- passwords are never returned in API responses
- current local implementation stores:
  - `password_salt`
  - `password_hash`

## Access Token

Current contract:
- opaque bearer token

Response shape:
```json
{
  "access_token": "opaque-token",
  "token_type": "bearer"
}
```

Transport:
- `Authorization: Bearer <token>`

## User-Session Ownership

Purpose:
- bind save-slot identities to one account
- ensure `/game/sessions` only returns slots owned by the authenticated user

Canonical ownership fields:
- `user_id`
- `save_slot`
- `created_at`
- `updated_at`

## Local Storage Shape

Current local auth repository persists three logical tables:

### `users`
- `id`
- `email`
- `username`
- `password_salt`
- `password_hash`
- `created_at`
- `updated_at`

### `auth_tokens`
- `token_hash`
- `user_id`
- `created_at`

### `user_sessions`
- `user_id`
- `save_slot`
- `created_at`
- `updated_at`

### `user_llm_settings`
- `user_id`
- `provider`
- `model_name`
- `embedding_model`
- `base_url`
- `api_key`
- `use_mock_llm`
- `force_fake_embeddings`
- `updated_at`

### `user_pack_states`
- `user_id`
- `pack_id`
- `enabled`
- `updated_at`

### `user_session_metadata`
- `user_id`
- `save_slot`
- `language`
- `enabled_packs_json`
- `location_label`
- `turn_count`
- `updated_label`

### `user_chat_history`
- `user_id`
- `save_slot`
- `history_json`
- `updated_at`

## Planned PostgreSQL Mapping

Cloud migration target:
- `users`
- `auth_tokens` or `user_tokens`
- `user_sessions`
- `user_llm_settings`
- `user_pack_states`
- `user_session_metadata`
- `user_chat_history`

Reference files:
- `game/infrastructure/postgres/schema.sql`
- `docs/data-contracts/postgres-storage-model.md`
