# Cloud Handoff

This document marks the handoff point between local architecture work and server-side
configuration work.

## Local Work Completed

The repository now includes:

- FastAPI shell and route structure
- application-service boundaries
- infrastructure store contracts
- session store factory
- PostgreSQL storage implementations (auth, user-scoped state, session stores)
- PostgreSQL draft schema
- interface and runtime documentation for the migration path

## What Still Needs a Real Server or Database

The following steps should be done in a real environment, not just in local code:

1. Provision PostgreSQL.
2. Decide where the database runs:
- same cloud server
- managed PostgreSQL service

3. Set real environment variables:
- `TEXTRPG_STORAGE_BACKEND`
- `TEXTRPG_POSTGRES_DSN`
- `OPENAI_API_KEY`
- any reverse-proxy or deployment-specific settings

4. Convert the draft schema into executable migrations and run them.
5. Validate and harden the PostgreSQL repositories against a live database.
6. Run the FastAPI app under a production process manager.
7. Configure reverse proxy, domain, HTTPS, and firewall rules if needed.

## Recommended Server-Side Order

1. Prepare Python environment and install dependencies.
2. Start FastAPI locally on the server with `local` storage first.
3. Provision PostgreSQL.
4. Apply schema and verify connectivity.
5. Validate PostgreSQL repository behavior and performance under real load.
6. Switch `TEXTRPG_STORAGE_BACKEND=postgres`.
7. Run integration tests against the server environment.
8. Put the service behind a reverse proxy.

## Current Safety Note

The repository recognizes the `postgres` backend flag and includes concrete PostgreSQL
implementations. Do not switch production traffic to `postgres` until migrations,
integration tests, and operational checks are completed in the target environment.
