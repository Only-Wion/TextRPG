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
- selected-session summary
- `load session`
- future `duplicate session`
- future `archive session`

May show:
- lightweight health/status summary

Must not own:
- turn-by-turn gameplay
- full pack editing
- full LLM/settings editing

Current backend dependencies:
- `GET /game/sessions`
- `POST /game/load`

Missing backend support:
- duplicate session
- archive session

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

Must not own:
- session inventory management
- pack installation/export
- runtime settings editing

Current backend dependencies:
- `GET /game/state`
- `POST /game/step`
- `POST /game/load`

### `/packs`

Primary job:
- Pack management.

Owns:
- installed pack list
- enable/disable
- future install from URL
- future ZIP upload
- future export

May show:
- selected/default export candidate

Must not own:
- session start flow
- runtime model settings
- active gameplay

Current backend dependencies:
- `GET /packs`
- `PATCH /packs/{pack_id}/enabled`

Missing backend support:
- install from URL
- ZIP upload
- export
- remove pack

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
