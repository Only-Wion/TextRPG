# Auth API Contract

This document defines the account and login endpoints introduced for user-scoped gameplay.

## Current Phase

- Current local implementation: sqlite-backed auth and user-session ownership
- Target cloud implementation: PostgreSQL-backed auth and ownership tables behind the same contracts

## Routes

### `POST /auth/register`

Purpose:
- Create a new account and immediately return an access token.

Request body:
```json
{
  "email": "hero@example.com",
  "username": "hero",
  "password": "correct horse battery staple"
}
```

Response:
```json
{
  "access_token": "opaque-token",
  "token_type": "bearer",
  "user": {
    "id": "uuid",
    "email": "hero@example.com",
    "username": "hero"
  }
}
```

### `POST /auth/login`

Purpose:
- Exchange valid credentials for an access token.

Request body:
```json
{
  "email_or_username": "hero",
  "password": "correct horse battery staple"
}
```

Response:
- Matches `POST /auth/register`.

### `GET /auth/me`

Purpose:
- Return the authenticated user derived from the bearer token.

Authentication:
- `Authorization: Bearer <token>`

Response:
```json
{
  "id": "uuid",
  "email": "hero@example.com",
  "username": "hero"
}
```

### `POST /auth/logout`

Purpose:
- Revoke the current bearer token.

Authentication:
- `Authorization: Bearer <token>`

Response:
```json
{
  "ok": true
}
```

## Auth Model

- Current token format: opaque bearer token stored server-side
- Current local repository: sqlite
- Planned cloud repository: PostgreSQL

## Route Protection

The following routes now require an authenticated user:

- `GET /game/state`
- `GET /game/sessions`
- `POST /game/start`
- `POST /game/load`
- `POST /game/step`
- `POST /game/sessions/{slot_id}/duplicate`
- `POST /game/sessions/{slot_id}/archive`
- `PATCH /game/ui-mode`
- `PATCH /game/ui-auto-update`
- `POST /game/ui/generate`
- `POST /game/ui/update`
