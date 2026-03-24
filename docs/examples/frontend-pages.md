# Frontend Page Examples

## Main Game View

Route:
- `/`

Key regions:
- sidebar navigation
- hero session banner
- scene state strip
- narration feed
- command composer
- session and world summary rail
- inline command error feedback

Current data sources:
- `frontend/lib/api.ts#getGameStateView`
- fallback: `frontend/lib/mock-data.ts#createMockStateView`

## Sessions View

Route:
- `/sessions`

Key regions:
- left navigation
- save-slot list
- current selection summary
- quick actions
- session notes

Current data sources:
- `frontend/lib/api.ts#getSessionManagerView`
- primary backend route: `GET /game/sessions`
- `frontend/lib/api.ts#loadGameSession`
- fallback: `frontend/lib/mock-data.ts#createMockSessionManagerView`

## Pack Manager View

Route:
- `/packs`

Key regions:
- installed pack table
- enable / disable toggle
- install from URL
- install from ZIP
- export pack

Current data sources:
- `frontend/lib/api.ts#getPacks`
- `frontend/lib/api.ts#setPackEnabled`

## Settings View

Route:
- `/settings`

Key regions:
- settings form
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
