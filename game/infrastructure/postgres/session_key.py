from __future__ import annotations

from pathlib import Path


def session_key_from_slot_dir(slot_dir: Path) -> str:
    """Build the canonical session key from a local save-slot directory."""

    return slot_dir.name
