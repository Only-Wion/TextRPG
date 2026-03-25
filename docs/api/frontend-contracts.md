# Frontend Contracts

This document defines the current frontend-side contract expectations for the new
Next.js application.

## Current Status

- Frontend workspace: `frontend/`
- Current implementation stage: componentized shell with API client abstraction
- Live backend integration: read paths and core write paths are wired, with mock fallback for initial reads when FastAPI is not reachable

## Frontend Routes

### `/sessions`

Purpose:
- Session management

Responsibilities:
- Render save-slot list
- Switch the left workspace into an in-page create-session draft state
- Render current-session summary
- Start and save a new session from the in-page draft workflow
- Trigger `load session`
- Trigger `duplicate session`
- Trigger `archive session`

Primary backend dependencies:
- `GET /game/sessions`
- `GET /packs`
- `POST /game/start`
- `POST /game/load`
- `POST /game/sessions/{slot_id}/duplicate`
- `POST /game/sessions/{slot_id}/archive`

### `/`

Purpose:
- Main game view

Responsibilities:
- Render session navigation shell
- Render collapsible top control drawer
- Render narration feed
- Render command composer
- Render left-sidebar inspector groups

Primary backend dependencies:
- `GET /game/state`
- `POST /game/step`
- `POST /game/load`

### `/packs`

Purpose:
- Pack management

Responsibilities:
- Render installed pack list
- Toggle pack enable state
- Remove local packs
- Export a pack to the local runtime exports directory
- Reserve install-from-URL and ZIP upload regions for later file-based endpoints

Primary backend dependencies:
- `GET /packs`
- `PATCH /packs/{pack_id}/enabled`
- `DELETE /packs/{pack_id}`
- `POST /packs/{pack_id}/export`

### `/settings`

Purpose:
- Runtime settings management

Responsibilities:
- Render LLM settings form
- Save LLM settings
- Render current settings preview

Primary backend dependencies:
- `GET /settings/llm`
- `PUT /settings/llm`

### `/setup`

Purpose:
- Session bootstrap and launch review

Responsibilities:
- new-session slot choice
- language choice
- selected pack summary
- selected runtime summary
- launch preview
- launch action

Primary backend dependencies:
- `GET /game/state`
- `GET /packs`
- `GET /settings/llm`
- `POST /game/start`

## Frontend Data Contract Source

Canonical frontend-facing types currently live in:
- `frontend/lib/api-contract.ts`

Current frontend data access entrypoints live in:
- `frontend/lib/api.ts`

Current frontend write entrypoints live in:
- `frontend/lib/api.ts#startGameSession`
- `frontend/lib/api.ts#loadGameSession`
- `frontend/lib/api.ts#duplicateGameSession`
- `frontend/lib/api.ts#archiveGameSession`
- `frontend/lib/api.ts#stepGameSession`
- `frontend/lib/api.ts#setPackEnabled`
- `frontend/lib/api.ts#removePack`
- `frontend/lib/api.ts#exportPack`
- `frontend/lib/api.ts#updateLLMSettings`

Mock fallback data used for local UI development lives in:
- `frontend/lib/mock-data.ts`

These types mirror:
- `docs/data-contracts/game-session.md`
- `docs/data-contracts/pack-and-settings.md`

Note:
- `StateView.enabled_packs`
- `StateView.location_label`
- `StateView.storage_backend_label`

are now part of the FastAPI `GET /game/state` response contract.
The frontend still normalizes fallback values when the backend is unavailable.

## Runtime Behavior

- The frontend first attempts to read from the FastAPI backend.
- If the backend is unavailable, the current implementation falls back to local mock data.
- This keeps local page development unblocked before full backend integration.
- Client-side write actions do not use mock fallbacks. Failed writes surface an error message in the UI.

Environment variables:
- `NEXT_PUBLIC_API_BASE_URL`
- `API_BASE_URL`

## Current Limitation

- Pack install-from-URL and ZIP upload remain placeholder UI because file upload and remote fetch endpoints are not available yet.
- Pack export currently returns a local filesystem path instead of a streamed browser download.
