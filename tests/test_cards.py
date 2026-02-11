from __future__ import annotations

from game.packs.validator import validate_card_frontmatter
from game.packs.card_editor import validate_card


def test_card_frontmatter_validation() -> None:
    frontmatter = {'id': 'hero', 'type': 'character', 'tags': []}
    validate_card_frontmatter(frontmatter, 'Body')


def test_card_validation_allows_custom_type() -> None:
    frontmatter = {'id': 'hero', 'type': 'quest', 'tags': []}
    validate_card(frontmatter, 'Body')


def test_card_validation_rejects_empty_type() -> None:
    frontmatter = {'id': 'hero', 'type': '   ', 'tags': []}
    try:
        validate_card(frontmatter, 'Body')
        raise AssertionError('Expected ValueError for empty type')
    except ValueError:
        pass
