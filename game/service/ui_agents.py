from __future__ import annotations

from typing import Any, Dict, List
import json
import yaml

from ..core.card_repository import Card
from ..llm import llm_generate_ui_panels, llm_update_ui_panel


class UICardPlannerAgent:
    """根据 ui 卡牌生成前端可渲染的面板定义。"""

    def plan(
        self,
        cards: List[Card],
        *,
        world_facts: Dict[str, Any] | None = None,
        chat_history: List[Dict[str, str]] | None = None,
        rag_lookup: Dict[str, List[Dict[str, Any]]] | None = None,
    ) -> List[Dict[str, Any]]:
        # 遍历卡牌并汇总可渲染的面板定义
        panels: List[Dict[str, Any]] = []
        for card in cards:
            panels.extend(
                self._plan_card(
                    card,
                    world_facts=world_facts or {},
                    chat_history=chat_history or [],
                    rag_snippets=rag_lookup.get(card.id, []) if rag_lookup else [],
                )
            )
        return panels

    def _plan_card(
        self,
        card: Card,
        *,
        world_facts: Dict[str, Any],
        chat_history: List[Dict[str, str]],
        rag_snippets: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        # 读取卡牌文本并提取 frontmatter 与正文
        raw_text = card.path.read_text(encoding='utf-8')
        fm_text, body_text = _split_frontmatter_and_body(raw_text)
        instruction_text = raw_text if not fm_text else f"{fm_text.strip()}\n\n{body_text.strip()}"

        # 通过 LLM 根据卡牌描述生成 UI 面板的 HTML 内容
        payload = llm_generate_ui_panels({
            'instruction_text': instruction_text,
            'card_meta': {'id': card.id, 'type': card.type, 'tags': list(card.tags)},
            'world_facts': world_facts,
            'recent_messages': chat_history[-8:],
            'rag_snippets': rag_snippets,
        })
        panels_data = payload.get('panels', []) if isinstance(payload, dict) else []

        # 兜底：若 LLM 未生成任何面板，生成一个占位面板
        if not panels_data:
            panels_data.append({
                'title': f'{card.id} 面板 1',
                'html': (
                    "<div style='display:flex;flex-direction:column;gap:8px;'>"
                    "<div style='font-weight:700;'>界面生成中</div>"
                    "<div style='white-space:pre-line;'>等待更多内容\\n请继续探索世界</div>"
                    "</div>"
                ),
            })

        layouts = _build_panel_layouts(len(panels_data))
        panels: List[Dict[str, Any]] = []
        for idx, panel in enumerate(panels_data):
            layout = layouts[idx]
            panels.append({
                'panel_id': f"{card.id}_{idx + 1}",
                'title': str(panel.get('title', f'{card.id} 面板 {idx + 1}')),
                'panel_type': 'html',
                'visible_by_default': True,
                'layout': layout,
                'html': str(panel.get('html', '')).strip(),
                'sections': [],
            })
        return panels


class UIPanelUpdateAgent:
    """根据世界状态/历史记录/RAG 判断是否需要更新 UI 面板。"""

    def update(
        self,
        panels: List[Dict[str, Any]],
        *,
        world_facts: Dict[str, Any],
        chat_history: List[Dict[str, str]],
        rag_lookup: Dict[str, List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        updated_panels: List[Dict[str, Any]] = []
        for panel in panels:
            if panel.get('panel_type') != 'html' and not panel.get('html'):
                updated_panels.append(panel)
                continue
            card_id = str(panel.get('panel_id', '')).split('_', 1)[0]
            decision = llm_update_ui_panel({
                'panel_title': panel.get('title', ''),
                'current_html': panel.get('html', ''),
                'card_meta': {'id': card_id},
                'world_facts': world_facts,
                'recent_messages': chat_history[-8:],
                'rag_snippets': rag_lookup.get(card_id, []),
            })
            if isinstance(decision, dict) and decision.get('update'):
                html = str(decision.get('html', '')).strip()
                panel = {**panel, 'html': html}
            updated_panels.append(panel)
        return updated_panels


class UIPanelStateAgent:
    """根据世界状态实时计算每个面板的显示数据。"""

    def update(
        self,
        panel_defs: List[Dict[str, Any]],
        world_facts: Dict[str, Any],
        chat_history: List[Dict[str, str]],
        quest_cards: List[Dict[str, Any]] | None = None,
    ) -> List[Dict[str, Any]]:
        # 防御式读取世界状态，避免类型不符合预期
        attrs = world_facts.get('attrs', {}) if isinstance(world_facts, dict) else {}
        edges = world_facts.get('edges', []) if isinstance(world_facts, dict) else []
        quest_cards = quest_cards or []

        panels: List[Dict[str, Any]] = []
        for panel in panel_defs:
            if panel.get('panel_type') == 'html' or panel.get('html'):
                panels.append({
                    **panel,
                    'meta': {
                        'turn_messages': len(chat_history),
                    },
                })
                continue
            panel_type = panel.get('panel_type', 'facts_list')
            sections = panel.get('sections', [])
            rendered_sections: List[Dict[str, Any]] = []
            # 根据面板类型分发渲染逻辑
            if panel_type == 'quest_tracker':
                rendered_sections = self._build_quest_sections(sections, attrs, quest_cards)
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

    def _build_quest_sections(
        self,
        sections: List[Dict[str, Any]],
        attrs: Dict[str, Any],
        quest_cards: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        rendered: List[Dict[str, Any]] = []
        quest_status = _extract_quest_status(attrs)

        for section in sections:
            prefix = str(section.get('attr_prefix', 'quest.'))
            entries: List[Dict[str, Any]] = []
            seen_keys: set[str] = set()

            # 从世界属性中收集任务相关键值
            for key, value in attrs.items():
                if key.startswith(prefix):
                    entries.append({'key': key, 'value': value})
                    seen_keys.add(key)

            # 结合任务卡补充缺失的状态条目
            for quest in quest_cards:
                quest_id = str(quest.get('id', '')).strip()
                if not quest_id:
                    continue
                status = quest_status.get(quest_id, 'available')
                key = f'quest.{quest_id}.status'
                if key in seen_keys:
                    continue
                summary = str(quest.get('summary', '')).strip()
                value = status if not summary else f'{status} | {summary}'
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
            # 根据关系类型与主体过滤边
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
            # 未指定 sections 时，直接展示全部事实
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
            # 只渲染在 keys 白名单中的属性
            entries = [{'key': k, 'value': attrs.get(k)} for k in keys if k in attrs]
            rendered.append({
                'title': section.get('title', 'Facts'),
                'entries': entries,
                'empty_text': section.get('empty_text', '暂无状态'),
            })
        return rendered


def _extract_quest_status(attrs: Dict[str, Any]) -> Dict[str, str]:
    # 汇总任务状态，兼容两种键前缀
    status: Dict[str, str] = {}
    for key, value in attrs.items():
        if key.startswith('quest.') and key.endswith('.status'):
            quest_id = key[len('quest.'):-len('.status')]
            status[quest_id] = str(value)
        elif key.startswith('quest_status.'):
            quest_id = key[len('quest_status.'):]
            status[quest_id] = str(value)
    return status


def _split_frontmatter_and_body(text: str) -> tuple[str, str]:
    # 解析以 --- 包裹的 frontmatter
    if not text.startswith('---'):
        return '', text
    parts = text.split('---', 2)
    if len(parts) < 3:
        return '', text
    return parts[1], parts[2].lstrip('\n')


def _extract_schema(frontmatter: Dict[str, Any], body_text: str) -> Dict[str, Any] | None:
    # 先使用 frontmatter 的 ui_schema，否则再尝试正文 JSON/YAML
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


def _build_panel_layouts(
    count: int,
    *,
    start_x: int = 20,
    start_y: int = 120,
    width: int = 360,
    height: int = 640,
    gap: int = 24,
) -> List[Dict[str, int]]:
    """为面板生成不重叠的手机竖屏布局(9:16)。"""
    if count <= 0:
        return []
    columns = 1 if count <= 3 else 2
    layouts: List[Dict[str, int]] = []
    for idx in range(count):
        col = idx % columns
        row = idx // columns
        layouts.append({
            'x': start_x + col * (width + gap),
            'y': start_y + row * (height + gap),
            'width': width,
            'height': height,
        })
    return layouts
