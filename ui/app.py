from __future__ import annotations

import tempfile
import sys
from pathlib import Path
from typing import Dict, Any

import streamlit as st
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from game.service.api import GameService


def get_service() -> GameService:
    """返回 UI 使用的 GameService 缓存实例。"""
    if 'service' not in st.session_state:
        st.session_state.service = GameService()
    return st.session_state.service


def page_play() -> None:
    """Play page: start/load game, show history, send input."""
    service = get_service()

    if 'show_top_bar' not in st.session_state:
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
            background: #ffffff;
            border-bottom: 1px solid #e6e6e6;
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
            background: #ffffff;
            border-top: 1px solid #e6e6e6;
            padding: 8px 24px 10px 24px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    packs = service.list_packs()
    pack_ids = [p['pack_id'] for p in packs]
    enabled_ids = [p['pack_id'] for p in packs if p.get('enabled')]

    if 'language' not in st.session_state:
        st.session_state.language = 'zh'
    lang_options = ['Chinese', 'English']
    default_index = 0 if st.session_state.language == 'zh' else 1

    if not st.session_state.show_top_bar:
        st.markdown("<div class='top-toggle'>", unsafe_allow_html=True)
        if st.button('Menu'):
            st.session_state.show_top_bar = True
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='top-bar'>", unsafe_allow_html=True)
        col1, col2, col3, col4, col5 = st.columns([1.2, 2.4, 1.2, 2.2, 0.6])
        with col1:
            save_slot = st.text_input('Save Slot', value='slot_001')
        with col2:
            selected_packs = st.multiselect('Enabled Packs', options=pack_ids, default=enabled_ids)
        with col3:
            language_label = st.selectbox('Language', options=lang_options, index=default_index)
            language = 'en' if language_label == 'English' else 'zh'
            st.session_state.language = language
        with col4:
            b1, b2 = st.columns(2)
            with b1:
                if st.button('Start', use_container_width=True):
                    service.start_new_game(save_slot, selected_packs, language=language)
            with b2:
                if st.button('Load', use_container_width=True):
                    service.load_game(save_slot, language=language)
        with col5:
            if st.button('Hide'):
                st.session_state.show_top_bar = False
                st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    state_view = service.get_current_state_view()

    history = state_view.get('chat_history', [])
    if history:
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            try:
                with st.chat_message('user' if role == 'user' else 'assistant'):
                    st.write(content)
            except Exception:
                st.write(f"{role}: {content}")
    else:
        st.write([])

    with st.sidebar.expander('World Facts', expanded=False):
        st.json(state_view.get('world_facts', {}))

    with st.sidebar.expander('Debug Info', expanded=False):
        st.write('Retrieved Cards')
        st.write(state_view.get('retrieved_cards', []))
        st.write('Validated Ops')
        st.json(state_view.get('validated_ops', []))
        st.write('Errors')
        st.write(state_view.get('errors', []))

    st.markdown("<div class='bottom-bar'>", unsafe_allow_html=True)
    user_input = st.chat_input('Type a command, press Enter')
    if user_input and user_input.strip():
        service.set_language(st.session_state.language)
        service.step(user_input.strip())
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


def page_pack_manager() -> None:
    """卡包管理页：安装、启用、移除、导出卡包。"""
    st.title('Pack Manager')
    service = get_service()
    packs = service.list_packs()

    st.subheader('Installed Packs')
    for p in packs:
        col1, col2, col3, col4 = st.columns(4)
        col1.write(f"{p['name']} ({p['pack_id']})")
        col2.write(f"v{p['version']} by {p['author']}")
        enabled = col3.checkbox('Enabled', value=p.get('enabled', False), key=f"enable_{p['pack_id']}")
        if enabled != p.get('enabled', False):
            service.enable_pack(p['pack_id'], enabled)
        if col4.button('Remove', key=f"remove_{p['pack_id']}"):
            service.remove_pack(p['pack_id'])
            st.rerun()

    st.subheader('Install from URL')
    url = st.text_input('Pack ZIP URL')
    if st.button('Download & Install'):
        if url.strip():
            service.install_pack_from_url(url.strip())
            st.rerun()

    st.subheader('Install from ZIP')
    uploaded = st.file_uploader('Upload pack zip', type=['zip'])
    if uploaded is not None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / 'pack.zip'
            path.write_bytes(uploaded.read())
            service.install_pack_from_zip(path)
            st.rerun()

    st.subheader('Export Pack')
    pack_to_export = st.selectbox('Pack', options=[p['pack_id'] for p in packs] or [''])
    if st.button('Export'):
        if pack_to_export:
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / f'{pack_to_export}.zip'
                service.export_pack(pack_to_export, out)
                st.download_button('Download ZIP', data=out.read_bytes(), file_name=out.name)


def page_card_designer() -> None:
    """卡牌设计页：创建/编辑/校验卡牌。"""
    st.title('Card Designer')
    service = get_service()
    packs = service.list_packs()
    pack_ids = [p['pack_id'] for p in packs]

    mode = st.radio('Mode', ['Edit existing pack', 'Create new pack'])
    if mode == 'Create new pack':
        st.subheader('New Pack Manifest')
        pack_id = st.text_input('pack_id')
        name = st.text_input('name')
        version = st.text_input('version', value='0.1.0')
        author = st.text_input('author')
        description = st.text_area('description')
        cards_root = st.text_input('cards_root', value='cards')
        if st.button('Create Pack'):
            manifest = {
                'pack_id': pack_id,
                'name': name,
                'version': version,
                'author': author,
                'description': description,
                'cards_root': cards_root,
            }
            service.create_pack(manifest)
            st.rerun()
        return

    if not pack_ids:
        st.info('No packs installed.')
        return

    pack_id = st.selectbox('Pack', options=pack_ids)

    left, right = st.columns([3, 1])
    with left:
        st.subheader('Create / Edit Card')
        card_type = st.selectbox('Type', options=['character', 'item', 'location', 'event', 'memory'])
        card_id = st.text_input('Card ID')

        if st.button('Generate Template'):
            template = service.get_card_template(card_type)
            st.session_state.card_frontmatter = yaml.safe_dump(template, sort_keys=False)

        frontmatter_text = st.text_area('YAML frontmatter', value=st.session_state.get('card_frontmatter', ''))
        body_text = st.text_area('Body (Markdown)', value=st.session_state.get('card_body', ''))

        if st.button('Save Card'):
            frontmatter = yaml.safe_load(frontmatter_text) or {}
            service.create_card(pack_id, card_type, card_id, frontmatter, body_text)
            st.success('Saved.')

        if st.button('Validate'):
            frontmatter = yaml.safe_load(frontmatter_text) or {}
            try:
                service.validate_card(frontmatter, body_text)
                st.success('Valid.')
            except Exception as exc:
                st.error(str(exc))

    with right:
        st.subheader('Existing Cards')
        card_paths = service.list_pack_cards(pack_id)
        categories = sorted({p.parent.name for p in card_paths})
        category = st.selectbox('Category', options=['All'] + categories)
        keyword = st.text_input('Search', placeholder='filename or keyword')

        if category != 'All':
            card_paths = [p for p in card_paths if p.parent.name == category]
        if keyword.strip():
            needle = keyword.strip().lower()
            card_paths = [p for p in card_paths if needle in p.name.lower()]

        with st.container(height=600, border=True):
            for path in card_paths:
                label = f'{path.parent.name}/{path.name}'
                if st.button(f'Load {label}', key=f'load_{path}'):
                    card = service.load_card(path)
                    st.session_state.card_frontmatter = yaml.safe_dump(card['frontmatter'], sort_keys=False)
                    st.session_state.card_body = card['body']
                    st.rerun()


def main() -> None:
    """Streamlit 页面路由入口。"""
    st.sidebar.title('TextRPG UI')
    page = st.sidebar.radio('Page', ['Play', 'Pack Manager', 'Card Designer'])
    if page == 'Play':
        page_play()
    elif page == 'Pack Manager':
        page_pack_manager()
    else:
        page_card_designer()


if __name__ == '__main__':
    main()
