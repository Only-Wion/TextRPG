# Frontend Page Examples

## Main Game View

Route:
- `/`

Key regions:
- sidebar navigation
- account block with sign-out action
- collapsible shared sidebar handle
- collapsible top control drawer
- left-sidebar inspector groups for world facts, UI agent, and debug info
- fixed-height narration transcript with internal scroll
- sticky bottom command composer
- inline command error feedback

Current interactive behaviors:
- transcript auto-scrolls to the latest message
- submitted turns animate the final narration into the transcript after the turn response returns
- `Start` routes to `/sessions?mode=create`
- `Load` routes to `/sessions`
- shared sidebar handle collapses and expands the left rail locally
- top drawer handle expands/collapses the control strip locally
- the left sidebar keeps its own scroll region when inspector content grows taller than the viewport

Current data sources:
- `frontend/lib/api.ts#getGameStateView`
- fallback: `frontend/lib/mock-data.ts#createMockStateView`

## Sessions View

Route:
- `/sessions`

Key regions:
- left navigation
- account block with sign-out action
- shared collapsible sidebar handle
- save-slot list
- in-place create-session panel
- current selection summary
- quick actions
- session notes

Current data sources:
- `frontend/lib/api.ts#getSessionManagerView`
- primary backend route: `GET /game/sessions`
- `frontend/lib/api.ts#getPacks`
- `frontend/lib/api.ts#startGameSession`
- `frontend/lib/api.ts#loadGameSession`
- `frontend/lib/api.ts#duplicateGameSession`
- `frontend/lib/api.ts#archiveGameSession`
- fallback: `frontend/lib/mock-data.ts#createMockSessionManagerView`

## Pack Manager View

Route:
- `/packs`

Key regions:
- shared left sidebar with account block
- installed pack table
- shared collapsible sidebar handle
- enable / disable toggle
- remove action
- install from URL
- install from ZIP
- export pack

Current data sources:
- `frontend/lib/api.ts#getPacks`
- `frontend/lib/api.ts#setPackEnabled`
- `frontend/lib/api.ts#removePack`
- `frontend/lib/api.ts#exportPack`

## Settings View

Route:
- `/settings`

Key regions:
- shared left sidebar with account block
- settings form
- shared collapsible sidebar handle
- mock toggles
- save action
- current settings preview

Current data sources:
- `frontend/lib/api.ts#getLLMSettings`
- `frontend/lib/api.ts#updateLLMSettings`

## Card Designer View

Route:
- `/card-designer`

Key regions:
- shared left sidebar with account block
- shared collapsible sidebar handle
- card editor panel
- existing cards / structure panel
- Pack Builder Agent panel

Workspace states:
- default edit workbench
- create-pack workbench

Current data sources:
- `GET /card-designer/packs`
- `POST /card-designer/packs`
- `GET /card-designer/packs/{pack_id}/card-types`
- `GET /card-designer/packs/{pack_id}/cards`
- `GET /card-designer/packs/{pack_id}/cards/{card_path}`
- `GET /card-designer/packs/{pack_id}/canvas-state`
- `PUT /card-designer/packs/{pack_id}/canvas-state`
- `POST /card-designer/packs/{pack_id}/cards/template`
- `POST /card-designer/packs/{pack_id}/cards`
- `POST /card-designer/cards/validate`
- `DELETE /card-designer/packs/{pack_id}/cards/{card_path}`
- `POST /card-designer/agent/sessions`
- `GET /card-designer/agent/sessions/{session_id}`
- `POST /card-designer/agent/sessions/{session_id}/messages`
