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
from game.service.pack_builder_agent import PackBuilderAgent


LLM_PROVIDER_PRESETS = {
    'deepseek': {
        'label': 'DeepSeek',
        'base_url': 'https://api.deepseek.com/v1',
        'model_name': 'deepseek-chat',
        'embedding_model': 'text-embedding-3-small',
        'force_fake_embeddings': True,
    },
    'alibaba': {
        'label': '阿里通义',
        'base_url': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        'model_name': 'qwen-plus',
        'embedding_model': 'text-embedding-v4',
        'force_fake_embeddings': False,
    },
    'bytedance': {
        'label': '字节豆包',
        'base_url': 'https://ark.cn-beijing.volces.com/api/v3',
        'model_name': 'doubao-pro-32k-241215',
        'embedding_model': 'doubao-embedding-text-240715',
        'force_fake_embeddings': False,
    },
    'custom': {
        'label': '自定义 OpenAI Compatible',
        'base_url': '',
        'model_name': 'gpt-4o-mini',
        'embedding_model': 'text-embedding-3-small',
        'force_fake_embeddings': False,
    },
}


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




def _render_card_designer_splitter() -> None:
    """给 Card Designer 三栏注入可拖拽分割线（前端增强）。"""
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const KEY = 'textrpg_card_designer_three_col_ratios';
        const DIVIDER_A_ID = 'textrpg-card-designer-divider-a';
        const DIVIDER_B_ID = 'textrpg-card-designer-divider-b';

        const byText = (selector, text) => Array.from(doc.querySelectorAll(selector)).find((el) => el.textContent.trim() === text);
        const leftAnchor = byText('h3', 'Create / Edit Card');
        const middleAnchor = byText('h3', 'Existing Cards');
        const rightAnchor = byText('h3', 'Pack Builder Chat');
        if (!leftAnchor || !middleAnchor || !rightAnchor) return;

        const leftCol = leftAnchor.closest('[data-testid="column"]');
        const middleCol = middleAnchor.closest('[data-testid="column"]');
        const rightCol = rightAnchor.closest('[data-testid="column"]');
        if (!leftCol || !middleCol || !rightCol) return;
        if (leftCol.parentElement !== middleCol.parentElement || middleCol.parentElement !== rightCol.parentElement) return;

        const row = leftCol.parentElement;
        row.style.position = 'relative';
        row.style.display = 'flex';
        row.style.flexWrap = 'nowrap';
        row.style.alignItems = 'stretch';
        row.style.gap = '12px';

        const clamp = (v, min, max) => Math.max(min, Math.min(max, v));

        let ratios = [0.42, 0.30, 0.28];
        try {
          const saved = JSON.parse(localStorage.getItem(KEY) || '[]');
          if (Array.isArray(saved) && saved.length === 3) {
            const total = Number(saved[0]) + Number(saved[1]) + Number(saved[2]);
            if (total > 0.99 && total < 1.01) {
              ratios = [Number(saved[0]), Number(saved[1]), Number(saved[2])];
            }
          }
        } catch (_) {}

        let dividerA = doc.getElementById(DIVIDER_A_ID);
        if (!dividerA) {
          dividerA = doc.createElement('div');
          dividerA.id = DIVIDER_A_ID;
          dividerA.style.position = 'absolute';
          dividerA.style.top = '0';
          dividerA.style.bottom = '0';
          dividerA.style.width = '12px';
          dividerA.style.cursor = 'col-resize';
          dividerA.style.background = 'linear-gradient(180deg, #ff8f8f, #e84b4b)';
          dividerA.style.borderRadius = '10px';
          dividerA.style.zIndex = '80';
          row.appendChild(dividerA);
        }

        let dividerB = doc.getElementById(DIVIDER_B_ID);
        if (!dividerB) {
          dividerB = doc.createElement('div');
          dividerB.id = DIVIDER_B_ID;
          dividerB.style.position = 'absolute';
          dividerB.style.top = '0';
          dividerB.style.bottom = '0';
          dividerB.style.width = '12px';
          dividerB.style.cursor = 'col-resize';
          dividerB.style.background = 'linear-gradient(180deg, #80b8ff, #3d7fe0)';
          dividerB.style.borderRadius = '10px';
          dividerB.style.zIndex = '80';
          row.appendChild(dividerB);
        }

        const apply = () => {
          const total = ratios[0] + ratios[1] + ratios[2];
          ratios = ratios.map((x) => x / total);

          leftCol.style.flex = `0 0 calc(${ratios[0] * 100}% - 8px)`;
          middleCol.style.flex = `0 0 calc(${ratios[1] * 100}% - 8px)`;
          rightCol.style.flex = `0 0 calc(${ratios[2] * 100}% - 8px)`;

          leftCol.style.minWidth = '360px';
          middleCol.style.minWidth = '320px';
          rightCol.style.minWidth = '300px';

          dividerA.style.left = `calc(${ratios[0] * 100}% - 6px)`;
          dividerB.style.left = `calc(${(ratios[0] + ratios[1]) * 100}% - 6px)`;
          localStorage.setItem(KEY, JSON.stringify(ratios));
        };

        apply();

        let dragA = false;
        let dragB = false;

        dividerA.onpointerdown = (e) => { dragA = true; dividerA.setPointerCapture(e.pointerId); e.preventDefault(); };
        dividerB.onpointerdown = (e) => { dragB = true; dividerB.setPointerCapture(e.pointerId); e.preventDefault(); };

        const onMove = (e) => {
          const rect = row.getBoundingClientRect();
          if (!rect.width) return;
          const x = (e.clientX - rect.left) / rect.width;

          if (dragA) {
            const r0 = clamp(x, 0.24, 0.68);
            const r12 = 1 - r0;
            const old12 = ratios[1] + ratios[2];
            const keep = old12 > 0 ? ratios[1] / old12 : 0.5;
            ratios[0] = r0;
            ratios[1] = r12 * keep;
            ratios[2] = r12 * (1 - keep);
            apply();
          }

          if (dragB) {
            const r01 = ratios[0];
            const r2 = clamp(1 - x, 0.18, 0.55);
            const remain = 1 - r2;
            const r0 = clamp(ratios[0], 0.24, remain - 0.18);
            ratios[0] = r0;
            ratios[1] = remain - r0;
            ratios[2] = r2;
            if (ratios[1] < 0.18) {
              ratios[1] = 0.18;
              ratios[0] = remain - 0.18;
            }
            apply();
          }
        };

        const stop = () => { dragA = false; dragB = false; };
        dividerA.onpointermove = onMove;
        dividerB.onpointermove = onMove;
        dividerA.onpointerup = stop;
        dividerB.onpointerup = stop;
        dividerA.onpointercancel = stop;
        dividerB.onpointercancel = stop;
        </script>
        """,
        height=0,
        scrolling=False,
    )


def _render_existing_cards_mindmap(card_paths: list[Path]) -> None:
    """以思维导图风格可视化 Existing Cards，支持滚轮按鼠标点缩放。"""
    data: dict[str, list[str]] = {}
    for path in card_paths:
        key = path.parent.name
        data.setdefault(key, []).append(path.stem)
    for k in data:
        data[k].sort()

    payload = json.dumps(data, ensure_ascii=False)
    components.html(
        f"""
        <div id="mindmap-wrap" style="width:100%;height:420px;border:1px solid #ddd;border-radius:10px;overflow:hidden;background:#fff;">
          <svg id="mindmap-svg" width="100%" height="100%" style="display:block;touch-action:none;"></svg>
        </div>
        <script>
        const data = {payload};
        const svg = document.getElementById('mindmap-svg');
        const wrap = document.getElementById('mindmap-wrap');
        const NS = 'http://www.w3.org/2000/svg';

        const width = wrap.clientWidth || 680;
        const height = wrap.clientHeight || 420;

        const root = document.createElementNS(NS, 'g');
        svg.appendChild(root);

        const edges = document.createElementNS(NS, 'g');
        const nodes = document.createElementNS(NS, 'g');
        root.appendChild(edges);
        root.appendChild(nodes);

        const categories = Object.keys(data).sort();
        const rootNode = {{ x: 120, y: height / 2, label: 'Cards' }};

        function mkText(x, y, t, bold=false) {{
          const txt = document.createElementNS(NS, 'text');
          txt.setAttribute('x', x); txt.setAttribute('y', y);
          txt.setAttribute('font-size', bold ? '15' : '13');
          txt.setAttribute('font-weight', bold ? '700' : '500');
          txt.setAttribute('fill', '#222');
          txt.textContent = t;
          return txt;
        }}

        function mkRect(x,y,w,h,fill='#f7f7fb',stroke='#ddd',r=8) {{
          const rect = document.createElementNS(NS, 'rect');
          rect.setAttribute('x',x); rect.setAttribute('y',y);
          rect.setAttribute('width',w); rect.setAttribute('height',h);
          rect.setAttribute('rx',r); rect.setAttribute('fill',fill);
          rect.setAttribute('stroke',stroke);
          return rect;
        }}

        function mkLine(x1,y1,x2,y2) {{
          const line = document.createElementNS(NS, 'line');
          line.setAttribute('x1',x1); line.setAttribute('y1',y1);
          line.setAttribute('x2',x2); line.setAttribute('y2',y2);
          line.setAttribute('stroke','#c9ced6'); line.setAttribute('stroke-width','1.5');
          return line;
        }}

        nodes.appendChild(mkRect(rootNode.x-50, rootNode.y-18, 100, 36, '#e8f0ff', '#9bb7ff', 10));
        nodes.appendChild(mkText(rootNode.x-22, rootNode.y+5, rootNode.label, true));

        const catGap = Math.max(90, height / Math.max(1, categories.length));
        categories.forEach((cat, i) => {{
          const cy = (i + 0.5) * catGap;
          const cx = 320;
          edges.appendChild(mkLine(rootNode.x + 50, rootNode.y, cx - 90, cy));
          nodes.appendChild(mkRect(cx - 80, cy - 16, 160, 32, '#f3f8f3', '#b8d6b8', 9));
          nodes.appendChild(mkText(cx - 60, cy + 5, cat, true));

          const cards = data[cat] || [];
          const cardGap = 30;
          const startY = cy - ((cards.length - 1) * cardGap) / 2;
          cards.forEach((name, idx) => {{
            const nx = 560;
            const ny = startY + idx * cardGap;
            edges.appendChild(mkLine(cx + 80, cy, nx - 95, ny));
            nodes.appendChild(mkRect(nx - 90, ny - 13, 180, 26, '#fafafa', '#d9d9d9', 7));
            const label = name.length > 24 ? name.slice(0, 22) + '…' : name;
            nodes.appendChild(mkText(nx - 80, ny + 5, label, false));
          }});
        }});

        let scale = 1;
        let tx = 0;
        let ty = 0;
        function applyTransform() {{
          root.setAttribute('transform', `translate(${{tx}},${{ty}}) scale(${{scale}})`);
        }}
        applyTransform();

        wrap.addEventListener('wheel', (e) => {{
          e.preventDefault();
          const rect = wrap.getBoundingClientRect();
          const mx = e.clientX - rect.left;
          const my = e.clientY - rect.top;

          const oldScale = scale;
          const factor = e.deltaY < 0 ? 1.1 : 0.9;
          scale = Math.max(0.4, Math.min(2.8, scale * factor));

          tx = mx - (mx - tx) * (scale / oldScale);
          ty = my - (my - ty) * (scale / oldScale);
          applyTransform();
        }}, {{ passive: false }});

        let dragging = false;
        let sx = 0;
        let sy = 0;
        wrap.addEventListener('pointerdown', (e) => {{ dragging = true; sx = e.clientX - tx; sy = e.clientY - ty; }});
        wrap.addEventListener('pointermove', (e) => {{ if (!dragging) return; tx = e.clientX - sx; ty = e.clientY - sy; applyTransform(); }});
        wrap.addEventListener('pointerup', () => dragging = false);
        wrap.addEventListener('pointerleave', () => dragging = false);
        </script>
        """,
        height=430,
        scrolling=False,
    )


def _get_pack_builder_agent(service: GameService) -> PackBuilderAgent:
    """返回卡牌包构建 agent 的缓存实例。"""
    if 'pack_builder_agent' not in st.session_state:
        st.session_state.pack_builder_agent = PackBuilderAgent(service)
    return st.session_state.pack_builder_agent


def _ensure_pack_builder_state() -> dict[str, Any]:
    """初始化 card designer 的 agent 对话状态。"""
    if 'pack_builder_state' not in st.session_state:
        st.session_state.pack_builder_state = {
            'history': [],
            'memory': '',
            'question_mode': True,
            'creation_started': False,
            'selected_pack_id': '',
        }
    return st.session_state.pack_builder_state


def _render_pack_builder_chat_column() -> None:
    """在右侧渲染卡牌包构建 agent 聊天记录（独立滚动区域）。"""
    st.subheader('Pack Builder Chat')
    st.caption('聊天记录会保留在当前浏览器会话，并用于后续创建记忆。')
    state = _ensure_pack_builder_state()
    history = state.get('history', [])
    with st.container(height=620, border=True):
        if not history:
            st.info('暂无对话，先在底部输入你的卡牌包需求。')
            return
        for msg in history:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            with st.chat_message('user' if role == 'user' else 'assistant'):
                st.write(content)


def page_card_designer() -> None:
    """卡牌设计页：创建/编辑/校验卡牌 + Agent 辅助创建卡包。"""
    st.title('Card Designer')
    st.markdown(
        """
        <style>
        .main .block-container {
            max-width: 1880px;
            padding-left: 1.2rem;
            padding-right: 1.2rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
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
            state = _ensure_pack_builder_state()
            state['selected_pack_id'] = pack_id
            st.rerun()
        return

    if not pack_ids:
        st.info('No packs installed.')
        return

    pack_id = st.selectbox('Pack', options=pack_ids)

    if 'editing_card_path' not in st.session_state:
        st.session_state.editing_card_path = ''
    if 'editing_card_id' not in st.session_state:
        st.session_state.editing_card_id = ''
    if 'editing_card_type' not in st.session_state:
        st.session_state.editing_card_type = ''
    if 'card_designer_notice' not in st.session_state:
        st.session_state.card_designer_notice = None

    agent_state = _ensure_pack_builder_state()
    if not agent_state.get('selected_pack_id'):
        agent_state['selected_pack_id'] = pack_id

    edit_col, cards_col, chat_col = st.columns([4.0, 2.9, 3.1])
    with edit_col:
        st.subheader('Create / Edit Card')
        type_options = service.list_pack_card_types(pack_id) or ['card']
        default_type = st.session_state.get('editing_card_type')
        default_type_index = type_options.index(default_type) if default_type in type_options else 0
        selected_type = st.selectbox('Type (select existing/default)', options=type_options, index=default_type_index)
        custom_type = st.text_input('Or input custom Type', placeholder='e.g. quest, faction, skill_tree')
        card_type = custom_type.strip() or selected_type

        card_id = st.text_input('Card ID', value=st.session_state.get('editing_card_id', ''))

        if st.button('Generate Template'):
            template = service.get_card_template(card_type)
            st.session_state.card_frontmatter = yaml.safe_dump(template, sort_keys=False, allow_unicode=True)

        frontmatter_text = st.text_area('YAML frontmatter', value=st.session_state.get('card_frontmatter', ''))
        body_text = st.text_area('Body (Markdown)', value=st.session_state.get('card_body', ''))

        b_new, b_save, b_delete, b_validate = st.columns(4)

        with b_new:
            if st.button('New Card', use_container_width=True):
                st.session_state.editing_card_path = ''
                st.session_state.editing_card_id = ''
                st.session_state.editing_card_type = ''
                st.session_state.card_frontmatter = ''
                st.session_state.card_body = ''
                st.session_state.card_designer_notice = ('info', 'Switched to new card mode.')
                st.rerun()

        with b_save:
            if st.button('Save Card', use_container_width=True):
                frontmatter = yaml.safe_load(frontmatter_text) or {}
                original_path = Path(st.session_state.editing_card_path) if st.session_state.get('editing_card_path') else None
                saved_path = service.save_card(pack_id, card_type, card_id, frontmatter, body_text, original_path=original_path)
                st.session_state.editing_card_path = str(saved_path)
                st.session_state.editing_card_id = card_id
                st.session_state.editing_card_type = card_type
                st.session_state.card_designer_notice = ('success', 'Saved.')
                st.rerun()

        with b_delete:
            if st.button('Delete Card', use_container_width=True):
                original_path = st.session_state.get('editing_card_path')
                if not original_path:
                    st.session_state.card_designer_notice = ('warning', 'Please load/select a card before deleting.')
                else:
                    service.delete_card(pack_id, Path(original_path))
                    st.session_state.editing_card_path = ''
                    st.session_state.editing_card_id = ''
                    st.session_state.editing_card_type = ''
                    st.session_state.card_frontmatter = ''
                    st.session_state.card_body = ''
                    st.session_state.card_designer_notice = ('success', 'Deleted.')
                st.rerun()

        with b_validate:
            if st.button('Validate', use_container_width=True):
                frontmatter = yaml.safe_load(frontmatter_text) or {}
                try:
                    service.validate_card(frontmatter, body_text)
                    st.session_state.card_designer_notice = ('success', 'Valid.')
                except Exception as exc:
                    st.session_state.card_designer_notice = ('error', str(exc))
                st.rerun()

        notice = st.session_state.get('card_designer_notice')
        if notice:
            level, message = notice
            if level == 'success':
                st.success(message)
            elif level == 'warning':
                st.warning(message)
            elif level == 'error':
                st.error(message)
            else:
                st.info(message)

    with cards_col:
        st.subheader('Existing Cards')
        all_paths = service.list_pack_cards(pack_id)
        categories = sorted({p.parent.name for p in all_paths})
        category = st.selectbox('Category', options=['All'] + categories)
        keyword = st.text_input('Search', placeholder='filename or keyword')

        card_paths = list(all_paths)
        if category != 'All':
            card_paths = [p for p in card_paths if p.parent.name == category]
        if keyword.strip():
            needle = keyword.strip().lower()
            card_paths = [p for p in card_paths if needle in p.name.lower()]

        _render_existing_cards_mindmap(card_paths)

        quick_options = [f"{p.parent.name}/{p.name}" for p in card_paths]
        if quick_options:
            quick_pick = st.selectbox('Quick Load from filtered cards', options=quick_options)
            if st.button('Load Selected Card'):
                path = card_paths[quick_options.index(quick_pick)]
                card = service.load_card(path)
                st.session_state.card_frontmatter = yaml.safe_dump(card['frontmatter'], sort_keys=False, allow_unicode=True)
                st.session_state.card_body = card['body']
                st.session_state.editing_card_path = str(path)
                st.session_state.editing_card_id = str(card['frontmatter'].get('id', path.stem))
                st.session_state.editing_card_type = str(card['frontmatter'].get('type', ''))
                st.rerun()
        else:
            st.info('No cards matched current filter.')

    with chat_col:
        _render_pack_builder_chat_column()

    _render_card_designer_splitter()

    st.markdown('---')
    st.caption('Pack Builder Agent：在底部输入需求，可自动调用工具创建/修改卡牌包。')
    prompt = st.chat_input('描述你要创建的卡牌包（支持询问模式，回复“开始创建”进入执行）', key='card_designer_agent_input')
    if prompt and prompt.strip():
        agent = _get_pack_builder_agent(service)
        result = agent.process(prompt.strip(), agent_state)
        st.session_state.pack_builder_state = result['state']
        st.rerun()



def page_settings() -> None:
    """设置页：配置多平台 LLM 接入参数。"""
    st.title('Settings')
    st.caption('配置后会立即用于后续对话、叙事与卡包构建任务。')

    service = get_service()
    current = service.get_llm_settings()

    provider_keys = list(LLM_PROVIDER_PRESETS.keys())
    if current.get('provider') not in provider_keys:
        provider_keys.append(str(current.get('provider')))
        LLM_PROVIDER_PRESETS[str(current.get('provider'))] = {
            'label': f"Custom ({current.get('provider')})",
            'base_url': current.get('base_url', ''),
            'model_name': current.get('model_name', ''),
            'embedding_model': current.get('embedding_model', ''),
            'force_fake_embeddings': current.get('force_fake_embeddings', False),
        }

    provider_index = provider_keys.index(current.get('provider', 'custom')) if current.get('provider', 'custom') in provider_keys else provider_keys.index('custom')
    provider = st.selectbox(
        'LLM Platform',
        options=provider_keys,
        index=provider_index,
        format_func=lambda key: LLM_PROVIDER_PRESETS.get(key, {}).get('label', key),
    )

    preset = LLM_PROVIDER_PRESETS.get(provider, LLM_PROVIDER_PRESETS['custom'])

    with st.form('llm_settings_form'):
        api_key = st.text_input('API Key', value='', type='password', placeholder='请输入对应平台的 API Key')
        keep_existing_key = st.checkbox('保留当前密钥（不覆盖）', value=True)
        base_url = st.text_input('Base URL', value=current.get('base_url') or preset.get('base_url', ''))
        model_name = st.text_input('Chat Model', value=current.get('model_name') or preset.get('model_name', ''))
        embedding_model = st.text_input('Embedding Model', value=current.get('embedding_model') or preset.get('embedding_model', ''))
        use_mock_llm = st.checkbox('启用 Mock LLM（离线测试）', value=bool(current.get('use_mock_llm', False)))
        force_fake_embeddings = st.checkbox(
            '强制 Fake Embeddings',
            value=bool(current.get('force_fake_embeddings', preset.get('force_fake_embeddings', False))),
        )
        submitted = st.form_submit_button('保存设置')

    if submitted:
        payload = {
            'provider': provider,
            'base_url': base_url.strip(),
            'model_name': model_name.strip(),
            'embedding_model': embedding_model.strip(),
            'use_mock_llm': use_mock_llm,
            'force_fake_embeddings': force_fake_embeddings,
        }
        if api_key.strip():
            payload['api_key'] = api_key.strip()
        elif keep_existing_key and current.get('api_key_set'):
            payload['api_key'] = load_api_key_for_update()
        else:
            payload['api_key'] = ''

        saved = service.update_llm_settings(payload)
        st.success(f"已保存：{LLM_PROVIDER_PRESETS.get(saved.get('provider', ''), {}).get('label', saved.get('provider'))}")

    st.markdown('---')
    st.subheader('当前配置状态')
    st.json(current)


def load_api_key_for_update() -> str:
    """读取磁盘中已保存 API Key，用于“保留当前密钥”场景。"""
    settings_path = PROJECT_ROOT / 'data' / 'llm_settings.json'
    if not settings_path.exists():
        return ''
    try:
        payload = json.loads(settings_path.read_text(encoding='utf-8'))
        if isinstance(payload, dict):
            return str(payload.get('api_key', ''))
    except Exception:
        return ''
    return ''


def main() -> None:
    """Streamlit 页面路由入口。"""
    st.sidebar.title('TextRPG UI')
    page = st.sidebar.radio('Page', ['Play', 'Pack Manager', 'Card Designer', 'Settings'])
    if page == 'Play':
        page_play()
    elif page == 'Pack Manager':
        page_pack_manager()
    elif page == 'Card Designer':
        page_card_designer()
    else:
        page_settings()


if __name__ == '__main__':
    main()
