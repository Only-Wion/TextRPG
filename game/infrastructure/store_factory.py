from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from game.config import SETTINGS
from game.core.kg_store import KGStore
from game.core.rag_store import RAGStore
from game.core.world_store import WorldStore

from .contracts import KGStoreProtocol, RAGStoreProtocol, WorldStoreProtocol
from .postgres.stores import PostgresKGStore, PostgresRAGStore, PostgresWorldStore
from .postgres.session_key import session_key_from_slot_dir


@dataclass
class SessionStores:
    """Concrete store bundle for one save slot."""

    world: WorldStoreProtocol
    kg: KGStoreProtocol
    rag: RAGStoreProtocol


class SessionStoreFactory:
    """Factory for session-scoped persistence implementations."""

    def create(self, *, world_db_path: Path, kg_db_path: Path, rag_dir: Path) -> SessionStores:
        if SETTINGS.storage_backend == "postgres":
            if not SETTINGS.postgres_dsn:
                raise ValueError("TEXTRPG_POSTGRES_DSN is required when TEXTRPG_STORAGE_BACKEND=postgres")
            session_key = session_key_from_slot_dir(world_db_path.parent)
            return SessionStores(
                world=PostgresWorldStore(dsn=SETTINGS.postgres_dsn, session_key=session_key),
                kg=PostgresKGStore(dsn=SETTINGS.postgres_dsn, session_key=session_key),
                rag=PostgresRAGStore(dsn=SETTINGS.postgres_dsn, session_key=session_key),
            )
        return SessionStores(
            world=WorldStore(db_path=world_db_path),
            kg=KGStore(db_path=kg_db_path),
            rag=RAGStore(persist_dir=rag_dir),
        )
