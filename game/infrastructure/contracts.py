from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class WorldStoreProtocol(Protocol):
    """Contract for dynamic world attribute persistence."""

    def set_attr(
        self, entity_id: str, key: str, value: str, source: str, ts: int
    ) -> None: ...

    def all_attrs(self) -> dict[str, dict[str, str]]: ...


class KGStoreProtocol(Protocol):
    """Contract for relation edge persistence."""

    def add_edge(
        self, sub: str, rel: str, obj: str, confidence: float, source: str
    ) -> None: ...

    def remove_edge(self, sub: str, rel: str, obj: str) -> None: ...

    def all_edges(self) -> list[dict[str, Any]]: ...


class RAGStoreProtocol(Protocol):
    """Contract for semantic memory persistence and retrieval."""

    def add_memory(self, text: str, tags: list[str]) -> None: ...

    def search(self, query: str, k: int) -> list[dict[str, Any]]: ...


class ChatHistoryStoreProtocol(Protocol):
    """Contract for chat history persistence."""

    def load(self, path: Path) -> list[dict[str, str]]: ...

    def save(self, path: Path, history: list[dict[str, Any]]) -> None: ...


class UIPanelStoreProtocol(Protocol):
    """Contract for UI panel cache persistence."""

    def load(self, path: Path) -> list[dict[str, Any]]: ...

    def save(self, path: Path, panels: list[dict[str, Any]]) -> None: ...


class SessionMetadataStoreProtocol(Protocol):
    """Contract for save-slot session metadata persistence."""

    def load(self, path: Path) -> dict[str, Any]: ...

    def save(self, path: Path, payload: dict[str, Any]) -> None: ...


class UserRepositoryProtocol(Protocol):
    """Contract for account creation, lookup, and token-backed auth."""

    def create_user(
        self, email: str, username: str, password: str
    ) -> dict[str, Any]: ...

    def authenticate(self, email_or_username: str, password: str) -> dict[str, Any]: ...

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None: ...

    def issue_token(self, user_id: str) -> str: ...

    def get_user_by_token(self, token: str) -> dict[str, Any] | None: ...

    def revoke_token(self, token: str) -> None: ...


class UserSessionIndexProtocol(Protocol):
    """Contract for mapping save slots to the owning user account."""

    def bind_session(self, user_id: str, save_slot: str) -> None: ...

    def list_session_slots(self, user_id: str) -> list[str]: ...

    def user_owns_session(self, user_id: str, save_slot: str) -> bool: ...

    def clone_binding(
        self, user_id: str, source_slot: str, target_slot: str
    ) -> None: ...

    def archive_binding(self, user_id: str, save_slot: str) -> None: ...


class UserSettingsRepositoryProtocol(Protocol):
    """Contract for user-scoped runtime settings persistence."""

    def get_llm_settings(self, user_id: str) -> dict[str, Any]: ...

    def update_llm_settings(
        self, user_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...


class UserPackStateRepositoryProtocol(Protocol):
    """Contract for per-user pack enable state."""

    def list_enabled_pack_ids(self, user_id: str) -> list[str]: ...

    def set_pack_enabled(self, user_id: str, pack_id: str, enabled: bool) -> None: ...

    def replace_enabled_pack_ids(self, user_id: str, pack_ids: list[str]) -> None: ...


class UserPackCatalogRepositoryProtocol(Protocol):
    """Contract for user-owned pack metadata, versions, and publication identities."""

    def list_user_packs(self, user_id: str) -> list[dict[str, Any]]: ...

    def get_user_pack(self, user_id: str, private_pack_id: str) -> dict[str, Any] | None: ...

    def upsert_user_pack(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]: ...

    def remove_user_pack(self, user_id: str, private_pack_id: str) -> None: ...

    def upsert_user_pack_version(
        self,
        user_id: str,
        private_pack_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]: ...

    def list_user_pack_versions(
        self, user_id: str, private_pack_id: str
    ) -> list[dict[str, Any]]: ...


class UserSessionMetadataRepositoryProtocol(Protocol):
    """Contract for per-user session summary metadata persistence."""

    def save_session_metadata(
        self, user_id: str, save_slot: str, payload: dict[str, Any]
    ) -> None: ...

    def list_session_summaries(self, user_id: str) -> list[dict[str, Any]]: ...

    def delete_session_metadata(self, user_id: str, save_slot: str) -> None: ...


class UserChatHistoryRepositoryProtocol(Protocol):
    """Contract for per-user chat history persistence."""

    def load_chat_history(
        self, user_id: str, save_slot: str
    ) -> list[dict[str, Any]]: ...

    def save_chat_history(
        self, user_id: str, save_slot: str, history: list[dict[str, Any]]
    ) -> None: ...

    def delete_chat_history(self, user_id: str, save_slot: str) -> None: ...


class CardDesignerSessionRepositoryProtocol(Protocol):
    """Contract for per-user Card Designer AI/draft workspace persistence."""

    def create_designer_session(
        self, user_id: str, pack_id: str | None = None
    ) -> dict[str, Any]: ...

    def get_designer_session(
        self, user_id: str, session_id: str
    ) -> dict[str, Any] | None: ...

    def save_designer_session(
        self, user_id: str, session_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]: ...

    def delete_designer_session(self, user_id: str, session_id: str) -> None: ...


class UserUiTemplateRepositoryProtocol(Protocol):
    """Contract for user-scoped pack UI templates and session UI bindings."""

    def list_pack_ui_templates(
        self, user_id: str, pack_id: str
    ) -> list[dict[str, Any]]: ...

    def get_pack_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> dict[str, Any] | None: ...

    def save_pack_ui_template(
        self,
        user_id: str,
        pack_id: str,
        template_id: str,
        name: str,
        template_payload: dict[str, Any],
        variable_template: dict[str, Any],
    ) -> dict[str, Any]: ...

    def delete_pack_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> None: ...

    def count_sessions_using_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> int: ...

    def get_session_ui_binding(
        self, user_id: str, save_slot: str
    ) -> dict[str, Any] | None: ...

    def save_session_ui_binding(
        self,
        user_id: str,
        save_slot: str,
        pack_id: str,
        template_id: str,
        variables: dict[str, Any],
        visibility: dict[str, bool],
    ) -> dict[str, Any]: ...

    def delete_session_ui_binding(self, user_id: str, save_slot: str) -> None: ...
