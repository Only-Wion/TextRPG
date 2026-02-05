from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from ..config import SNAPSHOT_DIR


def write_snapshot(attrs: Dict[str, Dict[str, str]], edges: List[Dict[str, str]], snapshot_dir: Path | str | None = None) -> None:
    """按实体写出当前状态的 Markdown 快照。"""
    snapshot_dir = snapshot_dir or SNAPSHOT_DIR
    if isinstance(snapshot_dir, str):
        snapshot_dir = Path(snapshot_dir)
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    by_entity: Dict[str, Dict[str, List[Dict[str, str]]]] = {}
    for e in edges:
        by_entity.setdefault(e['subject_id'], {}).setdefault('edges', []).append(e)
        by_entity.setdefault(e['object_id'], {}).setdefault('edges_in', []).append(e)
    entities = set(list(attrs.keys()) + list(by_entity.keys()))
    for entity_id in entities:
        lines = [f'# {entity_id}', '']
        ent_attrs = attrs.get(entity_id, {})
        if ent_attrs:
            lines.append('## Attributes')
            for k, v in ent_attrs.items():
                lines.append(f'- {k}: {v}')
            lines.append('')
        ent_edges = by_entity.get(entity_id, {}).get('edges', [])
        if ent_edges:
            lines.append('## Relations (out)')
            for e in ent_edges:
                lines.append(f"- ({e['relation']}) -> {e['object_id']}")
            lines.append('')
        ent_edges_in = by_entity.get(entity_id, {}).get('edges_in', [])
        if ent_edges_in:
            lines.append('## Relations (in)')
            for e in ent_edges_in:
                lines.append(f"- {e['subject_id']} -> ({e['relation']})")
            lines.append('')
        path = snapshot_dir / f'{entity_id}.md'
        path.write_text('\n'.join(lines).strip() + '\n', encoding='utf-8')
