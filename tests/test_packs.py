from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from game.packs.manager import PackManager
from game.packs.registry import PackRegistry, PackRecord
from game.packs.zip_utils import safe_extract
from game.packs.validator import validate_manifest


def make_pack_zip(tmp_path: Path) -> Path:
    pack_dir = tmp_path / 'pack'
    cards_dir = pack_dir / 'cards' / 'characters'
    cards_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        'pack_id': 'demo_pack',
        'name': 'Demo',
        'version': '0.1.0',
        'author': 'tester',
        'description': 'demo',
        'cards_root': 'cards',
    }
    (pack_dir / 'pack.json').write_text(json.dumps(manifest), encoding='utf-8')
    (cards_dir / 'hero.md').write_text('---\nid: hero\ntype: character\ntags: []\n---\n\nHero\n', encoding='utf-8')
    zip_path = tmp_path / 'pack.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for p in pack_dir.rglob('*'):
            if p.is_file():
                zf.write(p, p.relative_to(pack_dir))
    return zip_path


def test_manifest_validation() -> None:
    manifest = {
        'pack_id': 'demo_pack',
        'name': 'Demo',
        'version': '0.1.0',
        'author': 'tester',
        'description': 'demo',
        'cards_root': 'cards',
    }
    validate_manifest(manifest)


def test_zip_slip_protection(tmp_path: Path) -> None:
    zip_path = tmp_path / 'bad.zip'
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('../evil.txt', 'boom')
    with pytest.raises(ValueError):
        safe_extract(zip_path, tmp_path / 'out')


def test_registry_crud(tmp_path: Path) -> None:
    registry = PackRegistry(tmp_path / 'registry.json')
    record = PackRecord(
        pack_id='demo_pack',
        name='Demo',
        version='0.1.0',
        author='tester',
        description='demo',
        cards_root='cards',
        enabled=False,
        source='local',
    )
    registry.upsert(record)
    assert registry.get('demo_pack') is not None
    registry.set_enabled('demo_pack', True)
    assert registry.get('demo_pack').enabled is True
    registry.remove('demo_pack')
    assert registry.get('demo_pack') is None


def test_install_pack_from_zip(tmp_path: Path) -> None:
    zip_path = make_pack_zip(tmp_path)
    packs_root = tmp_path / 'packs'
    registry_path = tmp_path / 'registry.json'
    manager = PackManager(packs_root=packs_root, registry_path=registry_path)
    record = manager.install_pack_from_zip(zip_path)
    assert (packs_root / record.pack_id / record.version).exists()
