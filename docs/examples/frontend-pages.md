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
- `Start` routes to `/setup`
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

## Session Setup View

Route:
- `/setup`

Key regions:
- session bootstrap header
- shared left sidebar with account block
- shared collapsible sidebar handle
- three-step preflight strip
- slot and language cards
- selected packs summary card
- runtime summary card
- launch preview card
- environment/launch checklist card
- start-session action and inline setup error feedback

Current data sources:
- `frontend/lib/api.ts#getGameStateView`
- `frontend/lib/api.ts#getSetupBootstrapView`
- `frontend/lib/api.ts#getPacks`
- `frontend/lib/api.ts#getLLMSettings`
