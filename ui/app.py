from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ui.components.custom_ui_panels import clear_custom_ui_panels
from ui.core.theme import apply_global_theme
from ui.pages.card_designer import render_card_designer_page
from ui.pages.pack_manager import render_pack_manager_page
from ui.pages.play import render_play_page
from ui.pages.settings import render_settings_page


def main() -> None:
    apply_global_theme()

    st.sidebar.title("TextRPG UI")
    page = st.sidebar.radio("Page", ["Play", "Pack Manager", "Card Designer", "Settings"])

    if page != "Play":
        clear_custom_ui_panels()

    if page == "Play":
        render_play_page()
    elif page == "Pack Manager":
        render_pack_manager_page()
    elif page == "Card Designer":
        render_card_designer_page()
    else:
        render_settings_page()


if __name__ == "__main__":
    main()

