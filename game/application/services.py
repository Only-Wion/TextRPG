from __future__ import annotations

from pathlib import Path
from typing import Any

from game.infrastructure.contracts import (
    UserChatHistoryRepositoryProtocol,
    UserPackStateRepositoryProtocol,
    UserRepositoryProtocol,
    UserSessionIndexProtocol,
    UserSessionMetadataRepositoryProtocol,
    UserSettingsRepositoryProtocol,
)
from game.config import SETTINGS
from game.service.api import GameService


class GameServiceRegistry:
    """Assign one transitional GameService instance per authenticated user."""

    def __init__(self, settings_repository: UserSettingsRepositoryProtocol):
        self._services: dict[str, GameService] = {}
        self._settings_repository = settings_repository

    def for_user(self, user_id: str) -> GameService:
        service = self._services.get(user_id)
        if service is None:
            service = GameService()
            self._services[user_id] = service
        service.set_runtime_llm_settings(self._settings_repository.get_llm_settings(user_id))
        return service


class AuthService:
    """Application contract for account registration, login, and token auth."""

    def __init__(self, user_repository: UserRepositoryProtocol):
        self._user_repository = user_repository

    def register(self, email: str, username: str, password: str) -> dict[str, Any]:
        user = self._user_repository.create_user(email, username, password)
        token = self._user_repository.issue_token(user["id"])
        return {
            "user": user,
            "access_token": token,
            "token_type": "bearer",
        }

    def login(self, email_or_username: str, password: str) -> dict[str, Any]:
        user = self._user_repository.authenticate(email_or_username, password)
        token = self._user_repository.issue_token(user["id"])
        return {
            "user": user,
            "access_token": token,
            "token_type": "bearer",
        }

    def get_current_user(self, token: str) -> dict[str, Any]:
        user = self._user_repository.get_user_by_token(token)
        if not user:
            raise ValueError("invalid or expired token")
        return user

    def logout(self, token: str) -> None:
        self._user_repository.revoke_token(token)


class SessionService:
    """Application contract for user-scoped game session lifecycle and turns."""

    def __init__(
        self,
        registry: GameServiceRegistry,
        session_index: UserSessionIndexProtocol,
        pack_state_repository: UserPackStateRepositoryProtocol,
        session_metadata_repository: UserSessionMetadataRepositoryProtocol,
        chat_history_repository: UserChatHistoryRepositoryProtocol,
    ):
        self._registry = registry
        self._session_index = session_index
        self._pack_state_repository = pack_state_repository
        self._session_metadata_repository = session_metadata_repository
        self._chat_history_repository = chat_history_repository

    def start_new_game(
        self,
        user_id: str,
        save_slot: str,
        pack_ids: list[str] | None = None,
        language: str | None = None,
    ) -> None:
        service = self._registry.for_user(user_id)
        service.start_new_game(save_slot, pack_ids, language=language)
        self._session_index.bind_session(user_id, save_slot)
        self._sync_current_chat_history(user_id)
        self._sync_current_session_metadata(user_id)
        if pack_ids is not None:
            self._pack_state_repository.replace_enabled_pack_ids(user_id, pack_ids)

    def load_game(self, user_id: str, save_slot: str, language: str | None = None) -> None:
        self._ensure_user_owns_slot(user_id, save_slot)
        service = self._registry.for_user(user_id)
        service.load_game(save_slot, language=language)
        self._hydrate_or_backfill_chat_history(user_id, save_slot)
        self._sync_current_session_metadata(user_id)
        state = service.get_current_state_view()
        self._pack_state_repository.replace_enabled_pack_ids(user_id, state.get('enabled_packs', []))

    def step(self, user_id: str, input_text: str) -> dict[str, Any]:
        result = self._registry.for_user(user_id).step(input_text)
        self._sync_current_chat_history(user_id)
        self._sync_current_session_metadata(user_id)
        return result

    def get_current_state_view(self, user_id: str) -> dict[str, Any]:
        return self._registry.for_user(user_id).get_current_state_view()

    def list_sessions(self, user_id: str) -> dict[str, Any]:
        service = self._registry.for_user(user_id)
        allowed_slots = self._session_index.list_session_slots(user_id)
        persisted_summaries = self._session_metadata_repository.list_session_summaries(user_id)
        persisted_by_slot = {summary["slot_id"]: summary for summary in persisted_summaries}

        missing_slots = [slot for slot in allowed_slots if slot not in persisted_by_slot]
        if missing_slots:
            fallback = service.list_sessions(allowed_slots=missing_slots)
            for summary in fallback.get("sessions", []):
                self._session_metadata_repository.save_session_metadata(
                    user_id,
                    summary["slot_id"],
                    self._summary_to_metadata(summary),
                )
            persisted_summaries = self._session_metadata_repository.list_session_summaries(user_id)

        active_state = service.get_current_state_view()
        active_slot = active_state.get("save_slot")
        selected_slot = active_slot if active_slot in {summary["slot_id"] for summary in persisted_summaries} else None
        if not selected_slot:
            selected_slot = persisted_summaries[0]["slot_id"] if persisted_summaries else "slot_001"
        return {
            "selected_slot": selected_slot,
            "backend_status": "online",
            "storage_backend": SETTINGS.storage_backend,
            "last_sync_label": "just now",
            "sessions": persisted_summaries,
        }

    def duplicate_session(self, user_id: str, source_slot: str, target_slot: str | None = None) -> dict[str, Any]:
        self._ensure_user_owns_slot(user_id, source_slot)
        service = self._registry.for_user(user_id)
        result = service.duplicate_session(source_slot, target_slot)
        duplicated_slot = result.get("selected_slot")
        if duplicated_slot:
            self._session_index.clone_binding(user_id, source_slot, duplicated_slot)
            duplicated_summary = next(
                (summary for summary in result.get("sessions", []) if summary.get("slot_id") == duplicated_slot),
                None,
            )
            if duplicated_summary:
                self._session_metadata_repository.save_session_metadata(
                    user_id,
                    duplicated_slot,
                    self._summary_to_metadata(duplicated_summary),
                )
            source_history = self._chat_history_repository.load_chat_history(user_id, source_slot)
            if source_history:
                self._chat_history_repository.save_chat_history(user_id, duplicated_slot, source_history)
        return self.list_sessions(user_id)

    def archive_session(self, user_id: str, save_slot: str) -> dict[str, Any]:
        self._ensure_user_owns_slot(user_id, save_slot)
        service = self._registry.for_user(user_id)
        result = service.archive_session(save_slot)
        self._session_index.archive_binding(user_id, save_slot)
        self._session_metadata_repository.delete_session_metadata(user_id, save_slot)
        self._chat_history_repository.delete_chat_history(user_id, save_slot)
        return self.list_sessions(user_id)

    def set_language(self, user_id: str, language: str) -> None:
        self._registry.for_user(user_id).set_language(language)

    def set_ui_update_mode(self, user_id: str, mode: str) -> None:
        self._registry.for_user(user_id).set_ui_update_mode(mode)

    def set_ui_auto_update_every(self, user_id: str, turns: int) -> None:
        self._registry.for_user(user_id).set_ui_auto_update_every(turns)

    def trigger_ui_generation(self, user_id: str, force: bool = False) -> None:
        self._registry.for_user(user_id).trigger_ui_generation(force=force)

    def trigger_ui_update(self, user_id: str) -> None:
        self._registry.for_user(user_id).trigger_ui_update()

    def _ensure_user_owns_slot(self, user_id: str, save_slot: str) -> None:
        if not self._session_index.user_owns_session(user_id, save_slot):
            raise ValueError("session not found")

    def _sync_current_session_metadata(self, user_id: str) -> None:
        service = self._registry.for_user(user_id)
        metadata = service.get_current_session_metadata()
        if metadata:
            self._session_metadata_repository.save_session_metadata(user_id, metadata["save_slot"], metadata)

    def _sync_current_chat_history(self, user_id: str) -> None:
        service = self._registry.for_user(user_id)
        state = service.get_current_state_view()
        save_slot = state.get("save_slot")
        if not save_slot:
            return
        self._chat_history_repository.save_chat_history(user_id, save_slot, service.get_current_chat_history())

    def _hydrate_or_backfill_chat_history(self, user_id: str, save_slot: str) -> None:
        service = self._registry.for_user(user_id)
        persisted_history = self._chat_history_repository.load_chat_history(user_id, save_slot)
        if persisted_history:
            service.set_current_chat_history(persisted_history)
            return
        self._chat_history_repository.save_chat_history(user_id, save_slot, service.get_current_chat_history())

    def _summary_to_metadata(self, summary: dict[str, Any]) -> dict[str, Any]:
        return {
            "save_slot": summary["slot_id"],
            "language": summary["language"],
            "enabled_packs": summary["enabled_packs"],
            "location_label": summary["location_label"],
            "turn_count": summary["turn_count"],
            "updated_at": summary["updated_label"],
        }


class PackService:
    """Application contract for pack lifecycle and card editing workflows."""

    def __init__(self, game_service: GameService, pack_state_repository: UserPackStateRepositoryProtocol):
        self._game_service = game_service
        self._pack_state_repository = pack_state_repository

    def list_packs(self, user_id: str) -> list[dict[str, Any]]:
        enabled_pack_ids = set(self._pack_state_repository.list_enabled_pack_ids(user_id))
        records = self._game_service.list_packs()
        for record in records:
            record['enabled'] = record['pack_id'] in enabled_pack_ids
        return records

    def install_pack_from_url(self, url: str) -> dict[str, Any]:
        return self._game_service.install_pack_from_url(url)

    def install_pack_from_zip(self, path: Path) -> dict[str, Any]:
        return self._game_service.install_pack_from_zip(path)

    def remove_pack(self, pack_id: str) -> None:
        self._game_service.remove_pack(pack_id)

    def enable_pack(self, user_id: str, pack_id: str, enabled: bool) -> None:
        records = {record['pack_id'] for record in self._game_service.list_packs()}
        if pack_id not in records:
            raise ValueError('pack not found')
        self._pack_state_repository.set_pack_enabled(user_id, pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        self._game_service.export_pack(pack_id, output_path)

    def export_pack_to_runtime_exports(self, pack_id: str) -> dict[str, Any]:
        return self._game_service.export_pack_to_runtime_exports(pack_id)

    def create_pack(self, manifest: dict[str, Any]) -> None:
        self._game_service.create_pack(manifest)

    def export_pack_manifest(self, data: dict[str, Any]) -> None:
        self._game_service.export_pack_manifest(data)

    def list_pack_card_types(self, pack_id: str) -> list[str]:
        return self._game_service.list_pack_card_types(pack_id)

    def list_pack_cards(self, pack_id: str) -> list[Path]:
        return self._game_service.list_pack_cards(pack_id)

    def load_card(self, path: Path) -> dict[str, Any]:
        return self._game_service.load_card(path)

    def create_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: dict[str, Any],
        body: str,
    ) -> Path:
        return self._game_service.create_card(pack_id, card_type, card_id, frontmatter, body)

    def save_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: dict[str, Any],
        body: str,
        original_path: Path | None = None,
    ) -> Path:
        return self._game_service.save_card(pack_id, card_type, card_id, frontmatter, body, original_path=original_path)

    def update_card(self, path: Path, frontmatter: dict[str, Any], body: str) -> None:
        self._game_service.update_card(path, frontmatter, body)

    def validate_card(self, frontmatter: dict[str, Any], body: str) -> None:
        self._game_service.validate_card(frontmatter, body)

    def delete_card(self, pack_id: str, path: Path) -> None:
        self._game_service.delete_card(pack_id, path)

    def get_card_template(self, card_type: str) -> dict[str, Any]:
        return self._game_service.get_card_template(card_type)


class SettingsService:
    """Application contract for runtime settings management."""

    def __init__(self, settings_repository: UserSettingsRepositoryProtocol, registry: GameServiceRegistry):
        self._settings_repository = settings_repository
        self._registry = registry

    def get_llm_settings(self, user_id: str) -> dict[str, Any]:
        settings = self._settings_repository.get_llm_settings(user_id)
        self._registry.for_user(user_id)
        return {
            'provider': settings['provider'],
            'model_name': settings['model_name'],
            'embedding_model': settings['embedding_model'],
            'base_url': settings['base_url'],
            'api_key_set': bool(settings['api_key']),
            'use_mock_llm': settings['use_mock_llm'],
            'force_fake_embeddings': settings['force_fake_embeddings'],
        }

    def update_llm_settings(self, user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        settings = self._settings_repository.update_llm_settings(user_id, payload)
        self._registry.for_user(user_id)
        return {
            'provider': settings['provider'],
            'model_name': settings['model_name'],
            'embedding_model': settings['embedding_model'],
            'base_url': settings['base_url'],
            'api_key_set': bool(settings['api_key']),
            'use_mock_llm': settings['use_mock_llm'],
            'force_fake_embeddings': settings['force_fake_embeddings'],
        }
