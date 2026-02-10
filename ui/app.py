from __future__ import annotations

import tempfile
import sys
from pathlib import Path
from typing import Dict, Any
import json

import streamlit as st
import streamlit.components.v1 as components
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




def _render_custom_ui_panels(state_view: Dict[str, Any]) -> None:
    """渲染自定义 UI 面板（浮窗，支持拖拽与缩放）。"""
    panels = state_view.get('custom_ui_panels', [])

    st.sidebar.markdown('---')
    st.sidebar.subheader('Custom UI Panels')

    for panel in panels:
        key = f"panel_visible_{panel.get('panel_id')}"
        if key not in st.session_state:
            st.session_state[key] = bool(panel.get('visible_by_default', True))
        st.session_state[key] = st.sidebar.checkbox(
            panel.get('title', panel.get('panel_id', 'panel')),
            value=st.session_state[key],
            key=f"checkbox_{panel.get('panel_id')}"
        )

    floating = [p for p in panels if st.session_state.get(f"panel_visible_{p.get('panel_id')}", True)]
    payload = json.dumps(floating, ensure_ascii=False)

    components.html(
        f"""
        <script>
        const panels = {payload};
        const doc = window.parent.document;
        const ROOT_ID = 'textrpg-custom-ui-root';
        const STYLE_ID = 'textrpg-custom-ui-style';

        const oldRoot = doc.getElementById(ROOT_ID);
        if (oldRoot) oldRoot.remove();

        let style = doc.getElementById(STYLE_ID);
        if (!style) {{
          style = doc.createElement('style');
          style.id = STYLE_ID;
          style.textContent = `
            #${{ROOT_ID}} {{ position: fixed; inset: 0; pointer-events: none; z-index: 996; }}
            #${{ROOT_ID}} .custom-ui-panel {{
              position: fixed; border: 1px solid #ddd; border-radius: 10px;
              background: rgba(255,255,255,0.95); box-shadow: 0 8px 24px rgba(0,0,0,.12);
              overflow: auto; resize: both; pointer-events: auto;
            }}
            #${{ROOT_ID}} .custom-ui-header {{
              padding: 8px 10px; font-weight: 700; background: #f7f7f9;
              cursor: move; border-bottom: 1px solid #e8e8ef; user-select: none;
            }}
            #${{ROOT_ID}} .custom-ui-body {{ padding: 8px 10px; font-size: 13px; }}
            #${{ROOT_ID}} .custom-ui-section {{ margin-bottom: 10px; }}
            #${{ROOT_ID}} .custom-ui-section h5 {{ margin: 2px 0 6px 0; font-size: 13px; }}
            #${{ROOT_ID}} .custom-ui-item {{ padding: 2px 0; border-bottom: 1px dashed #f0f0f0; }}
            #${{ROOT_ID}} .custom-ui-empty {{ color: #888; font-style: italic; }}
          `;
          doc.head.appendChild(style);
        }}

        const root = doc.createElement('div');
        root.id = ROOT_ID;
        doc.body.appendChild(root);

        const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

        for (const panel of panels) {{
          const layout = panel.layout || {{}};
          const x = Number(layout.x ?? 20);
          const y = Number(layout.y ?? 120);
          const w = Number(layout.width ?? 360);
          const h = Number(layout.height ?? 280);

          const panelEl = doc.createElement('div');
          panelEl.className = 'custom-ui-panel';
          panelEl.style.left = `${{x}}px`;
          panelEl.style.top = `${{y}}px`;
          panelEl.style.width = `${{w}}px`;
          panelEl.style.height = `${{h}}px`;

          const header = doc.createElement('div');
          header.className = 'custom-ui-header';
          header.textContent = String(panel.title ?? panel.panel_id ?? 'panel');

          const body = doc.createElement('div');
          body.className = 'custom-ui-body';

          for (const section of (panel.sections || [])) {{
            const sectionWrap = doc.createElement('div');
            sectionWrap.className = 'custom-ui-section';

            const h5 = doc.createElement('h5');
            h5.textContent = String(section.title ?? 'Section');
            sectionWrap.appendChild(h5);

            const entries = section.entries || [];
            if (!entries.length) {{
              const empty = doc.createElement('div');
              empty.className = 'custom-ui-empty';
              empty.textContent = String(section.empty_text ?? 'No data');
              sectionWrap.appendChild(empty);
            }} else {{
              for (const entry of entries) {{
                const item = doc.createElement('div');
                item.className = 'custom-ui-item';
                if (entry && typeof entry === 'object' && ('key' in entry)) {{
                  const keyStrong = doc.createElement('b');
                  keyStrong.textContent = String(entry.key);
                  item.appendChild(keyStrong);
                  item.appendChild(doc.createTextNode(': ' + String(entry.value)));
                }} else {{
                  item.textContent = String(entry);
                }}
                sectionWrap.appendChild(item);
              }}
            }}
            body.appendChild(sectionWrap);
          }}

          panelEl.appendChild(header);
          panelEl.appendChild(body);
          root.appendChild(panelEl);

          let dragging = false;
          let offsetX = 0;
          let offsetY = 0;

          header.addEventListener('pointerdown', (e) => {{
            dragging = true;
            header.setPointerCapture(e.pointerId);
            offsetX = e.clientX - panelEl.offsetLeft;
            offsetY = e.clientY - panelEl.offsetTop;
          }});

          header.addEventListener('pointermove', (e) => {{
            if (!dragging) return;
            const maxX = Math.max(0, window.parent.innerWidth - panelEl.offsetWidth);
            const maxY = Math.max(0, window.parent.innerHeight - panelEl.offsetHeight);
            panelEl.style.left = `${{clamp(e.clientX - offsetX, 0, maxX)}}px`;
            panelEl.style.top = `${{clamp(e.clientY - offsetY, 0, maxY)}}px`;
          }});

          const stopDragging = () => {{ dragging = false; }};
          header.addEventListener('pointerup', stopDragging);
          header.addEventListener('pointercancel', stopDragging);
        }}
        </script>
        """,
        height=0,
        scrolling=False,
    )

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
    _render_custom_ui_panels(state_view)

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
        card_type = st.selectbox('Type', options=['character', 'item', 'location', 'event', 'memory', 'ui'])
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
