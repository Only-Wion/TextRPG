from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict
from langgraph.graph import StateGraph, END
from langgraph.config import get_stream_writer

from ..state import GameState
from ..ops import OpsPayload
from ..llm import llm_narrate_stream, llm_plan_ops
from ..infrastructure.contracts import (
    KGStoreProtocol,
    RAGStoreProtocol,
    WorldStoreProtocol,
)
from .card_repository import CardRepository
from .rule_engine import RuleEngine
from .snapshot import write_snapshot
from .admin import parse_admin_command
from ..config import SETTINGS


@dataclass(frozen=True)
class TurnGraphBundle:
    narration_app: Any
    ops_app: Any


def _get(state: Any, key: str, default: Any) -> Any:
    """从 dict 或 Pydantic 模型中安全读取字段。"""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)


def ingest_input(state: Dict[str, Any]) -> Dict[str, Any]:
    """裁剪最近消息，用于提示词上下文。"""
    history = _get(state, "chat_history", [])
    if isinstance(history, list) and history:
        recent = history[-SETTINGS.max_recent_messages :]
    else:
        recent = _get(state, "recent_messages", [])[-SETTINGS.max_recent_messages :]
    return {"recent_messages": recent}


def retrieve_context(
    state: Dict[str, Any],
    repo: CardRepository,
    rag: RAGStoreProtocol,
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rules: RuleEngine,
) -> Dict[str, Any]:
    """收集卡牌、记忆、世界状态与允许的动作。"""
    cards = [
        {"id": c.id, "type": c.type, "tags": c.tags, "content": c.content}
        for c in repo.search(_get(state, "player_input", ""), k=SETTINGS.top_k_cards)
    ]
    memories = rag.search(_get(state, "player_input", ""), k=SETTINGS.top_k_memories)
    attrs = world.all_attrs()
    edges = kg.all_edges()
    world_facts = {"attrs": attrs, "edges": edges}
    allowed_actions = rules.allowed_actions(world_facts)
    return {
        "retrieved_cards": cards,
        "retrieved_memories": memories,
        "world_facts": world_facts,
        "allowed_actions": allowed_actions,
    }


def plan_ops(state: Dict[str, Any]) -> Dict[str, Any]:
    """根据管理员命令或 LLM 生成草案 ops。"""
    admin_ops = parse_admin_command(_get(state, "player_input", ""))
    if admin_ops:
        return {"draft_ops": admin_ops}
    payload = llm_plan_ops(state)
    return {"draft_ops": payload.get("ops", [])}


def validate_ops(state: Dict[str, Any], rules: RuleEngine) -> Dict[str, Any]:
    """校验草案+覆盖层 ops，返回有效 ops 与错误。"""
    merged = list(_get(state, "draft_ops", []))
    try:
        payload = OpsPayload.model_validate({"ops": merged})
    except Exception as exc:
        return {"validated_ops": [], "errors": [f"Invalid ops payload: {exc}"]}
    world_facts = _get(state, "world_facts", {})
    edges = world_facts.get("edges", [])
    valid_ops, errors = rules.validate_ops(payload, edges)
    return {"validated_ops": valid_ops, "errors": errors}


def apply_updates(
    state: Dict[str, Any],
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rag: RAGStoreProtocol,
) -> Dict[str, Any]:
    """将已验证的 ops 应用到持久化存储。"""
    turn = int(_get(state, "turn_id", 0))
    for op in _get(state, "validated_ops", []):
        if op["type"] == "SetAttr":
            world.set_attr(
                op["entity_id"], op["key"], op["value"], op.get("source", "llm"), turn
            )
        elif op["type"] == "AddEdge":
            kg.add_edge(
                op["subject_id"],
                op["relation"],
                op["object_id"],
                op.get("confidence", 0.8),
                op.get("source", "llm"),
            )
        elif op["type"] == "RemoveEdge":
            kg.remove_edge(op["subject_id"], op["relation"], op["object_id"])
        elif op["type"] == "LogMemory":
            rag.add_memory(op["text"], op.get("tags", []))
    return {}


def narrate(state: Dict[str, Any]) -> Dict[str, Any]:
    """通过 LLM 流式生成叙事文本，并向图流写入增量。"""
    writer = get_stream_writer()
    parts: list[str] = []
    for delta in llm_narrate_stream(state):
        if not isinstance(delta, str) or not delta:
            continue
        parts.append(delta)
        writer({"type": "narration_delta", "delta": delta})
    return {"narration": "".join(parts)}


def checkpoint(
    state: Dict[str, Any],
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rag: RAGStoreProtocol,
) -> Dict[str, Any]:
    """写入状态快照并保存回合摘要。"""
    attrs = world.all_attrs()
    edges = kg.all_edges()
    snapshot_dir = _get(state, "snapshot_dir", "") or None
    write_snapshot(attrs, edges, snapshot_dir=snapshot_dir)
    summary = f"Turn {_get(state, 'turn_id', 0)}: {_get(state, 'player_input', '')} -> {_get(state, 'narration', '')}"
    rag.add_memory(summary, ["turn_summary"])
    return {}


def _ops_interval() -> int:
    return max(1, int(getattr(SETTINGS, "ops_every_n_turns", 1) or 1))


def should_run_ops(state: Dict[str, Any]) -> bool:
    """按回合间隔判断是否触发 ops 分支。"""
    turn_id = int(_get(state, "turn_id", 0) or 0)
    return turn_id > 0 and turn_id % _ops_interval() == 0


def build_narration_graph(
    repo: CardRepository,
    rag: RAGStoreProtocol,
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rules: RuleEngine,
):
    """构建只负责叙事输出的 LangGraph。"""
    graph = StateGraph(GameState)
    graph.add_node("ingest_input", ingest_input)
    graph.add_node(
        "retrieve_context", lambda s: retrieve_context(s, repo, rag, world, kg, rules)
    )
    graph.add_node("narrate", narrate)

    graph.set_entry_point("ingest_input")
    graph.add_edge("ingest_input", "retrieve_context")
    graph.add_edge("retrieve_context", "narrate")
    graph.add_edge("narrate", END)

    return graph.compile()


def build_ops_graph(
    repo: CardRepository,
    rag: RAGStoreProtocol,
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rules: RuleEngine,
):
    """构建只负责 ops 规划、校验和落库的 LangGraph。"""
    graph = StateGraph(GameState)
    graph.add_node("ingest_input", ingest_input)
    graph.add_node(
        "retrieve_context", lambda s: retrieve_context(s, repo, rag, world, kg, rules)
    )
    graph.add_node("plan_ops", plan_ops)
    graph.add_node("validate_ops", lambda s: validate_ops(s, rules))
    graph.add_node("apply_updates", lambda s: apply_updates(s, world, kg, rag))
    graph.add_node("checkpoint", lambda s: checkpoint(s, world, kg, rag))

    graph.set_entry_point("ingest_input")
    graph.add_edge("ingest_input", "retrieve_context")
    graph.add_edge("retrieve_context", "plan_ops")
    graph.add_edge("plan_ops", "validate_ops")
    graph.add_edge("validate_ops", "apply_updates")
    graph.add_edge("apply_updates", "checkpoint")
    graph.add_edge("checkpoint", END)

    return graph.compile()


def build_turn_graphs(
    repo: CardRepository,
    rag: RAGStoreProtocol,
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rules: RuleEngine,
):
    """构建叙事图与 ops 图的组合。"""
    return TurnGraphBundle(
        narration_app=build_narration_graph(repo, rag, world, kg, rules),
        ops_app=build_ops_graph(repo, rag, world, kg, rules),
    )


def build_graph(
    repo: CardRepository,
    rag: RAGStoreProtocol,
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    rules: RuleEngine,
):
    """兼容旧调用方的单图构建入口，返回叙事图。"""
    return build_narration_graph(repo, rag, world, kg, rules)
