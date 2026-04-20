from __future__ import annotations

from typing import Any

from .card_repository import CardRepository
from ..infrastructure.contracts import KGStoreProtocol, WorldStoreProtocol

EVENT_ACTIVE_KEY = "active"
EVENT_STARTED_KEY = "started"
EVENT_COMPLETED_KEY = "completed"
CONDITION_PREFIX = "condition::"


def condition_world_key(condition_key: str) -> str:
    normalized = str(condition_key or "").strip()
    return f"{CONDITION_PREFIX}{normalized}" if normalized else ""


def _as_bool(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "done"}


def seed_story_runtime(
    repo: CardRepository,
    world: WorldStoreProtocol,
    kg: KGStoreProtocol,
    *,
    turn: int = 0,
) -> None:
    """Prime KG edges and runtime world flags from pack-authored event graph metadata."""
    attrs = world.all_attrs()
    edges = {
        (str(edge.get("subject_id") or ""), str(edge.get("relation") or ""), str(edge.get("object_id") or ""))
        for edge in kg.all_edges()
    }

    for card in repo.all():
        for relation in card.initial_relations:
            if not isinstance(relation, dict):
                continue
            subject_id = str(relation.get("subject_id") or card.id).strip()
            rel = str(relation.get("relation") or "").strip()
            object_id = str(relation.get("object_id") or "").strip()
            if not subject_id or not rel or not object_id:
                continue
            edge_key = (subject_id, rel, object_id)
            if edge_key not in edges:
                kg.add_edge(subject_id, rel, object_id, 1.0, "pack_seed")
                edges.add(edge_key)

        if card.type != "event":
            continue

        existing = attrs.get(card.id, {})
        if EVENT_ACTIVE_KEY not in existing:
            world.set_attr(card.id, EVENT_ACTIVE_KEY, "false", "pack_seed", turn)
        if EVENT_STARTED_KEY not in existing:
            world.set_attr(card.id, EVENT_STARTED_KEY, "false", "pack_seed", turn)
        if EVENT_COMPLETED_KEY not in existing:
            world.set_attr(card.id, EVENT_COMPLETED_KEY, "false", "pack_seed", turn)

        for related in card.related_cards:
            edge_key = (card.id, "related_to", related)
            if edge_key not in edges and repo.get(related):
                kg.add_edge(card.id, "related_to", related, 1.0, "pack_seed")
                edges.add(edge_key)

        for transition in repo.next_events_for(card.id):
            target_id = str(transition.get("event_id") or "").strip()
            if not target_id:
                continue
            edge_key = (card.id, "next_event", target_id)
            if edge_key not in edges:
                kg.add_edge(card.id, "next_event", target_id, 1.0, "pack_seed")
                edges.add(edge_key)
            condition_key = condition_world_key(transition.get("condition_key") or "")
            if condition_key and condition_key not in existing:
                world.set_attr(card.id, condition_key, "false", "pack_seed", turn)

    refreshed = world.all_attrs()
    active_event_ids = active_event_ids_from_world(repo, refreshed)
    if active_event_ids:
        return
    for entry_id in repo.entry_event_ids():
        world.set_attr(entry_id, EVENT_ACTIVE_KEY, "true", "pack_seed", turn)


def active_event_ids_from_world(
    repo: CardRepository, attrs: dict[str, dict[str, str]]
) -> list[str]:
    active: list[str] = []
    for card in repo.event_cards():
        event_attrs = attrs.get(card.id, {})
        if _as_bool(event_attrs.get(EVENT_ACTIVE_KEY)) and not _as_bool(
            event_attrs.get(EVENT_COMPLETED_KEY)
        ):
            active.append(card.id)
    if active:
        return active
    return repo.entry_event_ids()


def event_condition_rows(
    repo: CardRepository, attrs: dict[str, dict[str, str]], event_id: str
) -> list[dict[str, Any]]:
    event_attrs = attrs.get(event_id, {})
    rows: list[dict[str, Any]] = []
    for transition in repo.next_events_for(event_id):
        key = condition_world_key(transition.get("condition_key") or "")
        rows.append(
            {
                "event_id": event_id,
                "next_event_id": transition.get("event_id"),
                "condition_key": transition.get("condition_key", ""),
                "condition_label": transition.get("condition_label", ""),
                "priority": int(transition.get("priority") or 0),
                "is_satisfied": _as_bool(event_attrs.get(key)) if key else False,
            }
        )
    return rows


def advance_active_events(
    repo: CardRepository,
    world: WorldStoreProtocol,
    *,
    turn: int,
) -> list[dict[str, Any]]:
    """Advance any active events whose outgoing conditions are satisfied."""
    attrs = world.all_attrs()
    active_event_ids = active_event_ids_from_world(repo, attrs)
    promoted: list[dict[str, Any]] = []

    for event_id in active_event_ids:
        world.set_attr(event_id, EVENT_STARTED_KEY, "true", "story_graph", turn)
        transitions = event_condition_rows(repo, attrs, event_id)
        satisfied = [row for row in transitions if row["is_satisfied"]]
        if not satisfied:
            continue

        world.set_attr(event_id, EVENT_COMPLETED_KEY, "true", "story_graph", turn)
        world.set_attr(event_id, EVENT_ACTIVE_KEY, "false", "story_graph", turn)
        for row in satisfied:
            next_event_id = str(row.get("next_event_id") or "").strip()
            if not next_event_id or not repo.get(next_event_id):
                continue
            world.set_attr(next_event_id, EVENT_ACTIVE_KEY, "true", "story_graph", turn)
            promoted.append(
                {
                    "from_event_id": event_id,
                    "to_event_id": next_event_id,
                    "condition_key": row.get("condition_key", ""),
                    "condition_label": row.get("condition_label", ""),
                }
            )

    return promoted
