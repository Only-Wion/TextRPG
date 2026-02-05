from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict
import yaml

PACK_ID_RE = re.compile(r'^[a-zA-Z0-9_-]+$')
SEMVER_RE = re.compile(r'^\d+\.\d+\.\d+$')


def load_manifest(path: Path) -> Dict[str, Any]:
    """从 JSON 或 YAML 加载卡包 manifest。"""
    if path.suffix.lower() in ('.yaml', '.yml'):
        data = yaml.safe_load(path.read_text(encoding='utf-8'))
    else:
        data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict):
        raise ValueError('manifest must be an object')
    return data


def validate_manifest(data: Dict[str, Any]) -> None:
    """校验 manifest 的必填字段与格式。"""
    required = ['pack_id', 'name', 'version', 'author', 'description', 'cards_root']
    for key in required:
        if key not in data:
            raise ValueError(f'manifest missing field: {key}')
    pack_id = str(data['pack_id'])
    version = str(data['version'])
    if not PACK_ID_RE.match(pack_id):
        raise ValueError('pack_id is invalid')
    if not SEMVER_RE.match(version):
        raise ValueError('version must be semver (x.y.z)')


def validate_card_frontmatter(frontmatter: Dict[str, Any], body: str) -> None:
    """校验卡牌 frontmatter 与正文的最低要求。"""
    if not isinstance(frontmatter, dict):
        raise ValueError('frontmatter must be a mapping')
    required = ['id', 'type', 'tags']
    for key in required:
        if key not in frontmatter:
            raise ValueError(f'frontmatter missing field: {key}')
    if not isinstance(frontmatter['tags'], list):
        raise ValueError('tags must be a list')
    if not isinstance(body, str) or not body.strip():
        raise ValueError('body must be non-empty')
