from __future__ import annotations

from pathlib import Path

from game.core.card_repository import Card
from game import llm as llm_module
from game.service.ui_agents import UICardPlannerAgent, UIPanelStateAgent


def test_ui_card_planner_builds_panel_definition(tmp_path: Path) -> None:
    path = tmp_path / 'quest_tracker_main.md'
    path.write_text(
        """---
ui_schema:
  panel_id: quest_tracker_main
  title: 任务推进
  panel_type: quest_tracker
  visible_by_default: true
  layout:
    x: 10
    y: 20
    width: 400
    height: 300
  sections:
    - title: 可推进任务
      attr_prefix: quest.
---

ui card body
""",
        encoding='utf-8',
    )

    card = Card(
        id='quest_tracker_main',
        type='ui',
        tags=['ui', 'quest'],
        initial_relations=[],
        hooks=[],
        path=path,
    )

    planner = UICardPlannerAgent()
    panels = planner.plan([card])

    assert len(panels) == 1
    panel = panels[0]
    assert panel['panel_id'] == 'quest_tracker_main'
    assert panel['panel_type'] == 'quest_tracker'
    assert panel['layout']['width'] == 400


def test_ui_state_agent_tracks_quest_attrs() -> None:
    updater = UIPanelStateAgent()
    panel_defs = [
        {
            'panel_id': 'quest_tracker_main',
            'title': '任务推进',
            'panel_type': 'quest_tracker',
            'visible_by_default': True,
            'layout': {'x': 10, 'y': 20, 'width': 400, 'height': 300},
            'sections': [{'title': '可推进任务', 'attr_prefix': 'quest.'}],
        }
    ]
    world_facts = {
        'attrs': {
            'quest.join_guild.status': 'in_progress',
            'quest.find_weapon_master.status': 'done',
            'player.hp': 95,
        },
        'edges': [],
    }

    panels = updater.update(panel_defs, world_facts, chat_history=[])

    entries = panels[0]['sections'][0]['entries']
    keys = [e['key'] for e in entries]
    assert 'quest.join_guild.status' in keys
    assert 'quest.find_weapon_master.status' in keys
    assert 'player.hp' not in keys


def test_ui_state_agent_uses_quest_cards_when_no_quest_attrs() -> None:
    updater = UIPanelStateAgent()
    panel_defs = [
        {
            'panel_id': 'quest_tracker_main',
            'title': '任务推进',
            'panel_type': 'quest_tracker',
            'visible_by_default': True,
            'layout': {'x': 10, 'y': 20, 'width': 400, 'height': 300},
            'sections': [{'title': '可推进任务', 'attr_prefix': 'quest.'}],
        }
    ]
    world_facts = {'attrs': {'player.hp': 95}, 'edges': []}
    quest_cards = [
        {'id': 'quest_join_guild', 'summary': '触发：在工会会长对话。'},
        {'id': 'quest_tavern_rumors', 'summary': '触发：在酒馆问询。'},
    ]

    panels = updater.update(panel_defs, world_facts, chat_history=[], quest_cards=quest_cards)

    entries = panels[0]['sections'][0]['entries']
    keys = [e['key'] for e in entries]
    assert 'quest.quest_join_guild.status' in keys
    assert 'quest.quest_tavern_rumors.status' in keys
    values = {e['key']: e['value'] for e in entries}
    assert values['quest.quest_join_guild.status'].startswith('available')


def test_llm_logging_writes_request_and_response(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr(llm_module, 'PROJECT_ROOT', tmp_path)
    monkeypatch.setattr(llm_module, '_LLM_LOGGER', llm_module.logging.getLogger('game.llm.test'))

    class DummyMessage:
        def __init__(self, content: str) -> None:
            self.content = content
            self.usage_metadata = {'input_tokens': 3, 'output_tokens': 5}
            self.response_metadata = {'token_usage': {'prompt_tokens': 3, 'completion_tokens': 5}}
            self.type = 'human'

    class DummyResponse:
        def __init__(self, content: str) -> None:
            self.content = content
            self.usage_metadata = {'input_tokens': 7, 'output_tokens': 11}
            self.response_metadata = {'token_usage': {'prompt_tokens': 7, 'completion_tokens': 11}}

    class DummyLLM:
        def invoke(self, messages):
            return DummyResponse('ok-response')

    response = llm_module._invoke_llm_with_logging(
        DummyLLM(),
        'unit_test_scene',
        [DummyMessage('prompt-a'), DummyMessage('prompt-b')],
    )

    assert response.content == 'ok-response'

    log_path = tmp_path / 'data' / 'logs' / 'llm_api.log'
    assert log_path.exists()
    content = log_path.read_text(encoding='utf-8')
    assert 'scene=unit_test_scene phase=request' in content
    assert 'scene=unit_test_scene phase=response' in content
    assert 'prompt-a' in content
    assert 'ok-response' in content
