# Database Migrations

This directory is reserved for future database migration files.

## Current Status

- No executable PostgreSQL migrations have been added yet.
- The authoritative draft schema is currently:
  - `game/infrastructure/postgres/schema.sql`

## Planned Workflow

1. Convert the draft schema into executable migration files.
2. Add migration tooling.
3. Run migrations against a real PostgreSQL instance.
4. Implement PostgreSQL repositories against the migrated schema.

## Important

The steps above require an actual database environment. They should be performed only
after switching to the target server or a prepared PostgreSQL environment.
