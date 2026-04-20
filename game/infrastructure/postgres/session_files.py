from __future__ import annotations

from pathlib import Path
from typing import Any

from game.infrastructure.contracts import ChatHistoryStoreProtocol, UIPanelStoreProtocol
from .db import as_json, connect, ensure_schema
from .session_key import session_key_from_slot_dir


class PostgresChatHistoryStore(ChatHistoryStoreProtocol):
    """PostgreSQL-backed chat history store."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        ensure_schema(dsn)

    def _session_key_from_path(self, path: Path) -> str:
        return session_key_from_slot_dir(path.parent)

    def load(self, path: Path) -> list[dict[str, str]]:
        session_key = self._session_key_from_path(path)
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select role, content
                    from chat_messages
                    where session_key = %s
                    order by message_index asc
                    """,
                    (session_key,),
                )
                rows = cursor.fetchall() or []
        return [
            {
                "role": str(row["role"]),
                "content": str(row["content"]),
            }
            for row in rows
        ]

    def save(self, path: Path, history: list[dict[str, Any]]) -> None:
        session_key = self._session_key_from_path(path)
        normalized = [item for item in history if isinstance(item, dict)]
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into game_sessions (session_key, save_slot)
                    values (%s, %s)
                    on conflict(session_key) do nothing
                    """,
                    (session_key, session_key),
                )
                cursor.execute("delete from chat_messages where session_key = %s", (session_key,))
                for idx, item in enumerate(normalized):
                    cursor.execute(
                        """
                        insert into chat_messages (session_key, message_index, role, content)
                        values (%s, %s, %s, %s)
                        """,
                        (
                            session_key,
                            idx,
                            str(item.get("role", "assistant")),
                            str(item.get("content", "")),
                        ),
                    )
            conn.commit()


class PostgresUIPanelStore(UIPanelStoreProtocol):
    """PostgreSQL-backed UI panel cache store."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        ensure_schema(dsn)

    def _session_key_from_path(self, path: Path) -> str:
        return session_key_from_slot_dir(path.parent)

    def load(self, path: Path) -> list[dict[str, Any]]:
        session_key = self._session_key_from_path(path)
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select payload
                    from ui_panel_defs
                    where session_key = %s
                    order by panel_id asc
                    """,
                    (session_key,),
                )
                rows = cursor.fetchall() or []
        panels: list[dict[str, Any]] = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, dict):
                panels.append(payload)
        return panels

    def save(self, path: Path, panels: list[dict[str, Any]]) -> None:
        session_key = self._session_key_from_path(path)
        normalized = [item for item in panels if isinstance(item, dict)]
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into game_sessions (session_key, save_slot)
                    values (%s, %s)
                    on conflict(session_key) do nothing
                    """,
                    (session_key, session_key),
                )
                cursor.execute("delete from ui_panel_defs where session_key = %s", (session_key,))
                for idx, panel in enumerate(normalized):
                    cursor.execute(
                        """
                        insert into ui_panel_defs (session_key, panel_id, payload)
                        values (%s, %s, %s)
                        """,
                        (session_key, f"{idx:08d}", as_json(panel)),
                    )
            conn.commit()
