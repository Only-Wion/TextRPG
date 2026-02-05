# TextRPG

AI text adventure using LangChain + LangGraph with cards, rules, memory, overlays, and downloadable card packs.

## Quick start (CLI)

1) Activate conda env:

```
conda activate E:\TextRPG\.conda\envs\TextRPG-py311
```

2) Install deps:

```
pip install -r requirements.txt
```

3) Run the game:

```
python -m game.main
```

If `OPENAI_API_KEY` is not set, the game runs in mock-LLM mode.

## UI (Streamlit)

```
streamlit run ui/app.py
```

## Card packs

Packs are installed under `game/cards_packs/<pack_id>/<version>/`. Each pack zip must include `pack.json` (or `pack.yaml`) and a `cards_root` folder with the standard card layout.

Conflict priority: overlay > save_slot dynamic state > enabled pack > built-in cards.

## Card creation tutorial

### 1) Card basics

Each card is a `.md` file with YAML frontmatter + body text:

```
---
id: bartender
type: character
tags: [npc]
initial_relations:
  - subject_id: bartender
    relation: at
    object_id: tavern
hooks: []
---

The bartender polishes glasses and watches the room with a knowing gaze.
```

Required frontmatter fields:
- `id`: unique string across all loaded cards.
- `type`: one of `character | item | location | event | memory`.
- `tags`: list of strings.

Optional frontmatter fields:
- `initial_relations`: list of edges to bootstrap (subject_id, relation, object_id).
- `hooks`: free-form list of strings.

### 2) Folder structure

Cards live under:

```
game/cards/
  characters/
  items/
  locations/
  events/
  memories/
```

Examples:
- `game/cards/characters/bartender.md`
- `game/cards/items/rusty_key.md`
- `game/cards/locations/tavern.md`

### 3) Relations and rules

Relations are validated by `game/cards/card_logic.md`. For example:
- `at`: character -> location (only one per subject)
- `has`: character -> item (multiple allowed)

If you add new relation types, you must update `card_logic.md` accordingly.

### 4) Quick creation in the UI

Open the UI:

```
streamlit run ui/app.py
```

Then go to **Card Designer**:
- Choose a pack (or create a new pack).
- Select type and enter card id.
- Paste/edit YAML frontmatter and body.
- Click **Save Card**.

### 5) Overlay ops (optional)

If you want to modify runtime state via files, add an overlay card under:

```
game/cards/_overlay/
```

Overlay frontmatter format:

```
---
kind: overlay_ops
priority: 10
ops:
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: rusty_key
    confidence: 0.9
    source: overlay
---
```

The overlay ops will be merged each turn before validation.

## Overlay cheats / admin

Overlay ops live in `game/cards/_overlay/` (and in pack overlays). Each file contains frontmatter like:

```
---
kind: overlay_ops
priority: 10
ops:
  - type: AddEdge
    subject_id: player
    relation: has
    object_id: rusty_key
    confidence: 0.9
    source: overlay
---
```

During each turn, overlays are loaded and merged with LLM ops, then validated and applied. Edit overlays to "cheat" or adjust state. You can also use admin commands in the CLI:

```
/give player rusty_key
/teleport player tavern
/set bartender.mood angry
```

## Notes

- State snapshots are written to `data/saves/slot_001/state_snapshot/` each turn.
- SQLite is the source of truth for relationships and attributes.

conda activate E:\TextRPG\.conda\envs\TextRPG-py311
pip install -r requirements.txt
python -m game.main
streamlit run ui/app.py
pytest
