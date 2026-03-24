from __future__ import annotations

from pathlib import Path
from typing import Any

from game.service.api import GameService


class SessionService:
    """Application contract for game session lifecycle and turn progression."""

    def __init__(self, game_service: GameService):
        self._game_service = game_service

    def start_new_game(self, save_slot: str, pack_ids: list[str] | None = None, language: str | None = None) -> None:
        self._game_service.start_new_game(save_slot, pack_ids, language=language)

    def load_game(self, save_slot: str, language: str | None = None) -> None:
        self._game_service.load_game(save_slot, language=language)

    def step(self, input_text: str) -> dict[str, Any]:
        return self._game_service.step(input_text)

    def get_current_state_view(self) -> dict[str, Any]:
        return self._game_service.get_current_state_view()

    def list_sessions(self) -> dict[str, Any]:
        return self._game_service.list_sessions()

    def set_language(self, language: str) -> None:
        self._game_service.set_language(language)

    def set_ui_update_mode(self, mode: str) -> None:
        self._game_service.set_ui_update_mode(mode)

    def set_ui_auto_update_every(self, turns: int) -> None:
        self._game_service.set_ui_auto_update_every(turns)

    def trigger_ui_generation(self, force: bool = False) -> None:
        self._game_service.trigger_ui_generation(force=force)

    def trigger_ui_update(self) -> None:
        self._game_service.trigger_ui_update()


class PackService:
    """Application contract for pack lifecycle and card editing workflows."""

    def __init__(self, game_service: GameService):
        self._game_service = game_service

    def list_packs(self) -> list[dict[str, Any]]:
        return self._game_service.list_packs()

    def install_pack_from_url(self, url: str) -> dict[str, Any]:
        return self._game_service.install_pack_from_url(url)

    def install_pack_from_zip(self, path: Path) -> dict[str, Any]:
        return self._game_service.install_pack_from_zip(path)

    def remove_pack(self, pack_id: str) -> None:
        self._game_service.remove_pack(pack_id)

    def enable_pack(self, pack_id: str, enabled: bool) -> None:
        self._game_service.enable_pack(pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        self._game_service.export_pack(pack_id, output_path)

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

    def __init__(self, game_service: GameService):
        self._game_service = game_service

    def get_llm_settings(self) -> dict[str, Any]:
        return self._game_service.get_llm_settings()

    def update_llm_settings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._game_service.update_llm_settings(payload)
