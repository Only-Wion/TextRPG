from __future__ import annotations

import time
from typing import Any

from game.infrastructure.contracts import KGStoreProtocol, RAGStoreProtocol, WorldStoreProtocol
from .db import as_json, connect, ensure_schema


class PostgresWorldStore(WorldStoreProtocol):
    """PostgreSQL-backed world attribute store."""

    def __init__(self, dsn: str, session_key: str):
        self.dsn = dsn
        self.session_key = session_key
        ensure_schema(dsn)
        self._ensure_game_session()

    def _ensure_game_session(self) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into game_sessions (session_key, save_slot)
                    values (%s, %s)
                    on conflict(session_key) do nothing
                    """,
                    (self.session_key, self.session_key),
                )
            conn.commit()

    def set_attr(self, entity_id: str, key: str, value: str, source: str, ts: int) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into world_attrs (session_key, entity_id, key, value, source, ts)
                    values (%s, %s, %s, %s, %s, %s)
                    on conflict(session_key, entity_id, key) do update set
                        value = excluded.value,
                        source = excluded.source,
                        ts = excluded.ts
                    """,
                    (self.session_key, entity_id, key, value, source, int(ts)),
                )
            conn.commit()

    def all_attrs(self) -> dict[str, dict[str, str]]:
        data: dict[str, dict[str, str]] = {}
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select entity_id, key, value
                    from world_attrs
                    where session_key = %s
                    """,
                    (self.session_key,),
                )
                rows = cursor.fetchall() or []
        for row in rows:
            data.setdefault(str(row["entity_id"]), {})[str(row["key"])] = str(row["value"])
        return data

    def close(self) -> None:
        return None


class PostgresKGStore(KGStoreProtocol):
    """PostgreSQL-backed knowledge graph store."""

    def __init__(self, dsn: str, session_key: str):
        self.dsn = dsn
        self.session_key = session_key
        ensure_schema(dsn)
        self._ensure_game_session()

    def _ensure_game_session(self) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into game_sessions (session_key, save_slot)
                    values (%s, %s)
                    on conflict(session_key) do nothing
                    """,
                    (self.session_key, self.session_key),
                )
            conn.commit()

    def add_edge(self, sub: str, rel: str, obj: str, confidence: float, source: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into kg_edges (session_key, sub, rel, obj, ts, confidence, source)
                    values (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (self.session_key, sub, rel, obj, int(time.time()), float(confidence), source),
                )
            conn.commit()

    def remove_edge(self, sub: str, rel: str, obj: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    delete from kg_edges
                    where session_key = %s and sub = %s and rel = %s and obj = %s
                    """,
                    (self.session_key, sub, rel, obj),
                )
            conn.commit()

    def all_edges(self) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select sub, rel, obj, ts, confidence, source
                    from kg_edges
                    where session_key = %s
                    order by ts asc
                    """,
                    (self.session_key,),
                )
                rows = cursor.fetchall() or []
        return [
            {
                "subject_id": row["sub"],
                "relation": row["rel"],
                "object_id": row["obj"],
                "ts": row["ts"],
                "confidence": row["confidence"],
                "source": row["source"],
            }
            for row in rows
        ]

    def close(self) -> None:
        return None


class PostgresRAGStore(RAGStoreProtocol):
    """PostgreSQL-backed semantic memory store (keyword fallback)."""

    def __init__(self, dsn: str, session_key: str):
        self.dsn = dsn
        self.session_key = session_key
        ensure_schema(dsn)
        self._ensure_game_session()

    def _ensure_game_session(self) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into game_sessions (session_key, save_slot)
                    values (%s, %s)
                    on conflict(session_key) do nothing
                    """,
                    (self.session_key, self.session_key),
                )
            conn.commit()

    def add_memory(self, text: str, tags: list[str]) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into memory_entries (session_key, text, tags, metadata)
                    values (%s, %s, %s, %s)
                    """,
                    (self.session_key, text, tags, as_json({"ts": int(time.time())})),
                )
            conn.commit()

    def search(self, query: str, k: int) -> list[dict[str, Any]]:
        normalized = (query or "").strip()
        if not normalized:
            return []
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select text, tags, metadata
                    from memory_entries
                    where session_key = %s and text ilike %s
                    order by created_at desc
                    limit %s
                    """,
                    (self.session_key, f"%{normalized}%", max(1, int(k))),
                )
                rows = cursor.fetchall() or []
                if not rows:
                    cursor.execute(
                        """
                        select text, tags, metadata
                        from memory_entries
                        where session_key = %s
                        order by created_at desc
                        limit %s
                        """,
                        (self.session_key, max(1, int(k))),
                    )
                    rows = cursor.fetchall() or []
        return [
            {
                "text": row["text"],
                "metadata": {
                    "tags": row["tags"] if isinstance(row["tags"], list) else [],
                    **(row["metadata"] if isinstance(row["metadata"], dict) else {}),
                },
            }
            for row in rows
        ]

    def close(self) -> None:
        return None
