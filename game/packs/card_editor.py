from __future__ import annotations

from pathlib import Path
from typing import Any, Dict
import yaml

from .validator import validate_card_frontmatter

CARD_TYPES = ['character', 'item', 'location', 'event', 'memory', 'ui']


def render_card(frontmatter: Dict[str, Any], body: str) -> str:
    """将 YAML frontmatter 与正文渲染为 Markdown 卡牌。"""
    return '---\n' + yaml.safe_dump(frontmatter, sort_keys=False).strip() + '\n---\n\n' + body.strip() + '\n'


def parse_card(path: Path) -> tuple[Dict[str, Any], str]:
    """解析 Markdown 卡牌文件并返回 frontmatter 与正文。"""
    text = path.read_text(encoding='utf-8')
    if text.startswith('---'):
        parts = text.split('---', 2)
        fm = yaml.safe_load(parts[1]) or {}
        body = parts[2].lstrip('\n')
        return fm, body
    return {}, text


def validate_card(frontmatter: Dict[str, Any], body: str) -> None:
    """校验卡牌类型与基础 frontmatter/body 规则。"""
    if frontmatter.get('type') not in CARD_TYPES:
        raise ValueError('type is invalid')
    validate_card_frontmatter(frontmatter, body)
