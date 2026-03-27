from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any


def _load_psycopg() -> tuple[Any, Any, Any]:
    try:
        import psycopg
        from psycopg.rows import dict_row
        from psycopg.types.json import Json
    except ImportError as exc:
        raise RuntimeError(
            "psycopg is required for PostgreSQL backend. Install dependencies from requirements.txt."
        ) from exc
    return psycopg, dict_row, Json


def connect(dsn: str):
    psycopg, dict_row, _ = _load_psycopg()
    return psycopg.connect(dsn, row_factory=dict_row)


@lru_cache(maxsize=8)
def ensure_schema(dsn: str) -> None:
    schema_path = Path(__file__).with_name("schema.sql")
    sql = schema_path.read_text(encoding="utf-8")
    with connect(dsn) as conn:
        with conn.cursor() as cursor:
            cursor.execute(sql)
        conn.commit()


def as_json(value: Any):
    _, _, Json = _load_psycopg()
    return Json(value)