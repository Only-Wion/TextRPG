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
    CardDesignerSessionRepositoryProtocol,
    UserUiTemplateRepositoryProtocol,
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
    CardDesignerSessionRepositoryProtocol,
    UserUiTemplateRepositoryProtocol,
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

                create table if not exists user_card_designer_sessions (
                    session_id text primary key,
                    user_id text not null references users(id) on delete cascade,
                    selected_pack_id text not null default '',
                    mode text not null default 'edit',
                    state_json text not null,
                    updated_at text not null default current_timestamp
                );

                create table if not exists user_pack_ui_templates (
                    template_id text not null,
                    user_id text not null references users(id) on delete cascade,
                    pack_id text not null,
                    name text not null,
                    template_json text not null,
                    variable_template_json text not null,
                    created_at text not null default current_timestamp,
                    updated_at text not null default current_timestamp,
                    primary key (user_id, pack_id, template_id)
                );

                create table if not exists user_session_ui_bindings (
                    user_id text not null references users(id) on delete cascade,
                    save_slot text not null,
                    pack_id text not null,
                    template_id text not null,
                    variables_json text not null,
                    visibility_json text not null,
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

    def create_designer_session(self, user_id: str, pack_id: str | None = None) -> dict[str, Any]:
        session_id = str(uuid.uuid4())
        payload = {
            "session_id": session_id,
            "selected_pack_id": str(pack_id or ""),
            "mode": "edit",
            "state": {
                "history": [],
                "memory": "",
                "question_mode": True,
                "creation_started": False,
                "selected_pack_id": str(pack_id or ""),
            },
        }
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_card_designer_sessions (
                    session_id, user_id, selected_pack_id, mode, state_json
                ) values (?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    user_id,
                    payload["selected_pack_id"],
                    payload["mode"],
                    json.dumps(payload["state"], ensure_ascii=False),
                ),
            )
        return payload

    def get_designer_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select session_id, selected_pack_id, mode, state_json, updated_at
                from user_card_designer_sessions
                where user_id = ? and session_id = ?
                """,
                (user_id, session_id),
            ).fetchone()
        if not row:
            return None
        try:
            state = json.loads(row["state_json"])
        except Exception:
            state = {}
        if not isinstance(state, dict):
            state = {}
        state.setdefault("selected_pack_id", row["selected_pack_id"] or "")
        return {
            "session_id": row["session_id"],
            "selected_pack_id": row["selected_pack_id"] or "",
            "mode": row["mode"] or "edit",
            "state": state,
            "updated_at": row["updated_at"],
        }

    def save_designer_session(self, user_id: str, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        selected_pack_id = str(payload.get("selected_pack_id", "") or "")
        mode = str(payload.get("mode", "edit") or "edit")
        state = payload.get("state", {}) or {}
        if not isinstance(state, dict):
            state = {}
        state["selected_pack_id"] = selected_pack_id
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_card_designer_sessions (
                    session_id, user_id, selected_pack_id, mode, state_json
                ) values (?, ?, ?, ?, ?)
                on conflict(session_id) do update set
                    selected_pack_id = excluded.selected_pack_id,
                    mode = excluded.mode,
                    state_json = excluded.state_json,
                    updated_at = current_timestamp
                """,
                (
                    session_id,
                    user_id,
                    selected_pack_id,
                    mode,
                    json.dumps(state, ensure_ascii=False),
                ),
            )
        return self.get_designer_session(user_id, session_id) or {
            "session_id": session_id,
            "selected_pack_id": selected_pack_id,
            "mode": mode,
            "state": state,
        }

    def delete_designer_session(self, user_id: str, session_id: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "delete from user_card_designer_sessions where user_id = ? and session_id = ?",
                (user_id, session_id),
            )

    def list_pack_ui_templates(self, user_id: str, pack_id: str) -> list[dict[str, Any]]:
        with _connect(self.db_path) as conn:
            rows = conn.execute(
                """
                select
                    t.template_id,
                    t.name,
                    t.template_json,
                    t.variable_template_json,
                    t.created_at,
                    t.updated_at,
                    (
                        select count(*)
                        from user_session_ui_bindings b
                        where b.user_id = t.user_id and b.pack_id = t.pack_id and b.template_id = t.template_id
                    ) as sessions_in_use
                from user_pack_ui_templates t
                where t.user_id = ? and t.pack_id = ?
                order by updated_at desc, template_id asc
                """,
                (user_id, pack_id),
            ).fetchall()
        result: list[dict[str, Any]] = []
        for row in rows:
            try:
                template_payload = json.loads(str(row["template_json"]))
            except Exception:
                template_payload = {}
            if not isinstance(template_payload, dict):
                template_payload = {}

            try:
                variable_template = json.loads(str(row["variable_template_json"]))
            except Exception:
                variable_template = {}
            if not isinstance(variable_template, dict):
                variable_template = {}

            result.append(
                {
                    "template_id": row["template_id"],
                    "pack_id": pack_id,
                    "name": row["name"],
                    "template": template_payload,
                    "variable_template": variable_template,
                    "sessions_in_use": int(row["sessions_in_use"] or 0),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                }
            )
        return result

    def get_pack_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> dict[str, Any] | None:
        records = self.list_pack_ui_templates(user_id, pack_id)
        for record in records:
            if record["template_id"] == template_id:
                return record
        return None

    def save_pack_ui_template(
        self,
        user_id: str,
        pack_id: str,
        template_id: str,
        name: str,
        template_payload: dict[str, Any],
        variable_template: dict[str, Any],
    ) -> dict[str, Any]:
        normalized_template_id = str(template_id).strip() or str(uuid.uuid4())
        normalized_name = str(name).strip() or f"Template {normalized_template_id[:8]}"
        payload = template_payload if isinstance(template_payload, dict) else {}
        variables = variable_template if isinstance(variable_template, dict) else {}
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_pack_ui_templates (
                    template_id, user_id, pack_id, name, template_json, variable_template_json
                ) values (?, ?, ?, ?, ?, ?)
                on conflict(user_id, pack_id, template_id) do update set
                    name = excluded.name,
                    template_json = excluded.template_json,
                    variable_template_json = excluded.variable_template_json,
                    updated_at = current_timestamp
                """,
                (
                    normalized_template_id,
                    user_id,
                    pack_id,
                    normalized_name,
                    json.dumps(payload, ensure_ascii=False),
                    json.dumps(variables, ensure_ascii=False),
                ),
            )
        return self.get_pack_ui_template(user_id, pack_id, normalized_template_id) or {
            "template_id": normalized_template_id,
            "pack_id": pack_id,
            "name": normalized_name,
            "template": payload,
            "variable_template": variables,
        }

    def delete_pack_ui_template(self, user_id: str, pack_id: str, template_id: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                delete from user_pack_ui_templates
                where user_id = ? and pack_id = ? and template_id = ?
                """,
                (user_id, pack_id, template_id),
            )

    def count_sessions_using_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> int:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select count(*) as c
                from user_session_ui_bindings
                where user_id = ? and pack_id = ? and template_id = ?
                """,
                (user_id, pack_id, template_id),
            ).fetchone()
        return int((row["c"] if row else 0) or 0)

    def get_session_ui_binding(self, user_id: str, save_slot: str) -> dict[str, Any] | None:
        with _connect(self.db_path) as conn:
            row = conn.execute(
                """
                select pack_id, template_id, variables_json, visibility_json, updated_at
                from user_session_ui_bindings
                where user_id = ? and save_slot = ?
                """,
                (user_id, save_slot),
            ).fetchone()
        if not row:
            return None
        try:
            variables = json.loads(str(row["variables_json"]))
        except Exception:
            variables = {}
        if not isinstance(variables, dict):
            variables = {}
        try:
            visibility = json.loads(str(row["visibility_json"]))
        except Exception:
            visibility = {}
        if not isinstance(visibility, dict):
            visibility = {}
        return {
            "save_slot": save_slot,
            "pack_id": row["pack_id"],
            "template_id": row["template_id"],
            "variables": variables,
            "visibility": {str(k): bool(v) for k, v in visibility.items()},
            "updated_at": row["updated_at"],
        }

    def save_session_ui_binding(
        self,
        user_id: str,
        save_slot: str,
        pack_id: str,
        template_id: str,
        variables: dict[str, Any],
        visibility: dict[str, bool],
    ) -> dict[str, Any]:
        normalized_variables = variables if isinstance(variables, dict) else {}
        normalized_visibility = visibility if isinstance(visibility, dict) else {}
        with _connect(self.db_path) as conn:
            conn.execute(
                """
                insert into user_session_ui_bindings (
                    user_id, save_slot, pack_id, template_id, variables_json, visibility_json
                ) values (?, ?, ?, ?, ?, ?)
                on conflict(user_id, save_slot) do update set
                    pack_id = excluded.pack_id,
                    template_id = excluded.template_id,
                    variables_json = excluded.variables_json,
                    visibility_json = excluded.visibility_json,
                    updated_at = current_timestamp
                """,
                (
                    user_id,
                    save_slot,
                    pack_id,
                    template_id,
                    json.dumps(normalized_variables, ensure_ascii=False),
                    json.dumps(normalized_visibility, ensure_ascii=False),
                ),
            )
        return self.get_session_ui_binding(user_id, save_slot) or {
            "save_slot": save_slot,
            "pack_id": pack_id,
            "template_id": template_id,
            "variables": normalized_variables,
            "visibility": normalized_visibility,
        }

    def delete_session_ui_binding(self, user_id: str, save_slot: str) -> None:
        with _connect(self.db_path) as conn:
            conn.execute(
                "delete from user_session_ui_bindings where user_id = ? and save_slot = ?",
                (user_id, save_slot),
            )
