from __future__ import annotations

from functools import lru_cache

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from game.application.services import (
    AuthService,
    CardDesignerService,
    GameServiceRegistry,
    PackService,
    SessionService,
    SettingsService,
)
from game.infrastructure.auth_sqlite import SqliteAuthRepository
from game.service.api import GameService

bearer_scheme = HTTPBearer(auto_error=False)


@lru_cache(maxsize=1)
def get_game_service() -> GameService:
    """Return the transitional singleton application service."""
    return GameService()


@lru_cache(maxsize=1)
def get_game_service_registry() -> GameServiceRegistry:
    return GameServiceRegistry(get_auth_repository())


@lru_cache(maxsize=1)
def get_auth_repository() -> SqliteAuthRepository:
    return SqliteAuthRepository()


def get_auth_service() -> AuthService:
    return AuthService(get_auth_repository())


def get_session_service() -> SessionService:
    repository = get_auth_repository()
    return SessionService(get_game_service_registry(), repository, repository, repository, repository)


def get_pack_service() -> PackService:
    return PackService(get_game_service(), get_auth_repository())


def get_settings_service() -> SettingsService:
    return SettingsService(get_auth_repository(), get_game_service_registry())


def get_card_designer_service() -> CardDesignerService:
    return CardDesignerService(get_game_service(), get_auth_repository())


def get_current_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise PermissionError("authentication required")
    return credentials.credentials


def get_current_user(token: str = Depends(get_current_token)) -> dict:
    return get_auth_service().get_current_user(token)
