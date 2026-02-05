from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class PackRecord:
    """已安装卡包的注册信息。"""
    pack_id: str
    name: str
    version: str
    author: str
    description: str
    cards_root: str
    enabled: bool
    source: str


class PackRegistry:
    """基于 JSON 的卡包注册表。"""
    def __init__(self, registry_path: Path):
        self.registry_path = registry_path
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.registry_path.exists():
            self._write({'packs': {}})

    def list(self) -> List[PackRecord]:
        """列出全部卡包记录。"""
        data = self._read()
        records: List[PackRecord] = []
        for pack_id, payload in data.get('packs', {}).items():
            records.append(PackRecord(pack_id=pack_id, **payload))
        return records

    def get(self, pack_id: str) -> Optional[PackRecord]:
        """按 id 获取卡包记录。"""
        data = self._read()
        payload = data.get('packs', {}).get(pack_id)
        if not payload:
            return None
        return PackRecord(pack_id=pack_id, **payload)

    def upsert(self, record: PackRecord) -> None:
        """插入或更新卡包记录。"""
        data = self._read()
        data.setdefault('packs', {})[record.pack_id] = {
            'name': record.name,
            'version': record.version,
            'author': record.author,
            'description': record.description,
            'cards_root': record.cards_root,
            'enabled': record.enabled,
            'source': record.source,
        }
        self._write(data)

    def remove(self, pack_id: str) -> None:
        """移除卡包记录。"""
        data = self._read()
        if pack_id in data.get('packs', {}):
            data['packs'].pop(pack_id, None)
            self._write(data)

    def set_enabled(self, pack_id: str, enabled: bool) -> None:
        """切换卡包启用状态。"""
        data = self._read()
        if pack_id not in data.get('packs', {}):
            raise ValueError('pack not found')
        data['packs'][pack_id]['enabled'] = enabled
        self._write(data)

    def _read(self) -> Dict[str, Dict]:
        """读取注册表 JSON 文件。"""
        return json.loads(self.registry_path.read_text(encoding='utf-8'))

    def _write(self, data: Dict[str, Dict]) -> None:
        """写入注册表 JSON 文件。"""
        self.registry_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
