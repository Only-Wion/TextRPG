from __future__ import annotations

from typing import Any

from game.infrastructure.contracts import KGStoreProtocol, RAGStoreProtocol, WorldStoreProtocol


class PostgresWorldStore(WorldStoreProtocol):
    """Skeleton for a PostgreSQL-backed world attribute store."""

    def __init__(self, dsn: str, session_key: str):
        self.dsn = dsn
        self.session_key = session_key

    def set_attr(self, entity_id: str, key: str, value: str, source: str, ts: int) -> None:
        raise NotImplementedError("PostgreSQL world store is not implemented yet")

    def all_attrs(self) -> dict[str, dict[str, str]]:
        raise NotImplementedError("PostgreSQL world store is not implemented yet")

    def close(self) -> None:
        return None


class PostgresKGStore(KGStoreProtocol):
    """Skeleton for a PostgreSQL-backed knowledge graph store."""

    def __init__(self, dsn: str, session_key: str):
        self.dsn = dsn
        self.session_key = session_key

    def add_edge(self, sub: str, rel: str, obj: str, confidence: float, source: str) -> None:
        raise NotImplementedError("PostgreSQL KG store is not implemented yet")

    def remove_edge(self, sub: str, rel: str, obj: str) -> None:
        raise NotImplementedError("PostgreSQL KG store is not implemented yet")

    def all_edges(self) -> list[dict[str, Any]]:
        raise NotImplementedError("PostgreSQL KG store is not implemented yet")

    def close(self) -> None:
        return None


class PostgresRAGStore(RAGStoreProtocol):
    """Skeleton for a PostgreSQL-backed semantic memory store."""

    def __init__(self, dsn: str, session_key: str):
        self.dsn = dsn
        self.session_key = session_key

    def add_memory(self, text: str, tags: list[str]) -> None:
        raise NotImplementedError("PostgreSQL RAG store is not implemented yet")

    def search(self, query: str, k: int) -> list[dict[str, Any]]:
        raise NotImplementedError("PostgreSQL RAG store is not implemented yet")

    def close(self) -> None:
        return None
