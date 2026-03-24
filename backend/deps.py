from __future__ import annotations

from functools import lru_cache

from game.application.services import PackService, SessionService, SettingsService
from game.service.api import GameService


@lru_cache(maxsize=1)
def get_game_service() -> GameService:
    """Return the transitional singleton application service."""
    return GameService()


def get_session_service() -> SessionService:
    return SessionService(get_game_service())


def get_pack_service() -> PackService:
    return PackService(get_game_service())


def get_settings_service() -> SettingsService:
    return SettingsService(get_game_service())
