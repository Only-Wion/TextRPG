from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from game.config import load_runtime_llm_settings, normalize_llm_settings
from game.infrastructure.contracts import (
    CardDesignerSessionRepositoryProtocol,
    UserPackCatalogRepositoryProtocol,
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


def _hash_redeem_key(redeem_key: str) -> str:
    return hashlib.sha256(redeem_key.strip().encode("utf-8")).hexdigest()


class PostgresAuthRepository(
    UserRepositoryProtocol,
    UserSessionIndexProtocol,
    UserSettingsRepositoryProtocol,
    UserPackStateRepositoryProtocol,
    UserPackCatalogRepositoryProtocol,
    UserSessionMetadataRepositoryProtocol,
    UserChatHistoryRepositoryProtocol,
    CardDesignerSessionRepositoryProtocol,
    UserUiTemplateRepositoryProtocol,
):
    """PostgreSQL-backed repository for auth and user-scoped state."""

    def __init__(self, dsn: str):
        self.dsn = dsn
        ensure_schema(dsn)
        self._ensure_runtime_columns()
        self._ensure_default_llm_plans()

    def _ensure_runtime_columns(self) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "alter table user_session_metadata add column if not exists ui_generation_status text not null default 'ready'"
                )
            conn.commit()

    def _ensure_default_llm_plans(self) -> None:
        defaults = [
            {
                "plan_id": "deepseek-starter",
                "name": "DeepSeek Starter",
                "description": "平衡成本与质量，适合日常剧情推进",
                "provider": "deepseek",
                "model_name": "deepseek-chat",
                "embedding_model": "text-embedding-3-small",
                "base_url": "https://api.deepseek.com/v1",
                "server_api_key_encrypted": "",
                "input_tokens_per_coin": 1200,
                "output_tokens_per_coin": 800,
                "display_order": 10,
            },
            {
                "plan_id": "qwen-standard",
                "name": "Qwen Standard",
                "description": "通用对话方案，稳定性较高",
                "provider": "alibaba",
                "model_name": "qwen-plus",
                "embedding_model": "text-embedding-v4",
                "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
                "server_api_key_encrypted": "",
                "input_tokens_per_coin": 1000,
                "output_tokens_per_coin": 700,
                "display_order": 20,
            },
        ]
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                for item in defaults:
                    cursor.execute(
                        """
                        insert into llm_plan_catalog (
                            plan_id, name, description, provider, model_name, embedding_model,
                            base_url, server_api_key_encrypted, input_tokens_per_coin,
                            output_tokens_per_coin, is_active, display_order
                        ) values (
                            %(plan_id)s, %(name)s, %(description)s, %(provider)s, %(model_name)s,
                            %(embedding_model)s, %(base_url)s, %(server_api_key_encrypted)s,
                            %(input_tokens_per_coin)s, %(output_tokens_per_coin)s, true,
                            %(display_order)s
                        )
                        on conflict(plan_id) do nothing
                        """,
                        item,
                    )
            conn.commit()

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
                        (
                            user_id,
                            normalized_email,
                            normalized_username,
                            salt_b64,
                            password_hash,
                        ),
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
        if not row or not _verify_password(
            password, row["password_salt"], row["password_hash"]
        ):
            raise ValueError("invalid credentials")
        return {
            "id": row["id"],
            "email": row["email"],
            "username": row["username"],
        }

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "select id, email, username from users where id = %s", (user_id,)
                )
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
                cursor.execute(
                    "delete from auth_tokens where token_hash = %s",
                    (_hash_token(token),),
                )
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
        selected = self.get_user_selected_llm_plan(user_id)
        if selected:
            return {
                "provider": selected["provider"],
                "model_name": selected["model_name"],
                "embedding_model": selected["embedding_model"],
                "base_url": selected["base_url"],
                "api_key": selected.get("server_api_key_encrypted", ""),
                "use_mock_llm": False,
                "force_fake_embeddings": bool(
                    str(selected.get("provider", "")).strip().lower() == "deepseek"
                ),
                "plan_id": selected["plan_id"],
                "input_tokens_per_coin": int(selected["input_tokens_per_coin"]),
                "output_tokens_per_coin": int(selected["output_tokens_per_coin"]),
            }
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
            "plan_id": "",
            "input_tokens_per_coin": 0,
            "output_tokens_per_coin": 0,
        }

    def update_llm_settings(
        self, user_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
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

    def list_llm_plans(self) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select plan_id, name, description, provider, model_name, embedding_model,
                           base_url, input_tokens_per_coin, output_tokens_per_coin,
                           is_active, display_order, updated_at
                    from llm_plan_catalog
                    where is_active = true
                    order by display_order asc, plan_id asc
                    """
                )
                rows = cursor.fetchall() or []
        return [dict(row) for row in rows]

    def list_all_llm_plans(self) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select plan_id, name, description, provider, model_name, embedding_model,
                           base_url, input_tokens_per_coin, output_tokens_per_coin,
                           is_active, display_order, updated_at
                    from llm_plan_catalog
                    order by is_active desc, display_order asc, plan_id asc
                    """
                )
                rows = cursor.fetchall() or []
        return [dict(row) for row in rows]

    def get_user_selected_llm_plan(self, user_id: str) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select p.plan_id, p.name, p.description, p.provider, p.model_name,
                           p.embedding_model, p.base_url, p.server_api_key_encrypted,
                           p.input_tokens_per_coin, p.output_tokens_per_coin,
                           p.is_active, p.display_order
                    from user_llm_plan_selection s
                    join llm_plan_catalog p on p.plan_id = s.plan_id
                    where s.user_id = %s and p.is_active = true
                    """,
                    (user_id,),
                )
                row = cursor.fetchone()
        return dict(row) if row else None

    def set_user_selected_llm_plan(self, user_id: str, plan_id: str) -> dict[str, Any]:
        normalized_plan_id = str(plan_id).strip()
        if not normalized_plan_id:
            raise ValueError("plan_id is required")
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "select plan_id from llm_plan_catalog where plan_id = %s and is_active = true",
                    (normalized_plan_id,),
                )
                exists = cursor.fetchone()
                if not exists:
                    raise ValueError("llm plan not found")
                cursor.execute(
                    """
                    insert into user_llm_plan_selection (user_id, plan_id)
                    values (%s, %s)
                    on conflict(user_id) do update set
                        plan_id = excluded.plan_id,
                        updated_at = now()
                    """,
                    (user_id, normalized_plan_id),
                )
            conn.commit()
        selected = self.get_user_selected_llm_plan(user_id)
        if not selected:
            raise ValueError("failed to persist llm plan selection")
        return selected

    def get_user_coin_balance(self, user_id: str) -> float:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_coin_accounts (user_id, coin_balance)
                    values (%s, 0)
                    on conflict(user_id) do nothing
                    """,
                    (user_id,),
                )
                cursor.execute(
                    "select coin_balance from user_coin_accounts where user_id = %s",
                    (user_id,),
                )
                row = cursor.fetchone()
            conn.commit()
        return float(row["coin_balance"] if row else 0)

    def redeem_coin_key(self, user_id: str, redeem_key: str) -> dict[str, Any]:
        normalized = str(redeem_key).strip()
        if not normalized:
            raise ValueError("redeem key is required")
        key_hash = _hash_redeem_key(normalized)
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_coin_accounts (user_id, coin_balance)
                    values (%s, 0)
                    on conflict(user_id) do nothing
                    """,
                    (user_id,),
                )
                cursor.execute(
                    """
                    select key_hash, status, tier_cny, coins_granted
                    from coin_redeem_keys
                    where key_hash = %s
                    for update
                    """,
                    (key_hash,),
                )
                row = cursor.fetchone()
                if not row:
                    raise ValueError("invalid redeem key")
                if str(row["status"]) != "unused":
                    raise ValueError("redeem key already used")
                coins = Decimal(str(row["coins_granted"]))
                cursor.execute(
                    """
                    update user_coin_accounts
                    set coin_balance = coin_balance + %s,
                        updated_at = now()
                    where user_id = %s
                    returning coin_balance
                    """,
                    (coins, user_id),
                )
                balance_row = cursor.fetchone()
                balance_after = Decimal(
                    str(balance_row["coin_balance"] if balance_row else 0)
                )
                cursor.execute(
                    """
                    update coin_redeem_keys
                    set status = 'redeemed',
                        redeemed_by_user_id = %s,
                        redeemed_at = now()
                    where key_hash = %s
                    """,
                    (user_id, key_hash),
                )
                cursor.execute(
                    """
                    insert into user_coin_ledger (
                        user_id, delta_coin, balance_after, reason_type, reason_detail_json, related_id
                    ) values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        coins,
                        balance_after,
                        "recharge",
                        as_json({"tier_cny": int(row["tier_cny"])}),
                        key_hash,
                    ),
                )
            conn.commit()
        return {
            "coins_added": float(coins),
            "balance_after": float(balance_after),
        }

    def list_user_coin_ledger(
        self,
        user_id: str,
        *,
        reason_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 50), 200))
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                if reason_type:
                    cursor.execute(
                        """
                        select ledger_id, delta_coin, balance_after, reason_type,
                               reason_detail_json, related_id, created_at
                        from user_coin_ledger
                        where user_id = %s and reason_type = %s
                        order by created_at desc
                        limit %s
                        """,
                        (user_id, str(reason_type), normalized_limit),
                    )
                else:
                    cursor.execute(
                        """
                        select ledger_id, delta_coin, balance_after, reason_type,
                               reason_detail_json, related_id, created_at
                        from user_coin_ledger
                        where user_id = %s
                        order by created_at desc
                        limit %s
                        """,
                        (user_id, normalized_limit),
                    )
                rows = cursor.fetchall() or []
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["delta_coin"] = float(payload.get("delta_coin") or 0)
            payload["balance_after"] = float(payload.get("balance_after") or 0)
            result.append(payload)
        return result

    def charge_llm_usage(
        self,
        user_id: str,
        plan_id: str,
        scene: str,
        input_tokens: int,
        output_tokens: int,
        input_tokens_per_coin: int,
        output_tokens_per_coin: int,
    ) -> dict[str, Any]:
        in_tokens = max(0, int(input_tokens or 0))
        out_tokens = max(0, int(output_tokens or 0))
        in_rate = max(1, int(input_tokens_per_coin or 1))
        out_rate = max(1, int(output_tokens_per_coin or 1))

        in_cost = (Decimal(in_tokens) / Decimal(in_rate)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        out_cost = (Decimal(out_tokens) / Decimal(out_rate)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        total_cost = (in_cost + out_cost).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )

        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_coin_accounts (user_id, coin_balance)
                    values (%s, 0)
                    on conflict(user_id) do nothing
                    """,
                    (user_id,),
                )
                cursor.execute(
                    "select coin_balance from user_coin_accounts where user_id = %s for update",
                    (user_id,),
                )
                row = cursor.fetchone()
                current_balance = Decimal(str(row["coin_balance"] if row else 0))
                # Allow this call to overdraft. Reject only if the account is already negative.
                if current_balance < Decimal("0"):
                    raise ValueError("insufficient coin balance")

                cursor.execute(
                    """
                    insert into llm_usage_records (
                        user_id, plan_id, scene, input_tokens, output_tokens,
                        input_coin_cost, output_coin_cost, total_coin_cost
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    returning usage_id
                    """,
                    (
                        user_id,
                        str(plan_id or ""),
                        str(scene or "unknown"),
                        in_tokens,
                        out_tokens,
                        in_cost,
                        out_cost,
                        total_cost,
                    ),
                )
                usage_row = cursor.fetchone()
                usage_id = str(usage_row["usage_id"] if usage_row else "")
                cursor.execute(
                    """
                    update user_coin_accounts
                    set coin_balance = coin_balance - %s,
                        updated_at = now()
                    where user_id = %s
                    returning coin_balance
                    """,
                    (total_cost, user_id),
                )
                after_row = cursor.fetchone()
                balance_after = Decimal(
                    str(after_row["coin_balance"] if after_row else 0)
                )
                cursor.execute(
                    """
                    insert into user_coin_ledger (
                        user_id, delta_coin, balance_after, reason_type, reason_detail_json, related_id
                    ) values (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_id,
                        -total_cost,
                        balance_after,
                        "llm_usage",
                        as_json(
                            {
                                "plan_id": str(plan_id or ""),
                                "scene": str(scene or "unknown"),
                                "input_tokens": in_tokens,
                                "output_tokens": out_tokens,
                                "input_coin_cost": float(in_cost),
                                "output_coin_cost": float(out_cost),
                            }
                        ),
                        usage_id,
                    ),
                )
            conn.commit()
        return {
            "usage_id": usage_id,
            "total_coin_cost": float(total_cost),
            "balance_after": float(balance_after),
        }

    def admin_upsert_llm_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
        plan_id = str(payload.get("plan_id") or "").strip()
        if not plan_id:
            raise ValueError("plan_id is required")
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into llm_plan_catalog (
                        plan_id, name, description, provider, model_name, embedding_model,
                        base_url, server_api_key_encrypted, input_tokens_per_coin,
                        output_tokens_per_coin, is_active, display_order
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict(plan_id) do update set
                        name = excluded.name,
                        description = excluded.description,
                        provider = excluded.provider,
                        model_name = excluded.model_name,
                        embedding_model = excluded.embedding_model,
                        base_url = excluded.base_url,
                        server_api_key_encrypted = case
                            when excluded.server_api_key_encrypted = '' then llm_plan_catalog.server_api_key_encrypted
                            else excluded.server_api_key_encrypted
                        end,
                        input_tokens_per_coin = excluded.input_tokens_per_coin,
                        output_tokens_per_coin = excluded.output_tokens_per_coin,
                        is_active = excluded.is_active,
                        display_order = excluded.display_order,
                        updated_at = now()
                    """,
                    (
                        plan_id,
                        str(payload.get("name") or plan_id),
                        str(payload.get("description") or ""),
                        str(payload.get("provider") or "custom"),
                        str(payload.get("model_name") or ""),
                        str(payload.get("embedding_model") or ""),
                        str(payload.get("base_url") or ""),
                        str(payload.get("server_api_key_encrypted") or ""),
                        max(1, int(payload.get("input_tokens_per_coin") or 1)),
                        max(1, int(payload.get("output_tokens_per_coin") or 1)),
                        bool(payload.get("is_active", True)),
                        int(payload.get("display_order") or 0),
                    ),
                )
            conn.commit()
        selected = next(
            (item for item in self.list_llm_plans() if item.get("plan_id") == plan_id),
            None,
        )
        if selected:
            return selected
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select plan_id, name, description, provider, model_name, embedding_model,
                           base_url, input_tokens_per_coin, output_tokens_per_coin,
                           is_active, display_order, updated_at
                    from llm_plan_catalog
                    where plan_id = %s
                    """,
                    (plan_id,),
                )
                row = cursor.fetchone()
        if not row:
            raise ValueError("failed to persist llm plan")
        return dict(row)

    def admin_delete_llm_plan(self, plan_id: str) -> None:
        normalized_plan_id = str(plan_id).strip()
        if not normalized_plan_id:
            raise ValueError("plan_id is required")
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_llm_plan_selection where plan_id = %s",
                    (normalized_plan_id,),
                )
                cursor.execute(
                    "delete from llm_plan_catalog where plan_id = %s",
                    (normalized_plan_id,),
                )
            conn.commit()

    def admin_set_llm_plan_active(
        self, plan_id: str, is_active: bool
    ) -> dict[str, Any]:
        normalized_plan_id = str(plan_id).strip()
        if not normalized_plan_id:
            raise ValueError("plan_id is required")
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    update llm_plan_catalog
                    set is_active = %s, updated_at = now()
                    where plan_id = %s
                    """,
                    (bool(is_active), normalized_plan_id),
                )
                if cursor.rowcount == 0:
                    raise ValueError("llm plan not found")
            conn.commit()
        selected = next(
            (
                item
                for item in self.list_all_llm_plans()
                if item.get("plan_id") == normalized_plan_id
            ),
            None,
        )
        if selected is None:
            raise ValueError("failed to update llm plan")
        return selected

    def admin_list_redeem_keys(
        self, *, status: str | None = None, limit: int = 200
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit or 200), 500))
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                if status:
                    cursor.execute(
                        """
                        select key_hash, tier_cny, coins_granted, batch_id, status,
                               redeemed_by_user_id, redeemed_at, created_at
                        from coin_redeem_keys
                        where status = %s
                        order by created_at desc
                        limit %s
                        """,
                        (str(status), normalized_limit),
                    )
                else:
                    cursor.execute(
                        """
                        select key_hash, tier_cny, coins_granted, batch_id, status,
                               redeemed_by_user_id, redeemed_at, created_at
                        from coin_redeem_keys
                        order by created_at desc
                        limit %s
                        """,
                        (normalized_limit,),
                    )
                rows = cursor.fetchall() or []
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["coins_granted"] = float(payload.get("coins_granted") or 0)
            result.append(payload)
        return result

    def admin_generate_redeem_keys(
        self,
        *,
        tier_cny: int,
        coins_granted: float,
        count: int,
        batch_id: str,
    ) -> list[str]:
        normalized_count = max(1, min(int(count or 1), 10000))
        normalized_batch_id = str(batch_id).strip() or str(uuid.uuid4())
        normalized_tier = int(tier_cny)
        normalized_coins = Decimal(str(coins_granted)).quantize(
            Decimal("0.0001"), rounding=ROUND_HALF_UP
        )
        generated: list[str] = []
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                for _ in range(normalized_count):
                    code = f"TRPG-{secrets.token_hex(8).upper()}"
                    generated.append(code)
                    cursor.execute(
                        """
                        insert into coin_redeem_keys (
                            key_hash, tier_cny, coins_granted, batch_id, status
                        ) values (%s, %s, %s, %s, 'unused')
                        """,
                        (
                            _hash_redeem_key(code),
                            normalized_tier,
                            normalized_coins,
                            normalized_batch_id,
                        ),
                    )
            conn.commit()
        return generated

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
        normalized = sorted(
            {str(pack_id).strip() for pack_id in pack_ids if str(pack_id).strip()}
        )
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_pack_states where user_id = %s", (user_id,)
                )
                for pack_id in normalized:
                    cursor.execute(
                        """
                        insert into user_pack_states (user_id, pack_id, enabled)
                        values (%s, %s, true)
                        """,
                        (user_id, pack_id),
                    )
            conn.commit()

    def list_user_packs(self, user_id: str) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select internal_pack_id, user_id, private_pack_id, public_pack_id,
                           name, author, description, cards_root, source, visibility,
                           (
                               select version
                               from user_pack_versions v
                               where v.internal_pack_id = user_pack_catalog.internal_pack_id
                               order by updated_at desc, version desc
                               limit 1
                           ) as version,
                           created_at, updated_at
                    from user_pack_catalog
                    where user_id = %s
                    order by updated_at desc, private_pack_id asc
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall() or []
        return [dict(row) for row in rows]

    def get_user_pack(
        self, user_id: str, private_pack_id: str
    ) -> dict[str, Any] | None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select internal_pack_id, user_id, private_pack_id, public_pack_id,
                           name, author, description, cards_root, source, visibility,
                           (
                               select version
                               from user_pack_versions v
                               where v.internal_pack_id = user_pack_catalog.internal_pack_id
                               order by updated_at desc, version desc
                               limit 1
                           ) as version,
                           created_at, updated_at
                    from user_pack_catalog
                    where user_id = %s and private_pack_id = %s
                    """,
                    (user_id, private_pack_id),
                )
                row = cursor.fetchone()
        return dict(row) if row else None

    def upsert_user_pack(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        private_pack_id = str(
            payload.get("private_pack_id") or payload.get("pack_id") or ""
        ).strip()
        if not private_pack_id:
            raise ValueError("private_pack_id is required")
        internal_pack_id = str(payload.get("internal_pack_id") or uuid.uuid4())
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_pack_catalog (
                        internal_pack_id, user_id, private_pack_id, public_pack_id,
                        name, author, description, cards_root, source, visibility
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict(user_id, private_pack_id) do update set
                        public_pack_id = excluded.public_pack_id,
                        name = excluded.name,
                        author = excluded.author,
                        description = excluded.description,
                        cards_root = excluded.cards_root,
                        source = excluded.source,
                        visibility = excluded.visibility,
                        updated_at = now()
                    """,
                    (
                        internal_pack_id,
                        user_id,
                        private_pack_id,
                        str(payload.get("public_pack_id") or "").strip() or None,
                        str(payload.get("name") or private_pack_id),
                        str(payload.get("author") or "unknown"),
                        str(payload.get("description") or ""),
                        str(payload.get("cards_root") or "cards"),
                        str(payload.get("source") or "local"),
                        str(payload.get("visibility") or "private"),
                    ),
                )
            conn.commit()
        return self.get_user_pack(user_id, private_pack_id) or {}

    def remove_user_pack(self, user_id: str, private_pack_id: str) -> None:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "delete from user_pack_catalog where user_id = %s and private_pack_id = %s",
                    (user_id, private_pack_id),
                )
            conn.commit()

    def upsert_user_pack_version(
        self,
        user_id: str,
        private_pack_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        pack = self.get_user_pack(user_id, private_pack_id)
        if not pack:
            raise ValueError("pack not found")
        version = str(payload.get("version") or "").strip()
        if not version:
            raise ValueError("version is required")
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_pack_versions (
                        internal_pack_id, version, storage_backend, storage_path, cards_root, manifest_json
                    ) values (%s, %s, %s, %s, %s, %s)
                    on conflict(internal_pack_id, version) do update set
                        storage_backend = excluded.storage_backend,
                        storage_path = excluded.storage_path,
                        cards_root = excluded.cards_root,
                        manifest_json = excluded.manifest_json,
                        updated_at = now()
                    """,
                    (
                        str(pack["internal_pack_id"]),
                        version,
                        str(payload.get("storage_backend") or "filesystem"),
                        str(payload.get("storage_path") or ""),
                        str(
                            payload.get("cards_root")
                            or pack.get("cards_root")
                            or "cards"
                        ),
                        as_json(payload.get("manifest") or {}),
                    ),
                )
            conn.commit()
        rows = self.list_user_pack_versions(user_id, private_pack_id)
        return next((item for item in rows if item.get("version") == version), {})

    def list_user_pack_versions(
        self, user_id: str, private_pack_id: str
    ) -> list[dict[str, Any]]:
        pack = self.get_user_pack(user_id, private_pack_id)
        if not pack:
            return []
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select version, storage_backend, storage_path, cards_root, manifest_json,
                           created_at, updated_at
                    from user_pack_versions
                    where internal_pack_id = %s
                    order by version desc
                    """,
                    (str(pack["internal_pack_id"]),),
                )
                rows = cursor.fetchall() or []
        result: list[dict[str, Any]] = []
        for row in rows:
            payload = dict(row)
            payload["manifest"] = payload.get("manifest_json") or {}
            payload.pop("manifest_json", None)
            result.append(payload)
        return result

    def save_session_metadata(
        self, user_id: str, save_slot: str, payload: dict[str, Any]
    ) -> None:
        enabled_packs = payload.get("enabled_packs", [])
        if not isinstance(enabled_packs, list):
            enabled_packs = []
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    insert into user_session_metadata (
                        user_id, save_slot, language, enabled_packs_json,
                        location_label, turn_count, updated_label, ui_generation_status
                    ) values (%s, %s, %s, %s, %s, %s, %s, %s)
                    on conflict(user_id, save_slot) do update set
                        language = excluded.language,
                        enabled_packs_json = excluded.enabled_packs_json,
                        location_label = excluded.location_label,
                        turn_count = excluded.turn_count,
                        updated_label = excluded.updated_label,
                        ui_generation_status = excluded.ui_generation_status
                    """,
                    (
                        user_id,
                        save_slot,
                        str(payload.get("language", "zh") or "zh"),
                        as_json([str(pack_id) for pack_id in enabled_packs]),
                        str(payload.get("location_label", "Unknown") or "Unknown"),
                        int(payload.get("turn_count", 0) or 0),
                        str(payload.get("updated_at", "unknown") or "unknown"),
                        str(payload.get("ui_generation_status", "ready") or "ready"),
                    ),
                )
            conn.commit()

    def list_session_summaries(self, user_id: str) -> list[dict[str, Any]]:
        with connect(self.dsn) as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    select save_slot, language, enabled_packs_json, location_label, turn_count, updated_label, ui_generation_status
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
                    "ui_generation_status": str(row["ui_generation_status"] or "ready"),
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

    def save_chat_history(
        self, user_id: str, save_slot: str, history: list[dict[str, Any]]
    ) -> None:
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

    def create_designer_session(
        self, user_id: str, pack_id: str | None = None
    ) -> dict[str, Any]:
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

    def get_designer_session(
        self, user_id: str, session_id: str
    ) -> dict[str, Any] | None:
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

    def save_designer_session(
        self, user_id: str, session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
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

    def list_pack_ui_templates(
        self, user_id: str, pack_id: str
    ) -> list[dict[str, Any]]:
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

    def delete_pack_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> None:
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

    def get_session_ui_binding(
        self, user_id: str, save_slot: str
    ) -> dict[str, Any] | None:
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
