from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List
import json
import yaml

from ..core.card_repository import Card


@dataclass
class UIPanel:
    """运行时 UI 面板定义。"""
    panel_id: str
    title: str
    panel_type: str
    visible_by_default: bool
    layout: Dict[str, int]
    sections: List[Dict[str, Any]]


class UICardPlannerAgent:
    """根据 ui 卡牌生成前端可渲染的面板定义。"""

    def plan(self, cards: List[Card]) -> List[Dict[str, Any]]:
        panels: List[Dict[str, Any]] = []
        for card in cards:
            panel = self._plan_card(card)
            if panel:
                panels.append(panel)
        return panels

    def _plan_card(self, card: Card) -> Dict[str, Any] | None:
        raw_text = card.path.read_text(encoding='utf-8')
        fm_text, body_text = _split_frontmatter_and_body(raw_text)
        frontmatter = {}
        if fm_text:
            try:
                frontmatter = yaml.safe_load(fm_text) or {}
            except Exception:
                frontmatter = {}

        schema = _extract_schema(frontmatter, body_text)
        if not schema:
            return None

        layout = schema.get('layout', {}) if isinstance(schema, dict) else {}
        normalized_layout = {
            'x': int(layout.get('x', 20)),
            'y': int(layout.get('y', 120)),
            'width': int(layout.get('width', 360)),
            'height': int(layout.get('height', 280)),
        }
        return {
            'panel_id': str(schema.get('panel_id', card.id)),
            'title': str(schema.get('title', card.id)),
            'panel_type': str(schema.get('panel_type', 'facts_list')),
            'visible_by_default': bool(schema.get('visible_by_default', True)),
            'layout': normalized_layout,
            'sections': schema.get('sections', []),
        }


class UIPanelStateAgent:
    """根据世界状态实时计算每个面板的显示数据。"""

    def update(self, panel_defs: List[Dict[str, Any]], world_facts: Dict[str, Any], chat_history: List[Dict[str, str]]) -> List[Dict[str, Any]]:
        attrs = world_facts.get('attrs', {}) if isinstance(world_facts, dict) else {}
        edges = world_facts.get('edges', []) if isinstance(world_facts, dict) else []
        panels: List[Dict[str, Any]] = []
        for panel in panel_defs:
            panel_type = panel.get('panel_type', 'facts_list')
            sections = panel.get('sections', [])
            rendered_sections: List[Dict[str, Any]] = []
            if panel_type == 'quest_tracker':
                rendered_sections = self._build_quest_sections(sections, attrs)
            elif panel_type == 'relation_board':
                rendered_sections = self._build_relation_sections(sections, edges)
            else:
                rendered_sections = self._build_facts_sections(sections, attrs)
            panels.append({
                **panel,
                'sections': rendered_sections,
                'meta': {
                    'turn_messages': len(chat_history),
                },
            })
        return panels

    def _build_quest_sections(self, sections: List[Dict[str, Any]], attrs: Dict[str, Any]) -> List[Dict[str, Any]]:
        rendered: List[Dict[str, Any]] = []
        for section in sections:
            prefix = str(section.get('attr_prefix', 'quest.'))
            entries = []
            for key, value in attrs.items():
                if key.startswith(prefix):
                    entries.append({'key': key, 'value': value})
            entries.sort(key=lambda x: x['key'])
            rendered.append({
                'title': section.get('title', 'Quests'),
                'entries': entries,
                'empty_text': section.get('empty_text', '暂无任务数据'),
            })
        return rendered

    def _build_relation_sections(self, sections: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        rendered: List[Dict[str, Any]] = []
        for section in sections:
            relation = section.get('relation')
            subject = section.get('subject_id')
            filtered = []
            for edge in edges:
                if relation and edge.get('relation') != relation:
                    continue
                if subject and edge.get('subject_id') != subject:
                    continue
                filtered.append(edge)
            rendered.append({
                'title': section.get('title', 'Relations'),
                'entries': filtered,
                'empty_text': section.get('empty_text', '暂无关系数据'),
            })
        return rendered

    def _build_facts_sections(self, sections: List[Dict[str, Any]], attrs: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not sections:
            return [
                {
                    'title': 'Facts',
                    'entries': [{'key': k, 'value': v} for k, v in attrs.items()],
                    'empty_text': '暂无状态',
                }
            ]
        rendered: List[Dict[str, Any]] = []
        for section in sections:
            keys = section.get('keys', [])
            entries = [{'key': k, 'value': attrs.get(k)} for k in keys if k in attrs]
            rendered.append({
                'title': section.get('title', 'Facts'),
                'entries': entries,
                'empty_text': section.get('empty_text', '暂无状态'),
            })
        return rendered


def _split_frontmatter_and_body(text: str) -> tuple[str, str]:
    if not text.startswith('---'):
        return '', text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return '', text
    return parts[1], parts[2].lstrip('\n')


def _extract_schema(frontmatter: Dict[str, Any], body_text: str) -> Dict[str, Any] | None:
    schema = frontmatter.get('ui_schema')
    if isinstance(schema, dict):
        return schema

    stripped = body_text.strip()
    if not stripped:
        return {
            'panel_type': 'facts_list',
            'sections': [],
        }

    try:
        as_json = json.loads(stripped)
        if isinstance(as_json, dict):
            return as_json
    except Exception:
        pass

    try:
        as_yaml = yaml.safe_load(stripped)
        if isinstance(as_yaml, dict):
            return as_yaml
    except Exception:
        pass

    return {
        'panel_type': 'facts_list',
        'sections': [],
    }
