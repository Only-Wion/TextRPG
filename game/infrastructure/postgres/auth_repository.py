from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from typing import Any

from game.config import load_runtime_llm_settings, normalize_llm_settings
from game.infrastructure.contracts import (
    CardDesignerSessionRepositoryProtocol,
    UserUiTemplateRepositoryProtocol,
    UserChatHistoryRepositoryProtocol,
    UserPackStateRepositoryProtocol,
    UserRepositoryProtocol,
    UserSessionIndexProtocol,
    UserSessionMetadataRepositoryProtocol,
    UserSettingsRepositoryProtocol,
)

from .db import as_json, connect, ensure_schema


def _hash_password(password: str, salt: bytes) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return base64.b64encode(digest).decode("ascii")


def _new_password_payload(password: str) -> tuple[str, str]:
    salt = secrets.token_bytes(16)
    return base64.b64encode(salt).decode("ascii"), _hash_password(password, salt)


def _verify_password(password: str, salt_b64: str, password_hash: str) -> bool:
    salt = base64.b64decode(salt_b64.encode("ascii"))
    candidate = _hash_password(password, salt)
    return hmac.compare_digest(candidate, password_hash)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


class PostgresAuthRepository(
    UserRepositoryProtocol,
    UserSessionIndexProtocol,
    UserSettingsRepositoryProtocol,
    UserPackStateRepositoryProtocol,
    UserSessionMetadataRepositoryProtocol,
    UserChatHistoryRepositoryProtocol,
    CardDesignerSessionRepositoryProtocol,
    UserUiTemplateRepositoryProtocol,
):
    """PostgreSQL-backed repository for auth and user-scoped state."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        ensure_schema(dsn)

    def create_user(self, email: str, username: str, password: str) -> dict[str, Any]:
        normalized_email = email.strip().lower()
        normalized_username = username.strip()
        normalized_password = password.strip()
        if not normalized_email or not normalized_username or not normalized_password:
            raise ValueError("email, username, and password are required")

        salt_b64, password_hash = _new_password_payload(normalized_password)
        user_id = str(uuid.uuid4())
        try:
            with connect(self.dsn) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        insert into users (id, email, username, password_salt, password_hash)
                        values (%s, %s, %s, %s, %s)
                        """,
                        (user_id, normalized_email, normalized_username, salt_b64, password_hash),
                    )
                conn.commit()
        except Exception as exc:
            if "duplicate key" in str(exc).lower():
                raise ValueError("email or username already exists") from exc
            raise
        return self.get_user_by_id(user_id) or {}

    def authenticate(self, email_or_username: str, password: str) -> dict[str, Any]:
        normalized_login = email_or_username.strip().lower()
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select id, email, username, password_salt, password_hash
                    from users
                    where lower(email) = %s or lower(username) = %s
                    """,
                    (normalized_login, normalized_login),
                )
                row = cursor.fetchone()
        if not row or not _verify_password(password, row["password_salt"], row["password_hash"]):
            raise ValueError("invalid credentials")
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute("select id, email, username from users where id = %s", (user_id,))
                row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def issue_token(self, user_id: str) -> str:
        token = secrets.token_urlsafe(32)
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "insert into auth_tokens (token_hash, user_id) values (%s, %s)",
                    (_hash_token(token), user_id),
                )
            conn.commit()
        return token

    def get_user_by_token(self, token: str) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select users.id, users.email, users.username
                    from auth_tokens
                    join users on users.id = auth_tokens.user_id
                    where auth_tokens.token_hash = %s
                    """,
                    (_hash_token(token),),
                )
                row = cursor.fetchone()
        if not row:
            return None
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def revoke_token(self, token: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute("delete from auth_tokens where token_hash = %s", (_hash_token(token),))
            conn.commit()

    def bind_session(self, user_id: str, save_slot: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_sessions (user_id, save_slot)
                    values (%s, %s)
                    on conflict(user_id, save_slot)
                    do update set updated_at = now()
                    """,
                    (user_id, save_slot),
                )
            conn.commit()

    def list_session_slots(self, user_id: str) -> list[str]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select save_slot
                    from user_sessions
                    where user_id = %s
                    order by updated_at desc, created_at desc
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall() or []
        return [str(row["save_slot"]) for row in rows]

    def user_owns_session(self, user_id: str, save_slot: str) -> bool:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "select 1 from user_sessions where user_id = %s and save_slot = %s",
                    (user_id, save_slot),
                )
                row = cursor.fetchone()
        return row is not None

    def clone_binding(self, user_id: str, source_slot: str, target_slot: str) -> None:
        if not self.user_owns_session(user_id, source_slot):
            raise ValueError("session not found")
        self.bind_session(user_id, target_slot)

    def archive_binding(self, user_id: str, save_slot: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_sessions where user_id = %s and save_slot = %s",
                    (user_id, save_slot),
                )
            conn.commit()

    def get_llm_settings(self, user_id: str) -> dict[str, Any]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select provider, model_name, embedding_model, base_url, api_key_encrypted,
                           use_mock_llm, force_fake_embeddings
                    from user_llm_settings
                    where user_id = %s
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
        if not row:
            return load_runtime_llm_settings().__dict__.copy()
        return {
            "provider": row["provider"],
            "model_name": row["model_name"],
            "embedding_model": row["embedding_model"],
            "base_url": row["base_url"],
            "api_key": row["api_key_encrypted"],
            "use_mock_llm": bool(row["use_mock_llm"]),
            "force_fake_embeddings": bool(row["force_fake_embeddings"]),
        }

    def update_llm_settings(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        current = normalize_llm_settings(self.get_llm_settings(user_id))
        settings = normalize_llm_settings(payload, current)
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_llm_settings (
                        user_id, provider, model_name, embedding_model, base_url,
                        api_key_encrypted, use_mock_llm, force_fake_embeddings
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict(user_id) do update set
                        provider = excluded.provider,
                        model_name = excluded.model_name,
                        embedding_model = excluded.embedding_model,
                        base_url = excluded.base_url,
                        api_key_encrypted = excluded.api_key_encrypted,
                        use_mock_llm = excluded.use_mock_llm,
                        force_fake_embeddings = excluded.force_fake_embeddings,
                        updated_at = now()
                    """,
                    (
                        user_id,
                        settings.provider,
                        settings.model_name,
                        settings.embedding_model,
                        settings.base_url,
                        settings.api_key,
                        bool(settings.use_mock_llm),
                        bool(settings.force_fake_embeddings),
                    ),
                )
            conn.commit()
        return settings.__dict__.copy()

    def list_enabled_pack_ids(self, user_id: str) -> list[str]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select pack_id
                    from user_pack_states
                    where user_id = %s and enabled = true
                    order by updated_at desc, pack_id asc
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall() or []
        return [str(row["pack_id"]) for row in rows]

    def set_pack_enabled(self, user_id: str, pack_id: str, enabled: bool) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                if enabled:
                    cursor.execute(
                        """
                        insert into user_pack_states (user_id, pack_id, enabled)
                        values (%s, %s, true)
                        on conflict(user_id, pack_id) do update set
                            enabled = true,
                            updated_at = now()
                        """,
                        (user_id, pack_id),
                    )
                else:
                    cursor.execute(
                        "delete from user_pack_states where user_id = %s and pack_id = %s",
                        (user_id, pack_id),
                    )
            conn.commit()

    def replace_enabled_pack_ids(self, user_id: str, pack_ids: list[str]) -> None:
        normalized = sorted({str(pack_id).strip() for pack_id in pack_ids if str(pack_id).strip()})
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute("delete from user_pack_states where user_id = %s", (user_id,))
                for pack_id in normalized:
                    cursor.execute(
                        """
                        insert into user_pack_states (user_id, pack_id, enabled)
                        values (%s, %s, true)
                        """,
                        (user_id, pack_id),
                    )
            conn.commit()

    def save_session_metadata(self, user_id: str, save_slot: str, payload: dict[str, Any]) -> None:
        enabled_packs = payload.get("enabled_packs", [])
        if not isinstance(enabled_packs, list):
            enabled_packs = []
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_session_metadata (
                        user_id, save_slot, language, enabled_packs_json,
                        location_label, turn_count, updated_label
                    ) values (%s, %s, %s, %s, %s, %s, %s)
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
                        as_json([str(pack_id) for pack_id in enabled_packs]),
                        str(payload.get("location_label", "Unknown") or "Unknown"),
                        int(payload.get("turn_count", 0) or 0),
                        str(payload.get("updated_at", "unknown") or "unknown"),
                    ),
                )
            conn.commit()

    def list_session_summaries(self, user_id: str) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select save_slot, language, enabled_packs_json, location_label, turn_count, updated_label
                    from user_session_metadata
                    where user_id = %s
                    order by updated_label desc, save_slot asc
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall() or []
        summaries: list[dict[str, Any]] = []
        for row in rows:
            enabled_packs = row["enabled_packs_json"]
            if not isinstance(enabled_packs, list):
                enabled_packs = []
            summaries.append(
                {
                    "slot_id": row["save_slot"],
                    "language": row["language"],
                    "enabled_packs": [str(item) for item in enabled_packs],
                    "location_label": row["location_label"],
                    "turn_count": int(row["turn_count"] or 0),
                    "updated_label": row["updated_label"],
                }
            )
        return summaries

    def delete_session_metadata(self, user_id: str, save_slot: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_session_metadata where user_id = %s and save_slot = %s",
                    (user_id, save_slot),
                )
            conn.commit()

    def load_chat_history(self, user_id: str, save_slot: str) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select history_json
                    from user_chat_history
                    where user_id = %s and save_slot = %s
                    """,
                    (user_id, save_slot),
                )
                row = cursor.fetchone()
        if not row:
            return []
        data = row["history_json"]
        if not isinstance(data, list):
            return []
        return [item for item in data if isinstance(item, dict)]

    def save_chat_history(self, user_id: str, save_slot: str, history: list[dict[str, Any]]) -> None:
        normalized = [item for item in history if isinstance(item, dict)]
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_chat_history (user_id, save_slot, history_json)
                    values (%s, %s, %s)
                    on conflict(user_id, save_slot) do update set
                        history_json = excluded.history_json,
                        updated_at = now()
                    """,
                    (user_id, save_slot, as_json(normalized)),
                )
            conn.commit()

    def delete_chat_history(self, user_id: str, save_slot: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_chat_history where user_id = %s and save_slot = %s",
                    (user_id, save_slot),
                )
            conn.commit()

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
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_card_designer_sessions (
                        session_id, user_id, selected_pack_id, mode, state_json
                    ) values (%s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        user_id,
                        payload["selected_pack_id"],
                        payload["mode"],
                        as_json(payload["state"]),
                    ),
                )
            conn.commit()
        return payload

    def get_designer_session(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select session_id, selected_pack_id, mode, state_json, updated_at
                    from user_card_designer_sessions
                    where user_id = %s and session_id = %s
                    """,
                    (user_id, session_id),
                )
                row = cursor.fetchone()
        if not row:
            return None
        state = row["state_json"]
        if not isinstance(state, dict):
            state = {}
        state.setdefault("selected_pack_id", row["selected_pack_id"] or "")
        return {
            "session_id": row["session_id"],
            "selected_pack_id": row["selected_pack_id"] or "",
            "mode": row["mode"] or "edit",
            "state": state,
            "updated_at": str(row["updated_at"]),
        }

    def save_designer_session(self, user_id: str, session_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        selected_pack_id = str(payload.get("selected_pack_id", "") or "")
        mode = str(payload.get("mode", "edit") or "edit")
        state = payload.get("state", {}) or {}
        if not isinstance(state, dict):
            state = {}
        state["selected_pack_id"] = selected_pack_id
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_card_designer_sessions (
                        session_id, user_id, selected_pack_id, mode, state_json
                    ) values (%s, %s, %s, %s, %s)
                    on conflict(session_id) do update set
                        selected_pack_id = excluded.selected_pack_id,
                        mode = excluded.mode,
                        state_json = excluded.state_json,
                        updated_at = now()
                    """,
                    (session_id, user_id, selected_pack_id, mode, as_json(state)),
                )
            conn.commit()
        return self.get_designer_session(user_id, session_id) or {
            "session_id": session_id,
            "selected_pack_id": selected_pack_id,
            "mode": mode,
            "state": state,
        }

    def delete_designer_session(self, user_id: str, session_id: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_card_designer_sessions where user_id = %s and session_id = %s",
                    (user_id, session_id),
                )
            conn.commit()

    def list_pack_ui_templates(self, user_id: str, pack_id: str) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
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
                    where t.user_id = %s and t.pack_id = %s
                    order by updated_at desc, template_id asc
                    """,
                    (user_id, pack_id),
                )
                rows = cursor.fetchall() or []
        result: list[dict[str, Any]] = []
        for row in rows:
            template_payload = row["template_json"]
            if not isinstance(template_payload, dict):
                template_payload = {}
            variable_template = row["variable_template_json"]
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
                    "created_at": str(row["created_at"]),
                    "updated_at": str(row["updated_at"]),
                }
            )
        return result

    def get_pack_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> dict[str, Any] | None:
        for record in self.list_pack_ui_templates(user_id, pack_id):
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
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_pack_ui_templates (
                        template_id, user_id, pack_id, name, template_json, variable_template_json
                    ) values (%s, %s, %s, %s, %s, %s)
                    on conflict(user_id, pack_id, template_id) do update set
                        name = excluded.name,
                        template_json = excluded.template_json,
                        variable_template_json = excluded.variable_template_json,
                        updated_at = now()
                    """,
                    (
                        normalized_template_id,
                        user_id,
                        pack_id,
                        normalized_name,
                        as_json(payload),
                        as_json(variables),
                    ),
                )
            conn.commit()
        return self.get_pack_ui_template(user_id, pack_id, normalized_template_id) or {
            "template_id": normalized_template_id,
            "pack_id": pack_id,
            "name": normalized_name,
            "template": payload,
            "variable_template": variables,
        }

    def delete_pack_ui_template(self, user_id: str, pack_id: str, template_id: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    delete from user_pack_ui_templates
                    where user_id = %s and pack_id = %s and template_id = %s
                    """,
                    (user_id, pack_id, template_id),
                )
            conn.commit()

    def count_sessions_using_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> int:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select count(*) as c
                    from user_session_ui_bindings
                    where user_id = %s and pack_id = %s and template_id = %s
                    """,
                    (user_id, pack_id, template_id),
                )
                row = cursor.fetchone()
        return int((row["c"] if row else 0) or 0)

    def get_session_ui_binding(self, user_id: str, save_slot: str) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select pack_id, template_id, variables_json, visibility_json, updated_at
                    from user_session_ui_bindings
                    where user_id = %s and save_slot = %s
                    """,
                    (user_id, save_slot),
                )
                row = cursor.fetchone()
        if not row:
            return None
        variables = row["variables_json"]
        if not isinstance(variables, dict):
            variables = {}
        visibility = row["visibility_json"]
        if not isinstance(visibility, dict):
            visibility = {}
        return {
            "save_slot": save_slot,
            "pack_id": row["pack_id"],
            "template_id": row["template_id"],
            "variables": variables,
            "visibility": {str(k): bool(v) for k, v in visibility.items()},
            "updated_at": str(row["updated_at"]),
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
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_session_ui_bindings (
                        user_id, save_slot, pack_id, template_id, variables_json, visibility_json
                    ) values (%s, %s, %s, %s, %s, %s)
                    on conflict(user_id, save_slot) do update set
                        pack_id = excluded.pack_id,
                        template_id = excluded.template_id,
                        variables_json = excluded.variables_json,
                        visibility_json = excluded.visibility_json,
                        updated_at = now()
                    """,
                    (
                        user_id,
                        save_slot,
                        pack_id,
                        template_id,
                        as_json(normalized_variables),
                        as_json(normalized_visibility),
                    ),
                )
            conn.commit()
        return self.get_session_ui_binding(user_id, save_slot) or {
            "save_slot": save_slot,
            "pack_id": pack_id,
            "template_id": template_id,
            "variables": normalized_variables,
            "visibility": normalized_visibility,
        }

    def delete_session_ui_binding(self, user_id: str, save_slot: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_session_ui_bindings where user_id = %s and save_slot = %s",
                    (user_id, save_slot),
                )
            conn.commit()