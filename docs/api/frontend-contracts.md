# Frontend Contracts

This document defines the current frontend-side contract expectations for the new
Next.js application.

## Current Status

- Frontend workspace: `frontend/`
- Current implementation stage: componentized shell with API client abstraction
- Live backend integration: read paths and core write paths are wired, with mock fallback for initial reads when FastAPI is not reachable

## Frontend Routes

### `/login`

Purpose:
- Sign in and establish the bearer-token cookie used by authenticated pages.

Primary backend dependencies:
- `POST /auth/login`
- `GET /auth/me`

### `/register`

Purpose:
- Create an account and establish the bearer-token cookie.

Primary backend dependencies:
- `POST /auth/register`
- `GET /auth/me`

### `/sessions`

Purpose:
- Session management

Responsibilities:
- Render save-slot list
- Switch the left workspace into an in-page create-session draft state
- Render current-session summary
- Start and save a new session from the in-page draft workflow
- Load pack-scoped UI template options during create-session flow
- Optionally bind selected `ui_template_id` when creating session
- Trigger `load session`
- Trigger `duplicate session`
- Trigger `archive session`

Primary backend dependencies:
- `GET /auth/me`
- `GET /game/sessions`
- `GET /packs`
- `POST /game/start`
- `POST /game/load`
- `POST /game/sessions/{slot_id}/duplicate`
- `POST /game/sessions/{slot_id}/archive`
- `GET /packs/{pack_id}/ui-templates`

### `/`

Purpose:
- Main game view

Responsibilities:
- Render session navigation shell
- Render collapsible top control drawer
- Render narration feed (incremental stream deltas + finalized turn result)
- Render command composer
- Render left-sidebar inspector groups
- Provide UI Agent controls in sidebar (manual/auto mode, N-turn auto interval, update/rebuild)
- Render generated UI floating panels and per-panel visibility toggles
- Render the authenticated account block in the shared sidebar
- Trigger sign-out from the shared sidebar

Primary backend dependencies:
- `GET /auth/me`
- `GET /game/state`
- `POST /game/step`
- `POST /game/step/stream`
- `POST /game/load`
- `PATCH /game/ui-mode`
- `PATCH /game/ui-auto-update`
- `POST /game/ui/update`
- `POST /game/ui/generate`
- `PATCH /game/ui/visibility`

Turn-execution expectation:
- narration is updated every turn and may arrive before ops processing finishes.
- world-state mutations (`validated_ops`) are cadence-driven and run every N turns.
- N is backend-configured by `TEXTRPG_OPS_EVERY_N_TURNS` (default `3`).
- frontend should treat `result.narration` as always-fresh, while `result.validated_ops` may update less frequently.

### `/packs`

Purpose:
- Pack management

Responsibilities:
- Render installed pack list
- Toggle pack enable state
- Remove local packs
- Export a pack to the local runtime exports directory
- Manage pack-scoped UI templates (list/create/delete)
- Show template usage count (`sessions_in_use`) and block delete when template is still bound by active sessions
- Reserve install-from-URL and ZIP upload regions for later file-based endpoints
- Reflect the authenticated user's default enabled-pack set

Primary backend dependencies:
- `GET /auth/me`
- `GET /packs`
- `PATCH /packs/{pack_id}/enabled`
- `DELETE /packs/{pack_id}`
- `POST /packs/{pack_id}/export`
- `GET /packs/{pack_id}/ui-templates`
- `POST /packs/{pack_id}/ui-templates`
- `DELETE /packs/{pack_id}/ui-templates/{template_id}`

### `/settings`

Purpose:
- Runtime settings management

Responsibilities:
- Render LLM settings form
- Save LLM settings
- Render current settings preview
- Reflect the authenticated user's stored runtime settings

Primary backend dependencies:
- `GET /auth/me`
- `GET /settings/llm`
- `PUT /settings/llm`

### `/card-designer`

Purpose:
- AI-assisted pack and card authoring workbench

Responsibilities:
- render three-column designer layout
- edit or create one card
- browse existing cards with filtering
- reload and clear Existing Cards filters from the library panel
- create a new pack manifest
- manage a persisted Pack Builder Agent session
- render Pack Builder write-target indicator (`pack_id` + pack name)
- render pending `batch_save_cards` confirmation payload as collapsed card previews (title-first)

Primary backend dependencies:
- `GET /auth/me`
- `GET /card-designer/packs`
- `POST /card-designer/packs`
- `GET /card-designer/packs/{pack_id}/card-types`
- `GET /card-designer/packs/{pack_id}/cards`
- `GET /card-designer/packs/{pack_id}/cards/{card_path}`
- `POST /card-designer/packs/{pack_id}/cards/template`
- `POST /card-designer/packs/{pack_id}/cards`
- `POST /card-designer/cards/validate`
- `DELETE /card-designer/packs/{pack_id}/cards/{card_path}`
- `POST /card-designer/agent/sessions`
- `GET /card-designer/agent/sessions/{session_id}`
- `POST /card-designer/agent/sessions/{session_id}/messages`

## Frontend Data Contract Source

Canonical frontend-facing types currently live in:
- `frontend/lib/api-contract.ts`

Current frontend data access entrypoints live in:
- `frontend/lib/api.ts`

Current frontend write entrypoints live in:
- `frontend/lib/api.ts#login`
- `frontend/lib/api.ts#register`
- `frontend/lib/api.ts#logout`
- `frontend/lib/api.ts#startGameSession`
- `frontend/lib/api.ts#loadGameSession`
- `frontend/lib/api.ts#duplicateGameSession`
- `frontend/lib/api.ts#archiveGameSession`
- `frontend/lib/api.ts#stepGameSession`
- `frontend/lib/api.ts#stepGameSessionStream`
- `frontend/lib/api.ts#setPackEnabled`
- `frontend/lib/api.ts#removePack`
- `frontend/lib/api.ts#exportPack`
- `frontend/lib/api.ts#updateLLMSettings`
- `frontend/lib/api.ts#getDesignerPacks`
- `frontend/lib/api.ts#createDesignerPack`
- `frontend/lib/api.ts#getDesignerCardTypes`
- `frontend/lib/api.ts#getDesignerCards`
- `frontend/lib/api.ts#loadDesignerCard`
- `frontend/lib/api.ts#getDesignerCardTemplate`
- `frontend/lib/api.ts#saveDesignerCard`
- `frontend/lib/api.ts#validateDesignerCard`
- `frontend/lib/api.ts#deleteDesignerCard`
- `frontend/lib/api.ts#createDesignerAgentSession`
- `frontend/lib/api.ts#getDesignerAgentSession`
- `frontend/lib/api.ts#sendDesignerAgentMessage`

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

Additional state fields now used by Play:
- `StateView.ui_template_id`
- `StateView.ui_variable_values`
- `StateView.ui_panel_visibility`

Template contract note:
- `UiTemplateRecord.sessions_in_use` is used by Pack Manager delete controls to prevent occupied-template deletion.
The frontend still normalizes fallback values when the backend is unavailable.

## Runtime Behavior

- The frontend first attempts to read from the FastAPI backend.
- Card Designer library/session reads now use fail-fast fetches (`requiredJsonFetch`) and surface backend/auth errors directly instead of silently falling back to empty lists.
- Selected generic views still normalize limited fallback values for local development.
- Client-side write actions do not use mock fallbacks. Failed writes surface an error message in the UI.
- Authenticated server-rendered pages now expect a `textrpg_token` cookie to be present.
- `/`, `/sessions`, `/packs`, `/settings`, and `/card-designer` redirect to `/login` when the token is missing or does not resolve to a current user.

Environment variables:
- `NEXT_PUBLIC_API_BASE_URL`
- `API_BASE_URL`

Production deployment note:
- When the frontend is deployed on `https://textrpg.tech`, the backend must allow that origin
  through FastAPI CORS configuration.
- The current backend defaults already include `https://textrpg.tech` and
  `https://www.textrpg.tech`.
- Extra frontend origins can be added through `TEXTRPG_CORS_ALLOW_ORIGINS`.

## Current Limitation

- Pack install-from-URL and ZIP upload remain placeholder UI because file upload and remote fetch endpoints are not available yet.
- Pack export currently returns a local filesystem path instead of a streamed browser download.
- Pack enable/disable is user-scoped, while remove/export still operate on the shared installed-pack inventory.
