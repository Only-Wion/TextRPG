from __future__ import annotations

from typing import Dict, List


def parse_admin_command(text: str) -> List[Dict[str, str]]:
    """将斜杠命令解析为管理员 ops。"""
    if not text.startswith('/'):
        return []
    parts = text.strip().split()
    if len(parts) < 2:
        return []
    cmd = parts[0].lower()
    ops: List[Dict[str, str]] = []
    if cmd == '/give' and len(parts) >= 3:
        ops.append({
            'type': 'AddEdge',
            'subject_id': parts[1],
            'relation': 'has',
            'object_id': parts[2],
            'confidence': 1.0,
            'source': 'admin'
        })
    elif cmd == '/teleport' and len(parts) >= 3:
        ops.append({
            'type': 'AddEdge',
            'subject_id': parts[1],
            'relation': 'at',
            'object_id': parts[2],
            'confidence': 1.0,
            'source': 'admin'
        })
    elif cmd == '/set' and len(parts) >= 3:
        if '.' in parts[1]:
            entity_id, key = parts[1].split('.', 1)
            value = parts[2]
            ops.append({
                'type': 'SetAttr',
                'entity_id': entity_id,
                'key': key,
                'value': value,
                'source': 'admin'
            })
        else:
            key_val = parts[2].split('=', 1)
            if len(key_val) == 2:
                ops.append({
                    'type': 'SetAttr',
                    'entity_id': parts[1],
                    'key': key_val[0],
                    'value': key_val[1],
                    'source': 'admin'
                })
    return ops
