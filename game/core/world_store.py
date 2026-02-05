from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import sqlite3

from ..config import WORLD_DB_PATH

class WorldStore:
    """基于 SQLite 的实体属性存储。"""
    def __init__(self, db_path: Path = WORLD_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化 attrs 表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS attrs (entity_id TEXT, key TEXT, value TEXT, source TEXT, ts INTEGER)')
            conn.commit()

    def set_attr(self, entity_id: str, key: str, value: str, source: str, ts: int) -> None:
        """为实体写入/更新单个属性值。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM attrs WHERE entity_id=? AND key=?', (entity_id, key))
            conn.execute(
                'INSERT INTO attrs (entity_id, key, value, source, ts) VALUES (?, ?, ?, ?, ?)',
                (entity_id, key, value, source, ts),
            )
            conn.commit()

    def all_attrs(self) -> Dict[str, Dict[str, str]]:
        """返回按实体分组的全部属性。"""
        data: Dict[str, Dict[str, str]] = {}
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('SELECT entity_id, key, value FROM attrs').fetchall()
        for entity_id, key, value in rows:
            data.setdefault(entity_id, {})[key] = value
        return data
