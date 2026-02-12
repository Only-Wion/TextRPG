from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import json

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import MockLLM, get_llm
from .api import GameService


@dataclass
class ActionPlan:
    reply: str
    actions: List[Dict[str, Any]]


class PackBuilderAgent:
    """用于卡牌包创建/编辑的对话式 agent。"""

    START_CREATE_WORDS = {
        '开始创建',
        '开始',
        'start create',
        'create now',
        '开始进行创建',
    }

    def __init__(self, service: GameService):
        self.service = service
        prompts_dir = Path(__file__).resolve().parents[1] / 'prompts'
        self.system_prompt = (prompts_dir / 'pack_builder_system.md').read_text(encoding='utf-8')
        self.question_prompt = (prompts_dir / 'pack_builder_question_mode.md').read_text(encoding='utf-8')

    def process(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        history = list(state.get('history', []))
        question_mode = bool(state.get('question_mode', True))
        creation_started = bool(state.get('creation_started', False))

        normalized = user_input.strip().lower()
        if question_mode and not creation_started:
            if normalized in self.START_CREATE_WORDS:
                state['creation_started'] = True
                assistant = '好的，已结束询问模式，开始执行创建/修改。你可以继续描述需求，我会调用工具完成。'
                history.append({'role': 'user', 'content': user_input})
                history.append({'role': 'assistant', 'content': assistant})
                state['history'] = history
                state['memory'] = self._update_memory(history)
                return {'assistant': assistant, 'state': state, 'tool_logs': []}

            assistant = self._question_mode_reply(user_input, state)
            history.append({'role': 'user', 'content': user_input})
            history.append({'role': 'assistant', 'content': assistant})
            state['history'] = history
            state['memory'] = self._update_memory(history)
            return {'assistant': assistant, 'state': state, 'tool_logs': []}

        plan = self._plan(user_input, state)
        tool_logs = self._execute_actions(plan.actions, state)

        assistant = plan.reply.strip() or '已收到，我已处理你的请求。'
        if tool_logs:
            assistant += '\n\n执行记录：\n' + '\n'.join(f'- {x}' for x in tool_logs)

        history.append({'role': 'user', 'content': user_input})
        history.append({'role': 'assistant', 'content': assistant})
        state['history'] = history
        state['memory'] = self._update_memory(history)
        return {'assistant': assistant, 'state': state, 'tool_logs': tool_logs}

    def _question_mode_reply(self, user_input: str, state: Dict[str, Any]) -> str:
        llm = get_llm()
        if isinstance(llm, MockLLM):
            return (
                '我现在处于询问模式，会先帮你完善需求。\n'
                '建议你确认：\n'
                '1) 世界主题/风格；\n'
                '2) 玩家核心循环（探索/对话/战斗）；\n'
                '3) 主要卡牌类型及数量；\n'
                '4) 新手引导与第一小时目标。\n'
                '如果准备好了，请回复“开始创建”。'
            )

        messages = [
            SystemMessage(content=self.question_prompt),
            HumanMessage(content=json.dumps({'user_input': user_input, 'state': state}, ensure_ascii=False)),
        ]
        resp = llm.invoke(messages)
        return str(resp.content)

    def _plan(self, user_input: str, state: Dict[str, Any]) -> ActionPlan:
        llm = get_llm()
        if isinstance(llm, MockLLM):
            return ActionPlan(
                reply='当前是离线 mock 模式。我建议你直接描述要创建的 pack、卡牌类型和数量；我会尝试执行工具动作。',
                actions=[],
            )

        tool_schema = {
            'tools': [
                {'name': 'list_packs', 'args': {}},
                {'name': 'create_pack', 'args': {'manifest': 'dict'}},
                {'name': 'select_pack', 'args': {'pack_id': 'str'}},
                {'name': 'list_pack_cards', 'args': {'pack_id': 'str'}},
                {'name': 'save_card', 'args': {'pack_id': 'str', 'card_type': 'str', 'card_id': 'str', 'frontmatter': 'dict', 'body': 'str'}},
                {'name': 'delete_card', 'args': {'pack_id': 'str', 'card_path': 'str'}},
                {'name': 'batch_save_cards', 'args': {'pack_id': 'str', 'cards': 'list[dict]'}},
                {'name': 'audit_pack', 'args': {'pack_id': 'str'}},
            ]
        }
        messages = [
            SystemMessage(
                content=(
                    self.system_prompt
                    + '\n\nYou must output strict JSON: {"reply": "...", "actions": [{"tool": "...", "args": {...}}]}. '
                    + 'Use tool calls to operate packs and cards. No markdown wrappers.'
                )
            ),
            HumanMessage(
                content=json.dumps(
                    {
                        'user_input': user_input,
                        'memory': state.get('memory', ''),
                        'selected_pack_id': state.get('selected_pack_id', ''),
                        'tool_schema': tool_schema,
                    },
                    ensure_ascii=False,
                )
            ),
        ]
        resp = llm.invoke(messages)
        parsed = self._parse_json(str(resp.content))
        if not parsed:
            return ActionPlan(reply=str(resp.content), actions=[])
        return ActionPlan(reply=str(parsed.get('reply', '')), actions=list(parsed.get('actions', [])))

    def _execute_actions(self, actions: List[Dict[str, Any]], state: Dict[str, Any]) -> List[str]:
        logs: List[str] = []
        for action in actions:
            tool = str(action.get('tool', '')).strip()
            args = action.get('args', {}) or {}
            try:
                if tool == 'list_packs':
                    packs = self.service.list_packs()
                    logs.append(f'list_packs -> {len(packs)} packs')
                elif tool == 'create_pack':
                    manifest = dict(args.get('manifest', {}))
                    self.service.create_pack(manifest)
                    logs.append(f'create_pack -> {manifest.get("pack_id", "")}')
                elif tool == 'select_pack':
                    state['selected_pack_id'] = str(args.get('pack_id', '')).strip()
                    logs.append(f'select_pack -> {state.get("selected_pack_id", "")}')
                elif tool == 'list_pack_cards':
                    pack_id = str(args.get('pack_id') or state.get('selected_pack_id', ''))
                    cards = self.service.list_pack_cards(pack_id)
                    logs.append(f'list_pack_cards({pack_id}) -> {len(cards)} cards')
                elif tool == 'save_card':
                    pack_id = str(args.get('pack_id') or state.get('selected_pack_id', ''))
                    self.service.save_card(
                        pack_id=pack_id,
                        card_type=str(args.get('card_type', 'card')),
                        card_id=str(args.get('card_id', 'new_card')),
                        frontmatter=dict(args.get('frontmatter', {})),
                        body=str(args.get('body', '') or 'TBD'),
                    )
                    logs.append(f'save_card -> {pack_id}/{args.get("card_type", "")}/{args.get("card_id", "")}')
                elif tool == 'batch_save_cards':
                    pack_id = str(args.get('pack_id') or state.get('selected_pack_id', ''))
                    cards = list(args.get('cards', []))
                    for card in cards:
                        self.service.save_card(
                            pack_id=pack_id,
                            card_type=str(card.get('card_type', 'card')),
                            card_id=str(card.get('card_id', 'new_card')),
                            frontmatter=dict(card.get('frontmatter', {})),
                            body=str(card.get('body', '') or 'TBD'),
                        )
                    logs.append(f'batch_save_cards -> {pack_id}, count={len(cards)}')
                elif tool == 'delete_card':
                    pack_id = str(args.get('pack_id') or state.get('selected_pack_id', ''))
                    path = Path(str(args.get('card_path', '')))
                    self.service.delete_card(pack_id, path)
                    logs.append(f'delete_card -> {path.name}')
                elif tool == 'audit_pack':
                    pack_id = str(args.get('pack_id') or state.get('selected_pack_id', ''))
                    logs.append(self._audit_pack(pack_id))
                else:
                    logs.append(f'unknown tool: {tool}')
            except Exception as exc:
                logs.append(f'{tool} failed: {exc}')
        return logs

    def _audit_pack(self, pack_id: str) -> str:
        cards = self.service.list_pack_cards(pack_id)
        ids: dict[str, int] = {}
        invalid = 0
        for path in cards:
            try:
                fm = self.service.load_card(path).get('frontmatter', {})
                cid = str(fm.get('id', '')).strip() or path.stem
                ids[cid] = ids.get(cid, 0) + 1
            except Exception:
                invalid += 1
        duplicated = sorted([k for k, v in ids.items() if v > 1])
        return f'audit_pack({pack_id}) -> cards={len(cards)}, duplicated_ids={duplicated}, parse_errors={invalid}'

    def _update_memory(self, history: List[Dict[str, str]]) -> str:
        recent = history[-12:]
        lines = [f"{m.get('role', 'user')}: {m.get('content', '')}" for m in recent]
        return '\n'.join(lines)

    def _parse_json(self, text: str) -> Dict[str, Any] | None:
        try:
            data = json.loads(text)
            if isinstance(data, dict):
                return data
        except Exception:
            pass
        stripped = text.strip()
        if stripped.startswith('```'):
            stripped = stripped.strip('`')
            if stripped.startswith('json'):
                stripped = stripped[4:].strip()
            try:
                data = json.loads(stripped)
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
        return None
