from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from game.service.api import GameService


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def get_service() -> GameService:
    """Return cached GameService instance for UI."""
    if "service" not in st.session_state:
        st.session_state.service = GameService()
    return st.session_state.service


def load_api_key_for_update() -> str:
    """Load persisted API key from disk."""
    settings_path = PROJECT_ROOT / "data" / "llm_settings.json"
    if not settings_path.exists():
        return ""
    try:
        payload = json.loads(settings_path.read_text(encoding="utf-8"))
        if isinstance(payload, dict):
            return str(payload.get("api_key", ""))
    except Exception:
        return ""
    return ""

