from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from copy import deepcopy
from contextlib import ExitStack, contextmanager
from pathlib import Path
import re
from typing import Any, Dict, List, Optional
import gc
import json
import logging
import shutil
import threading

from ..config import (
    ARCHIVES_DIR,
    CARDS_DIR,
    EXPORTS_DIR,
    SAVES_DIR,
    PACKS_DIR,
    PACK_REGISTRY_PATH,
    USER_PACKS_DIR,
    SETTINGS,
    activate_runtime_llm_settings,
    activate_runtime_billing_context,
    get_slot_paths,
    load_runtime_llm_settings,
    normalize_llm_settings,
)
from ..core.card_repository import CardRepository
from ..core.rule_engine import RuleEngine
from ..core.graph import build_turn_graphs, retrieve_context, should_run_ops
from ..core.story_graph import seed_story_runtime
from ..infrastructure.contracts import (
    ChatHistoryStoreProtocol,
    KGStoreProtocol,
    RAGStoreProtocol,
    SessionMetadataStoreProtocol,
    UIPanelStoreProtocol,
    UserSettingsRepositoryProtocol,
    WorldStoreProtocol,
)
from ..infrastructure.session_files import (
    SessionMetadataStore,
)
from ..infrastructure.postgres.session_files import (
    PostgresChatHistoryStore,
    PostgresUIPanelStore,
)
from ..infrastructure.store_factory import SessionStoreFactory
from ..packs.manager import PackManager
from ..packs.card_editor import (
    DEFAULT_CARD_TYPES,
    validate_card,
)
from ..packs.validator import validate_manifest
from .ui_agents import (
    UICardPlannerAgent,
    UIPanelStateAgent,
    UIPanelUpdateAgent,
    UIVariableUpdateAgent,
)


logger = logging.getLogger(__name__)


@dataclass
class GameSession:
    save_slot: str
    repo: CardRepository
    world: WorldStoreProtocol
    kg: KGStoreProtocol
    rag: RAGStoreProtocol
    rules: RuleEngine
    narration_app: Any
    ops_app: Any
    state: Dict[str, Any]


class GameService:
    _UI_VAR_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_.-]+)\s*\}\}")

    def __init__(
        self,
        user_id: str = "default",
        packs_root: Path | None = None,
        store_factory: SessionStoreFactory | None = None,
        settings_repository: UserSettingsRepositoryProtocol | None = None,
    ):
        self.user_id = str(user_id)
        self._user_pack_root = USER_PACKS_DIR / self.user_id
        self._user_pack_registry_path = self._user_pack_root / "pack_registry.json"
        self._bootstrap_user_pack_namespace()
        if packs_root is not None:
            user_packs_root = packs_root
        elif SETTINGS.pack_storage_backend == "oss":
            user_packs_root = Path(SETTINGS.pack_cache_root) / self.user_id
        else:
            user_packs_root = self._user_pack_root
        self.pack_manager = PackManager(
            packs_root=user_packs_root,
            registry_path=self._user_pack_registry_path,
            user_namespace=self.user_id,
        )
        if SETTINGS.storage_backend != "postgres":
            raise ValueError(
                "PostgreSQL-only mode requires TEXTRPG_STORAGE_BACKEND=postgres"
            )
        if not SETTINGS.postgres_dsn:
            raise ValueError(
                "TEXTRPG_POSTGRES_DSN is required when TEXTRPG_STORAGE_BACKEND=postgres"
            )
        self.chat_history_store = PostgresChatHistoryStore(SETTINGS.postgres_dsn)
        self.ui_panel_store = PostgresUIPanelStore(SETTINGS.postgres_dsn)
        self.session_metadata_store: SessionMetadataStoreProtocol = (
            SessionMetadataStore()
        )
        self.store_factory = store_factory or SessionStoreFactory()
        self._session: GameSession | None = None
        self.ui_planner = UICardPlannerAgent()
        self.ui_state_agent = UIPanelStateAgent()
        self.ui_update_agent = UIPanelUpdateAgent()
        self.ui_variable_agent = UIVariableUpdateAgent()
        self._runtime_llm_settings = load_runtime_llm_settings()
        self._settings_repository = settings_repository
        self._ui_lock = threading.Lock()
        self._ui_gen_thread: threading.Thread | None = None
        self._ui_update_thread: threading.Thread | None = None
        self._pending_ui_generation_requested = False
        self._pending_ui_generation_force = False

    def _bootstrap_user_pack_namespace(self) -> None:
        self._user_pack_root.mkdir(parents=True, exist_ok=True)
        if self._user_pack_registry_path.exists():
            return
        self._user_pack_registry_path.write_text(
            json.dumps({"packs": {}}, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        if not PACK_REGISTRY_PATH.exists():
            return
        try:
            shared_registry = json.loads(PACK_REGISTRY_PATH.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(shared_registry, dict):
            return
        packs = shared_registry.get("packs", {})
        if not isinstance(packs, dict):
            return
        normalized_packs = {"packs": dict(packs)}
        self._user_pack_registry_path.write_text(
            json.dumps(normalized_packs, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        for pack_id, payload in packs.items():
            if SETTINGS.pack_storage_backend == "oss":
                # OSS mode keeps a local cache under pack_cache_root; avoid persisting
                # pack files inside data/user_packs.
                continue
            if not isinstance(payload, dict):
                continue
            version = str(payload.get("version", "")).strip()
            if not version:
                continue
            source_dir = PACKS_DIR / pack_id / version
            target_dir = self._user_pack_root / pack_id / version
            if source_dir.exists() and not target_dir.exists():
                target_dir.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(source_dir, target_dir, dirs_exist_ok=True)

    def start_new_game(
        self,
        save_slot: str,
        pack_ids: Optional[List[str]] = None,
        language: Optional[str] = None,
    ) -> None:
        self._release_active_session()
        if pack_ids is not None:
            self._set_enabled_packs(pack_ids)
        self._session = self._build_session(save_slot, language=language)
        self._persist_session_metadata(self._session)
        self._schedule_ui_generation(force=True)

    def load_game(self, save_slot: str, language: Optional[str] = None) -> None:
        self._release_active_session()
        metadata = self._load_session_metadata(save_slot)
        ui_generation_status = str(metadata.get("ui_generation_status", "") or "")
        if ui_generation_status and ui_generation_status != "ready":
            raise ValueError("UI is still generating. Please wait until it is ready.")
        if metadata.get("enabled_packs"):
            self._set_enabled_packs(metadata.get("enabled_packs", []))
        self._session = self._build_session(save_slot, language=language)
        self._persist_session_metadata(self._session)
        self._schedule_ui_generation(force=False)

    def step(self, input_text: str) -> Dict[str, Any]:
        if not self._session:
            raise RuntimeError("game not started")
        session = self._session
        session.state["turn_id"] = session.state.get("turn_id", 0) + 1
        session.state["player_input"] = input_text
        turn_state = deepcopy(session.state)

        ops_result_box: Dict[str, Any] = {}
        ops_error_box: List[BaseException] = []
        ops_thread = self._start_ops_branch(
            session, turn_state, ops_result_box, ops_error_box
        )
        try:
            with self._llm_settings_scope():
                narration_result = session.narration_app.invoke(turn_state)
        except Exception as exc:
            message = str(exc)
            # Surface common provider/model mismatches as a user-fixable 400 error.
            if "invalid_parameter_error" in message or "not supported" in message:
                raise ValueError(f"LLM settings invalid: {message}") from exc
            raise
        self._wait_for_ops_branch(ops_thread, ops_result_box, ops_error_box)
        return self._finalize_turn(
            session, input_text, narration_result, ops_result_box.get("result")
        )

    def step_stream(self, input_text: str):
        if not self._session:
            raise RuntimeError("game not started")

        session = self._session
        session.state["turn_id"] = session.state.get("turn_id", 0) + 1
        session.state["player_input"] = input_text
        turn_state = deepcopy(session.state)

        ops_result_box: Dict[str, Any] = {}
        ops_error_box: List[BaseException] = []
        ops_thread = self._start_ops_branch(
            session, turn_state, ops_result_box, ops_error_box
        )

        try:
            with self._llm_settings_scope():
                final_state: Dict[str, Any] | None = None
                for mode, payload in session.narration_app.stream(
                    turn_state,
                    stream_mode=["custom", "values"],
                ):
                    if mode == "custom" and isinstance(payload, dict):
                        if (
                            payload.get("type") == "narration_delta"
                            and isinstance(payload.get("delta"), str)
                            and payload.get("delta")
                        ):
                            yield {"type": "narration_delta", "delta": payload["delta"]}
                        continue

                    if mode == "values" and isinstance(payload, dict):
                        final_state = payload

                if isinstance(final_state, dict):
                    narration_result = final_state
                else:
                    narration_result = {}
        except Exception as exc:
            message = str(exc)
            if "invalid_parameter_error" in message or "not supported" in message:
                raise ValueError(f"LLM settings invalid: {message}") from exc
            raise

        self._wait_for_ops_branch(ops_thread, ops_result_box, ops_error_box)
        result = self._finalize_turn(
            session,
            input_text,
            narration_result,
            ops_result_box.get("result"),
        )
        yield {
            "type": "done",
            "result": result,
            "state_view": self.get_current_state_view(),
        }

    def _start_ops_branch(
        self,
        session: GameSession,
        turn_state: Dict[str, Any],
        result_box: Dict[str, Any],
        error_box: List[BaseException],
    ) -> threading.Thread | None:
        if not should_run_ops(turn_state):
            return None

        def runner() -> None:
            try:
                with self._llm_settings_scope():
                    result_box["result"] = session.ops_app.invoke(deepcopy(turn_state))
            except Exception as exc:
                error_box.append(exc)

        thread = threading.Thread(target=runner, daemon=True)
        thread.start()
        return thread

    def _wait_for_ops_branch(
        self,
        ops_thread: threading.Thread | None,
        result_box: Dict[str, Any],
        error_box: List[BaseException],
    ) -> None:
        if ops_thread is not None:
            ops_thread.join()
        if error_box:
            exc = error_box[0]
            message = str(exc)
            if "invalid_parameter_error" in message or "not supported" in message:
                raise ValueError(f"LLM settings invalid: {message}") from exc
            raise exc

    def _finalize_turn(
        self,
        session: GameSession,
        input_text: str,
        narration_result: Dict[str, Any],
        ops_result: Dict[str, Any] | None,
    ) -> Dict[str, Any]:
        session.state.update(narration_result or {})
        if isinstance(ops_result, dict):
            session.state.update(ops_result)

        narration = str(session.state.get("narration", ""))
        result = {
            "narration": narration,
            "validated_ops": session.state.get("validated_ops", []),
            "errors": session.state.get("errors", []),
        }

        history = list(session.state.get("chat_history", []))
        history.append({"role": "user", "content": input_text})
        history.append({"role": "assistant", "content": narration})
        session.state["chat_history"] = history
        session.state["recent_messages"] = history[-10:]

        self._refresh_world_facts(session)
        session.state.update(
            retrieve_context(
                session.state,
                session.repo,
                session.rag,
                session.world,
                session.kg,
                session.rules,
            )
        )
        if session.state.get("ui_update_mode", "manual") == "auto":
            every = int(session.state.get("ui_auto_update_every", 1) or 1)
            if every <= 0:
                every = 1
            if session.state["turn_id"] % every == 0:
                self._schedule_ui_update()
        else:
            self._refresh_custom_ui_panels(session)
        self._save_chat_history(session)
        self._persist_session_metadata(session)
        return result

    def set_language(self, language: str) -> None:
        if not self._session:
            return
        self._session.state["language"] = language
        self._persist_session_metadata(self._session)

    def get_current_state_view(self) -> Dict[str, Any]:
        if not self._session:
            return {}
        state = self._session.state
        return {
            "turn_id": state.get("turn_id"),
            "recent_messages": state.get("recent_messages", []),
            "chat_history": state.get("chat_history", []),
            "narration": state.get("narration", ""),
            "world_facts": state.get("world_facts", {}),
            "active_events": state.get("active_events", []),
            "event_conditions": state.get("event_conditions", []),
            "allowed_actions": state.get("allowed_actions", []),
            "retrieved_cards": [c.get("id") for c in state.get("retrieved_cards", [])],
            "validated_ops": state.get("validated_ops", []),
            "errors": state.get("errors", []),
            "custom_ui_panels": state.get("custom_ui_panels", []),
            "ui_template_id": state.get("ui_template_id", ""),
            "ui_variable_values": state.get("ui_variable_values", {}),
            "ui_panel_visibility": state.get("ui_panel_visibility", {}),
            "save_slot": state.get("save_slot"),
            "ui_generation_status": state.get("ui_generation_status", "idle"),
            "ui_update_status": state.get("ui_update_status", "idle"),
            "ui_update_mode": state.get("ui_update_mode", "manual"),
            "ui_auto_update_every": state.get("ui_auto_update_every", 1),
            "enabled_packs": state.get("enabled_packs", []),
            "location_label": self._infer_location_label(state),
            "storage_backend_label": SETTINGS.storage_backend,
        }

    def get_current_session_metadata(self) -> Dict[str, Any]:
        if not self._session:
            return {}
        return self._build_metadata_payload(self._session)

    def get_current_chat_history(self) -> List[Dict[str, Any]]:
        if not self._session:
            return []
        history = self._session.state.get("chat_history", [])
        if not isinstance(history, list):
            return []
        return [item for item in history if isinstance(item, dict)]

    def set_current_chat_history(self, history: List[Dict[str, Any]]) -> None:
        if not self._session:
            return
        normalized = [item for item in history if isinstance(item, dict)]
        self._session.state["chat_history"] = normalized
        self._session.state["recent_messages"] = normalized[-10:]
        self._refresh_custom_ui_panels(self._session)
        self._save_chat_history(self._session)

    def list_sessions(
        self,
        allowed_slots: Optional[List[str]] = None,
        selected_slot: Optional[str] = None,
    ) -> Dict[str, Any]:
        sessions: List[Dict[str, Any]] = []
        allowed_slot_set = set(allowed_slots or [])
        if SAVES_DIR.exists():
            slot_dirs = [path for path in SAVES_DIR.iterdir() if path.is_dir()]
            for slot_dir in sorted(
                slot_dirs, key=lambda path: path.stat().st_mtime, reverse=True
            ):
                if allowed_slot_set and slot_dir.name not in allowed_slot_set:
                    continue
                sessions.append(self._build_session_summary(slot_dir.name))

        selected_slot = selected_slot or (
            self._session.save_slot
            if self._session
            else (sessions[0]["slot_id"] if sessions else "slot_001")
        )
        if sessions and selected_slot not in {
            session["slot_id"] for session in sessions
        }:
            selected_slot = sessions[0]["slot_id"]
        return {
            "selected_slot": selected_slot,
            "backend_status": "online",
            "storage_backend": SETTINGS.storage_backend,
            "last_sync_label": "just now",
            "sessions": sessions,
        }

    def duplicate_session(
        self, source_slot: str, target_slot: Optional[str] = None
    ) -> Dict[str, Any]:
        source_paths = get_slot_paths(source_slot)
        if not source_paths["data_dir"].exists():
            raise ValueError("save slot not found")

        destination_slot = self._resolve_duplicate_slot(source_slot, target_slot)
        destination_paths = get_slot_paths(destination_slot)
        shutil.copytree(source_paths["data_dir"], destination_paths["data_dir"])

        metadata = self.session_metadata_store.load(
            destination_paths["session_meta_path"]
        )
        metadata["save_slot"] = destination_slot
        metadata["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        self.session_metadata_store.save(
            destination_paths["session_meta_path"], metadata
        )
        return self.list_sessions(selected_slot=destination_slot)

    def archive_session(self, save_slot: str) -> Dict[str, Any]:
        source_paths = get_slot_paths(save_slot)
        if not source_paths["data_dir"].exists():
            raise ValueError("save slot not found")

        if self._session and self._session.save_slot == save_slot:
            self._release_active_session()

        # Clear runtime caches keyed by slot name (e.g. postgres session_key)
        # to prevent stale chat/UI data from being reused by a future slot
        # with the same save_slot id.
        self._clear_slot_runtime_caches(save_slot)

        archived_path = self._resolve_archive_path(save_slot)
        archived_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_paths["data_dir"]), str(archived_path))

        remaining_slots = (
            [
                path.name
                for path in sorted(
                    SAVES_DIR.iterdir(),
                    key=lambda item: item.stat().st_mtime,
                    reverse=True,
                )
                if path.is_dir()
            ]
            if SAVES_DIR.exists()
            else []
        )
        next_selected = remaining_slots[0] if remaining_slots else "slot_001"
        return self.list_sessions(selected_slot=next_selected)

    def _clear_slot_runtime_caches(self, save_slot: str) -> None:
        paths = get_slot_paths(save_slot)
        try:
            self.chat_history_store.save(paths["chat_history_path"], [])
        except Exception:
            logger.exception(
                "ui-observe archive clear chat cache failed user=%s slot=%s",
                self.user_id,
                save_slot,
            )
        try:
            self.ui_panel_store.save(paths["ui_panels_path"], [])
        except Exception:
            logger.exception(
                "ui-observe archive clear ui cache failed user=%s slot=%s",
                self.user_id,
                save_slot,
            )

    def get_llm_settings(self) -> Dict[str, Any]:
        return self._runtime_llm_settings.to_public_dict()

    def set_runtime_llm_settings(self, payload: Dict[str, Any]) -> None:
        self._runtime_llm_settings = normalize_llm_settings(
            payload, self._runtime_llm_settings
        )

    def list_packs(self) -> List[Dict[str, Any]]:
        return [r.__dict__ for r in self.pack_manager.list_packs()]

    def install_pack_from_url(self, url: str) -> Dict[str, Any]:
        record = self.pack_manager.install_pack_from_url(url)
        return record.__dict__

    def install_pack_from_zip(self, path: Path) -> Dict[str, Any]:
        record = self.pack_manager.install_pack_from_zip(path)
        return record.__dict__

    def remove_pack(self, pack_id: str) -> None:
        record = self.pack_manager.registry.get(pack_id)
        if record and record.source == "builtin":
            raise ValueError("builtin packs cannot be removed")
        self.pack_manager.remove_pack(pack_id)

    def enable_pack(self, pack_id: str, enabled: bool) -> None:
        self.pack_manager.enable_pack(pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        self.pack_manager.export_pack(pack_id, output_path)

    def export_pack_to_runtime_exports(self, pack_id: str) -> Dict[str, Any]:
        record = self.pack_manager.registry.get(pack_id)
        if not record:
            raise ValueError("pack not found")
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EXPORTS_DIR / f"{pack_id}-{record.version}.zip"
        self.pack_manager.export_pack(pack_id, output_path)
        return {
            "ok": True,
            "pack_id": pack_id,
            "export_path": str(output_path),
        }

    def create_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
    ) -> Path:
        return self.pack_manager.create_card(
            pack_id, card_type, card_id, frontmatter, body
        )

    def save_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
        folder_path: str | None = None,
        original_path: Path | None = None,
    ) -> Path:
        return self.pack_manager.save_card(
            pack_id,
            card_type,
            card_id,
            frontmatter,
            body,
            folder_path=folder_path,
            original_path=original_path,
        )

    def update_card(self, path: Path, frontmatter: Dict[str, Any], body: str) -> None:
        self.pack_manager.update_card(path, frontmatter, body)

    def validate_card(self, frontmatter: Dict[str, Any], body: str) -> None:
        validate_card(frontmatter, body)

    def export_pack_manifest(self, data: Dict[str, Any]) -> None:
        validate_manifest(data)

    def create_pack(self, manifest: Dict[str, Any]) -> None:
        record = self.pack_manager.create_pack(manifest)
        self.pack_manager.sync_pack_content(record.pack_id)

    def get_card_template(self, card_type: str) -> Dict[str, Any]:
        normalized_type = str(card_type).strip() or "card"
        return {
            "id": "new_id",
            "type": normalized_type,
            "tags": [],
            "initial_relations": [],
            "hooks": [],
        }

    def list_pack_card_types(self, pack_id: str) -> List[str]:
        root = self._pack_cards_root(pack_id)
        existing: List[str] = []
        seen: set[str] = set()
        for path in self.pack_manager.list_pack_cards(pack_id):
            fm = self.pack_manager.load_card(pack_id, path).get("frontmatter", {})
            t = str(fm.get("type", "")).strip()
            if t and t not in seen:
                seen.add(t)
                existing.append(t)

        merged = list(existing)
        for t in DEFAULT_CARD_TYPES:
            if t not in seen:
                merged.append(t)
        return merged

    def list_pack_cards(self, pack_id: str) -> List[Path]:
        return self.pack_manager.list_pack_cards(pack_id)

    def load_card(self, path: Path, pack_id: str | None = None) -> Dict[str, Any]:
        resolved_pack_id = pack_id or self._infer_pack_id_from_card_path(path)
        return self.pack_manager.load_card(resolved_pack_id, path)

    def delete_card(self, pack_id: str, path: Path) -> None:
        self.pack_manager.delete_card(pack_id, path)

    def card_exists(self, pack_id: str, path: Path) -> bool:
        return self.pack_manager.card_exists(pack_id, path)

    def _infer_pack_id_from_card_path(self, path: Path) -> str:
        raw = Path(path)
        try:
            rel = raw.resolve(strict=False).relative_to(
                self.pack_manager.packs_root.resolve(strict=False)
            )
        except Exception:
            rel = raw
        parts = rel.parts
        if not parts:
            raise ValueError("invalid card path")
        return str(parts[0])

    def _build_session(
        self, save_slot: str, language: Optional[str] = None
    ) -> GameSession:
        paths = get_slot_paths(save_slot)
        metadata = self.session_metadata_store.load(paths["session_meta_path"])
        enabled_documents = self.pack_manager.list_enabled_card_documents()
        enabled_canvas_documents = (
            self.pack_manager.list_enabled_canvas_state_documents()
        )
        repo = CardRepository(cards_dir=CARDS_DIR)
        repo.load(
            extra_documents=enabled_documents,
            canvas_documents=enabled_canvas_documents,
        )
        repo_cards = list(repo.all())
        card_type_counts: Dict[str, int] = {}
        for card in repo_cards:
            card_type_counts[card.type] = card_type_counts.get(card.type, 0) + 1
        logger.warning(
            "oss-cards session repo user=%s slot=%s enabled_docs=%d canvas_docs=%d total_cards=%d type_counts=%s card_ids=%s",
            self.user_id,
            save_slot,
            len(enabled_documents),
            len(enabled_canvas_documents),
            len(repo_cards),
            card_type_counts,
            [c.id for c in repo_cards],
        )
        with self._llm_settings_scope():
            stores = self.store_factory.create(
                world_db_path=paths["world_db_path"],
                kg_db_path=paths["kg_db_path"],
                rag_dir=paths["rag_dir"],
            )
        world = stores.world
        kg = stores.kg
        rag = stores.rag
        cards_index = {c.id: {"type": c.type, "tags": c.tags} for c in repo.all()}
        rules = RuleEngine(cards_index)
        if not kg.all_edges():
            for card in repo.all():
                for rel in card.initial_relations:
                    kg.add_edge(
                        rel["subject_id"],
                        rel["relation"],
                        rel["object_id"],
                        0.9,
                        "bootstrap",
                    )
        graphs = build_turn_graphs(repo, rag, world, kg, rules)
        ui_cards = list(repo.by_type("ui"))
        logger.warning(
            "ui-observe session build user=%s slot=%s enabled_packs=%s ui_cards=%d ui_card_ids=%s",
            self.user_id,
            save_slot,
            [r.pack_id for r in self.pack_manager.list_packs() if r.enabled],
            len(ui_cards),
            [c.id for c in ui_cards],
        )
        ui_panel_defs = self.ui_panel_store.load(paths["ui_panels_path"])
        quest_catalog = self._collect_quest_catalog(repo)
        state = {
            "turn_id": 0,
            "recent_messages": [],
            "chat_history": [],
            "save_slot": save_slot,
            "snapshot_dir": str(paths["snapshot_dir"]),
            "enabled_packs": [
                r.pack_id for r in self.pack_manager.list_packs() if r.enabled
            ],
            "language": language or str(metadata.get("language", "")).strip() or "zh",
            "custom_ui_panel_defs": ui_panel_defs,
            "custom_ui_panels": [],
            "ui_template_id": "",
            "ui_variable_template": {"variables": []},
            "ui_variable_values": {},
            "ui_panel_visibility": {},
            "quest_catalog": quest_catalog,
            "ui_generation_status": "ready" if ui_panel_defs else "pending",
            "ui_update_status": "idle",
            "ui_update_mode": "manual",
            "ui_auto_update_every": 1,
        }
        history = self.chat_history_store.load(paths["chat_history_path"])
        if history:
            state["chat_history"] = history
            state["recent_messages"] = history[-10:]
        session = GameSession(
            save_slot=save_slot,
            repo=repo,
            world=world,
            kg=kg,
            rag=rag,
            rules=rules,
            narration_app=graphs.narration_app,
            ops_app=graphs.ops_app,
            state=state,
        )
        seed_story_runtime(repo, world, kg, turn=0)
        self._refresh_world_facts(session)
        session.state.update(
            retrieve_context(
                session.state,
                session.repo,
                session.rag,
                session.world,
                session.kg,
                session.rules,
            )
        )
        self._refresh_custom_ui_panels(session)
        return session

    def _refresh_world_facts(self, session: GameSession) -> None:
        session.state["world_facts"] = {
            "attrs": session.world.all_attrs(),
            "edges": session.kg.all_edges(),
        }

    def _refresh_custom_ui_panels(self, session: GameSession) -> None:
        panel_defs = session.state.get("custom_ui_panel_defs", [])
        world_facts = session.state.get("world_facts", {})
        history = session.state.get("chat_history", [])
        quest_catalog = session.state.get("quest_catalog", [])
        rendered_panels = self.ui_state_agent.update(
            panel_defs, world_facts, history, quest_catalog
        )
        current_values = session.state.get("ui_variable_values", {})
        if not isinstance(current_values, dict):
            current_values = {}

        variable_template = session.state.get("ui_variable_template", {})
        if not isinstance(variable_template, dict) or not variable_template:
            variable_template = {
                "variables": sorted(self._collect_ui_variable_names(panel_defs))
            }
            session.state["ui_variable_template"] = variable_template

        merged_values = self.ui_variable_agent.update(
            variable_template,
            current_values,
            world_facts=world_facts if isinstance(world_facts, dict) else {},
            chat_history=history if isinstance(history, list) else [],
            rendered_panels=rendered_panels,
            state=session.state,
        )
        session.state["ui_variable_values"] = merged_values

        visibility = session.state.get("ui_panel_visibility", {})
        if not isinstance(visibility, dict):
            visibility = {}
            session.state["ui_panel_visibility"] = visibility

        session.state["custom_ui_panels"] = [
            self._render_panel_with_runtime_state(panel, merged_values, visibility)
            for panel in rendered_panels
            if isinstance(panel, dict)
        ]

    def set_ui_update_mode(self, mode: str) -> None:
        if not self._session:
            return
        self._session.state["ui_update_mode"] = "auto" if mode == "auto" else "manual"

    def set_ui_auto_update_every(self, turns: int) -> None:
        if not self._session:
            return
        turns = int(turns or 1)
        if turns <= 0:
            turns = 1
        self._session.state["ui_auto_update_every"] = turns

    def set_ui_panel_visibility(self, panel_id: str, visible: bool) -> None:
        if not self._session:
            return
        visibility = self._session.state.get("ui_panel_visibility", {})
        if not isinstance(visibility, dict):
            visibility = {}
        visibility[str(panel_id)] = bool(visible)
        self._session.state["ui_panel_visibility"] = visibility
        self._refresh_custom_ui_panels(self._session)

    def apply_ui_template(
        self,
        template_id: str,
        template_payload: dict[str, Any],
        variable_template: dict[str, Any] | None = None,
        variable_values: dict[str, Any] | None = None,
        visibility: dict[str, bool] | None = None,
    ) -> None:
        if not self._session:
            return
        payload = template_payload if isinstance(template_payload, dict) else {}
        panels = payload.get("panels", [])
        if not isinstance(panels, list):
            panels = []
        self._session.state["ui_template_id"] = str(template_id or "")
        self._session.state["custom_ui_panel_defs"] = [
            panel for panel in panels if isinstance(panel, dict)
        ]
        variable_template_payload = (
            variable_template
            if isinstance(variable_template, dict)
            else {"variables": []}
        )
        self._session.state["ui_variable_template"] = variable_template_payload
        vars_payload = variable_values if isinstance(variable_values, dict) else {}
        self._session.state["ui_variable_values"] = vars_payload
        visibility_payload = visibility if isinstance(visibility, dict) else {}
        self._session.state["ui_panel_visibility"] = {
            str(k): bool(v) for k, v in visibility_payload.items()
        }
        self._refresh_custom_ui_panels(self._session)

    def get_ui_template_snapshot(self) -> tuple[dict[str, Any], dict[str, Any]]:
        if not self._session:
            return {"panels": []}, {"variables": []}
        panel_defs = self._session.state.get("custom_ui_panel_defs", [])
        if not isinstance(panel_defs, list):
            panel_defs = []
        variable_template = self._session.state.get("ui_variable_template", {})
        if not isinstance(variable_template, dict):
            variable_template = {}
        variable_names = variable_template.get("variables", [])
        if not isinstance(variable_names, list) or not variable_names:
            variable_names = sorted(self._collect_ui_variable_names(panel_defs))
        return {"panels": panel_defs}, {"variables": variable_names}

    def trigger_ui_generation(self, force: bool = False) -> None:
        if not self._session:
            return
        self._schedule_ui_generation(force=force)

    def trigger_ui_update(self) -> None:
        if not self._session:
            return
        self._schedule_ui_update()

    def _schedule_ui_generation(self, force: bool) -> None:
        if not self._session:
            return
        if self._ui_gen_thread and self._ui_gen_thread.is_alive():
            # 生成线程忙时，记录一次待执行请求，避免切换会话时请求丢失。
            self._pending_ui_generation_requested = True
            self._pending_ui_generation_force = (
                self._pending_ui_generation_force or force
            )
            logger.warning(
                "ui-observe generation queued user=%s force=%s",
                self.user_id,
                self._pending_ui_generation_force,
            )
            return
        thread = threading.Thread(
            target=self._generate_ui_panels, args=(force,), daemon=True
        )
        self._ui_gen_thread = thread
        thread.start()

    def _schedule_ui_update(self) -> None:
        if not self._session:
            return
        if self._ui_update_thread and self._ui_update_thread.is_alive():
            return
        thread = threading.Thread(target=self._update_ui_panels, daemon=True)
        self._ui_update_thread = thread
        thread.start()

    def _generate_ui_panels(self, force: bool) -> None:
        if not self._session:
            return
        with self._ui_lock:
            session = self._session
        try:
            if str(session.state.get("ui_template_id") or "").strip():
                with self._ui_lock:
                    if session is self._session:
                        session.state["ui_generation_status"] = "ready"
                if session is self._session:
                    self._refresh_custom_ui_panels(session)
                return

            paths = get_slot_paths(session.save_slot)
            cached = self.ui_panel_store.load(paths["ui_panels_path"])
            if cached and not force:
                with self._ui_lock:
                    if session is self._session:
                        if str(session.state.get("ui_template_id") or "").strip():
                            session.state["ui_generation_status"] = "ready"
                        else:
                            session.state["custom_ui_panel_defs"] = cached
                            session.state["ui_generation_status"] = "ready"
                if session is self._session:
                    self._refresh_custom_ui_panels(session)
                return

            with self._ui_lock:
                if session is self._session:
                    session.state["ui_generation_status"] = "running"

            rag_lookup = self._build_ui_rag_lookup(session)
            ui_cards = list(session.repo.by_type("ui"))
            logger.warning(
                "ui-observe generation start user=%s slot=%s force=%s ui_cards=%d ui_card_ids=%s",
                self.user_id,
                session.save_slot,
                force,
                len(ui_cards),
                [c.id for c in ui_cards],
            )
            with self._llm_settings_scope():
                panels = self.ui_planner.plan(
                    ui_cards,
                    world_facts=session.state.get("world_facts", {}),
                    chat_history=session.state.get("chat_history", []),
                    rag_lookup=rag_lookup,
                )
            logger.warning(
                "ui-observe generation done user=%s slot=%s panels=%d",
                self.user_id,
                session.save_slot,
                len(panels),
            )
            with self._ui_lock:
                if session is self._session:
                    if str(session.state.get("ui_template_id") or "").strip():
                        session.state["ui_generation_status"] = "ready"
                    else:
                        session.state["custom_ui_panel_defs"] = panels
                        session.state["ui_generation_status"] = "ready"
            if session is self._session:
                if not str(session.state.get("ui_template_id") or "").strip():
                    logger.warning(
                        "ui-observe saving panels user=%s slot=%s panels=%d",
                        self.user_id,
                        session.save_slot,
                        len(panels),
                    )
                    self.ui_panel_store.save(paths["ui_panels_path"], panels)
                    logger.warning(
                        "ui-observe saved panels user=%s slot=%s path=%s",
                        self.user_id,
                        session.save_slot,
                        paths["ui_panels_path"],
                    )
                self._refresh_custom_ui_panels(session)
                self._persist_session_metadata(session)
        except Exception:
            logger.exception(
                "ui-observe generation error user=%s slot=%s",
                self.user_id,
                session.save_slot if session else "",
            )
            with self._ui_lock:
                if session is self._session:
                    session.state["ui_generation_status"] = "error"
            if session is self._session:
                self._persist_session_metadata(session)
        finally:
            with self._ui_lock:
                if threading.current_thread() is self._ui_gen_thread:
                    self._ui_gen_thread = None
                self._pending_ui_generation_requested = False
                self._pending_ui_generation_force = False

    def _update_ui_panels(self) -> None:
        if not self._session:
            return
        with self._ui_lock:
            session = self._session
            session.state["ui_update_status"] = "running"
        try:
            if str(session.state.get("ui_template_id") or "").strip():
                with self._ui_lock:
                    if session is self._session:
                        self._refresh_custom_ui_panels(session)
                        session.state["ui_update_status"] = "ready"
                return

            rag_lookup = self._build_ui_rag_lookup(session)
            with self._llm_settings_scope():
                updated = self.ui_update_agent.update(
                    session.state.get("custom_ui_panel_defs", []),
                    world_facts=session.state.get("world_facts", {}),
                    chat_history=session.state.get("chat_history", []),
                    rag_lookup=rag_lookup,
                )
            with self._ui_lock:
                if session is self._session:
                    session.state["custom_ui_panel_defs"] = updated
                    session.state["ui_update_status"] = "ready"
            if session is self._session:
                paths = get_slot_paths(session.save_slot)
                self.ui_panel_store.save(paths["ui_panels_path"], updated)
                self._refresh_custom_ui_panels(session)
        except Exception:
            with self._ui_lock:
                if session is self._session:
                    session.state["ui_update_status"] = "error"

    def _build_ui_rag_lookup(
        self, session: GameSession
    ) -> Dict[str, List[Dict[str, Any]]]:
        lookup: Dict[str, List[Dict[str, Any]]] = {}
        recent = session.state.get("recent_messages", [])
        recent_text = ""
        if isinstance(recent, list):
            recent_text = "\n".join(
                str(m.get("content", "")) for m in recent if isinstance(m, dict)
            )
        for card in session.repo.by_type("ui"):
            query = f"{card.id} {card.type} {recent_text}".strip()
            lookup[card.id] = session.rag.search(query, k=4)
        return lookup

    def _render_panel_with_runtime_state(
        self,
        panel: dict[str, Any],
        variables: dict[str, Any],
        visibility: dict[str, bool],
    ) -> dict[str, Any]:
        panel_id = str(panel.get("panel_id", ""))
        panel_visible = visibility.get(
            panel_id, bool(panel.get("visible_by_default", True))
        )
        rendered = dict(panel)
        rendered["visible"] = bool(panel_visible)

        html = rendered.get("html")
        if isinstance(html, str) and html:
            rendered["html"] = self._inject_variables(html, variables)

        sections = rendered.get("sections", [])
        if isinstance(sections, list):
            normalized_sections: list[dict[str, Any]] = []
            for section in sections:
                if not isinstance(section, dict):
                    continue
                normalized = dict(section)
                entries = normalized.get("entries")
                if isinstance(entries, list):
                    normalized_entries: list[dict[str, Any]] = []
                    for entry in entries:
                        if not isinstance(entry, dict):
                            continue
                        next_entry = dict(entry)
                        value = next_entry.get("value")
                        if isinstance(value, str):
                            next_entry["value"] = self._inject_variables(
                                value, variables
                            )
                        normalized_entries.append(next_entry)
                    normalized["entries"] = normalized_entries
                normalized_sections.append(normalized)
            rendered["sections"] = normalized_sections
        return rendered

    def _inject_variables(self, text: str, variables: dict[str, Any]) -> str:
        def replace(match: re.Match[str]) -> str:
            key = str(match.group(1) or "").strip()
            if not key:
                return ""
            return str(variables.get(key, ""))

        return self._UI_VAR_PATTERN.sub(replace, text)

    def _collect_ui_variable_names(self, panel_defs: list[dict[str, Any]]) -> set[str]:
        names: set[str] = set()
        for panel in panel_defs:
            html = panel.get("html")
            if isinstance(html, str):
                for match in self._UI_VAR_PATTERN.findall(html):
                    if match:
                        names.add(str(match))
            sections = panel.get("sections", [])
            if not isinstance(sections, list):
                continue
            for section in sections:
                if not isinstance(section, dict):
                    continue
                entries = section.get("entries", [])
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    value = entry.get("value")
                    if isinstance(value, str):
                        for match in self._UI_VAR_PATTERN.findall(value):
                            if match:
                                names.add(str(match))
        return names

    def _build_ui_variable_values(
        self, session: GameSession, rendered_panels: list[dict[str, Any]]
    ) -> dict[str, Any]:
        state = session.state
        world_facts = (
            state.get("world_facts", {})
            if isinstance(state.get("world_facts"), dict)
            else {}
        )
        attrs = (
            world_facts.get("attrs", {})
            if isinstance(world_facts.get("attrs"), dict)
            else {}
        )
        flattened: dict[str, Any] = {
            "turn_id": state.get("turn_id", 0),
            "save_slot": state.get("save_slot", ""),
            "location_label": self._infer_location_label(state),
        }

        for entity_id, values in attrs.items():
            if not isinstance(values, dict):
                continue
            for key, value in values.items():
                flattened[f"{entity_id}.{key}"] = value

        for panel in rendered_panels:
            if not isinstance(panel, dict):
                continue
            panel_id = str(panel.get("panel_id", ""))
            if panel_id:
                flattened[f"panel.{panel_id}.title"] = panel.get("title", "")
        return flattened

    def _collect_quest_catalog(self, repo: CardRepository) -> List[Dict[str, Any]]:
        quests: List[Dict[str, Any]] = []
        for card in repo.by_type("quest"):
            summary = ""
            content = card.content.strip()
            if content:
                summary = content.splitlines()[0].strip()
            quests.append(
                {
                    "id": card.id,
                    "tags": list(card.tags),
                    "summary": summary,
                }
            )
        return quests

    def _pack_cards_root(self, pack_id: str) -> Path:
        return self.pack_manager.get_pack_cards_root(pack_id)

    def _resolve_card_type_dir(self, pack_root: Path, card_type: str) -> str:
        normalized = str(card_type).strip()
        if not normalized:
            return "cards"
        singular = normalized
        plural = "memories" if normalized == "memory" else f"{normalized}s"

        # 浼樺厛澶嶇敤宸插瓨鍦ㄧ洰褰曪紝鍏煎浣滆€呰嚜瀹氫箟鍛藉悕?
        if (pack_root / singular).exists():
            return singular
        if (pack_root / plural).exists():
            return plural
        return plural

    def _is_within(self, path: Path, root: Path) -> bool:
        try:
            path.resolve().relative_to(root.resolve())
            return True
        except Exception:
            return False

    def _load_chat_history(self, path: Path) -> List[Dict[str, str]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [m for m in data if isinstance(m, dict)]
        except Exception:
            return []
        return []

    def _load_ui_panels(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return [p for p in data if isinstance(p, dict)]
        except Exception:
            return []
        return []

    def _save_ui_panels(self, path: Path, panels: List[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(panels, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _save_chat_history(self, session: GameSession) -> None:
        path = get_slot_paths(session.save_slot)["chat_history_path"]
        history = session.state.get("chat_history", [])
        self.chat_history_store.save(path, history)

    def _set_enabled_packs(self, pack_ids: List[str]) -> None:
        desired = {str(pack_id) for pack_id in pack_ids}
        for record in self.pack_manager.list_packs():
            self.pack_manager.enable_pack(record.pack_id, record.pack_id in desired)

    def _load_session_metadata(self, save_slot: str) -> Dict[str, Any]:
        return self.session_metadata_store.load(
            get_slot_paths(save_slot)["session_meta_path"]
        )

    def _build_session_summary(self, save_slot: str) -> Dict[str, Any]:
        paths = get_slot_paths(save_slot)
        metadata = self.session_metadata_store.load(paths["session_meta_path"])
        updated_at = metadata.get("updated_at")
        if not updated_at:
            try:
                updated_at = datetime.fromtimestamp(
                    paths["data_dir"].stat().st_mtime
                ).strftime("%Y-%m-%d %H:%M")
            except Exception:
                updated_at = "unknown"
        enabled_packs = metadata.get("enabled_packs", [])
        if not isinstance(enabled_packs, list):
            enabled_packs = []
        ui_generation_status = str(
            metadata.get("ui_generation_status", "") or ""
        ).strip()
        if not ui_generation_status:
            ui_generation_status = "ready"
        return {
            "slot_id": save_slot,
            "language": str(metadata.get("language", "")).strip() or "zh",
            "enabled_packs": [str(pack_id) for pack_id in enabled_packs],
            "location_label": str(metadata.get("location_label", "")).strip()
            or "Unknown",
            "turn_count": int(metadata.get("turn_count", 0) or 0),
            "updated_label": str(updated_at),
            "ui_generation_status": ui_generation_status,
        }

    def _persist_session_metadata(self, session: GameSession | None) -> None:
        if not session:
            return
        paths = get_slot_paths(session.save_slot)
        payload = self._build_metadata_payload(session)
        self.session_metadata_store.save(paths["session_meta_path"], payload)

    def _release_active_session(self) -> None:
        session = self._session
        self._session = None
        if not session:
            return
        for store_name in ("world", "kg", "rag"):
            store = getattr(session, store_name, None)
            close = getattr(store, "close", None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        gc.collect()

    def _build_metadata_payload(self, session: GameSession) -> Dict[str, Any]:
        return {
            "save_slot": session.save_slot,
            "language": session.state.get("language", "zh"),
            "enabled_packs": session.state.get("enabled_packs", []),
            "location_label": self._infer_location_label(session.state),
            "turn_count": int(session.state.get("turn_id", 0) or 0),
            "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "ui_generation_status": str(
                session.state.get("ui_generation_status", "pending") or "pending"
            ),
        }

    def _infer_location_label(self, state: Dict[str, Any]) -> str:
        world_facts = state.get("world_facts", {})
        attrs = world_facts.get("attrs", {}) if isinstance(world_facts, dict) else {}
        player_attrs = attrs.get("player", {}) if isinstance(attrs, dict) else {}
        raw_location = ""
        if isinstance(player_attrs, dict):
            raw_location = str(player_attrs.get("location", "")).strip()
        if not raw_location:
            return "Unknown"
        return raw_location.replace("_", " ").strip().title()

    def _resolve_duplicate_slot(
        self, source_slot: str, target_slot: Optional[str]
    ) -> str:
        candidate = str(target_slot or "").strip()
        if candidate:
            if get_slot_paths(candidate)["data_dir"].exists():
                raise ValueError("target save slot already exists")
            return candidate

        index = 1
        while True:
            candidate = f"{source_slot}_copy_{index:02d}"
            if not get_slot_paths(candidate)["data_dir"].exists():
                return candidate
            index += 1

    def _resolve_archive_path(self, save_slot: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return ARCHIVES_DIR / f"{save_slot}_{timestamp}"

    def _ensure_llm_call_allowed(self) -> None:
        if not self._settings_repository:
            return
        balance = float(self._settings_repository.get_user_coin_balance(self.user_id) or 0.0)
        if balance < 0:
            raise ValueError("当前代币余额已为负数，请先充值后再继续调用。")

    def _on_llm_usage(self, scene: str, input_tokens: int, output_tokens: int) -> None:
        if not self._settings_repository:
            return
        plan_id = str(getattr(self._runtime_llm_settings, "plan_id", "") or "").strip()
        input_rate = int(getattr(self._runtime_llm_settings, "input_tokens_per_coin", 0) or 0)
        output_rate = int(getattr(self._runtime_llm_settings, "output_tokens_per_coin", 0) or 0)
        if not plan_id or input_rate <= 0 or output_rate <= 0:
            return
        self._settings_repository.charge_llm_usage(
            user_id=self.user_id,
            plan_id=plan_id,
            scene=str(scene or "unknown"),
            input_tokens=int(input_tokens or 0),
            output_tokens=int(output_tokens or 0),
            input_tokens_per_coin=input_rate,
            output_tokens_per_coin=output_rate,
        )

    @contextmanager
    def _llm_settings_scope(self):
        with ExitStack() as stack:
            self._ensure_llm_call_allowed()
            stack.enter_context(activate_runtime_llm_settings(self._runtime_llm_settings))
            stack.enter_context(
                activate_runtime_billing_context(
                    {
                        "user_id": self.user_id,
                        "plan_id": str(getattr(self._runtime_llm_settings, "plan_id", "") or ""),
                        "on_usage": self._on_llm_usage,
                    }
                )
            )
            yield


def json_dump(data: Dict[str, Any]) -> str:
    import json

    return json.dumps(data, indent=2)
