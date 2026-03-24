from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class WorldStoreProtocol(Protocol):
    """Contract for dynamic world attribute persistence."""

    def set_attr(self, entity_id: str, key: str, value: str, source: str, ts: int) -> None:
        ...

    def all_attrs(self) -> dict[str, dict[str, str]]:
        ...


class KGStoreProtocol(Protocol):
    """Contract for relation edge persistence."""

    def add_edge(self, sub: str, rel: str, obj: str, confidence: float, source: str) -> None:
        ...

    def remove_edge(self, sub: str, rel: str, obj: str) -> None:
        ...

    def all_edges(self) -> list[dict[str, Any]]:
        ...


class RAGStoreProtocol(Protocol):
    """Contract for semantic memory persistence and retrieval."""

    def add_memory(self, text: str, tags: list[str]) -> None:
        ...

    def search(self, query: str, k: int) -> list[dict[str, Any]]:
        ...


class ChatHistoryStoreProtocol(Protocol):
    """Contract for chat history persistence."""

    def load(self, path: Path) -> list[dict[str, str]]:
        ...

    def save(self, path: Path, history: list[dict[str, Any]]) -> None:
        ...


class UIPanelStoreProtocol(Protocol):
    """Contract for UI panel cache persistence."""

    def load(self, path: Path) -> list[dict[str, Any]]:
        ...

    def save(self, path: Path, panels: list[dict[str, Any]]) -> None:
        ...


class SessionMetadataStoreProtocol(Protocol):
    """Contract for save-slot session metadata persistence."""

    def load(self, path: Path) -> dict[str, Any]:
        ...

    def save(self, path: Path, payload: dict[str, Any]) -> None:
        ...
