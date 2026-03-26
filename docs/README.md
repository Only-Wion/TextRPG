# TextRPG Interface Docs

This directory is the single source of truth for layer boundaries, service contracts,
HTTP APIs, data contracts, and runtime flow in this project.

## Principles

1. Contract first
Define or update the interface document before changing implementation code.

2. Single source of truth
Each core contract should have one authoritative document in `docs/`.

3. Keep docs close to code
The docs here describe the code that exists in this repository and the target shape we
are moving toward. They are not product marketing material.

4. Docs and code change together
Any change to service methods, request or response schema, state structure, repository
behavior, or runtime flow must update the corresponding document in the same change.

5. Examples are part of the contract
When a contract changes, update examples so humans and AI tooling see the latest shape.

## Structure

- `architecture/`
  Layer definitions, module ownership, dependency rules, migration mapping.
- `api/`
  Application service contracts and HTTP API contracts.
- `api/auth-api.md`
  Authentication, token, and protected-route HTTP contract.
- `data-contracts/`
  Canonical request, response, state, and domain payload structures.
- `data-contracts/user-and-auth.md`
  Canonical user, token, and user-session ownership payloads.
- `runtime/`
  Runtime lifecycle and state transition flow.
- `migration/`
  Local-to-server handoff notes and migration-phase guidance.
- `examples/`
  Concrete request, response, and page examples.
- `api/frontend-contracts.md`
  Frontend route and data-contract expectations for the Next.js app.
- `frontend/page-ownership.md`
  Frontend page responsibilities, route boundaries, and cross-page ownership rules.
- `../frontend/README.md`
  Local frontend workspace notes, runtime assumptions, and integration entrypoints.

## Maintenance Workflow

1. Design or revise the contract.
2. Update the document under `docs/`.
3. Confirm the contract boundary and ownership.
4. Implement code changes.
5. Update tests.
6. Refresh examples.
7. Review both code and docs together.

## Review Checklist

- Did any layer boundary change?
- Did any service method signature change?
- Did any HTTP route or schema change?
- Did any persisted or in-memory state structure change?
- Did runtime flow or side effects change?
- Were examples updated?

If any answer is yes, at least one file in `docs/` should also change.
