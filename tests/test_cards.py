from __future__ import annotations

import pytest

from game.packs.validator import validate_card_frontmatter
from game.packs.card_editor import validate_card


def test_card_frontmatter_validation() -> None:
    frontmatter = {'id': 'hero', 'type': 'character', 'tags': []}
    validate_card_frontmatter(frontmatter, 'Body')


def test_card_validation_invalid_type() -> None:
    frontmatter = {'id': 'hero', 'type': 'unknown', 'tags': []}
    with pytest.raises(ValueError):
        validate_card(frontmatter, 'Body')
