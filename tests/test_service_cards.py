from __future__ import annotations

from pathlib import Path

from game.service.api import GameService
from game.packs.manager import PackManager


def build_service(tmp_path: Path) -> GameService:
    service = GameService(packs_root=tmp_path / 'packs')
    service.pack_manager = PackManager(packs_root=tmp_path / 'packs', registry_path=tmp_path / 'registry.json')
    service.create_pack(
        {
            'pack_id': 'demo_pack',
            'name': 'Demo',
            'version': '0.1.0',
            'author': 'tester',
            'description': 'demo',
            'cards_root': 'cards',
        }
    )
    return service


def test_save_card_rename_removes_original(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    old_path = service.create_card('demo_pack', 'location', 'old_room', {'tags': []}, 'Old')

    new_path = service.save_card(
        'demo_pack',
        'location',
        'new_room',
        {'tags': []},
        'New',
        original_path=old_path,
    )

    assert new_path.exists()
    assert not old_path.exists()


def test_delete_card_removes_file(tmp_path: Path) -> None:
    service = build_service(tmp_path)
    path = service.create_card('demo_pack', 'location', 'to_delete', {'tags': []}, 'Body')
    assert path.exists()

    service.delete_card('demo_pack', path)

    assert not path.exists()
