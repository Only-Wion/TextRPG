from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional
import json

from ..config import CARDS_DIR, get_slot_paths
from ..core.card_repository import CardRepository
from ..core.rule_engine import RuleEngine
from ..core.rag_store import RAGStore
from ..core.kg_store import KGStore
from ..core.world_store import WorldStore
from ..core.graph import build_graph
from ..packs.manager import PackManager
from ..packs.registry import PackRecord
from ..packs.card_editor import CARD_TYPES, parse_card, render_card, validate_card
from ..packs.validator import validate_manifest
from .ui_agents import UICardPlannerAgent, UIPanelStateAgent


@dataclass
class GameSession:
    """按存档槽位组织的运行时对象容器。"""
    save_slot: str
    repo: CardRepository
    world: WorldStore
    kg: KGStore
    rag: RAGStore
    rules: RuleEngine
    app: Any
    state: Dict[str, Any]


class GameService:
    """UI/CLI 使用的服务层 API。"""
    def __init__(self, packs_root: Path | None = None):
        self.pack_manager = PackManager(packs_root=packs_root) if packs_root else PackManager()
        self._session: GameSession | None = None
        self.ui_planner = UICardPlannerAgent()
        self.ui_state_agent = UIPanelStateAgent()

    def start_new_game(self, save_slot: str, pack_ids: Optional[List[str]] = None, language: Optional[str] = None) -> None:
        """开启新游戏会话，可选启用指定卡包。"""
        if pack_ids is not None:
            for record in self.pack_manager.list_packs():
                self.pack_manager.enable_pack(record.pack_id, record.pack_id in pack_ids)
        self._session = self._build_session(save_slot, language=language)

    def load_game(self, save_slot: str, language: Optional[str] = None) -> None:
        """加载指定存档槽位的游戏会话。"""
        self._session = self._build_session(save_slot, language=language)

    def step(self, input_text: str) -> Dict[str, Any]:
        """推进一回合的 LangGraph 流程。"""
        if not self._session:
            raise RuntimeError('game not started')
        session = self._session
        session.state['turn_id'] = session.state.get('turn_id', 0) + 1
        session.state['player_input'] = input_text
        result = session.app.invoke(session.state)
        narration = result.get('narration', '')
        session.state.update(result)
        history = list(session.state.get('chat_history', []))
        history.append({'role': 'user', 'content': input_text})
        history.append({'role': 'assistant', 'content': narration})
        session.state['chat_history'] = history
        session.state['recent_messages'] = history[-10:]
        self._refresh_world_facts(session)
        self._refresh_custom_ui_panels(session)
        self._save_chat_history(session)
        return result

    def set_language(self, language: str) -> None:
        """更新会话语言偏好。"""
        if not self._session:
            return
        self._session.state['language'] = language

    def get_current_state_view(self) -> Dict[str, Any]:
        """返回适用于 UI 展示的状态视图。"""
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
        }

    def list_packs(self) -> List[Dict[str, Any]]:
        """从注册表列出已安装卡包。"""
        return [r.__dict__ for r in self.pack_manager.list_packs()]

    def install_pack_from_url(self, url: str) -> Dict[str, Any]:
        """从 URL 下载并安装卡包。"""
        record = self.pack_manager.install_pack_from_url(url)
        return record.__dict__

    def install_pack_from_zip(self, path: Path) -> Dict[str, Any]:
        """从本地 zip 安装卡包。"""
        record = self.pack_manager.install_pack_from_zip(path)
        return record.__dict__

    def remove_pack(self, pack_id: str) -> None:
        """删除已安装卡包及其文件。"""
        self.pack_manager.remove_pack(pack_id)

    def enable_pack(self, pack_id: str, enabled: bool) -> None:
        """启用或禁用卡包。"""
        self.pack_manager.enable_pack(pack_id, enabled)

    def export_pack(self, pack_id: str, output_path: Path) -> None:
        """导出卡包为 zip 文件。"""
        self.pack_manager.export_pack(pack_id, output_path)

    def create_card(self, pack_id: str, card_type: str, card_id: str, frontmatter: Dict[str, Any], body: str) -> Path:
        """在卡包内创建一张新卡牌文件。"""
        if card_type not in CARD_TYPES:
            raise ValueError('invalid type')
        frontmatter = dict(frontmatter)
        frontmatter['id'] = card_id
        frontmatter['type'] = card_type
        validate_card(frontmatter, body)
        pack_root = self._pack_cards_root(pack_id)
        plural = 'memories' if card_type == 'memory' else f'{card_type}s'
        card_dir = pack_root / plural
        card_dir.mkdir(parents=True, exist_ok=True)
        path = card_dir / f'{card_id}.md'
        path.write_text(render_card(frontmatter, body), encoding='utf-8')
        return path

    def update_card(self, path: Path, frontmatter: Dict[str, Any], body: str) -> None:
        """更新现有卡牌文件。"""
        validate_card(frontmatter, body)
        path.write_text(render_card(frontmatter, body), encoding='utf-8')

    def validate_card(self, frontmatter: Dict[str, Any], body: str) -> None:
        """校验卡牌 frontmatter 与正文。"""
        validate_card(frontmatter, body)

    def export_pack_manifest(self, data: Dict[str, Any]) -> None:
        """导出前校验 manifest 数据。"""
        validate_manifest(data)

    def create_pack(self, manifest: Dict[str, Any]) -> None:
        """创建空卡包目录并写入注册表。"""
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
        """返回指定卡牌类型的最小 frontmatter 模板。"""
        if card_type not in CARD_TYPES:
            raise ValueError('invalid type')
        return {
            'id': 'new_id',
            'type': card_type,
            'tags': [],
            'initial_relations': [],
            'hooks': [],
        }

    def list_pack_cards(self, pack_id: str) -> List[Path]:
        """列出卡包内所有卡牌文件。"""
        root = self._pack_cards_root(pack_id)
        return list(root.rglob('*.md'))

    def load_card(self, path: Path) -> Dict[str, Any]:
        """加载卡牌文件并返回 frontmatter 与正文。"""
        fm, body = parse_card(path)
        return {'frontmatter': fm, 'body': body}

    def _build_session(self, save_slot: str, language: Optional[str] = None) -> GameSession:
        """构建包含仓库与存储的 GameSession。"""
        paths = get_slot_paths(save_slot)
        enabled_roots = self.pack_manager.get_enabled_cards_roots()
        repo = CardRepository(cards_dir=CARDS_DIR, extra_roots=enabled_roots)
        repo.load()
        world = WorldStore(db_path=paths['world_db_path'])
        kg = KGStore(db_path=paths['kg_db_path'])
        rag = RAGStore(persist_dir=paths['rag_dir'])
        cards_index = {c.id: {'type': c.type, 'tags': c.tags} for c in repo.all()}
        rules = RuleEngine(cards_index)
        if not kg.all_edges():
            for card in repo.all():
                for rel in card.initial_relations:
                    kg.add_edge(rel['subject_id'], rel['relation'], rel['object_id'], 0.9, 'bootstrap')
        app = build_graph(repo, rag, world, kg, rules)
        ui_cards = list(repo.by_type('ui'))
        ui_panel_defs = self.ui_planner.plan(ui_cards)
        quest_catalog = self._collect_quest_catalog(repo)
        state = {
            'turn_id': 0,
            'recent_messages': [],
            'chat_history': [],
            'save_slot': save_slot,
            'snapshot_dir': str(paths['snapshot_dir']),
            'enabled_packs': [r.pack_id for r in self.pack_manager.list_packs() if r.enabled],
            'language': language or 'zh',
            'custom_ui_panel_defs': ui_panel_defs,
            'custom_ui_panels': [],
            'quest_catalog': quest_catalog,
        }
        history = self._load_chat_history(paths['chat_history_path'])
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
        """同步最新世界状态到会话视图。"""
        session.state['world_facts'] = {
            'attrs': session.world.all_attrs(),
            'edges': session.kg.all_edges(),
        }

    def _refresh_custom_ui_panels(self, session: GameSession) -> None:
        """基于 UI 卡牌定义刷新面板展示数据。"""
        panel_defs = session.state.get('custom_ui_panel_defs', [])
        world_facts = session.state.get('world_facts', {})
        history = session.state.get('chat_history', [])
        quest_catalog = session.state.get('quest_catalog', [])
        session.state['custom_ui_panels'] = self.ui_state_agent.update(panel_defs, world_facts, history, quest_catalog)


    def _collect_quest_catalog(self, repo: CardRepository) -> List[Dict[str, Any]]:
        """收集卡牌仓库中的 quest 卡牌用于任务面板展示。"""
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
        """解析某个卡包的 cards 根目录。"""
        record = self.pack_manager.registry.get(pack_id)
        if not record:
            raise ValueError('pack not found')
        return self.pack_manager.packs_root / record.pack_id / record.version / record.cards_root

    def _load_chat_history(self, path: Path) -> List[Dict[str, str]]:
        """从存档中读取聊天记录。"""
        if not path.exists():
            return []
        try:
            data = json.loads(path.read_text(encoding='utf-8'))
            if isinstance(data, list):
                return [m for m in data if isinstance(m, dict)]
        except Exception:
            return []
        return []

    def _save_chat_history(self, session: GameSession) -> None:
        """将聊天记录写入存档文件。"""
        path = get_slot_paths(session.save_slot)['chat_history_path']
        path.parent.mkdir(parents=True, exist_ok=True)
        history = session.state.get('chat_history', [])
        path.write_text(json.dumps(history, ensure_ascii=False, indent=2), encoding='utf-8')

def json_dump(data: Dict[str, Any]) -> str:
    """将 dict 序列化为格式化 JSON。"""
    import json

    return json.dumps(data, indent=2)
