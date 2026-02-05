from __future__ import annotations

from typing import Any, Dict
from langgraph.graph import StateGraph, END

from ..state import GameState
from ..ops import OpsPayload
from ..llm import llm_plan_ops, llm_narrate
from .card_repository import CardRepository
from .rule_engine import RuleEngine
from .rag_store import RAGStore
from .kg_store import KGStore
from .world_store import WorldStore
from .snapshot import write_snapshot
from .admin import parse_admin_command
from ..config import SETTINGS


def _get(state: Any, key: str, default: Any) -> Any:
    """从 dict 或 Pydantic 模型中安全读取字段。"""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def ingest_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """裁剪最近消息，用于提示词上下文。"""
    history = _get(state, 'chat_history', [])
    if isinstance(history, list) and history:
        recent = history[-SETTINGS.max_recent_messages:]
    else:
        recent = _get(state, 'recent_messages', [])[-SETTINGS.max_recent_messages:]
    return {'recent_messages': recent}


def load_overlays(state: Dict[str, Any], repo: CardRepository) -> Dict[str, Any]:
    """加载 cards/_overlay 中的 overlay ops。"""
    return {'overlay_ops': repo.load_overlays()}


def retrieve_context(state: Dict[str, Any], repo: CardRepository, rag: RAGStore, world: WorldStore, kg: KGStore, rules: RuleEngine) -> Dict[str, Any]:
    """收集卡牌、记忆、世界状态与允许的动作。"""
    cards = [
        {'id': c.id, 'type': c.type, 'tags': c.tags, 'content': c.content}
        for c in repo.search(_get(state, 'player_input', ''), k=SETTINGS.top_k_cards)
    ]
    memories = rag.search(_get(state, 'player_input', ''), k=SETTINGS.top_k_memories)
    attrs = world.all_attrs()
    edges = kg.all_edges()
    world_facts = {'attrs': attrs, 'edges': edges}
    allowed_actions = rules.allowed_actions(world_facts)
    return {
        'retrieved_cards': cards,
        'retrieved_memories': memories,
        'world_facts': world_facts,
        'allowed_actions': allowed_actions,
    }


def plan_ops(state: Dict[str, Any]) -> Dict[str, Any]:
    """根据管理员命令或 LLM 生成草案 ops。"""
    admin_ops = parse_admin_command(_get(state, 'player_input', ''))
    if admin_ops:
        return {'draft_ops': admin_ops}
    payload = llm_plan_ops(state)
    return {'draft_ops': payload.get('ops', [])}


def validate_ops(state: Dict[str, Any], rules: RuleEngine) -> Dict[str, Any]:
    """校验草案+覆盖层 ops，返回有效 ops 与错误。"""
    merged = list(_get(state, 'draft_ops', [])) + list(_get(state, 'overlay_ops', []))
    try:
        payload = OpsPayload.model_validate({'ops': merged})
    except Exception as exc:
        return {'validated_ops': [], 'errors': [f'Invalid ops payload: {exc}']}
    world_facts = _get(state, 'world_facts', {})
    edges = world_facts.get('edges', [])
    valid_ops, errors = rules.validate_ops(payload, edges)
    return {'validated_ops': valid_ops, 'errors': errors}


def apply_updates(state: Dict[str, Any], world: WorldStore, kg: KGStore, rag: RAGStore) -> Dict[str, Any]:
    """将已验证的 ops 应用到持久化存储。"""
    turn = int(_get(state, 'turn_id', 0))
    for op in _get(state, 'validated_ops', []):
        if op['type'] == 'SetAttr':
            world.set_attr(op['entity_id'], op['key'], op['value'], op.get('source', 'llm'), turn)
        elif op['type'] == 'AddEdge':
            kg.add_edge(op['subject_id'], op['relation'], op['object_id'], op.get('confidence', 0.8), op.get('source', 'llm'))
        elif op['type'] == 'RemoveEdge':
            kg.remove_edge(op['subject_id'], op['relation'], op['object_id'])
        elif op['type'] == 'LogMemory':
            rag.add_memory(op['text'], op.get('tags', []))
    return {}


def narrate(state: Dict[str, Any]) -> Dict[str, Any]:
    """通过 LLM 生成叙事文本。"""
    return {'narration': llm_narrate(state)}


def checkpoint(state: Dict[str, Any], world: WorldStore, kg: KGStore, rag: RAGStore) -> Dict[str, Any]:
    """写入状态快照并保存回合摘要。"""
    attrs = world.all_attrs()
    edges = kg.all_edges()
    snapshot_dir = _get(state, 'snapshot_dir', '') or None
    write_snapshot(attrs, edges, snapshot_dir=snapshot_dir)
    summary = f"Turn {_get(state, 'turn_id', 0)}: {_get(state, 'player_input', '')} -> {_get(state, 'narration', '')}"
    rag.add_memory(summary, ['turn_summary'])
    return {}


def build_graph(repo: CardRepository, rag: RAGStore, world: WorldStore, kg: KGStore, rules: RuleEngine):
    """构建并编译 LangGraph 状态机。"""
    graph = StateGraph(GameState)
    graph.add_node('ingest_input', ingest_input)
    graph.add_node('load_overlays', lambda s: load_overlays(s, repo))
    graph.add_node('retrieve_context', lambda s: retrieve_context(s, repo, rag, world, kg, rules))
    graph.add_node('plan_ops', plan_ops)
    graph.add_node('validate_ops', lambda s: validate_ops(s, rules))
    graph.add_node('apply_updates', lambda s: apply_updates(s, world, kg, rag))
    graph.add_node('narrate', narrate)
    graph.add_node('checkpoint', lambda s: checkpoint(s, world, kg, rag))

    graph.set_entry_point('ingest_input')
    graph.add_edge('ingest_input', 'load_overlays')
    graph.add_edge('load_overlays', 'retrieve_context')
    graph.add_edge('retrieve_context', 'plan_ops')
    graph.add_edge('plan_ops', 'validate_ops')
    graph.add_edge('validate_ops', 'apply_updates')
    graph.add_edge('apply_updates', 'narrate')
    graph.add_edge('narrate', 'checkpoint')
    graph.add_edge('checkpoint', END)

    return graph.compile()
