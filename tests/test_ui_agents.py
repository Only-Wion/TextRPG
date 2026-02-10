from __future__ import annotations

from pathlib import Path

from game.core.card_repository import Card
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
