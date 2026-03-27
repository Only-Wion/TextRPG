# Frontend Page Ownership

This document records the intended responsibility split for each frontend page.
It exists to keep future UI work aligned during iterative vibecoding.

## Principles

1. One page, one primary job.
2. Editing and management pages should not be duplicated inside bootstrap pages.
3. Cross-page summaries are allowed; cross-page full editors are not.
4. If a page begins to own a second major workflow, split it.

## Route Ownership

### `/login`

Primary job:
- sign in

Owns:
- credential submission
- bearer-token bootstrap
- redirect into the authenticated app shell after a successful sign-in

Must not own:
- session management
- gameplay

### `/register`

Primary job:
- account creation

Owns:
- registration form
- initial bearer-token bootstrap
- redirect into the authenticated app shell after a successful registration

Must not own:
- session management
- gameplay

### `/sessions`

Primary job:
- Session inventory and session lifecycle entry.

Owns:
- session list
- in-page `new session` draft mode
- selected-session summary
- `load session`
- `save session` from the in-page create workflow
- `duplicate session`
- `archive session`

May show:
- lightweight health/status summary
- current authenticated user in the shared sidebar

Must not own:
- turn-by-turn gameplay
- full pack editing
- full LLM/settings editing

Current backend dependencies:
- `GET /auth/me`
- `GET /game/sessions`
- `GET /packs`
- `POST /game/start`
- `POST /game/load`
- `POST /game/sessions/{slot_id}/duplicate`
- `POST /game/sessions/{slot_id}/archive`

### `/`

Primary job:
- Active play.

Owns:
- narration feed
- command input
- current world facts
- current UI/debug state

May show:
- session summary
- load/new shortcuts
- a collapsible top control drawer
- a left-sidebar inspector with collapsible sections
- current authenticated user and logout action in the shared sidebar

Must not own:
- session inventory management
- pack installation/export
- runtime settings editing

Current backend dependencies:
- `GET /auth/me`
- `GET /game/state`
- `POST /game/step`
- `POST /game/load`

Current frontend behaviors:
- `Start` shortcut routes to `/setup`
- `Load` shortcut routes to `/sessions`
- top control drawer expands/collapses locally via handle arrows
- shared left sidebar expands/collapses locally via a vertical handle
- shared left sidebar includes the current user account block and a sign-out action
- world facts, UI agent, and debug info live in left-sidebar inspector groups
- the left sidebar scrolls independently when its content exceeds viewport height
- transcript auto-scrolls to the latest message after each turn

### `/packs`

Primary job:
- Pack management.

Owns:
- installed pack list
- enable/disable
- remove local packs
- export local pack archive
- future install from URL
- future ZIP upload
- the authenticated user's default enabled-pack set

May show:
- selected/default export candidate

Must not own:
- session start flow
- runtime model settings
- active gameplay

Current backend dependencies:
- `GET /auth/me`
- `GET /packs`
- `PATCH /packs/{pack_id}/enabled`
- `DELETE /packs/{pack_id}`
- `POST /packs/{pack_id}/export`

Pack-state note:
- enable/disable is user-scoped and primarily affects future session bootstrap defaults
- remove/export still act on the shared installed-pack inventory

Missing backend support:
- install from URL
- ZIP upload

Current intentional UI placeholders:
- `Download & Install`
- `Upload pack ZIP`

### `/settings`

Primary job:
- Runtime settings management.

Owns:
- LLM provider/base URL/model configuration
- mock/fake embedding toggles
- save settings
- current settings preview

May show:
- current effective runtime summary

Must not own:
- pack editing
- session start flow
- active gameplay

Current backend dependencies:
- `GET /auth/me`
- `GET /settings/llm`
- `PUT /settings/llm`

### `/setup`

Primary job:
- Pre-flight review and start.

Owns:
- slot choice for new start
- language choice
- launch preview
- environment check
- start action

May show:
- selected pack summary
- selected runtime/settings summary
- links or shortcuts to `/packs` and `/settings`

Must not own:
- full pack manager UI
- full runtime settings form
- session inventory management

Current backend dependencies:
- `GET /auth/me`
- `GET /game/state`
- `GET /packs`
- `GET /settings/llm`
- `POST /game/start`

### `/card-designer`

Primary job:
- pack and card authoring workbench

Owns:
- create/edit card workflow
- existing-card browsing and quick load
- create-pack workflow
- Pack Builder Agent conversation and tool execution view

May show:
- current authenticated user in the shared sidebar
- pack summaries and draft state summaries

Must not own:
- active gameplay
- session inventory management
- runtime settings editing

Current backend dependencies:
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

Design note:
- `/setup` should summarize configuration, not replace `/packs` or `/settings`.

## Local Dev Behavior

- Read-only page bootstrap fetches can fall back to mock data when the backend is unavailable.
- Browser-triggered write actions require the FastAPI backend to be running and reachable from
  `http://127.0.0.1:3000`.
- If local CORS is misconfigured, the browser will surface these failures as `Failed to fetch`.
- The deployed frontend at `https://textrpg.tech` depends on the same backend CORS allowlist.
- If production login or register requests fail with `Failed to fetch`, first verify:
  - `frontend/.env.production` points at `https://api.textrpg.tech`
  - the backend has been restarted after CORS changes

## Shared Sidebar Contract

- `/`, `/setup`, `/sessions`, `/packs`, and `/settings` all use the shared `AppSidebar`.
- The shared sidebar owns:
  - page navigation
  - current authenticated user identity and logout action when available
  - session health summary when provided
  - inspector sections when provided
  - local expand/collapse behavior via a vertical handle on the sidebar edge
- When sidebar content grows taller than the viewport, only the sidebar scroll region should move.
- Collapsing the sidebar must not change route ownership or hide page-level actions in the main workspace.

## Page Relationship Rules

1. `/login` and `/register` bootstrap authenticated access.
1. `/`, `/sessions`, `/packs`, `/settings`, `/setup`, and `/card-designer` require an authenticated user context.
1. `/setup` summarizes choices and launches.
2. `/packs` edits world modules.
3. `/settings` edits runtime behavior.
4. `/sessions` manages existing saves.
5. `/card-designer` owns pack/card authoring workflows.
6. `/` is only for active play.

## Trigger Checklist For Future Changes

Update this file if any of the following changes:
- a page gains a new write action
- a page stops owning an action
- a page starts summarizing another page's data
- a new frontend route is added
- a backend endpoint becomes required for a page
