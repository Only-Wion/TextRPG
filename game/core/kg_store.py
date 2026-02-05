from __future__ import annotations

from pathlib import Path
from typing import Dict, List
import sqlite3
import time

from ..config import KG_DB_PATH

class KGStore:
    """基于 SQLite 的关系边存储。"""
    def __init__(self, db_path: Path = KG_DB_PATH):
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """初始化 edges 表。"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'CREATE TABLE IF NOT EXISTS edges (sub TEXT, rel TEXT, obj TEXT, ts INTEGER, confidence REAL, source TEXT)'
            )
            conn.commit()

    def add_edge(self, sub: str, rel: str, obj: str, confidence: float, source: str) -> None:
        """插入一条关系边。"""
        ts = int(time.time())
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                'INSERT INTO edges (sub, rel, obj, ts, confidence, source) VALUES (?, ?, ?, ?, ?, ?)',
                (sub, rel, obj, ts, confidence, source),
            )
            conn.commit()

    def remove_edge(self, sub: str, rel: str, obj: str) -> None:
        """按完全匹配条件移除关系边。"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('DELETE FROM edges WHERE sub=? AND rel=? AND obj=?', (sub, rel, obj))
            conn.commit()

    def all_edges(self) -> List[Dict[str, str]]:
        """返回所有关系边的列表。"""
        with sqlite3.connect(self.db_path) as conn:
            rows = conn.execute('SELECT sub, rel, obj, ts, confidence, source FROM edges').fetchall()
        return [
            {'subject_id': r[0], 'relation': r[1], 'object_id': r[2], 'ts': r[3], 'confidence': r[4], 'source': r[5]}
            for r in rows
        ]
