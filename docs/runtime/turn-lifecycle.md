# Turn Lifecycle

This document describes the canonical runtime flow for one game turn.

## Current Flow

The current turn pipeline is implemented in `game/core/graph.py`.

Order:

1. `ingest_input`
- Trims recent messages for prompt context.

2. `load_overlays`
- Loads overlay ops from `_overlay` card directories.

3. `retrieve_context`
- Retrieves cards, memories, world facts, and allowed actions.

4. `plan_ops`
- Parses admin commands or requests planned ops from the LLM.

5. `validate_ops`
- Validates planned ops and overlay ops against rules.

6. `apply_updates`
- Writes attributes, edges, and memories to persistence.

7. `narrate`
- Produces narration output from the LLM.

8. `checkpoint`
- Writes snapshot files and logs turn summary memory.

## Session Layer Side Effects

After the graph returns, the session service currently does the following:

1. Increments `turn_id`.
2. Appends user and assistant messages to chat history.
3. Refreshes world facts.
4. Refreshes UI panels immediately or schedules UI update.
5. Persists chat history.

These writes currently flow through infrastructure store contracts for:
- chat history persistence
- UI panel cache persistence
- world attribute persistence
- relation edge persistence
- semantic memory persistence and retrieval

Before the graph is built, session-scoped concrete stores are resolved through the
session store factory in `game/infrastructure/store_factory.py`.

The store factory currently supports:
- `local`: active implementation using SQLite, Chroma, and filesystem persistence
- `postgres`: reserved path for PostgreSQL-backed stores; current code provides skeletons only

For the PostgreSQL path, one runtime session maps to one canonical `session_key`.
That mapping is documented in `docs/data-contracts/postgres-storage-model.md`.

## Future Constraint

As the backend moves toward FastAPI + PostgreSQL, the lifecycle above should remain
stable even if session persistence and store implementations change.
