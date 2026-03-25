# Frontend Page Ownership

This document records the intended responsibility split for each frontend page.
It exists to keep future UI work aligned during iterative vibecoding.

## Principles

1. One page, one primary job.
2. Editing and management pages should not be duplicated inside bootstrap pages.
3. Cross-page summaries are allowed; cross-page full editors are not.
4. If a page begins to own a second major workflow, split it.

## Route Ownership

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

Must not own:
- turn-by-turn gameplay
- full pack editing
- full LLM/settings editing

Current backend dependencies:
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

Must not own:
- session inventory management
- pack installation/export
- runtime settings editing

Current backend dependencies:
- `GET /game/state`
- `POST /game/step`
- `POST /game/load`

Current frontend behaviors:
- `Start` shortcut routes to `/setup`
- `Load` shortcut routes to `/sessions`
- top control drawer expands/collapses locally via handle arrows
- shared left sidebar expands/collapses locally via a vertical handle
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

May show:
- selected/default export candidate

Must not own:
- session start flow
- runtime model settings
- active gameplay

Current backend dependencies:
- `GET /packs`
- `PATCH /packs/{pack_id}/enabled`
- `DELETE /packs/{pack_id}`
- `POST /packs/{pack_id}/export`

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
- `GET /game/state`
- `GET /packs`
- `GET /settings/llm`
- `POST /game/start`

Design note:
- `/setup` should summarize configuration, not replace `/packs` or `/settings`.

## Local Dev Behavior

- Read-only page bootstrap fetches can fall back to mock data when the backend is unavailable.
- Browser-triggered write actions require the FastAPI backend to be running and reachable from
  `http://127.0.0.1:3000`.
- If local CORS is misconfigured, the browser will surface these failures as `Failed to fetch`.

## Shared Sidebar Contract

- `/`, `/setup`, `/sessions`, `/packs`, and `/settings` all use the shared `AppSidebar`.
- The shared sidebar owns:
  - page navigation
  - session health summary when provided
  - inspector sections when provided
  - local expand/collapse behavior via a vertical handle on the sidebar edge
- When sidebar content grows taller than the viewport, only the sidebar scroll region should move.
- Collapsing the sidebar must not change route ownership or hide page-level actions in the main workspace.

## Page Relationship Rules

1. `/setup` summarizes choices and launches.
2. `/packs` edits world modules.
3. `/settings` edits runtime behavior.
4. `/sessions` manages existing saves.
5. `/` is only for active play.

## Trigger Checklist For Future Changes

Update this file if any of the following changes:
- a page gains a new write action
- a page stops owning an action
- a page starts summarizing another page's data
- a new frontend route is added
- a backend endpoint becomes required for a page
