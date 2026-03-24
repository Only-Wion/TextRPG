from __future__ import annotations

from pathlib import Path
from typing import Any

from game.infrastructure.contracts import ChatHistoryStoreProtocol, UIPanelStoreProtocol


class PostgresChatHistoryStore(ChatHistoryStoreProtocol):
    """Skeleton for a PostgreSQL-backed chat history store."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def load(self, path: Path) -> list[dict[str, str]]:
        raise NotImplementedError("PostgreSQL chat history store is not implemented yet")

    def save(self, path: Path, history: list[dict[str, Any]]) -> None:
        raise NotImplementedError("PostgreSQL chat history store is not implemented yet")


class PostgresUIPanelStore(UIPanelStoreProtocol):
    """Skeleton for a PostgreSQL-backed UI panel cache store."""

    def __init__(self, dsn: str):
        self.dsn = dsn

    def load(self, path: Path) -> list[dict[str, Any]]:
        raise NotImplementedError("PostgreSQL UI panel store is not implemented yet")

    def save(self, path: Path, panels: list[dict[str, Any]]) -> None:
        raise NotImplementedError("PostgreSQL UI panel store is not implemented yet")
