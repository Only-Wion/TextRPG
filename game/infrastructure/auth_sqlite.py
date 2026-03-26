from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from game.config import APP_DB_PATH, load_runtime_llm_settings, normalize_llm_settings
from .contracts import (
    UserChatHistoryRepositoryProtocol,
    UserPackStateRepositoryProtocol,
    UserRepositoryProtocol,
    UserSessionIndexProtocol,
    UserSessionMetadataRepositoryProtocol,
    UserSettingsRepositoryProtocol,
)


def _connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return base64.b64encode(digest).decode("ascii")


def _new_password_payload(password: str) -> tuple[str, str]:
    salt = os.urandom(16)
    return base64.b64encode(salt).decode("ascii"), _hash_password(password, salt)


def _verify_password(password: str, salt_b64: str, password_hash: str) -> bool:
    salt = base64.b64decode(salt_b64.encode("ascii"))
    candidate = _hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class SqliteAuthRepository(
    UserRepositoryProtocol,
    UserSessionIndexProtocol,
    UserSettingsRepositoryProtocol,
    UserPackStateRepositoryProtocol,
    UserSessionMetadataRepositoryProtocol,
    UserChatHistoryRepositoryProtocol,
):
    """Local-development auth/session-index repository backed by sqlite."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or APP_DB_PATH
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        with _connect(self.db_path) as conn:
            conn.executescript(
                """
                create table if not exists users (
                    id text primary key,
                    email text not null unique,
                    username text not null unique,
                    password_salt text not null,
                    password_hash text not null,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp
                );

                create table if not exists auth_tokens (
                    token_hash text primary key,
                    user_id text not null references users(id) on delete cascade,
                    created_at text not null default current_timestamp
                );

                create table if not exists user_sessions (
                    user_id text not null references users(id) on delete cascade,
                    save_slot text not null,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp,
                    primary key (user_id, save_slot)
                );

                create table if not exists user_llm_settings (
                    user_id text primary key references users(id) on delete cascade,
                    provider text not null,
                    model_name text not null,
                    embedding_model text not null,
                    base_url text not null,
                    api_key text not null,
                    use_mock_llm integer not null default 0,
                    force_fake_embeddings integer not null default 0,
                    updated_at text not null default current_timestamp
                );

                create table if not exists user_pack_states (
                    user_id text not null references users(id) on delete cascade,
                    pack_id text not null,
                    enabled integer not null default 1,
                    updated_at text not null default current_timestamp,
                    primary key (user_id, pack_id)
                );

                create table if not exists user_session_metadata (
                    user_id text not null references users(id) on delete cascade,
                    save_slot text not null,
                    language text not null,
                    enabled_packs_json text not null,
                    location_label text not null,
                    turn_count integer not null default 0,
                    updated_label text not null,
                    primary key (user_id, save_slot)
                );

                create table if not exists user_chat_history (
                    user_id text not null references users(id) on delete cascade,
                    save_slot text not null,
                    history_json text not null,
                    updated_at text not null default current_timestamp,
                    primary key (user_id, save_slot)
                );
                """
            )

    def create_user(self, email: str, username: str, password: str) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        normalized_username = username.strip()
        normalized_password = password.strip()
        if not normalized_email or not normalized_username or not normalized_password:
            raise ValueError("email, username, and password are required")

        salt_b64, password_hash = _new_password_payload(normalized_password)
        user_id = str(uuid.uuid4())
        try:
            with _connect(self.db_path) as conn:
                conn.execute(
                    """
                    insert into users (id, email, username, password_salt, password_hash)
                    values (?, ?, ?, ?, ?)
                    """,
                    (user_id, normalized_email, normalized_username, salt_b64, password_hash),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("email or username already exists") from exc
        return self.get_user_by_id(user_id) or {}

    def authenticate(self, email_or_username: str, password: str) -> dict[str, Any]:
        normalized_login = email_or_username.strip().lower()
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select id, email, username, password_salt, password_hash
                from users
                where lower(email) = ? or lower(username) = ?
                """,
                (normalized_login, normalized_login),
            ).fetchone()
        if not row or not _verify_password(password, row["password_salt"], row["password_hash"]):
            raise ValueError("invalid credentials")
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "select id, email, username from users where id = ?",
                (user_id,),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with _connect(self.db_path) as conn:
            conn.execute(
                "insert into auth_tokens (token_hash, user_id) values (?, ?)",
                (_hash_token(token), user_id),
            )
        return token

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select users.id, users.email, users.username
                from auth_tokens
                join users on users.id = auth_tokens.user_id
                where auth_tokens.token_hash = ?
                """,
                (_hash_token(token),),
            ).fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def revoke_token(self, token: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute("delete from auth_tokens where token_hash = ?", (_hash_token(token),))

    def bind_session(self, user_id: str, save_slot: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_sessions (user_id, save_slot)
                values (?, ?)
                on conflict(user_id, save_slot)
                do update set updated_at = current_timestamp
                """,
                (user_id, save_slot),
            )

    def list_session_slots(self, user_id: str) -> list[str]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                select save_slot
                from user_sessions
                where user_id = ?
                order by updated_at desc, created_at desc
                """,
                (user_id,),
            ).fetchall()
        return [str(row["save_slot"]) for row in rows]

    def user_owns_session(self, user_id: str, save_slot: str) -> bool:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                "select 1 from user_sessions where user_id = ? and save_slot = ?",
                (user_id, save_slot),
            ).fetchone()
        return row is not None

    def clone_binding(self, user_id: str, source_slot: str, target_slot: str) -> None:
        if not self.user_owns_session(user_id, source_slot):
            raise ValueError("session not found")
        self.bind_session(user_id, target_slot)

    def archive_binding(self, user_id: str, save_slot: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "delete from user_sessions where user_id = ? and save_slot = ?",
                (user_id, save_slot),
            )

    def get_llm_settings(self, user_id: str) -> dict[str, Any]:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select provider, model_name, embedding_model, base_url, api_key, use_mock_llm, force_fake_embeddings
                from user_llm_settings
                where user_id = ?
                """,
                (user_id,),
            ).fetchone()
        if not row:
            return load_runtime_llm_settings().__dict__.copy()
        return {
            "provider": row["provider"],
            "model_name": row["model_name"],
            "embedding_model": row["embedding_model"],
            "base_url": row["base_url"],
            "api_key": row["api_key"],
            "use_mock_llm": bool(row["use_mock_llm"]),
            "force_fake_embeddings": bool(row["force_fake_embeddings"]),
        }

    def update_llm_settings(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = normalize_llm_settings(self.get_llm_settings(user_id))
        settings = normalize_llm_settings(payload, current)
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_llm_settings (
                    user_id, provider, model_name, embedding_model, base_url, api_key, use_mock_llm, force_fake_embeddings
                ) values (?, ?, ?, ?, ?, ?, ?, ?)
                on conflict(user_id) do update set
                    provider = excluded.provider,
                    model_name = excluded.model_name,
                    embedding_model = excluded.embedding_model,
                    base_url = excluded.base_url,
                    api_key = excluded.api_key,
                    use_mock_llm = excluded.use_mock_llm,
                    force_fake_embeddings = excluded.force_fake_embeddings,
                    updated_at = current_timestamp
                """,
                (
                    user_id,
                    settings.provider,
                    settings.model_name,
                    settings.embedding_model,
                    settings.base_url,
                    settings.api_key,
                    int(settings.use_mock_llm),
                    int(settings.force_fake_embeddings),
                ),
            )
        return settings.__dict__.copy()

    def list_enabled_pack_ids(self, user_id: str) -> list[str]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                select pack_id
                from user_pack_states
                where user_id = ? and enabled = 1
                order by updated_at desc, pack_id asc
                """,
                (user_id,),
            ).fetchall()
        return [str(row["pack_id"]) for row in rows]

    def set_pack_enabled(self, user_id: str, pack_id: str, enabled: bool) -> None:
        with _connect(self.db_path) as conn:
            if enabled:
                conn.execute(
                    """
                    insert into user_pack_states (user_id, pack_id, enabled)
                    values (?, ?, 1)
                    on conflict(user_id, pack_id) do update set
                        enabled = 1,
                        updated_at = current_timestamp
                    """,
                    (user_id, pack_id),
                )
            else:
                conn.execute(
                    "delete from user_pack_states where user_id = ? and pack_id = ?",
                    (user_id, pack_id),
                )

    def replace_enabled_pack_ids(self, user_id: str, pack_ids: list[str]) -> None:
        normalized = sorted({str(pack_id).strip() for pack_id in pack_ids if str(pack_id).strip()})
        with _connect(self.db_path) as conn:
            conn.execute("delete from user_pack_states where user_id = ?", (user_id,))
            for pack_id in normalized:
                conn.execute(
                    """
                    insert into user_pack_states (user_id, pack_id, enabled)
                    values (?, ?, 1)
                    """,
                    (user_id, pack_id),
                )

    def save_session_metadata(self, user_id: str, save_slot: str, payload: dict[str, Any]) -> None:
        enabled_packs = payload.get("enabled_packs", [])
        if not isinstance(enabled_packs, list):
            enabled_packs = []
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_session_metadata (
                    user_id, save_slot, language, enabled_packs_json, location_label, turn_count, updated_label
                ) values (?, ?, ?, ?, ?, ?, ?)
                on conflict(user_id, save_slot) do update set
                    language = excluded.language,
                    enabled_packs_json = excluded.enabled_packs_json,
                    location_label = excluded.location_label,
                    turn_count = excluded.turn_count,
                    updated_label = excluded.updated_label
                """,
                (
                    user_id,
                    save_slot,
                    str(payload.get("language", "zh") or "zh"),
                    json.dumps([str(pack_id) for pack_id in enabled_packs], ensure_ascii=False),
                    str(payload.get("location_label", "Unknown") or "Unknown"),
                    int(payload.get("turn_count", 0) or 0),
                    str(payload.get("updated_at", "unknown") or "unknown"),
                ),
            )

    def list_session_summaries(self, user_id: str) -> list[dict[str, Any]]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                select save_slot, language, enabled_packs_json, location_label, turn_count, updated_label
                from user_session_metadata
                where user_id = ?
                order by updated_label desc, save_slot asc
                """,
                (user_id,),
            ).fetchall()
        summaries: list[dict[str, Any]] = []
        for row in rows:
            try:
                enabled_packs = json.loads(row["enabled_packs_json"])
            except Exception:
                enabled_packs = []
            summaries.append(
                {
                    "slot_id": row["save_slot"],
                    "language": row["language"],
                    "enabled_packs": enabled_packs if isinstance(enabled_packs, list) else [],
                    "location_label": row["location_label"],
                    "turn_count": int(row["turn_count"] or 0),
                    "updated_label": row["updated_label"],
                }
            )
        return summaries

    def delete_session_metadata(self, user_id: str, save_slot: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "delete from user_session_metadata where user_id = ? and save_slot = ?",
                (user_id, save_slot),
            )

    def load_chat_history(self, user_id: str, save_slot: str) -> list[dict[str, Any]]:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select history_json
                from user_chat_history
                where user_id = ? and save_slot = ?
                """,
                (user_id, save_slot),
            ).fetchone()
        if not row:
            return []
        try:
            data = json.loads(str(row["history_json"]))
        except Exception:
            return []
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def save_chat_history(self, user_id: str, save_slot: str, history: list[dict[str, Any]]) -> None:
        normalized = [item for item in history if isinstance(item, dict)]
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_chat_history (user_id, save_slot, history_json)
                values (?, ?, ?)
                on conflict(user_id, save_slot) do update set
                    history_json = excluded.history_json,
                    updated_at = current_timestamp
                """,
                (user_id, save_slot, json.dumps(normalized, ensure_ascii=False)),
            )

    def delete_chat_history(self, user_id: str, save_slot: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "delete from user_chat_history where user_id = ? and save_slot = ?",
                (user_id, save_slot),
            )
