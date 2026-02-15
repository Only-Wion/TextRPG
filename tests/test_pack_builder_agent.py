from pathlib import Path

from game.packs.manager import PackManager
from game.service.api import GameService
from game.service.pack_builder_agent import ActionPlan, PackBuilderAgent


def build_service(tmp_path: Path) -> GameService:
    service = GameService(packs_root=tmp_path / 'packs')
    service.pack_manager = PackManager(packs_root=tmp_path / 'packs', registry_path=tmp_path / 'registry.json')
    service.create_pack(
        {
            'pack_id': 'demo_pack',
            'name': 'Demo Pack',
            'version': '0.1.0',
            'author': 'tester',
            'description': 'demo',
            'cards_root': 'cards',
        }
    )
    return service


def test_question_mode_switch_to_creation(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {'history': [], 'question_mode': True, 'creation_started': False, 'selected_pack_id': 'demo_pack'}

    result = agent.process('开始创建', state)

    assert result['state']['creation_started'] is True
    assert result['tool_logs'] == []
    assert len(result['state']['history']) == 2


def test_execute_batch_save_and_delete(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {'history': [], 'selected_pack_id': 'demo_pack'}

    logs = agent._execute_actions(
        [
            {
                'tool': 'batch_save_cards',
                'args': {
                    'pack_id': 'demo_pack',
                    'cards': [
                        {'card_type': 'quest', 'card_id': 'q1', 'frontmatter': {'tags': ['main']}, 'body': 'Quest 1'},
                        {'card_type': 'quest', 'card_id': 'q2', 'frontmatter': {'tags': ['side']}, 'body': 'Quest 2'},
                    ],
                },
            },
            {
                'tool': 'delete_card',
                'args': {'pack_id': 'demo_pack', 'card_path': str(service._pack_cards_root('demo_pack') / 'quests' / 'q2.md')},
            },
            {'tool': 'audit_pack', 'args': {'pack_id': 'demo_pack'}},
        ],
        state,
    )

    cards = service.list_pack_cards('demo_pack')
    names = {p.name for p in cards}
    assert 'q1.md' in names
    assert 'q2.md' not in names
    assert any('batch_save_cards' in line for line in logs)
    assert any('audit_pack' in line for line in logs)


def test_start_create_triggers_tool_execution(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    agent = PackBuilderAgent(service)
    state = {
        'history': [{'role': 'user', 'content': '请创建一个新手任务卡'}],
        'question_mode': True,
        'creation_started': False,
        'selected_pack_id': 'demo_pack',
    }

    def fake_plan(user_input: str, _state: dict) -> ActionPlan:
        assert '立即调用工具开始创建' in user_input
        return ActionPlan(
            reply='开始执行',
            actions=[
                {
                    'tool': 'save_card',
                    'args': {
                        'pack_id': 'demo_pack',
                        'card_type': 'quest',
                        'card_id': 'starter_task',
                        'frontmatter': {'tags': ['tutorial']},
                        'body': '完成第一个任务',
                    },
                }
            ],
        )

    agent._plan = fake_plan  # type: ignore[method-assign]

    result = agent.process('开始创建', state)

    cards = {p.name for p in service.list_pack_cards('demo_pack')}
    assert 'starter_task.md' in cards
    assert result['state']['question_mode'] is False
    assert result['state']['creation_started'] is True
    assert any('save_card' in line for line in result['tool_logs'])
