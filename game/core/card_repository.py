from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List
import yaml

from ..config import CARDS_DIR

@dataclass
class Card:
    """从 Markdown 加载到内存的卡牌对象（正文按需加载）。"""
    id: str
    type: str
    tags: List[str]
    initial_relations: List[Dict[str, Any]]
    hooks: List[str]
    path: Path
    _content: str | None = None

    def load_content(self) -> str:
        """按需读取卡牌正文并缓存。"""
        if self._content is None:
            text = self.path.read_text(encoding='utf-8')
            _, body = parse_frontmatter(text)
            self._content = body.strip()
        return self._content

    @property
    def content(self) -> str:
        """卡牌正文（按需读取）。"""
        return self.load_content()


def parse_frontmatter(text: str) -> tuple[Dict[str, Any], str]:
    """解析 YAML frontmatter，返回 (frontmatter, body)。"""
    if text.startswith('---'):
        parts = text.split('---', 2)
        if len(parts) >= 3:
            fm = yaml.safe_load(parts[1]) or {}
            body = parts[2].lstrip('\n')
            return fm, body
    return {}, text


class CardRepository:
    """从内置与卡包目录加载、索引并检索卡牌。"""
    def __init__(self, cards_dir: Path = CARDS_DIR, extra_roots: List[Path] | None = None):
        self.cards_dir = cards_dir
        self.extra_roots = extra_roots or []
        self._cards: Dict[str, Card] = {}

    def load(self) -> None:
        """扫描卡牌目录并构建内存索引（正文不预加载）。"""
        self._cards.clear()
        roots = [self.cards_dir] + list(self.extra_roots)
        for root in roots:
            for path in root.rglob('*.md'):
                if '_overlay' in path.parts:
                    continue
                text = path.read_text(encoding='utf-8')
                fm, body = parse_frontmatter(text)
                card_id = fm.get('id')
                card_type = fm.get('type')
                if not card_id or not card_type:
                    continue
                tags = fm.get('tags', []) or []
                initial_relations = fm.get('initial_relations', []) or []
                hooks = fm.get('hooks', []) or []
                self._cards[card_id] = Card(
                    id=card_id,
                    type=card_type,
                    tags=tags,
                    initial_relations=initial_relations,
                    hooks=hooks,
                    path=path,
                )

    def all(self) -> Iterable[Card]:
        """返回所有已加载卡牌。"""
        return self._cards.values()

    def get(self, card_id: str) -> Card | None:
        """按 id 获取卡牌。"""
        return self._cards.get(card_id)

    def by_type(self, card_type: str) -> List[Card]:
        """按类型过滤卡牌。"""
        return [c for c in self._cards.values() if c.type == card_type]

    def by_tag(self, tag: str) -> List[Card]:
        """按标签过滤卡牌。"""
        return [c for c in self._cards.values() if tag in c.tags]

    def search(self, query: str, k: int) -> List[Card]:
        """对卡牌 id/type/tags 做简单关键词检索（正文按需加载）。"""
        if not query.strip():
            return list(self._cards.values())[:k]
        terms = {t.lower() for t in query.split() if t.strip()}
        scored: List[tuple[int, Card]] = []
        for card in self._cards.values():
            hay = f'{card.id} {card.type} {" ".join(card.tags)}'.lower()
            score = sum(1 for t in terms if t in hay)
            if score > 0:
                scored.append((score, card))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored[:k]]

    def load_overlays(self) -> List[Dict[str, Any]]:
        """从各个根目录的 _overlay 中加载 overlay ops。"""
        roots = [self.cards_dir] + list(self.extra_roots)
        overlays: List[tuple[int, List[Dict[str, Any]]]] = []
        for root in roots:
            overlay_dir = root / '_overlay'
            if not overlay_dir.exists():
                continue
            for path in overlay_dir.rglob('*.md'):
                text = path.read_text(encoding='utf-8')
                fm, _ = parse_frontmatter(text)
                if fm.get('kind') != 'overlay_ops':
                    continue
                priority = int(fm.get('priority', 0))
                ops = fm.get('ops', []) or []
                for op in ops:
                    op['source'] = 'overlay'
                overlays.append((priority, ops))
        overlays.sort(key=lambda x: x[0])
        merged: List[Dict[str, Any]] = []
        for _, ops in overlays:
            merged.extend(ops)
        return merged
