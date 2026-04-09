from __future__ import annotations

from pathlib import Path
from typing import Any

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
from game.config import (
    SETTINGS,
    activate_runtime_billing_context,
    activate_runtime_llm_settings,
    load_runtime_llm_settings,
    normalize_llm_settings,
)
from game.packs.validator import validate_manifest
from game.service.api import GameService
from game.service.pack_builder_agent import PackBuilderAgent


class GameServiceRegistry:
    """Assign one transitional GameService instance per authenticated user."""

    def __init__(self, settings_repository: UserSettingsRepositoryProtocol):
        self._services: dict[str, GameService] = {}
        self._settings_repository = settings_repository

    def for_user(self, user_id: str) -> GameService:
        service = self._services.get(user_id)
        if service is None:
            service = GameService(user_id, settings_repository=self._settings_repository)
            self._services[user_id] = service
        service.set_runtime_llm_settings(
            self._settings_repository.get_llm_settings(user_id)
        )
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
        ui_template_repository: UserUiTemplateRepositoryProtocol,
    ):
        self._registry = registry
        self._session_index = session_index
        self._pack_state_repository = pack_state_repository
        self._session_metadata_repository = session_metadata_repository
        self._chat_history_repository = chat_history_repository
        self._ui_template_repository = ui_template_repository

    def start_new_game(
        self,
        user_id: str,
        save_slot: str,
        pack_ids: list[str] | None = None,
        language: str | None = None,
        ui_template_id: str | None = None,
    ) -> None:
        service = self._registry.for_user(user_id)
        service.start_new_game(save_slot, pack_ids, language=language)
        self._apply_ui_binding(
            user_id, save_slot, service, ui_template_id=ui_template_id
        )
        self._session_index.bind_session(user_id, save_slot)
        self._sync_current_chat_history(user_id)
        self._sync_current_session_metadata(user_id)
        if pack_ids is not None:
            self._pack_state_repository.replace_enabled_pack_ids(user_id, pack_ids)

    def load_game(
        self, user_id: str, save_slot: str, language: str | None = None
    ) -> None:
        self._ensure_user_owns_slot(user_id, save_slot)
        service = self._registry.for_user(user_id)
        active_state = service.get_current_state_view()
        if (
            active_state.get("save_slot") == save_slot
            and str(active_state.get("ui_generation_status") or "") == "ready"
        ):
            metadata_ready = True
        else:
            metadata_ready = False
        summary = next(
            (
                item
                for item in self._session_metadata_repository.list_session_summaries(
                    user_id
                )
                if item.get("slot_id") == save_slot
            ),
            None,
        )
        if (
            not metadata_ready
            and summary
            and str(summary.get("ui_generation_status") or "")
            not in {
                "",
                "ready",
            }
        ):
            raise ValueError("UI is still generating. Please wait until it is ready.")
        service.load_game(save_slot, language=language)
        self._apply_ui_binding(user_id, save_slot, service)
        self._hydrate_or_backfill_chat_history(user_id, save_slot)
        self._sync_current_session_metadata(user_id)
        state = service.get_current_state_view()
        self._pack_state_repository.replace_enabled_pack_ids(
            user_id, state.get("enabled_packs", [])
        )

    def step(self, user_id: str, input_text: str) -> dict[str, Any]:
        result = self._registry.for_user(user_id).step(input_text)
        self._sync_current_chat_history(user_id)
        self._sync_current_session_metadata(user_id)
        self._sync_current_ui_binding(user_id)
        return result

    def step_stream(self, user_id: str, input_text: str):
        for event in self._registry.for_user(user_id).step_stream(input_text):
            if event.get("type") == "done":
                self._sync_current_chat_history(user_id)
                self._sync_current_session_metadata(user_id)
                self._sync_current_ui_binding(user_id)
            yield event

    def get_current_state_view(self, user_id: str) -> dict[str, Any]:
        return self._registry.for_user(user_id).get_current_state_view()

    def list_sessions(self, user_id: str) -> dict[str, Any]:
        service = self._registry.for_user(user_id)
        allowed_slots = self._session_index.list_session_slots(user_id)
        persisted_summaries = self._session_metadata_repository.list_session_summaries(
            user_id
        )
        persisted_by_slot = {
            summary["slot_id"]: summary for summary in persisted_summaries
        }

        missing_slots = [
            slot for slot in allowed_slots if slot not in persisted_by_slot
        ]
        if missing_slots:
            fallback = service.list_sessions(allowed_slots=missing_slots)
            for summary in fallback.get("sessions", []):
                self._session_metadata_repository.save_session_metadata(
                    user_id,
                    summary["slot_id"],
                    self._summary_to_metadata(summary),
                )
            persisted_summaries = (
                self._session_metadata_repository.list_session_summaries(user_id)
            )

        active_state = service.get_current_state_view()
        active_slot = active_state.get("save_slot")
        active_ui_status = str(active_state.get("ui_generation_status") or "").strip()
        selected_slot = (
            active_slot
            if active_slot in {summary["slot_id"] for summary in persisted_summaries}
            else None
        )
        if not selected_slot:
            selected_slot = (
                persisted_summaries[0]["slot_id"] if persisted_summaries else "slot_001"
            )
        if active_slot:
            for summary in persisted_summaries:
                if summary["slot_id"] == active_slot and active_ui_status:
                    summary["ui_generation_status"] = active_ui_status
        return {
            "selected_slot": selected_slot,
            "backend_status": "online",
            "storage_backend": SETTINGS.storage_backend,
            "last_sync_label": "just now",
            "sessions": persisted_summaries,
        }

    def duplicate_session(
        self, user_id: str, source_slot: str, target_slot: str | None = None
    ) -> dict[str, Any]:
        self._ensure_user_owns_slot(user_id, source_slot)
        service = self._registry.for_user(user_id)
        result = service.duplicate_session(source_slot, target_slot)
        duplicated_slot = result.get("selected_slot")
        if duplicated_slot:
            self._session_index.clone_binding(user_id, source_slot, duplicated_slot)
            duplicated_summary = next(
                (
                    summary
                    for summary in result.get("sessions", [])
                    if summary.get("slot_id") == duplicated_slot
                ),
                None,
            )
            if duplicated_summary:
                self._session_metadata_repository.save_session_metadata(
                    user_id,
                    duplicated_slot,
                    self._summary_to_metadata(duplicated_summary),
                )
            source_history = self._chat_history_repository.load_chat_history(
                user_id, source_slot
            )
            if source_history:
                self._chat_history_repository.save_chat_history(
                    user_id, duplicated_slot, source_history
                )
        return self.list_sessions(user_id)

    def archive_session(self, user_id: str, save_slot: str) -> dict[str, Any]:
        self._ensure_user_owns_slot(user_id, save_slot)
        service = self._registry.for_user(user_id)
        result = service.archive_session(save_slot)
        self._session_index.archive_binding(user_id, save_slot)
        self._session_metadata_repository.delete_session_metadata(user_id, save_slot)
        self._chat_history_repository.delete_chat_history(user_id, save_slot)
        self._ui_template_repository.delete_session_ui_binding(user_id, save_slot)
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

    def set_ui_panel_visibility(
        self, user_id: str, panel_id: str, visible: bool
    ) -> None:
        service = self._registry.for_user(user_id)
        service.set_ui_panel_visibility(panel_id, visible)
        self._sync_current_ui_binding(user_id)

    def list_pack_ui_templates(
        self, user_id: str, pack_id: str
    ) -> list[dict[str, Any]]:
        return self._ui_template_repository.list_pack_ui_templates(user_id, pack_id)

    def create_pack_ui_template(
        self,
        user_id: str,
        pack_id: str,
        name: str,
        template_payload: dict[str, Any] | None = None,
        variable_template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        service = self._registry.for_user(user_id)
        payload = template_payload if isinstance(template_payload, dict) else None
        vars_template = (
            variable_template if isinstance(variable_template, dict) else None
        )
        if payload is None or vars_template is None:
            snapshot, vars_snapshot = service.get_ui_template_snapshot()
            if payload is None:
                payload = snapshot
            if vars_template is None:
                vars_template = vars_snapshot
        return self._ui_template_repository.save_pack_ui_template(
            user_id,
            pack_id,
            "",
            name,
            payload,
            vars_template,
        )

    def delete_pack_ui_template(
        self, user_id: str, pack_id: str, template_id: str
    ) -> None:
        in_use = self._ui_template_repository.count_sessions_using_ui_template(
            user_id, pack_id, template_id
        )
        if in_use > 0:
            raise ValueError(
                f"template is currently used by {in_use} active session(s)"
            )
        self._ui_template_repository.delete_pack_ui_template(
            user_id, pack_id, template_id
        )

    def bind_session_ui_template(
        self,
        user_id: str,
        save_slot: str,
        pack_id: str,
        template_id: str,
    ) -> dict[str, Any]:
        self._ensure_user_owns_slot(user_id, save_slot)
        service = self._registry.for_user(user_id)
        state = service.get_current_state_view()
        if state.get("save_slot") != save_slot:
            service.load_game(save_slot)
        template = self._ui_template_repository.get_pack_ui_template(
            user_id, pack_id, template_id
        )
        if not template:
            raise ValueError("ui template not found")
        service.apply_ui_template(
            template_id,
            template.get("template", {}),
            template.get("variable_template", {}),
            {},
            {},
        )
        return self._ui_template_repository.save_session_ui_binding(
            user_id,
            save_slot,
            pack_id,
            template_id,
            service.get_current_state_view().get("ui_variable_values", {}),
            service.get_current_state_view().get("ui_panel_visibility", {}),
        )

    def _ensure_user_owns_slot(self, user_id: str, save_slot: str) -> None:
        if not self._session_index.user_owns_session(user_id, save_slot):
            raise ValueError("session not found")

    def _sync_current_session_metadata(self, user_id: str) -> None:
        service = self._registry.for_user(user_id)
        metadata = service.get_current_session_metadata()
        if metadata:
            self._session_metadata_repository.save_session_metadata(
                user_id, metadata["save_slot"], metadata
            )

    def _sync_current_chat_history(self, user_id: str) -> None:
        service = self._registry.for_user(user_id)
        state = service.get_current_state_view()
        save_slot = state.get("save_slot")
        if not save_slot:
            return
        self._chat_history_repository.save_chat_history(
            user_id, save_slot, service.get_current_chat_history()
        )

    def _sync_current_ui_binding(self, user_id: str) -> None:
        service = self._registry.for_user(user_id)
        state = service.get_current_state_view()
        save_slot = str(state.get("save_slot") or "").strip()
        if not save_slot:
            return
        binding = self._ui_template_repository.get_session_ui_binding(
            user_id, save_slot
        )
        if not binding:
            return
        self._ui_template_repository.save_session_ui_binding(
            user_id,
            save_slot,
            str(binding.get("pack_id") or ""),
            str(binding.get("template_id") or ""),
            state.get("ui_variable_values", {}),
            state.get("ui_panel_visibility", {}),
        )

    def _apply_ui_binding(
        self,
        user_id: str,
        save_slot: str,
        service: GameService,
        ui_template_id: str | None = None,
    ) -> None:
        binding = self._ui_template_repository.get_session_ui_binding(
            user_id, save_slot
        )
        if ui_template_id:
            state = service.get_current_state_view()
            pack_id = ""
            enabled = state.get("enabled_packs", [])
            if isinstance(enabled, list) and enabled:
                pack_id = str(enabled[0])
            if not pack_id:
                return
            template = self._ui_template_repository.get_pack_ui_template(
                user_id, pack_id, ui_template_id
            )
            if not template:
                raise ValueError("ui template not found")
            service.apply_ui_template(
                ui_template_id,
                template.get("template", {}),
                template.get("variable_template", {}),
                {},
                {},
            )
            self._ui_template_repository.save_session_ui_binding(
                user_id,
                save_slot,
                pack_id,
                ui_template_id,
                service.get_current_state_view().get("ui_variable_values", {}),
                service.get_current_state_view().get("ui_panel_visibility", {}),
            )
            return
        if not binding:
            return
        template = self._ui_template_repository.get_pack_ui_template(
            user_id,
            str(binding.get("pack_id") or ""),
            str(binding.get("template_id") or ""),
        )
        if not template:
            return
        service.apply_ui_template(
            str(binding.get("template_id") or ""),
            template.get("template", {}),
            template.get("variable_template", {}),
            binding.get("variables", {}),
            binding.get("visibility", {}),
        )

    def _hydrate_or_backfill_chat_history(self, user_id: str, save_slot: str) -> None:
        service = self._registry.for_user(user_id)
        persisted_history = self._chat_history_repository.load_chat_history(
            user_id, save_slot
        )
        if persisted_history:
            service.set_current_chat_history(persisted_history)
            return
        self._chat_history_repository.save_chat_history(
            user_id, save_slot, service.get_current_chat_history()
        )

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

    def __init__(
        self,
        registry: GameServiceRegistry,
        pack_state_repository: UserPackStateRepositoryProtocol,
        pack_catalog_repository: UserPackCatalogRepositoryProtocol,
        ui_template_repository: UserUiTemplateRepositoryProtocol,
    ):
        self._registry = registry
        self._pack_state_repository = pack_state_repository
        self._pack_catalog_repository = pack_catalog_repository
        self._ui_template_repository = ui_template_repository

    def _persist_pack_record(self, user_id: str, record: dict[str, Any]) -> None:
        private_pack_id = str(record.get("pack_id") or "").strip()
        if not private_pack_id:
            return
        cards_root = str(record.get("cards_root") or "cards")
        version = str(record.get("version") or "").strip()
        self._pack_catalog_repository.upsert_user_pack(
            user_id,
            {
                "private_pack_id": private_pack_id,
                "name": str(record.get("name") or private_pack_id),
                "author": str(record.get("author") or "unknown"),
                "description": str(record.get("description") or ""),
                "cards_root": cards_root,
                "source": str(record.get("source") or "local"),
                "visibility": "private",
            },
        )
        if not version:
            return
        oss_prefix = str(SETTINGS.oss_prefix or "textrpg").strip("/")
        storage_path = f"{oss_prefix}/users/{user_id}/packs/{private_pack_id}/{version}/{cards_root}"
        self._pack_catalog_repository.upsert_user_pack_version(
            user_id,
            private_pack_id,
            {
                "version": version,
                "storage_backend": SETTINGS.pack_storage_backend,
                "storage_path": storage_path,
                "cards_root": cards_root,
                "manifest": {
                    "pack_id": private_pack_id,
                    "name": str(record.get("name") or private_pack_id),
                    "version": version,
                    "author": str(record.get("author") or "unknown"),
                    "description": str(record.get("description") or ""),
                },
            },
        )

    def _sync_catalog_from_runtime(
        self, user_id: str, runtime_records: list[dict[str, Any]]
    ) -> None:
        for record in runtime_records:
            self._persist_pack_record(user_id, record)

    def list_packs(self, user_id: str) -> list[dict[str, Any]]:
        game_service = self._registry.for_user(user_id)
        enabled_pack_ids = set(
            self._pack_state_repository.list_enabled_pack_ids(user_id)
        )
        runtime_records = game_service.list_packs()
        self._sync_catalog_from_runtime(user_id, runtime_records)
        catalog_records = self._pack_catalog_repository.list_user_packs(user_id)
        records = [
            {
                "pack_id": str(item.get("private_pack_id") or ""),
                "name": str(item.get("name") or ""),
                "version": str(item.get("version") or "0.1.0"),
                "author": str(item.get("author") or ""),
                "description": str(item.get("description") or ""),
                "cards_root": str(item.get("cards_root") or "cards"),
                "enabled": False,
                "source": str(item.get("source") or "local"),
            }
            for item in catalog_records
        ]
        if not records:
            records = runtime_records
        for record in records:
            record["enabled"] = record["pack_id"] in enabled_pack_ids
        return records

    def install_pack_from_url(self, user_id: str, url: str) -> dict[str, Any]:
        record = self._registry.for_user(user_id).install_pack_from_url(url)
        self._persist_pack_record(user_id, record)
        return record

    def install_pack_from_zip(self, user_id: str, path: Path) -> dict[str, Any]:
        record = self._registry.for_user(user_id).install_pack_from_zip(path)
        self._persist_pack_record(user_id, record)
        return record

    def remove_pack(self, user_id: str, pack_id: str) -> None:
        self._registry.for_user(user_id).remove_pack(pack_id)
        self._pack_catalog_repository.remove_user_pack(user_id, pack_id)

    def enable_pack(self, user_id: str, pack_id: str, enabled: bool) -> None:
        records = {
            record["pack_id"]
            for record in self._registry.for_user(user_id).list_packs()
        }
        if pack_id not in records:
            raise ValueError("pack not found")
        self._pack_state_repository.set_pack_enabled(user_id, pack_id, enabled)

    def export_pack(self, user_id: str, pack_id: str, output_path: Path) -> None:
        self._registry.for_user(user_id).export_pack(pack_id, output_path)

    def export_pack_to_runtime_exports(
        self, user_id: str, pack_id: str
    ) -> dict[str, Any]:
        return self._registry.for_user(user_id).export_pack_to_runtime_exports(pack_id)

    def create_pack(self, user_id: str, manifest: dict[str, Any]) -> None:
        self._registry.for_user(user_id).create_pack(manifest)
        self._persist_pack_record(
            user_id,
            {
                "pack_id": str(manifest.get("pack_id") or ""),
                "name": str(manifest.get("name") or ""),
                "version": str(manifest.get("version") or "0.1.0"),
                "author": str(manifest.get("author") or "unknown"),
                "description": str(manifest.get("description") or ""),
                "cards_root": str(manifest.get("cards_root") or "cards"),
                "source": "local",
            },
        )

    def export_pack_manifest(self, data: dict[str, Any]) -> None:
        validate_manifest(data)

    def list_pack_card_types(self, user_id: str, pack_id: str) -> list[str]:
        return self._registry.for_user(user_id).list_pack_card_types(pack_id)

    def list_pack_cards(self, user_id: str, pack_id: str) -> list[Path]:
        return self._registry.for_user(user_id).list_pack_cards(pack_id)

    def load_card(self, user_id: str, path: Path) -> dict[str, Any]:
        return self._registry.for_user(user_id).load_card(path)

    def create_card(
        self,
        user_id: str,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: dict[str, Any],
        body: str,
    ) -> Path:
        return self._registry.for_user(user_id).create_card(
            pack_id, card_type, card_id, frontmatter, body
        )

    def save_card(
        self,
        user_id: str,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: dict[str, Any],
        body: str,
        folder_path: str | None = None,
        original_path: Path | None = None,
    ) -> Path:
        return self._registry.for_user(user_id).save_card(
            pack_id,
            card_type,
            card_id,
            frontmatter,
            body,
            folder_path=folder_path,
            original_path=original_path,
        )

    def update_card(
        self, user_id: str, path: Path, frontmatter: dict[str, Any], body: str
    ) -> None:
        self._registry.for_user(user_id).update_card(path, frontmatter, body)

    def validate_card(
        self, user_id: str, frontmatter: dict[str, Any], body: str
    ) -> None:
        self._registry.for_user(user_id).validate_card(frontmatter, body)

    def delete_card(self, user_id: str, pack_id: str, path: Path) -> None:
        self._registry.for_user(user_id).delete_card(pack_id, path)

    def get_card_template(self, user_id: str, card_type: str) -> dict[str, Any]:
        return self._registry.for_user(user_id).get_card_template(card_type)

    def list_ui_templates(self, user_id: str, pack_id: str) -> list[dict[str, Any]]:
        return self._ui_template_repository.list_pack_ui_templates(user_id, pack_id)

    def create_ui_template(
        self,
        user_id: str,
        pack_id: str,
        name: str,
        template_payload: dict[str, Any],
        variable_template: dict[str, Any],
    ) -> dict[str, Any]:
        return self._ui_template_repository.save_pack_ui_template(
            user_id,
            pack_id,
            "",
            name,
            template_payload,
            variable_template,
        )

    def delete_ui_template(self, user_id: str, pack_id: str, template_id: str) -> None:
        in_use = self._ui_template_repository.count_sessions_using_ui_template(
            user_id, pack_id, template_id
        )
        if in_use > 0:
            raise ValueError(
                f"template is currently used by {in_use} active session(s)"
            )
        self._ui_template_repository.delete_pack_ui_template(
            user_id, pack_id, template_id
        )


class SettingsService:
    """Application contract for runtime settings management."""

    def __init__(
        self,
        settings_repository: UserSettingsRepositoryProtocol,
        registry: GameServiceRegistry,
    ):
        self._settings_repository = settings_repository
        self._registry = registry

    @staticmethod
    def _redeem_tier_table() -> dict[int, float]:
        # Pricing tiers (CNY) mapped to granted site coins.
        return {
            1: 100.0,
            6: 650.0,
            18: 2100.0,
            30: 3800.0,
        }

    def get_settings_overview(self, user_id: str) -> dict[str, Any]:
        plans = self.list_llm_plans(user_id)
        selected = self._settings_repository.get_user_selected_llm_plan(user_id)
        balance = self._settings_repository.get_user_coin_balance(user_id)
        return {
            "plans": plans,
            "selected_plan_id": str(selected.get("plan_id", "")) if selected else "",
            "coin_balance": float(balance),
            "redeem_tiers": self._redeem_tier_table(),
        }

    def list_llm_plans(self, user_id: str) -> list[dict[str, Any]]:
        # Warm the user-scoped runtime service so the rest of session endpoints
        # stay in sync with latest settings.
        self._registry.for_user(user_id)
        plans = self._settings_repository.list_llm_plans()
        return [
            {
                "plan_id": str(item.get("plan_id", "")),
                "name": str(item.get("name", "")),
                "description": str(item.get("description", "")),
                "provider": str(item.get("provider", "")),
                "model_name": str(item.get("model_name", "")),
                "embedding_model": str(item.get("embedding_model", "")),
                "base_url": str(item.get("base_url", "")),
                "input_tokens_per_coin": int(item.get("input_tokens_per_coin") or 0),
                "output_tokens_per_coin": int(item.get("output_tokens_per_coin") or 0),
                "display_order": int(item.get("display_order") or 0),
            }
            for item in plans
        ]

    def get_selected_llm_plan(self, user_id: str) -> dict[str, Any]:
        selected = self._settings_repository.get_user_selected_llm_plan(user_id)
        if not selected:
            return {"selected_plan_id": ""}
        return {
            "selected_plan_id": str(selected.get("plan_id", "")),
            "name": str(selected.get("name", "")),
            "description": str(selected.get("description", "")),
            "input_tokens_per_coin": int(selected.get("input_tokens_per_coin") or 0),
            "output_tokens_per_coin": int(selected.get("output_tokens_per_coin") or 0),
        }

    def set_selected_llm_plan(self, user_id: str, plan_id: str) -> dict[str, Any]:
        selected = self._settings_repository.set_user_selected_llm_plan(user_id, plan_id)
        self._registry.for_user(user_id)
        return {
            "selected_plan_id": str(selected.get("plan_id", "")),
            "name": str(selected.get("name", "")),
            "description": str(selected.get("description", "")),
            "input_tokens_per_coin": int(selected.get("input_tokens_per_coin") or 0),
            "output_tokens_per_coin": int(selected.get("output_tokens_per_coin") or 0),
        }

    def get_coin_balance(self, user_id: str) -> dict[str, Any]:
        return {"coin_balance": float(self._settings_repository.get_user_coin_balance(user_id))}

    def redeem_coin_key(self, user_id: str, redeem_key: str) -> dict[str, Any]:
        payload = self._settings_repository.redeem_coin_key(user_id, redeem_key)
        return {
            "coins_added": float(payload.get("coins_added", 0.0)),
            "balance_after": float(payload.get("balance_after", 0.0)),
        }

    def list_coin_consumptions(self, user_id: str, limit: int = 100) -> list[dict[str, Any]]:
        rows = self._settings_repository.list_user_coin_ledger(
            user_id,
            reason_type="llm_usage",
            limit=limit,
        )
        result: list[dict[str, Any]] = []
        for row in rows:
            detail = row.get("reason_detail_json")
            if not isinstance(detail, dict):
                detail = {}
            result.append(
                {
                    "ledger_id": int(row.get("ledger_id") or 0),
                    "created_at": str(row.get("created_at", "")),
                    "delta_coin": float(row.get("delta_coin") or 0),
                    "balance_after": float(row.get("balance_after") or 0),
                    "scene": str(detail.get("scene", "")),
                    "plan_id": str(detail.get("plan_id", "")),
                    "input_tokens": int(detail.get("input_tokens") or 0),
                    "output_tokens": int(detail.get("output_tokens") or 0),
                    "input_coin_cost": float(detail.get("input_coin_cost") or 0),
                    "output_coin_cost": float(detail.get("output_coin_cost") or 0),
                }
            )
        return result

    def get_llm_settings(self, user_id: str) -> dict[str, Any]:
        settings = self._settings_repository.get_llm_settings(user_id)
        self._registry.for_user(user_id)
        return {
            "provider": settings["provider"],
            "model_name": settings["model_name"],
            "embedding_model": settings["embedding_model"],
            "base_url": settings["base_url"],
            "api_key_set": bool(settings["api_key"]),
            "use_mock_llm": settings["use_mock_llm"],
            "force_fake_embeddings": settings["force_fake_embeddings"],
        }

    def update_llm_settings(
        self, user_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        settings = self._settings_repository.update_llm_settings(user_id, payload)
        self._registry.for_user(user_id)
        return {
            "provider": settings["provider"],
            "model_name": settings["model_name"],
            "embedding_model": settings["embedding_model"],
            "base_url": settings["base_url"],
            "api_key_set": bool(settings["api_key"]),
            "use_mock_llm": settings["use_mock_llm"],
            "force_fake_embeddings": settings["force_fake_embeddings"],
        }


class CardDesignerService:
    """Application contract for the Card Designer workbench."""

    def __init__(
        self,
        registry: GameServiceRegistry,
        designer_repository: CardDesignerSessionRepositoryProtocol,
        settings_repository: UserSettingsRepositoryProtocol,
    ):
        self._registry = registry
        self._designer_repository = designer_repository
        self._settings_repository = settings_repository
        self._agent_by_user: dict[str, PackBuilderAgent] = {}

    def _service(self, user_id: str) -> GameService:
        return self._registry.for_user(user_id)

    def _agent_for_user(self, user_id: str) -> PackBuilderAgent:
        agent = self._agent_by_user.get(user_id)
        if agent is None:
            agent = PackBuilderAgent(self._service(user_id))
            self._agent_by_user[user_id] = agent
        return agent

    def list_packs(self, user_id: str) -> list[dict[str, Any]]:
        return self._service(user_id).list_packs()

    def create_pack(self, user_id: str, manifest: dict[str, Any]) -> dict[str, Any]:
        self._service(user_id).create_pack(manifest)
        return manifest

    def list_card_types(self, user_id: str, pack_id: str) -> list[str]:
        return self._service(user_id).list_pack_card_types(pack_id)

    def list_cards(
        self,
        user_id: str,
        pack_id: str,
        category: str | None = None,
        keyword: str | None = None,
    ) -> list[dict[str, Any]]:
        service = self._service(user_id)
        root = service._pack_cards_root(pack_id)
        normalized_category = (category or "").strip()
        normalized_keyword = (keyword or "").strip().lower()
        records: list[dict[str, Any]] = []
        for path in service.list_pack_cards(pack_id):
            rel_path = str(path.relative_to(root)).replace("\\", "/")
            category_name, folder_path = self._extract_category_and_folder(root, path)
            if (
                normalized_category
                and normalized_category.lower() != "all"
                and category_name != normalized_category
            ):
                continue
            if normalized_keyword and normalized_keyword not in rel_path.lower():
                continue
            card = service.load_card(path, pack_id)
            frontmatter = card.get("frontmatter", {})
            card_id = str(frontmatter.get("id", path.stem))
            card_type = str(
                frontmatter.get("type")
                or self._infer_card_type_from_category(category_name)
                or "card"
            )
            title = str(frontmatter.get("name") or frontmatter.get("title") or card_id)
            records.append(
                {
                    "path": rel_path,
                    "folder_path": folder_path,
                    "card_id": card_id,
                    "card_type": card_type,
                    "category": category_name,
                    "title": title,
                }
            )
        return sorted(records, key=lambda item: (item["category"], item["card_id"]))

    def load_card(self, user_id: str, pack_id: str, card_path: str) -> dict[str, Any]:
        service = self._service(user_id)
        target = self._resolve_card_path(service, pack_id, card_path)
        card = service.load_card(target, pack_id)
        frontmatter = card.get("frontmatter", {})
        root = service._pack_cards_root(pack_id)
        category_name, folder_path = self._extract_category_and_folder(root, target)
        return {
            "path": str(target.relative_to(root)).replace("\\", "/"),
            "folder_path": folder_path,
            "pack_id": pack_id,
            "card_type": str(
                frontmatter.get("type")
                or self._infer_card_type_from_category(category_name)
                or "card"
            ),
            "card_id": str(frontmatter.get("id", target.stem)),
            "frontmatter": frontmatter,
            "body": str(card.get("body", "")),
        }

    def get_card_template(self, user_id: str, card_type: str) -> dict[str, Any]:
        return self._service(user_id).get_card_template(card_type)

    def save_card(
        self,
        user_id: str,
        pack_id: str,
        card_type: str,
        card_id: str,
        folder_path: str | None,
        frontmatter: dict[str, Any],
        body: str,
        original_path: str | None = None,
    ) -> dict[str, Any]:
        service = self._service(user_id)
        original = (
            self._resolve_card_path(service, pack_id, original_path)
            if original_path
            else None
        )
        normalized_folder = self._normalize_folder_path(folder_path)
        if normalized_folder is None and original is not None:
            normalized_folder = self._folder_path_from_existing(
                service._pack_cards_root(pack_id),
                original,
            )
        saved = service.save_card(
            pack_id,
            card_type,
            card_id,
            frontmatter,
            body,
            folder_path=normalized_folder,
            original_path=original,
        )
        return self.load_card(
            user_id,
            pack_id,
            str(saved.relative_to(service._pack_cards_root(pack_id))).replace(
                "\\", "/"
            ),
        )

    def validate_card(
        self, user_id: str, frontmatter: dict[str, Any], body: str
    ) -> None:
        self._service(user_id).validate_card(frontmatter, body)

    def delete_card(self, user_id: str, pack_id: str, card_path: str) -> None:
        service = self._service(user_id)
        service.delete_card(
            pack_id, self._resolve_card_path(service, pack_id, card_path)
        )

    def create_agent_session(
        self, user_id: str, pack_id: str | None = None
    ) -> dict[str, Any]:
        return self._designer_repository.create_designer_session(user_id, pack_id)

    def get_agent_session(self, user_id: str, session_id: str) -> dict[str, Any]:
        session = self._designer_repository.get_designer_session(user_id, session_id)
        if not session:
            raise ValueError("designer session not found")
        return session

    def send_agent_message(
        self, user_id: str, session_id: str, message: str
    ) -> dict[str, Any]:
        session = self.get_agent_session(user_id, session_id)
        runtime_settings = normalize_llm_settings(
            self._settings_repository.get_llm_settings(user_id),
            load_runtime_llm_settings(),
        )
        state = dict(session.get("state", {}) or {})
        with activate_runtime_llm_settings(runtime_settings), activate_runtime_billing_context(
            {
                "user_id": user_id,
                "plan_id": str(getattr(runtime_settings, "plan_id", "") or ""),
                "on_usage": lambda scene, in_tokens, out_tokens: self._settings_repository.charge_llm_usage(
                    user_id=user_id,
                    plan_id=str(getattr(runtime_settings, "plan_id", "") or ""),
                    scene=f"designer:{scene}",
                    input_tokens=int(in_tokens or 0),
                    output_tokens=int(out_tokens or 0),
                    input_tokens_per_coin=int(getattr(runtime_settings, "input_tokens_per_coin", 0) or 0),
                    output_tokens_per_coin=int(getattr(runtime_settings, "output_tokens_per_coin", 0) or 0),
                )
                if str(getattr(runtime_settings, "plan_id", "") or "").strip()
                and int(getattr(runtime_settings, "input_tokens_per_coin", 0) or 0) > 0
                and int(getattr(runtime_settings, "output_tokens_per_coin", 0) or 0) > 0
                else None,
            }
        ):
            result = self._agent_for_user(user_id).process(message, state)
        updated_state = result.get("state", state)
        selected_pack_id = str(
            updated_state.get("selected_pack_id", "")
            or session.get("selected_pack_id", "")
        )
        persisted = self._designer_repository.save_designer_session(
            user_id,
            session_id,
            {
                "selected_pack_id": selected_pack_id,
                "mode": session.get("mode", "edit"),
                "state": updated_state,
            },
        )
        return {
            "session_id": session_id,
            "assistant": str(result.get("assistant", "")),
            "tool_logs": [str(item) for item in result.get("tool_logs", [])],
            "selected_pack_id": persisted.get("selected_pack_id", ""),
            "state": persisted.get("state", {}),
        }

    def _resolve_card_path(
        self, service: GameService, pack_id: str, card_path: str | None
    ) -> Path:
        if not card_path:
            raise ValueError("card path is required")
        root = service._pack_cards_root(pack_id)
        raw = Path(str(card_path).strip())
        target = raw if raw.is_absolute() else (root / raw)
        if not service.card_exists(pack_id, target):
            raise ValueError("card not found")
        if not service._is_within(target, root):
            raise ValueError("card path is outside pack root")
        return target

    def _extract_category_and_folder(self, root: Path, path: Path) -> tuple[str, str]:
        rel = path.relative_to(root)
        parts = rel.parts
        if len(parts) <= 1:
            return (path.parent.name, "")
        category = str(parts[0]).strip()
        folder = "/".join(
            str(part).strip() for part in parts[1:-1] if str(part).strip()
        )
        return (category, folder)

    def _infer_card_type_from_category(self, category: str) -> str:
        normalized = str(category).strip()
        if not normalized:
            return "card"
        if normalized == "memories":
            return "memory"
        if normalized.endswith("s") and len(normalized) > 1:
            return normalized[:-1]
        return normalized

    def _normalize_folder_path(self, folder_path: str | None) -> str | None:
        if folder_path is None:
            return None
        raw = str(folder_path).replace("\\", "/").strip().strip("/")
        if not raw:
            return ""
        if raw.startswith("/"):
            raise ValueError("folder path must be relative")
        parts = [segment.strip() for segment in raw.split("/")]
        if any((not segment) or segment in {".", ".."} for segment in parts):
            raise ValueError("folder path is invalid")
        return "/".join(parts)

    def _folder_path_from_existing(self, root: Path, path: Path) -> str:
        rel = path.relative_to(root)
        if len(rel.parts) <= 2:
            return ""
        return "/".join(rel.parts[1:-1])
