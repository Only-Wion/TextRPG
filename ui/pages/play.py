from __future__ import annotations

import streamlit as st

from ui.components.custom_ui_panels import render_custom_ui_panels
from ui.core.services import get_service


def render_play_page() -> None:
    service = get_service()

    if "show_top_bar" not in st.session_state:
        st.session_state.show_top_bar = True

    st.markdown(
        """
        <style>
        .block-container { padding-top: 86px; padding-bottom: 120px; }
        .stButton > button { white-space: nowrap; }
        .top-bar {
            position: fixed;
            left: 0;
            right: 0;
            top: 0;
            z-index: 999;
            background: #ffffffee;
            border-bottom: 1px solid #d7e2f2;
            backdrop-filter: blur(8px);
            padding: 10px 24px 12px 24px;
        }
        .top-toggle {
            position: fixed;
            top: 10px;
            right: 16px;
            z-index: 1000;
        }
        .bottom-bar {
            position: fixed;
            left: 0;
            right: 0;
            bottom: 0;
            z-index: 998;
            background: #ffffffee;
            border-top: 1px solid #d7e2f2;
            backdrop-filter: blur(8px);
            padding: 8px 24px 10px 24px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    packs = service.list_packs()
    pack_ids = [p["pack_id"] for p in packs]
    enabled_ids = [p["pack_id"] for p in packs if p.get("enabled")]

    if "language" not in st.session_state:
        st.session_state.language = "zh"
    lang_options = ["Chinese", "English"]
    default_index = 0 if st.session_state.language == "zh" else 1

    if not st.session_state.show_top_bar:
        st.markdown("<div class='top-toggle'>", unsafe_allow_html=True)
        if st.button("Menu"):
            st.session_state.show_top_bar = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='top-bar'>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns([1.2, 2.4, 1.2, 2.2, 0.6])
        with col1:
            save_slot = st.text_input("Save Slot", value="slot_001")
        with col2:
            selected_packs = st.multiselect("Enabled Packs", options=pack_ids, default=enabled_ids)
        with col3:
            language_label = st.selectbox("Language", options=lang_options, index=default_index)
            language = "en" if language_label == "English" else "zh"
            st.session_state.language = language
        with col4:
            b1, b2 = st.columns(2)
            with b1:
                if st.button("Start", use_container_width=True):
                    service.start_new_game(save_slot, selected_packs, language=language)
            with b2:
                if st.button("Load", use_container_width=True):
                    service.load_game(save_slot, language=language)
        with col5:
            if st.button("Hide"):
                st.session_state.show_top_bar = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    state_view = service.get_current_state_view()
    render_custom_ui_panels(state_view)

    history = state_view.get("chat_history", [])
    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            try:
                with st.chat_message("user" if role == "user" else "assistant"):
                    st.write(content)
            except Exception:
                st.write(f"{role}: {content}")
    else:
        st.write([])

    with st.sidebar.expander("World Facts", expanded=False):
        st.json(state_view.get("world_facts", {}))

    st.sidebar.markdown("---")
    st.sidebar.subheader("UI Agent")
    ui_update_mode = st.sidebar.selectbox(
        "Update Mode",
        options=["manual", "auto"],
        index=0 if state_view.get("ui_update_mode", "manual") == "manual" else 1,
    )
    service.set_ui_update_mode(ui_update_mode)
    if ui_update_mode == "auto":
        every = int(state_view.get("ui_auto_update_every", 1) or 1)
        ui_every = st.sidebar.number_input(
            "Auto Update Every (turns)",
            min_value=1,
            max_value=50,
            step=1,
            value=every,
        )
        service.set_ui_auto_update_every(ui_every)
    st.sidebar.caption(f"Generation: {state_view.get('ui_generation_status', 'idle')}")
    st.sidebar.caption(f"Update: {state_view.get('ui_update_status', 'idle')}")
    if st.sidebar.button("Generate UI"):
        service.trigger_ui_generation(force=True)
        st.rerun()
    if st.sidebar.button("Update UI"):
        service.trigger_ui_update()
        st.rerun()

    with st.sidebar.expander("Debug Info", expanded=False):
        st.write("Retrieved Cards")
        st.write(state_view.get("retrieved_cards", []))
        st.write("Validated Ops")
        st.json(state_view.get("validated_ops", []))
        st.write("Errors")
        st.write(state_view.get("errors", []))

    st.markdown("<div class='bottom-bar'>", unsafe_allow_html=True)
    user_input = st.chat_input("Type a command, press Enter")
    if user_input and user_input.strip():
        service.set_language(st.session_state.language)
        service.step(user_input.strip())
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
