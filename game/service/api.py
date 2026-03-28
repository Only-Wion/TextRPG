from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
import gc
import json
import shutil
import threading

from ..config import (
    ARCHIVES_DIR,
    CARDS_DIR,
    EXPORTS_DIR,
    SAVES_DIR,
    SETTINGS,
    activate_runtime_llm_settings,
    get_slot_paths,
    load_runtime_llm_settings,
    normalize_llm_settings,
)
from ..core.card_repository import CardRepository
from ..core.rule_engine import RuleEngine
from ..core.rag_store import RAGStore
from ..core.kg_store import KGStore
from ..core.world_store import WorldStore
from ..core.graph import build_graph
from ..infrastructure.contracts import (
    ChatHistoryStoreProtocol,
    KGStoreProtocol,
    RAGStoreProtocol,
    SessionMetadataStoreProtocol,
    UIPanelStoreProtocol,
    WorldStoreProtocol,
)
from ..infrastructure.session_files import ChatHistoryStore, SessionMetadataStore, UIPanelStore
from ..infrastructure.postgres.session_files import PostgresChatHistoryStore, PostgresUIPanelStore
from ..infrastructure.store_factory import SessionStoreFactory
from ..packs.manager import PackManager
from ..packs.registry import PackRecord
from ..packs.card_editor import DEFAULT_CARD_TYPES, parse_card, render_card, validate_card
from ..packs.validator import validate_manifest
from .ui_agents import UICardPlannerAgent, UIPanelStateAgent, UIPanelUpdateAgent


@dataclass
class GameSession:
    save_slot: str
    repo: CardRepository
    world: WorldStoreProtocol
    kg: KGStoreProtocol
    rag: RAGStoreProtocol
    rules: RuleEngine
    app: Any
    state: Dict[str, Any]


class GameService:
    def __init__(self, packs_root: Path | None = None, store_factory: SessionStoreFactory | None = None):
        self.pack_manager = PackManager(packs_root=packs_root) if packs_root else PackManager()
        if SETTINGS.storage_backend == 'postgres':
            if not SETTINGS.postgres_dsn:
                raise ValueError('TEXTRPG_POSTGRES_DSN is required when TEXTRPG_STORAGE_BACKEND=postgres')
            self.chat_history_store = PostgresChatHistoryStore(SETTINGS.postgres_dsn)
            self.ui_panel_store = PostgresUIPanelStore(SETTINGS.postgres_dsn)
        else:
            self.chat_history_store = ChatHistoryStore()
            self.ui_panel_store = UIPanelStore()
        self.session_metadata_store: SessionMetadataStoreProtocol = SessionMetadataStore()
        self.store_factory = store_factory or SessionStoreFactory()
        self._session: GameSession | None = None
        self.ui_planner = UICardPlannerAgent()
        self.ui_state_agent = UIPanelStateAgent()
        self.ui_update_agent = UIPanelUpdateAgent()
        self._runtime_llm_settings = load_runtime_llm_settings()
        self._ui_lock = threading.Lock()
        self._ui_gen_thread: threading.Thread | None = None
        self._ui_update_thread: threading.Thread | None = None

    def start_new_game(self, save_slot: str, pack_ids: Optional[List[str]] = None, language: Optional[str] = None) -> None:
        self._release_active_session()
        if pack_ids is not None:
            self._set_enabled_packs(pack_ids)
        self._session = self._build_session(save_slot, language=language)
        self._persist_session_metadata(self._session)
        self._schedule_ui_generation(force=True)

    def load_game(self, save_slot: str, language: Optional[str] = None) -> None:
        self._release_active_session()
        metadata = self._load_session_metadata(save_slot)
        if metadata.get('enabled_packs'):
            self._set_enabled_packs(metadata.get('enabled_packs', []))
        self._session = self._build_session(save_slot, language=language)
        self._persist_session_metadata(self._session)
        self._schedule_ui_generation(force=False)

    def step(self, input_text: str) -> Dict[str, Any]:
        if not self._session:
            raise RuntimeError('game not started')
        session = self._session
        session.state['turn_id'] = session.state.get('turn_id', 0) + 1
        session.state['player_input'] = input_text
        with self._llm_settings_scope():
            result = session.app.invoke(session.state)
        narration = result.get('narration', '')
        session.state.update(result)
        history = list(session.state.get('chat_history', []))
        history.append({'role': 'user', 'content': input_text})
        history.append({'role': 'assistant', 'content': narration})
        session.state['chat_history'] = history
        session.state['recent_messages'] = history[-10:]
        self._refresh_world_facts(session)
        if session.state.get('ui_update_mode', 'manual') == 'auto':
            every = int(session.state.get('ui_auto_update_every', 1) or 1)
            if every <= 0:
                every = 1
            if session.state['turn_id'] % every == 0:
                self._schedule_ui_update()
        else:
            self._refresh_custom_ui_panels(session)
        self._save_chat_history(session)
        self._persist_session_metadata(session)
        return result

    def set_language(self, language: str) -> None:
        if not self._session:
            return
        self._session.state['language'] = language
        self._persist_session_metadata(self._session)

    def get_current_state_view(self) -> Dict[str, Any]:
        if not self._session:
            return {}
        state = self._session.state
        return {
            'turn_id': state.get('turn_id'),
            'recent_messages': state.get('recent_messages', []),
            'chat_history': state.get('chat_history', []),
            'narration': state.get('narration', ''),
            'world_facts': state.get('world_facts', {}),
            'allowed_actions': state.get('allowed_actions', []),
            'retrieved_cards': [c.get('id') for c in state.get('retrieved_cards', [])],
            'validated_ops': state.get('validated_ops', []),
            'errors': state.get('errors', []),
            'custom_ui_panels': state.get('custom_ui_panels', []),
            'save_slot': state.get('save_slot'),
            'ui_generation_status': state.get('ui_generation_status', 'idle'),
            'ui_update_status': state.get('ui_update_status', 'idle'),
            'ui_update_mode': state.get('ui_update_mode', 'manual'),
            'ui_auto_update_every': state.get('ui_auto_update_every', 1),
            'enabled_packs': state.get('enabled_packs', []),
            'location_label': self._infer_location_label(state),
            'storage_backend_label': SETTINGS.storage_backend,
        }

    def get_current_session_metadata(self) -> Dict[str, Any]:
        if not self._session:
            return {}
        return self._build_metadata_payload(self._session)

    def get_current_chat_history(self) -> List[Dict[str, Any]]:
        if not self._session:
            return []
        history = self._session.state.get('chat_history', [])
        if not isinstance(history, list):
            return []
        return [item for item in history if isinstance(item, dict)]

    def set_current_chat_history(self, history: List[Dict[str, Any]]) -> None:
        if not self._session:
            return
        normalized = [item for item in history if isinstance(item, dict)]
        self._session.state['chat_history'] = normalized
        self._session.state['recent_messages'] = normalized[-10:]
        self._refresh_custom_ui_panels(self._session)
        self._save_chat_history(self._session)

    def list_sessions(self, allowed_slots: Optional[List[str]] = None, selected_slot: Optional[str] = None) -> Dict[str, Any]:
        sessions: List[Dict[str, Any]] = []
        allowed_slot_set = set(allowed_slots or [])
        if SAVES_DIR.exists():
            slot_dirs = [path for path in SAVES_DIR.iterdir() if path.is_dir()]
            for slot_dir in sorted(slot_dirs, key=lambda path: path.stat().st_mtime, reverse=True):
                if allowed_slot_set and slot_dir.name not in allowed_slot_set:
                    continue
                sessions.append(self._build_session_summary(slot_dir.name))

        selected_slot = selected_slot or (self._session.save_slot if self._session else (sessions[0]['slot_id'] if sessions else 'slot_001'))
        if sessions and selected_slot not in {session['slot_id'] for session in sessions}:
            selected_slot = sessions[0]['slot_id']
        return {
            'selected_slot': selected_slot,
            'backend_status': 'online',
            'storage_backend': SETTINGS.storage_backend,
            'last_sync_label': 'just now',
            'sessions': sessions,
        }

    def duplicate_session(self, source_slot: str, target_slot: Optional[str] = None) -> Dict[str, Any]:
        source_paths = get_slot_paths(source_slot)
        if not source_paths['data_dir'].exists():
            raise ValueError('save slot not found')

        destination_slot = self._resolve_duplicate_slot(source_slot, target_slot)
        destination_paths = get_slot_paths(destination_slot)
        shutil.copytree(source_paths['data_dir'], destination_paths['data_dir'])

        metadata = self.session_metadata_store.load(destination_paths['session_meta_path'])
        metadata['save_slot'] = destination_slot
        metadata['updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M')
        self.session_metadata_store.save(destination_paths['session_meta_path'], metadata)
        return self.list_sessions(selected_slot=destination_slot)

    def archive_session(self, save_slot: str) -> Dict[str, Any]:
        source_paths = get_slot_paths(save_slot)
        if not source_paths['data_dir'].exists():
            raise ValueError('save slot not found')

        if self._session and self._session.save_slot == save_slot:
            self._release_active_session()

        archived_path = self._resolve_archive_path(save_slot)
        archived_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source_paths['data_dir']), str(archived_path))

        remaining_slots = [
            path.name
            for path in sorted(SAVES_DIR.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True)
            if path.is_dir()
        ] if SAVES_DIR.exists() else []
        next_selected = remaining_slots[0] if remaining_slots else 'slot_001'
        return self.list_sessions(selected_slot=next_selected)



    def get_llm_settings(self) -> Dict[str, Any]:
        return self._runtime_llm_settings.to_public_dict()

    def set_runtime_llm_settings(self, payload: Dict[str, Any]) -> None:
        self._runtime_llm_settings = normalize_llm_settings(payload, self._runtime_llm_settings)


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
        if record and record.source == 'builtin':
            raise ValueError('builtin packs cannot be removed')
        self.pack_manager.remove_pack(pack_id)

    def enable_pack(self, pack_id: str, enabled: bool) -> None:
        self.pack_manager.enable_pack(pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        self.pack_manager.export_pack(pack_id, output_path)

    def export_pack_to_runtime_exports(self, pack_id: str) -> Dict[str, Any]:
        record = self.pack_manager.registry.get(pack_id)
        if not record:
            raise ValueError('pack not found')
        EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = EXPORTS_DIR / f'{pack_id}-{record.version}.zip'
        self.pack_manager.export_pack(pack_id, output_path)
        return {
            'ok': True,
            'pack_id': pack_id,
            'export_path': str(output_path),
        }

    def create_card(self, pack_id: str, card_type: str, card_id: str, frontmatter: Dict[str, Any], body: str) -> Path:
        return self.save_card(pack_id, card_type, card_id, frontmatter, body)

    def save_card(
        self,
        pack_id: str,
        card_type: str,
        card_id: str,
        frontmatter: Dict[str, Any],
        body: str,
        original_path: Path | None = None,
    ) -> Path:
        frontmatter = dict(frontmatter)
        frontmatter['id'] = card_id
        frontmatter['type'] = card_type
        validate_card(frontmatter, body)
        pack_root = self._pack_cards_root(pack_id)
        card_dir = pack_root / self._resolve_card_type_dir(pack_root, card_type)
        card_dir.mkdir(parents=True, exist_ok=True)
        path = card_dir / f'{card_id}.md'
        path.write_text(render_card(frontmatter, body), encoding='utf-8')

        if original_path:
            old_path = Path(original_path)
            if old_path != path and old_path.exists() and self._is_within(old_path, pack_root):
                old_path.unlink()
        return path

    def update_card(self, path: Path, frontmatter: Dict[str, Any], body: str) -> None:
        validate_card(frontmatter, body)
        path.write_text(render_card(frontmatter, body), encoding='utf-8')

    def validate_card(self, frontmatter: Dict[str, Any], body: str) -> None:
        validate_card(frontmatter, body)

    def export_pack_manifest(self, data: Dict[str, Any]) -> None:
        validate_manifest(data)

    def create_pack(self, manifest: Dict[str, Any]) -> None:
        validate_manifest(manifest)
        pack_id = str(manifest['pack_id'])
        version = str(manifest['version'])
        pack_dir = self.pack_manager.packs_root / pack_id / version
        if pack_dir.exists():
            raise ValueError('pack already exists')
        cards_root = Path(str(manifest['cards_root']))
        pack_dir.mkdir(parents=True, exist_ok=True)
        (pack_dir / cards_root).mkdir(parents=True, exist_ok=True)
        manifest_path = pack_dir / 'pack.json'
        manifest_path.write_text(json_dump(manifest), encoding='utf-8')
        record = PackRecord(
            pack_id=pack_id,
            name=str(manifest['name']),
            version=version,
            author=str(manifest['author']),
            description=str(manifest['description']),
            cards_root=str(manifest['cards_root']),
            enabled=False,
            source='local',
        )
        self.pack_manager.registry.upsert(record)

    def get_card_template(self, card_type: str) -> Dict[str, Any]:
        normalized_type = str(card_type).strip() or 'card'
        return {
            'id': 'new_id',
            'type': normalized_type,
            'tags': [],
            'initial_relations': [],
            'hooks': [],
        }

    def list_pack_card_types(self, pack_id: str) -> List[str]:
        root = self._pack_cards_root(pack_id)
        existing: List[str] = []
        seen: set[str] = set()
        for path in root.rglob('*.md'):
            fm, _ = parse_card(path)
            t = str(fm.get('type', '')).strip()
            if t and t not in seen:
                seen.add(t)
                existing.append(t)

        merged = list(existing)
        for t in DEFAULT_CARD_TYPES:
            if t not in seen:
                merged.append(t)
        return merged

    def list_pack_cards(self, pack_id: str) -> List[Path]:
        root = self._pack_cards_root(pack_id)
        return list(root.rglob('*.md'))

    def load_card(self, path: Path) -> Dict[str, Any]:
        fm, body = parse_card(path)
        return {'frontmatter': fm, 'body': body}

    def delete_card(self, pack_id: str, path: Path) -> None:
        pack_root = self._pack_cards_root(pack_id)
        target = Path(path)
        if not target.exists():
            return
        if not self._is_within(target, pack_root):
            raise ValueError('card path is outside pack root')
        target.unlink()

    def _build_session(self, save_slot: str, language: Optional[str] = None) -> GameSession:
        paths = get_slot_paths(save_slot)
        metadata = self.session_metadata_store.load(paths['session_meta_path'])
        enabled_roots = self.pack_manager.get_enabled_cards_roots()
        repo = CardRepository(cards_dir=CARDS_DIR, extra_roots=enabled_roots)
        repo.load()
        with self._llm_settings_scope():
            stores = self.store_factory.create(
                world_db_path=paths['world_db_path'],
                kg_db_path=paths['kg_db_path'],
                rag_dir=paths['rag_dir'],
            )
        world = stores.world
        kg = stores.kg
        rag = stores.rag
        cards_index = {c.id: {'type': c.type, 'tags': c.tags} for c in repo.all()}
        rules = RuleEngine(cards_index)
        if not kg.all_edges():
            for card in repo.all():
                for rel in card.initial_relations:
                    kg.add_edge(rel['subject_id'], rel['relation'], rel['object_id'], 0.9, 'bootstrap')
        app = build_graph(repo, rag, world, kg, rules)
        ui_cards = list(repo.by_type('ui'))
        ui_panel_defs = self.ui_panel_store.load(paths['ui_panels_path'])
        quest_catalog = self._collect_quest_catalog(repo)
        state = {
            'turn_id': 0,
            'recent_messages': [],
            'chat_history': [],
            'save_slot': save_slot,
            'snapshot_dir': str(paths['snapshot_dir']),
            'enabled_packs': [r.pack_id for r in self.pack_manager.list_packs() if r.enabled],
            'language': language or str(metadata.get('language', '')).strip() or 'zh',
            'custom_ui_panel_defs': ui_panel_defs,
            'custom_ui_panels': [],
            'quest_catalog': quest_catalog,
            'ui_generation_status': 'ready' if ui_panel_defs else 'pending',
            'ui_update_status': 'idle',
            'ui_update_mode': 'manual',
            'ui_auto_update_every': 1,
        }
        history = self.chat_history_store.load(paths['chat_history_path'])
        if history:
            state['chat_history'] = history
            state['recent_messages'] = history[-10:]
        session = GameSession(
            save_slot=save_slot,
            repo=repo,
            world=world,
            kg=kg,
            rag=rag,
            rules=rules,
            app=app,
            state=state,
        )
        self._refresh_world_facts(session)
        self._refresh_custom_ui_panels(session)
        return session

    def _refresh_world_facts(self, session: GameSession) -> None:
        session.state['world_facts'] = {
            'attrs': session.world.all_attrs(),
            'edges': session.kg.all_edges(),
        }

    def _refresh_custom_ui_panels(self, session: GameSession) -> None:
        panel_defs = session.state.get('custom_ui_panel_defs', [])
        world_facts = session.state.get('world_facts', {})
        history = session.state.get('chat_history', [])
        quest_catalog = session.state.get('quest_catalog', [])
        session.state['custom_ui_panels'] = self.ui_state_agent.update(panel_defs, world_facts, history, quest_catalog)

    def set_ui_update_mode(self, mode: str) -> None:
        if not self._session:
            return
        self._session.state['ui_update_mode'] = 'auto' if mode == 'auto' else 'manual'

    def set_ui_auto_update_every(self, turns: int) -> None:
        if not self._session:
            return
        turns = int(turns or 1)
        if turns <= 0:
            turns = 1
        self._session.state['ui_auto_update_every'] = turns

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
            return
        thread = threading.Thread(target=self._generate_ui_panels, args=(force,), daemon=True)
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
            paths = get_slot_paths(session.save_slot)
            cached = self.ui_panel_store.load(paths['ui_panels_path'])
            if cached and not force:
                with self._ui_lock:
                    if session is self._session:
                        session.state['custom_ui_panel_defs'] = cached
                        session.state['ui_generation_status'] = 'ready'
                if session is self._session:
                    self._refresh_custom_ui_panels(session)
                return

            with self._ui_lock:
                if session is self._session:
                    session.state['ui_generation_status'] = 'running'

            rag_lookup = self._build_ui_rag_lookup(session)
            with self._llm_settings_scope():
                panels = self.ui_planner.plan(
                    list(session.repo.by_type('ui')),
                    world_facts=session.state.get('world_facts', {}),
                    chat_history=session.state.get('chat_history', []),
                    rag_lookup=rag_lookup,
                )
            with self._ui_lock:
                if session is self._session:
                    session.state['custom_ui_panel_defs'] = panels
                    session.state['ui_generation_status'] = 'ready'
            if session is self._session:
                self.ui_panel_store.save(paths['ui_panels_path'], panels)
                self._refresh_custom_ui_panels(session)
        except Exception:
            with self._ui_lock:
                if session is self._session:
                    session.state['ui_generation_status'] = 'error'

    def _update_ui_panels(self) -> None:
        if not self._session:
            return
        with self._ui_lock:
            session = self._session
            session.state['ui_update_status'] = 'running'
        try:
            rag_lookup = self._build_ui_rag_lookup(session)
            with self._llm_settings_scope():
                updated = self.ui_update_agent.update(
                    session.state.get('custom_ui_panel_defs', []),
                    world_facts=session.state.get('world_facts', {}),
                    chat_history=session.state.get('chat_history', []),
                    rag_lookup=rag_lookup,
                )
            with self._ui_lock:
                if session is self._session:
                    session.state['custom_ui_panel_defs'] = updated
                    session.state['ui_update_status'] = 'ready'
            if session is self._session:
                paths = get_slot_paths(session.save_slot)
                self.ui_panel_store.save(paths['ui_panels_path'], updated)
                self._refresh_custom_ui_panels(session)
        except Exception:
            with self._ui_lock:
                if session is self._session:
                    session.state['ui_update_status'] = 'error'

    def _build_ui_rag_lookup(self, session: GameSession) -> Dict[str, List[Dict[str, Any]]]:
        lookup: Dict[str, List[Dict[str, Any]]] = {}
        recent = session.state.get('recent_messages', [])
        recent_text = ''
        if isinstance(recent, list):
            recent_text = '\n'.join(str(m.get('content', '')) for m in recent if isinstance(m, dict))
        for card in session.repo.by_type('ui'):
            query = f"{card.id} {card.type} {recent_text}".strip()
            lookup[card.id] = session.rag.search(query, k=4)
        return lookup


    def _collect_quest_catalog(self, repo: CardRepository) -> List[Dict[str, Any]]:
        quests: List[Dict[str, Any]] = []
        for card in repo.by_type('quest'):
            summary = ''
            content = card.content.strip()
            if content:
                summary = content.splitlines()[0].strip()
            quests.append({
                'id': card.id,
                'tags': list(card.tags),
                'summary': summary,
            })
        return quests

    def _pack_cards_root(self, pack_id: str) -> Path:
        record = self.pack_manager.registry.get(pack_id)
        if not record:
            raise ValueError('pack not found')
        return self.pack_manager.packs_root / record.pack_id / record.version / record.cards_root

    def _resolve_card_type_dir(self, pack_root: Path, card_type: str) -> str:
        normalized = str(card_type).strip()
        if not normalized:
            return 'cards'
        singular = normalized
        plural = 'memories' if normalized == 'memory' else f'{normalized}s'

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
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return [m for m in data if isinstance(m, dict)]
        except Exception:
            return []
        return []

    def _load_ui_panels(self, path: Path) -> List[Dict[str, Any]]:
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return [p for p in data if isinstance(p, dict)]
        except Exception:
            return []
        return []

    def _save_ui_panels(self, path: Path, panels: List[Dict[str, Any]]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(panels, ensure_ascii=False, indent=2), encoding='utf-8')

    def _save_chat_history(self, session: GameSession) -> None:
        path = get_slot_paths(session.save_slot)['chat_history_path']
        history = session.state.get('chat_history', [])
        self.chat_history_store.save(path, history)

    def _set_enabled_packs(self, pack_ids: List[str]) -> None:
        desired = {str(pack_id) for pack_id in pack_ids}
        for record in self.pack_manager.list_packs():
            self.pack_manager.enable_pack(record.pack_id, record.pack_id in desired)

    def _load_session_metadata(self, save_slot: str) -> Dict[str, Any]:
        return self.session_metadata_store.load(get_slot_paths(save_slot)['session_meta_path'])

    def _build_session_summary(self, save_slot: str) -> Dict[str, Any]:
        paths = get_slot_paths(save_slot)
        metadata = self.session_metadata_store.load(paths['session_meta_path'])
        updated_at = metadata.get('updated_at')
        if not updated_at:
            try:
                updated_at = datetime.fromtimestamp(paths['data_dir'].stat().st_mtime).strftime('%Y-%m-%d %H:%M')
            except Exception:
                updated_at = 'unknown'
        enabled_packs = metadata.get('enabled_packs', [])
        if not isinstance(enabled_packs, list):
            enabled_packs = []
        return {
            'slot_id': save_slot,
            'language': str(metadata.get('language', '')).strip() or 'zh',
            'enabled_packs': [str(pack_id) for pack_id in enabled_packs],
            'location_label': str(metadata.get('location_label', '')).strip() or 'Unknown',
            'turn_count': int(metadata.get('turn_count', 0) or 0),
            'updated_label': str(updated_at),
        }

    def _persist_session_metadata(self, session: GameSession | None) -> None:
        if not session:
            return
        paths = get_slot_paths(session.save_slot)
        payload = self._build_metadata_payload(session)
        self.session_metadata_store.save(paths['session_meta_path'], payload)

    def _release_active_session(self) -> None:
        session = self._session
        self._session = None
        if not session:
            return
        for store_name in ('world', 'kg', 'rag'):
            store = getattr(session, store_name, None)
            close = getattr(store, 'close', None)
            if callable(close):
                try:
                    close()
                except Exception:
                    pass
        gc.collect()

    def _build_metadata_payload(self, session: GameSession) -> Dict[str, Any]:
        return {
            'save_slot': session.save_slot,
            'language': session.state.get('language', 'zh'),
            'enabled_packs': session.state.get('enabled_packs', []),
            'location_label': self._infer_location_label(session.state),
            'turn_count': int(session.state.get('turn_id', 0) or 0),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M'),
        }

    def _infer_location_label(self, state: Dict[str, Any]) -> str:
        world_facts = state.get('world_facts', {})
        attrs = world_facts.get('attrs', {}) if isinstance(world_facts, dict) else {}
        player_attrs = attrs.get('player', {}) if isinstance(attrs, dict) else {}
        raw_location = ''
        if isinstance(player_attrs, dict):
            raw_location = str(player_attrs.get('location', '')).strip()
        if not raw_location:
            return 'Unknown'
        return raw_location.replace('_', ' ').strip().title()

    def _resolve_duplicate_slot(self, source_slot: str, target_slot: Optional[str]) -> str:
        candidate = str(target_slot or '').strip()
        if candidate:
            if get_slot_paths(candidate)['data_dir'].exists():
                raise ValueError('target save slot already exists')
            return candidate

        index = 1
        while True:
            candidate = f'{source_slot}_copy_{index:02d}'
            if not get_slot_paths(candidate)['data_dir'].exists():
                return candidate
            index += 1

    def _resolve_archive_path(self, save_slot: str) -> Path:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return ARCHIVES_DIR / f'{save_slot}_{timestamp}'

    def _llm_settings_scope(self):
        return activate_runtime_llm_settings(self._runtime_llm_settings)

def json_dump(data: Dict[str, Any]) -> str:
    import json

    return json.dumps(data, indent=2)

