from __future__ import annotations

from pathlib import Path
import argparse
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from game.config import USER_PACKS_DIR
from game.packs.manager import PackManager
from game.packs.storage import OssPackStorage


def _validate_oss_env() -> None:
    required = [
        "TEXTRPG_OSS_ENDPOINT",
        "TEXTRPG_OSS_BUCKET",
        "TEXTRPG_OSS_ACCESS_KEY_ID",
        "TEXTRPG_OSS_ACCESS_KEY_SECRET",
    ]
    missing = [name for name in required if not str(os.getenv(name, "")).strip()]
    if missing:
        raise RuntimeError(f"Missing required OSS env vars: {', '.join(missing)}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Sync installed local packs to OSS without changing registry records."
    )
    parser.add_argument(
        "--pack-id",
        action="append",
        default=[],
        help="Only sync specific pack_id (repeatable). Defaults to all installed packs.",
    )
    parser.add_argument(
        "--user-id",
        default="default",
        help="User namespace to migrate from data/user_packs/<user_id>.",
    )
    args = parser.parse_args()

    _validate_oss_env()
    user_id = str(args.user_id).strip() or "default"
    packs_root = USER_PACKS_DIR / user_id
    registry_path = packs_root / "pack_registry.json"
    storage = OssPackStorage(packs_root)
    manager = PackManager(
        packs_root=packs_root,
        registry_path=registry_path,
        storage=storage,
    )

    all_records = manager.list_packs()
    target_ids = {str(item).strip() for item in args.pack_id if str(item).strip()}
    records = (
        [record for record in all_records if record.pack_id in target_ids]
        if target_ids
        else all_records
    )

    if target_ids and not records:
        raise RuntimeError("No matching packs found in registry for provided --pack-id")

    if not records:
        print("No packs found in registry. Nothing to sync.")
        return 0

    print(f"Sync target count: {len(records)}")
    for record in records:
        manager.sync_pack_content(record.pack_id)
        print(f"Synced: {record.pack_id}@{record.version}")

    print("OSS migration sync complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
