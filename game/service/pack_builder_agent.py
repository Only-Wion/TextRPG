from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List
import json
import re

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import StructuredTool

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
        self.tool_schemas = [
            {'name': 'list_packs', 'args': {}},
            {'name': 'create_pack', 'args': {'manifest': 'dict'}},
            {'name': 'select_pack', 'args': {'pack_id': 'str'}},
            {'name': 'list_pack_cards', 'args': {'pack_id': 'str'}},
            {'name': 'save_card', 'args': {'pack_id': 'str', 'card_type': 'str', 'card_id': 'str', 'frontmatter': 'dict', 'body': 'str'}},
            {'name': 'delete_card', 'args': {'pack_id': 'str', 'card_path': 'str'}},
            {'name': 'batch_save_cards', 'args': {'pack_id': 'str', 'cards': 'list[dict]'}},
            {'name': 'audit_pack', 'args': {'pack_id': 'str'}},
        ]

    def process(self, user_input: str, state: Dict[str, Any]) -> Dict[str, Any]:
        history = list(state.get('history', []))
        question_mode = bool(state.get('question_mode', True))
        creation_started = bool(state.get('creation_started', False))

        normalized = user_input.strip().lower()
        if question_mode and not creation_started:
            if normalized in self.START_CREATE_WORDS:
                state['creation_started'] = True
                state['question_mode'] = False
                bootstrap_input = self._build_bootstrap_input(state)
                plan = self._plan(bootstrap_input, state)
                tool_logs = self._execute_actions(plan.actions, state)

                assistant = plan.reply.strip() or '已切换到执行模式，并开始按已确认需求创建/修改。'
                if tool_logs:
                    assistant += '\n\n执行记录：\n' + '\n'.join(f'- {x}' for x in tool_logs)
                elif plan.actions:
                    assistant += '\n\n（已规划动作，但未生成执行日志，请继续补充具体需求。）'
                else:
                    assistant += '\n\n（尚未生成可执行动作，请补充更具体的卡包/卡牌需求。）'

                history.append({'role': 'user', 'content': user_input})
                history.append({'role': 'assistant', 'content': assistant})
                state['history'] = history
                state['memory'] = self._update_memory(history)
                return {'assistant': assistant, 'state': state, 'tool_logs': tool_logs}

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


    def _build_bootstrap_input(self, state: Dict[str, Any]) -> str:
        """从历史中提炼需求，在“开始创建”时立即触发一次执行计划。"""
        history = list(state.get('history', []))
        user_lines: List[str] = []
        for msg in history:
            if msg.get('role') != 'user':
                continue
            content = str(msg.get('content', '')).strip()
            if not content:
                continue
            if content.lower() in self.START_CREATE_WORDS:
                continue
            user_lines.append(content)

        if user_lines:
            recent = '\n'.join(f'- {line}' for line in user_lines[-5:])
            return '请根据以下已确认需求，立即调用工具开始创建/修改：\n' + recent
        return '现在进入执行模式。请基于当前上下文立即调用工具开始创建。'

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

        tool_schema = {'tools': self.tool_schemas}
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
            retry_messages = [
                SystemMessage(content='Return STRICT JSON only: {"reply":"...","actions":[{"tool":"...","args":{}}]}'),
                HumanMessage(content=str(resp.content)),
            ]
            retry = llm.invoke(retry_messages)
            parsed = self._parse_json(str(retry.content))
        if not parsed:
            return ActionPlan(reply=str(resp.content), actions=[])
        return ActionPlan(reply=str(parsed.get('reply', '')), actions=list(parsed.get('actions', [])))

    def _safe_pack_id(self, raw: str, fallback: str = 'generated_pack') -> str:
        base = re.sub(r'[^a-zA-Z0-9_-]+', '_', str(raw or '').strip()).strip('_').lower()
        return base or fallback

    def _build_manifest_with_defaults(self, manifest: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        source = dict(manifest)
        preferred = str(source.get('pack_id') or state.get('selected_pack_id') or 'generated_pack')
        pack_id = self._safe_pack_id(preferred)
        return {
            'pack_id': pack_id,
            'name': str(source.get('name') or pack_id.replace('_', ' ').title()),
            'version': str(source.get('version') or '0.1.0'),
            'author': str(source.get('author') or 'PackBuilderAgent'),
            'description': str(source.get('description') or 'Generated by Pack Builder Agent'),
            'cards_root': str(source.get('cards_root') or 'cards'),
        }

    def _normalize_card_payload(self, card: Dict[str, Any], default_type: str = 'card') -> Dict[str, Any]:
        data = dict(card)
        frontmatter = dict(data.get('frontmatter', {}))
        card_type = str(data.get('card_type') or frontmatter.get('type') or default_type).strip() or default_type
        card_id = str(data.get('card_id') or frontmatter.get('id') or 'new_card').strip() or 'new_card'

        frontmatter.setdefault('id', card_id)
        frontmatter.setdefault('type', card_type)
        tags = frontmatter.get('tags')
        if not isinstance(tags, list):
            frontmatter['tags'] = [] if tags is None else [str(tags)]

        return {
            'card_type': card_type,
            'card_id': card_id,
            'frontmatter': frontmatter,
            'body': str(data.get('body', '') or 'TBD'),
        }

    def _execute_actions(self, actions: List[Dict[str, Any]], state: Dict[str, Any]) -> List[str]:
        logs: List[str] = []
        tools = self._build_runtime_tools(state)
        for action in actions:
            tool_name = str(action.get('tool', '')).strip()
            args = action.get('args', {}) or {}
            handler = tools.get(tool_name)
            if not handler:
                logs.append(f'unknown tool: {tool_name}')
                continue
            try:
                logs.append(str(handler.invoke(args)))
            except Exception as exc:
                logs.append(f'{tool_name} failed: {exc}')
        return logs

    def _build_runtime_tools(self, state: Dict[str, Any]) -> Dict[str, StructuredTool]:
        return {
            'list_packs': StructuredTool.from_function(
                name='list_packs',
                description='列出当前已注册的卡牌包。',
                func=lambda: f'list_packs -> {len(self.service.list_packs())} packs',
            ),
            'create_pack': StructuredTool.from_function(
                name='create_pack',
                description='创建一个新的卡牌包。',
                func=lambda manifest: self._tool_create_pack(manifest, state),
            ),
            'select_pack': StructuredTool.from_function(
                name='select_pack',
                description='选择后续操作要使用的卡牌包。',
                func=lambda pack_id: self._tool_select_pack(pack_id, state),
            ),
            'list_pack_cards': StructuredTool.from_function(
                name='list_pack_cards',
                description='列出某个卡牌包中的全部卡牌文件。',
                func=lambda pack_id='': self._tool_list_pack_cards(pack_id, state),
            ),
            'save_card': StructuredTool.from_function(
                name='save_card',
                description='保存单张卡牌。',
                func=lambda pack_id='', card_type='card', card_id='new_card', frontmatter=None, body='': self._tool_save_card(
                    {'pack_id': pack_id, 'card_type': card_type, 'card_id': card_id, 'frontmatter': frontmatter or {}, 'body': body},
                    state,
                ),
            ),
            'batch_save_cards': StructuredTool.from_function(
                name='batch_save_cards',
                description='批量保存卡牌。',
                func=lambda pack_id='', cards=None: self._tool_batch_save_cards(pack_id, cards or [], state),
            ),
            'delete_card': StructuredTool.from_function(
                name='delete_card',
                description='删除指定卡牌文件。',
                func=lambda pack_id='', card_path='': self._tool_delete_card(pack_id, card_path, state),
            ),
            'audit_pack': StructuredTool.from_function(
                name='audit_pack',
                description='审计卡牌包中的重复 ID 和解析错误。',
                func=lambda pack_id='': self._tool_audit_pack(pack_id, state),
            ),
        }

    def _resolve_pack_id(self, raw_pack_id: str, state: Dict[str, Any]) -> str:
        return self._safe_pack_id(str(raw_pack_id or state.get('selected_pack_id', '')))

    def _tool_create_pack(self, manifest: Dict[str, Any], state: Dict[str, Any]) -> str:
        normalized = self._build_manifest_with_defaults(dict(manifest or {}), state)
        self.service.create_pack(normalized)
        state['selected_pack_id'] = normalized['pack_id']
        return f'create_pack -> {normalized.get("pack_id", "")}'

    def _tool_select_pack(self, pack_id: str, state: Dict[str, Any]) -> str:
        target_pack = self._safe_pack_id(str(pack_id).strip())
        existing = {p.get('pack_id', '') for p in self.service.list_packs()}
        if target_pack in existing:
            state['selected_pack_id'] = target_pack
            return f'select_pack -> {target_pack}'
        return f'select_pack skipped: pack not found -> {target_pack}'

    def _tool_list_pack_cards(self, pack_id: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        cards = self.service.list_pack_cards(resolved)
        return f'list_pack_cards({resolved}) -> {len(cards)} cards'

    def _tool_save_card(self, args: Dict[str, Any], state: Dict[str, Any]) -> str:
        pack_id = self._resolve_pack_id(str(args.get('pack_id', '')), state)
        card_payload = self._normalize_card_payload(args)
        self.service.save_card(
            pack_id=pack_id,
            card_type=card_payload['card_type'],
            card_id=card_payload['card_id'],
            frontmatter=card_payload['frontmatter'],
            body=card_payload['body'],
        )
        return f"save_card -> {pack_id}/{card_payload['card_type']}/{card_payload['card_id']}"

    def _tool_batch_save_cards(self, pack_id: str, cards: List[Dict[str, Any]], state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        saved = 0
        for card in list(cards):
            self._tool_save_card({'pack_id': resolved, **dict(card)}, state)
            saved += 1
        return f'batch_save_cards -> {resolved}, count={saved}'

    def _tool_delete_card(self, pack_id: str, card_path: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        path = Path(str(card_path))
        self.service.delete_card(resolved, path)
        return f'delete_card -> {path.name}'

    def _tool_audit_pack(self, pack_id: str, state: Dict[str, Any]) -> str:
        resolved = self._resolve_pack_id(pack_id, state)
        if resolved not in {p.get('pack_id', '') for p in self.service.list_packs()}:
            return f'audit_pack skipped: pack not found -> {resolved}'
        return self._audit_pack(resolved)

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
                pass

        l = stripped.find('{')
        r = stripped.rfind('}')
        if l != -1 and r != -1 and r > l:
            snippet = stripped[l:r+1]
            try:
                data = json.loads(snippet)
                if isinstance(data, dict):
                    return data
            except Exception:
                return None
        return None
