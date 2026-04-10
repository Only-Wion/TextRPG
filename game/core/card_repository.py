from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List
import json
import yaml

from ..config import CARDS_DIR

GRAPH_CANDIDATE_PATHS = (
    ("story", "story_graph.json"),
    ("meta", "story_graph.json"),
    ("story_graph.json",),
)


def _normalize_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def _normalize_transition_list(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    if not isinstance(value, list):
        return result
    for item in value:
        if isinstance(item, str) and item.strip():
            result.append(
                {
                    "event_id": item.strip(),
                    "condition_key": "",
                    "condition_label": "",
                    "priority": 0,
                }
            )
            continue
        if not isinstance(item, dict):
            continue
        event_id = str(
            item.get("event_id")
            or item.get("target_event_id")
            or item.get("object_id")
            or item.get("to")
            or ""
        ).strip()
        if not event_id:
            continue
        result.append(
            {
                "event_id": event_id,
                "condition_key": str(
                    item.get("condition_key") or item.get("condition") or ""
                ).strip(),
                "condition_label": str(
                    item.get("condition_label")
                    or item.get("label")
                    or item.get("description")
                    or ""
                ).strip(),
                "priority": int(item.get("priority") or 0),
            }
        )
    return result


@dataclass
class Card:
    id: str
    type: str
    tags: List[str]
    initial_relations: List[Dict[str, Any]]
    hooks: List[str]
    path: Path
    title: str = ""
    frontmatter: Dict[str, Any] = field(default_factory=dict)
    related_cards: List[str] = field(default_factory=list)
    next_events: List[Dict[str, Any]] = field(default_factory=list)
    entry: bool = False
    _content: str | None = None

    def load_content(self) -> str:
        if self._content is None:
            text = self.path.read_text(encoding="utf-8")
            _, body = parse_frontmatter(text)
            self._content = body.strip()
        return self._content

    @property
    def content(self) -> str:
        return self.load_content()


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    normalized = text.lstrip("\ufeff \t\r\n")
    if normalized.startswith("---"):
        parts = normalized.split("---", 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip("\n")
            return fm, body
    return {}, text


class CardRepository:
    """Load card content separately from pack-level story graph structure."""

    def __init__(
        self, cards_dir: Path = CARDS_DIR, extra_roots: List[Path] | None = None
    ):
        self.cards_dir = cards_dir
        self.extra_roots = extra_roots or []
        self._cards: Dict[str, Card] = {}
        self._entry_event_ids: list[str] = []
        self._related_cards_by_event: dict[str, list[str]] = {}
        self._next_events_by_event: dict[str, list[dict[str, Any]]] = {}
        self._graph_nodes: dict[str, dict[str, Any]] = {}

    def load(self) -> None:
        self._cards.clear()
        self._entry_event_ids = []
        self._related_cards_by_event = {}
        self._next_events_by_event = {}
        self._graph_nodes = {}

        roots = [self.cards_dir] + list(self.extra_roots)
        for root in roots:
            for path in root.rglob("*.md"):
                if "_overlay" in path.parts:
                    continue
                text = path.read_text(encoding="utf-8")
                fm, _ = parse_frontmatter(text)
                card_id = str(fm.get("id") or "").strip()
                card_type = str(fm.get("type") or "").strip()
                if not card_id or not card_type:
                    continue

                initial_relations = fm.get("initial_relations", []) or []
                related_cards = _normalize_string_list(
                    fm.get("related_cards") or fm.get("related_card_ids")
                )
                next_events = _normalize_transition_list(
                    fm.get("next_events") or fm.get("event_branches")
                )

                for relation in initial_relations:
                    if not isinstance(relation, dict):
                        continue
                    rel = str(relation.get("relation") or "").strip()
                    obj = str(
                        relation.get("object_id")
                        or relation.get("target_event_id")
                        or relation.get("event_id")
                        or ""
                    ).strip()
                    if not rel or not obj:
                        continue
                    if rel in {"related_to", "relates_to"}:
                        related_cards.append(obj)
                    elif rel in {"next_event", "next_when", "precedes"}:
                        next_events.append(
                            {
                                "event_id": obj,
                                "condition_key": str(
                                    relation.get("condition_key")
                                    or relation.get("condition")
                                    or ""
                                ).strip(),
                                "condition_label": str(
                                    relation.get("condition_label")
                                    or relation.get("label")
                                    or ""
                                ).strip(),
                                "priority": int(relation.get("priority") or 0),
                            }
                        )

                tags = _normalize_string_list(fm.get("tags", []))
                hooks = _normalize_string_list(fm.get("hooks", []))
                self._cards[card_id] = Card(
                    id=card_id,
                    type=card_type,
                    tags=tags,
                    initial_relations=initial_relations,
                    hooks=hooks,
                    path=path,
                    title=str(fm.get("title") or fm.get("name") or card_id),
                    frontmatter=fm,
                    related_cards=list(dict.fromkeys(related_cards)),
                    next_events=next_events,
                    entry=bool(fm.get("entry") or fm.get("is_entry") or fm.get("start")),
                )

        for root in roots:
            self._load_story_graph_for_root(root)

    def _load_story_graph_for_root(self, cards_root: Path) -> None:
        pack_root = cards_root.parent
        graph_path: Path | None = None
        for candidate in GRAPH_CANDIDATE_PATHS:
            path = pack_root.joinpath(*candidate)
            if path.exists():
                graph_path = path
                break
        if graph_path is None:
            return
        try:
            payload = json.loads(graph_path.read_text(encoding="utf-8"))
        except Exception:
            return
        if not isinstance(payload, dict):
            return

        for entry_id in _normalize_string_list(payload.get("entry_events")):
            if self.get(entry_id):
                self._entry_event_ids.append(entry_id)

        nodes = payload.get("nodes")
        if isinstance(nodes, list):
            for node in nodes:
                if not isinstance(node, dict):
                    continue
                card_id = str(node.get("card_id") or "").strip()
                if card_id and self.get(card_id):
                    self._graph_nodes[card_id] = dict(node)

        edges = payload.get("edges")
        if not isinstance(edges, list):
            return
        for edge in edges:
            if not isinstance(edge, dict):
                continue
            source = str(edge.get("from") or edge.get("source") or "").strip()
            target = str(edge.get("to") or edge.get("target") or "").strip()
            if not source or not target or not self.get(source) or not self.get(target):
                continue
            edge_type = str(edge.get("type") or "").strip().lower()
            directed = bool(edge.get("directed"))
            if edge_type == "related" or (not directed and edge_type != "event_flow"):
                self._related_cards_by_event.setdefault(source, []).append(target)
                self._related_cards_by_event.setdefault(target, []).append(source)
                continue
            if edge_type == "event_flow" or directed:
                self._next_events_by_event.setdefault(source, []).append(
                    {
                        "event_id": target,
                        "condition_key": str(edge.get("condition_key") or "").strip(),
                        "condition_label": str(edge.get("label") or "").strip(),
                        "priority": int(edge.get("priority") or 0),
                        "edge_id": str(edge.get("id") or "").strip(),
                    }
                )

    def all(self) -> Iterable[Card]:
        return self._cards.values()

    def get(self, card_id: str) -> Card | None:
        return self._cards.get(card_id)

    def by_type(self, card_type: str) -> List[Card]:
        return [c for c in self._cards.values() if c.type == card_type]

    def by_tag(self, tag: str) -> List[Card]:
        return [c for c in self._cards.values() if tag in c.tags]

    def event_cards(self) -> List[Card]:
        return sorted(self.by_type("event"), key=lambda item: item.id)

    def entry_event_ids(self) -> List[str]:
        entries = list(dict.fromkeys(self._entry_event_ids))
        if entries:
            return entries
        fallback = [card.id for card in self.event_cards() if card.entry]
        if fallback:
            return fallback
        all_events = self.event_cards()
        return [all_events[0].id] if all_events else []

    def related_cards_for_event(self, event_id: str) -> List[Card]:
        related_ids = self._related_cards_by_event.get(event_id)
        if related_ids is None:
            event_card = self.get(event_id)
            related_ids = event_card.related_cards if event_card else []
        result: list[Card] = []
        seen: set[str] = set()
        for related_id in related_ids:
            related = self.get(related_id)
            if related and related.id not in seen:
                seen.add(related.id)
                result.append(related)
        return result

    def next_events_for(self, event_id: str) -> List[Dict[str, Any]]:
        transitions = self._next_events_by_event.get(event_id)
        if transitions is None:
            event_card = self.get(event_id)
            transitions = event_card.next_events if event_card else []
        result: list[dict[str, Any]] = []
        for item in transitions:
            target = str(item.get("event_id") or "").strip()
            if not target or not self.get(target):
                continue
            result.append(
                {
                    "event_id": target,
                    "condition_key": str(item.get("condition_key") or "").strip(),
                    "condition_label": str(item.get("condition_label") or "").strip(),
                    "priority": int(item.get("priority") or 0),
                    "edge_id": str(item.get("edge_id") or "").strip(),
                }
            )
        return result

    def graph_node(self, card_id: str) -> dict[str, Any]:
        return dict(self._graph_nodes.get(card_id, {}))

    def search(self, query: str, k: int) -> List[Card]:
        if not query.strip():
            return list(self._cards.values())[:k]
        terms = {t.lower() for t in query.split() if t.strip()}
        scored: List[tuple[int, Card]] = []
        for card in self._cards.values():
            hay = f'{card.id} {card.type} {card.title} {" ".join(card.tags)}'.lower()
            score = sum(1 for t in terms if t in hay)
            if score > 0:
                scored.append((score, card))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]
