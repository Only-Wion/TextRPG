# Frontend Workspace

This directory contains the local Next.js frontend for the TextRPG web application.

## Current Status

- App Router scaffold is in place
- Main routes implemented:
  - `/sessions`
  - `/`
  - `/packs`
  - `/card-designer`
  - `/settings`
- Data access is contract-driven through `frontend/lib/api.ts`
- When FastAPI is unavailable, the frontend falls back to `frontend/lib/mock-data.ts`

## Environment Variables

- `NEXT_PUBLIC_API_BASE_URL`
- `API_BASE_URL`

If neither variable is set, the frontend defaults to `http://127.0.0.1:8000`.

Production example:
```text
NEXT_PUBLIC_API_BASE_URL=https://api.textrpg.tech
API_BASE_URL=https://api.textrpg.tech
```

## Local Run Notes

- Run FastAPI on `http://127.0.0.1:8000`
- Run Next.js on `http://127.0.0.1:3000`
- Browser-triggered write actions depend on FastAPI CORS allowing the local frontend origin

If a button shows `Failed to fetch` in local development, check:
- the backend is running on port `8000`
- the frontend is running on port `3000`
- the backend was restarted after CORS or route changes
- the button is not one of the documented placeholders on `/sessions` or `/packs`

If login or register shows `Failed to fetch` in production, check:
- `frontend/.env.production` points to the deployed API origin
- the backend CORS allowlist includes the deployed frontend origin

## Contract References

- `docs/api/frontend-contracts.md`
- `docs/frontend/page-ownership.md`
- `docs/api/http-api.md`
- `docs/data-contracts/game-session.md`
- `docs/data-contracts/pack-and-settings.md`

## Next Steps

- Refine the Card Designer visual library panel beyond the current structured list
- Add pack install-from-URL and ZIP upload endpoints
- Continue migrating local transition repositories toward PostgreSQL-backed implementations
