from __future__ import annotations

from pathlib import Path

import streamlit as st
import yaml

from ui.components.card_designer import (
    ensure_pack_builder_state,
    get_pack_builder_agent,
    render_existing_cards_mindmap,
    render_pack_builder_chat_column,
)
from ui.core.services import get_service


def render_card_designer_page() -> None:
    st.title("Card Designer")
    service = get_service()
    packs = service.list_packs()
    pack_ids = [p["pack_id"] for p in packs]

    mode = st.radio("Mode", ["Edit existing pack", "Create new pack"])
    if mode == "Create new pack":
        st.subheader("New Pack Manifest")
        pack_id = st.text_input("pack_id")
        name = st.text_input("name")
        version = st.text_input("version", value="0.1.0")
        author = st.text_input("author")
        description = st.text_area("description")
        cards_root = st.text_input("cards_root", value="cards")
        if st.button("Create Pack"):
            manifest = {
                "pack_id": pack_id,
                "name": name,
                "version": version,
                "author": author,
                "description": description,
                "cards_root": cards_root,
            }
            service.create_pack(manifest)
            state = ensure_pack_builder_state()
            state["selected_pack_id"] = pack_id
            st.rerun()
        return

    if not pack_ids:
        st.info("No packs installed.")
        return

    pack_id = st.selectbox("Pack", options=pack_ids)

    if "editing_card_path" not in st.session_state:
        st.session_state.editing_card_path = ""
    if "editing_card_id" not in st.session_state:
        st.session_state.editing_card_id = ""
    if "editing_card_type" not in st.session_state:
        st.session_state.editing_card_type = ""
    if "card_designer_notice" not in st.session_state:
        st.session_state.card_designer_notice = None

    agent_state = ensure_pack_builder_state()
    if not agent_state.get("selected_pack_id"):
        agent_state["selected_pack_id"] = pack_id

    edit_col, cards_col, chat_col = st.columns([4.0, 2.9, 3.1])
    with edit_col:
        st.subheader("Create / Edit Card")
        type_options = service.list_pack_card_types(pack_id) or ["card"]
        default_type = st.session_state.get("editing_card_type")
        default_type_index = type_options.index(default_type) if default_type in type_options else 0
        selected_type = st.selectbox("Type (select existing/default)", options=type_options, index=default_type_index)
        custom_type = st.text_input("Or input custom Type", placeholder="e.g. quest, faction, skill_tree")
        card_type = custom_type.strip() or selected_type

        card_id = st.text_input("Card ID", value=st.session_state.get("editing_card_id", ""))

        if st.button("Generate Template"):
            template = service.get_card_template(card_type)
            st.session_state.card_frontmatter = yaml.safe_dump(template, sort_keys=False, allow_unicode=True)

        frontmatter_text = st.text_area("YAML frontmatter", value=st.session_state.get("card_frontmatter", ""))
        body_text = st.text_area("Body (Markdown)", value=st.session_state.get("card_body", ""))

        b_new, b_save, b_delete, b_validate = st.columns(4)

        with b_new:
            if st.button("New Card", use_container_width=True):
                st.session_state.editing_card_path = ""
                st.session_state.editing_card_id = ""
                st.session_state.editing_card_type = ""
                st.session_state.card_frontmatter = ""
                st.session_state.card_body = ""
                st.session_state.card_designer_notice = ("info", "Switched to new card mode.")
                st.rerun()

        with b_save:
            if st.button("Save Card", use_container_width=True):
                frontmatter = yaml.safe_load(frontmatter_text) or {}
                original_path = Path(st.session_state.editing_card_path) if st.session_state.get("editing_card_path") else None
                saved_path = service.save_card(pack_id, card_type, card_id, frontmatter, body_text, original_path=original_path)
                st.session_state.editing_card_path = str(saved_path)
                st.session_state.editing_card_id = card_id
                st.session_state.editing_card_type = card_type
                st.session_state.card_designer_notice = ("success", "Saved.")
                st.rerun()

        with b_delete:
            if st.button("Delete Card", use_container_width=True):
                original_path = st.session_state.get("editing_card_path")
                if not original_path:
                    st.session_state.card_designer_notice = ("warning", "Please load/select a card before deleting.")
                else:
                    service.delete_card(pack_id, Path(original_path))
                    st.session_state.editing_card_path = ""
                    st.session_state.editing_card_id = ""
                    st.session_state.editing_card_type = ""
                    st.session_state.card_frontmatter = ""
                    st.session_state.card_body = ""
                    st.session_state.card_designer_notice = ("success", "Deleted.")
                st.rerun()

        with b_validate:
            if st.button("Validate", use_container_width=True):
                frontmatter = yaml.safe_load(frontmatter_text) or {}
                try:
                    service.validate_card(frontmatter, body_text)
                    st.session_state.card_designer_notice = ("success", "Valid.")
                except Exception as exc:
                    st.session_state.card_designer_notice = ("error", str(exc))
                st.rerun()

        notice = st.session_state.get("card_designer_notice")
        if notice:
            level, message = notice
            if level == "success":
                st.success(message)
            elif level == "warning":
                st.warning(message)
            elif level == "error":
                st.error(message)
            else:
                st.info(message)

    with cards_col:
        st.subheader("Existing Cards")
        all_paths = service.list_pack_cards(pack_id)
        pick_card = st.query_params.get("pick_card")
        if pick_card:
            picked = next((p for p in all_paths if f"{p.parent.name}/{p.name}" == pick_card), None)
            if picked is not None:
                card = service.load_card(picked)
                st.session_state.card_frontmatter = yaml.safe_dump(card["frontmatter"], sort_keys=False, allow_unicode=True)
                st.session_state.card_body = card["body"]
                st.session_state.editing_card_path = str(picked)
                st.session_state.editing_card_id = str(card["frontmatter"].get("id", picked.stem))
                st.session_state.editing_card_type = str(card["frontmatter"].get("type", ""))
                st.session_state.card_designer_notice = ("success", f"Loaded from map: {pick_card}")
            for key in ("pick_card", "pick_ts"):
                if key in st.query_params:
                    del st.query_params[key]
            st.rerun()

        categories = sorted({p.parent.name for p in all_paths})
        category = st.selectbox("Category", options=["All"] + categories)
        keyword = st.text_input("Search", placeholder="filename or keyword")

        card_paths = list(all_paths)
        if category != "All":
            card_paths = [p for p in card_paths if p.parent.name == category]
        if keyword.strip():
            needle = keyword.strip().lower()
            card_paths = [p for p in card_paths if needle in p.name.lower()]

        render_existing_cards_mindmap(card_paths)
        st.caption("Mindmap interactions: double-click a card to load it; click an ellipsis node to expand one category; click blank area to collapse.")

        quick_options = [f"{p.parent.name}/{p.name}" for p in card_paths]
        if quick_options:
            quick_pick = st.selectbox("Quick Load from filtered cards", options=quick_options)
            if st.button("Load Selected Card"):
                path = card_paths[quick_options.index(quick_pick)]
                card = service.load_card(path)
                st.session_state.card_frontmatter = yaml.safe_dump(card["frontmatter"], sort_keys=False, allow_unicode=True)
                st.session_state.card_body = card["body"]
                st.session_state.editing_card_path = str(path)
                st.session_state.editing_card_id = str(card["frontmatter"].get("id", path.stem))
                st.session_state.editing_card_type = str(card["frontmatter"].get("type", ""))
                st.rerun()
        else:
            st.info("No cards matched current filter.")

    with chat_col:
        render_pack_builder_chat_column()

    st.markdown("---")
    st.caption("Pack Builder Agent: describe what pack you want to build.")
    prompt = st.chat_input("Describe the pack requirements, then run.", key="card_designer_agent_input")
    if prompt and prompt.strip():
        agent = get_pack_builder_agent(service)
        result = agent.process(prompt.strip(), agent_state)
        st.session_state.pack_builder_state = result["state"]
        st.rerun()
