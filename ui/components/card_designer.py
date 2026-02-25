from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from game.service.api import GameService
from game.service.pack_builder_agent import PackBuilderAgent


def get_pack_builder_agent(service: GameService) -> PackBuilderAgent:
    if "pack_builder_agent" not in st.session_state:
        st.session_state.pack_builder_agent = PackBuilderAgent(service)
    return st.session_state.pack_builder_agent


def ensure_pack_builder_state() -> dict[str, Any]:
    if "pack_builder_state" not in st.session_state:
        st.session_state.pack_builder_state = {
            "history": [],
            "memory": "",
            "question_mode": True,
            "creation_started": False,
            "selected_pack_id": "",
        }
    return st.session_state.pack_builder_state


def render_pack_builder_chat_column() -> None:
    st.subheader("Pack Builder Chat")
    st.caption("Chat history is stored in this browser session.")
    state = ensure_pack_builder_state()
    history = state.get("history", [])
    with st.container(height=620, border=True):
        if not history:
            st.info("No chat yet. Enter your request at the bottom.")
            return
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            with st.chat_message("user" if role == "user" else "assistant"):
                st.write(content)


def render_existing_cards_mindmap(card_paths: list[Path]) -> None:
    data: dict[str, list[str]] = {}
    for path in card_paths:
        key = path.parent.name
        data.setdefault(key, []).append(path.name)
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
        const MAX_VISIBLE_PER_CATEGORY = 5;
        let expandedCategory = null;
        let nodeBounds = [];

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

        function emitPick(cardPath) {{
          try {{
            const url = new URL(window.parent.location.href);
            url.searchParams.set('pick_card', cardPath);
            url.searchParams.set('pick_ts', String(Date.now()));
            window.parent.location.href = url.toString();
          }} catch (_) {{}}
        }}

        function hitNode(localX, localY) {{
          for (const b of nodeBounds) {{
            if (localX >= b.x && localX <= b.x + b.w && localY >= b.y && localY <= b.y + b.h) {{
              return b;
            }}
          }}
          return null;
        }}

        function clearGraph() {{
          while (edges.firstChild) edges.removeChild(edges.firstChild);
          while (nodes.firstChild) nodes.removeChild(nodes.firstChild);
          nodeBounds = [];
        }}

        function addCardNode(cat, fileName, cx, cy, nx, ny) {{
          edges.appendChild(mkLine(cx + 80, cy, nx - 95, ny));
          const rx = nx - 90;
          const ry = ny - 13;
          const rw = 180;
          const rh = 26;
          nodes.appendChild(mkRect(rx, ry, rw, rh, '#fafafa', '#d9d9d9', 7));
          const baseName = fileName.replace(/\\.md$/i, '');
          const label = baseName.length > 24 ? baseName.slice(0, 22) + '...' : baseName;
          nodes.appendChild(mkText(nx - 80, ny + 5, label, false));
          nodeBounds.push({{
            x: rx,
            y: ry,
            w: rw,
            h: rh,
            kind: 'card',
            cardPath: `${{cat}}/${{fileName}}`,
          }});
        }}

        function addEllipsisNode(cat, hiddenCount, cx, cy, nx, ny) {{
          edges.appendChild(mkLine(cx + 80, cy, nx - 95, ny));
          const rx = nx - 90;
          const ry = ny - 13;
          const rw = 180;
          const rh = 26;
          nodes.appendChild(mkRect(rx, ry, rw, rh, '#fff8e8', '#e5c98a', 7));
          nodes.appendChild(mkText(nx - 80, ny + 5, `... +${{hiddenCount}} more`, false));
          nodeBounds.push({{
            x: rx,
            y: ry,
            w: rw,
            h: rh,
            kind: 'ellipsis',
            category: cat,
          }});
        }}

        function renderGraph() {{
          clearGraph();

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
            const shouldExpand = expandedCategory === cat;
            const visibleCount = shouldExpand ? cards.length : Math.min(cards.length, MAX_VISIBLE_PER_CATEGORY);
            const hasHidden = cards.length > visibleCount;
            const totalShownNodes = visibleCount + (hasHidden ? 1 : 0);
            const cardGap = 30;
            const startY = cy - ((Math.max(totalShownNodes, 1) - 1) * cardGap) / 2;

            for (let idx = 0; idx < visibleCount; idx += 1) {{
              const nx = 560;
              const ny = startY + idx * cardGap;
              addCardNode(cat, cards[idx], cx, cy, nx, ny);
            }}

            if (hasHidden) {{
              const nx = 560;
              const ny = startY + visibleCount * cardGap;
              addEllipsisNode(cat, cards.length - visibleCount, cx, cy, nx, ny);
            }}
          }});
        }}
        renderGraph();

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

        wrap.addEventListener('dblclick', (e) => {{
          const rect = wrap.getBoundingClientRect();
          const lx = (e.clientX - rect.left - tx) / scale;
          const ly = (e.clientY - rect.top - ty) / scale;
          const hit = hitNode(lx, ly);
          if (hit && hit.kind === 'card') {{
            emitPick(hit.cardPath);
          }}
        }});

        wrap.addEventListener('click', (e) => {{
          const rect = wrap.getBoundingClientRect();
          const lx = (e.clientX - rect.left - tx) / scale;
          const ly = (e.clientY - rect.top - ty) / scale;
          const hit = hitNode(lx, ly);
          if (hit && hit.kind === 'ellipsis') {{
            expandedCategory = hit.category;
            renderGraph();
            applyTransform();
            return;
          }}
          if (expandedCategory) {{
            expandedCategory = null;
            renderGraph();
            applyTransform();
          }}
        }});
        </script>
        """,
        height=430,
        scrolling=False,
    )


def render_existing_cards_floating(default_visible: bool = True) -> None:
    visible_flag = "true" if default_visible else "false"
    script = """
        <script>
        const doc = window.parent.document;
        const POS_KEY = 'textrpg_cards_float_pos_v1';
        const SIZE_KEY = 'textrpg_cards_float_size_v1';
        const VIS_KEY = 'textrpg_cards_float_visible_v1';
        const STYLE_ID = 'textrpg-cards-float-style';
        const FLOAT_ID = 'textrpg-existing-cards-floating';
        const SHOW_BTN_ID = 'textrpg-existing-cards-show-btn';
        const DEFAULT_VISIBLE = __DEFAULT_VISIBLE__;

        if (!doc.getElementById(STYLE_ID)) {
          const style = doc.createElement('style');
          style.id = STYLE_ID;
          style.textContent = `
            #${FLOAT_ID} {
              position: fixed !important;
              right: 24px;
              top: 160px;
              width: 520px;
              height: 620px;
              z-index: 120;
              border: 1px solid #dcdfe6;
              border-radius: 12px;
              background: rgba(255,255,255,.98);
              box-shadow: 0 10px 32px rgba(0,0,0,.14);
              resize: both;
              overflow: auto !important;
              min-width: 320px;
              min-height: 240px;
              padding: 14px;
            }
            #${FLOAT_ID} h3 { cursor: move; margin-top: 0; padding-right: 84px; }
            #${SHOW_BTN_ID} {
              position: fixed;
              right: 24px;
              bottom: 28px;
              z-index: 121;
              border: 1px solid #d0d7e2;
              border-radius: 999px;
              background: #fff;
              color: #2a4365;
              padding: 8px 12px;
              font-size: 13px;
              font-weight: 600;
              cursor: pointer;
              box-shadow: 0 4px 14px rgba(0,0,0,.12);
            }
          `;
          doc.head.appendChild(style);
        }

        const byText = (selector, text) =>
          Array.from(doc.querySelectorAll(selector)).find((el) => el.textContent.trim() === text);
        const cardsAnchor = byText('h3', 'Existing Cards');
        if (!cardsAnchor) return;
        const cardsCol = cardsAnchor.closest('[data-testid="column"]');
        if (!cardsCol) return;
        cardsCol.id = FLOAT_ID;

        const closeBtnId = 'textrpg-existing-cards-close-btn';
        let closeBtn = doc.getElementById(closeBtnId);
        if (!closeBtn) {
          closeBtn = doc.createElement('button');
          closeBtn.id = closeBtnId;
          closeBtn.textContent = 'Hide';
          closeBtn.style.position = 'absolute';
          closeBtn.style.top = '10px';
          closeBtn.style.right = '10px';
          closeBtn.style.zIndex = '123';
          closeBtn.style.border = '1px solid #d0d7e2';
          closeBtn.style.borderRadius = '8px';
          closeBtn.style.padding = '4px 10px';
          closeBtn.style.background = '#fff';
          closeBtn.style.cursor = 'pointer';
          cardsCol.appendChild(closeBtn);
        }

        let showBtn = doc.getElementById(SHOW_BTN_ID);
        if (!showBtn) {
          showBtn = doc.createElement('button');
          showBtn.id = SHOW_BTN_ID;
          showBtn.textContent = 'Show Existing Cards';
          doc.body.appendChild(showBtn);
        }

        const applyVisibility = (v) => {
          cardsCol.style.display = v ? 'block' : 'none';
          showBtn.style.display = v ? 'none' : 'block';
          localStorage.setItem(VIS_KEY, JSON.stringify(!!v));
        };

        let visible = DEFAULT_VISIBLE;
        try {
          const raw = localStorage.getItem(VIS_KEY);
          if (raw !== null) visible = !!JSON.parse(raw);
        } catch (_) {}
        applyVisibility(visible);
        closeBtn.onclick = () => applyVisibility(false);
        showBtn.onclick = () => applyVisibility(true);

        const savePosSize = () => {
          const left = cardsCol.offsetLeft;
          const top = cardsCol.offsetTop;
          const width = cardsCol.offsetWidth;
          const height = cardsCol.offsetHeight;
          localStorage.setItem(POS_KEY, JSON.stringify({ left, top }));
          localStorage.setItem(SIZE_KEY, JSON.stringify({ width, height }));
        };

        const restorePosSize = () => {
          try {
            const pos = JSON.parse(localStorage.getItem(POS_KEY) || '{}');
            if (Number.isFinite(pos.left)) cardsCol.style.left = `${pos.left}px`;
            if (Number.isFinite(pos.top)) cardsCol.style.top = `${pos.top}px`;
            if (Number.isFinite(pos.left) || Number.isFinite(pos.top)) cardsCol.style.right = 'auto';
          } catch (_) {}
          try {
            const size = JSON.parse(localStorage.getItem(SIZE_KEY) || '{}');
            if (Number.isFinite(size.width)) cardsCol.style.width = `${size.width}px`;
            if (Number.isFinite(size.height)) cardsCol.style.height = `${size.height}px`;
          } catch (_) {}
        };
        restorePosSize();

        let dragging = false;
        let offX = 0;
        let offY = 0;
        cardsAnchor.onpointerdown = (e) => {
          e.preventDefault();
          dragging = true;
          offX = e.clientX - cardsCol.offsetLeft;
          offY = e.clientY - cardsCol.offsetTop;
          doc.addEventListener('pointermove', onDrag);
          doc.addEventListener('pointerup', stopDrag);
          doc.addEventListener('pointercancel', stopDrag);
        };

        const onDrag = (e) => {
          if (!dragging) return;
          const maxX = Math.max(0, window.parent.innerWidth - cardsCol.offsetWidth);
          const maxY = Math.max(0, window.parent.innerHeight - cardsCol.offsetHeight);
          const nextX = Math.max(0, Math.min(maxX, e.clientX - offX));
          const nextY = Math.max(0, Math.min(maxY, e.clientY - offY));
          cardsCol.style.left = `${nextX}px`;
          cardsCol.style.top = `${nextY}px`;
          cardsCol.style.right = 'auto';
        };

        const stopDrag = () => {
          if (!dragging) return;
          dragging = false;
          savePosSize();
          doc.removeEventListener('pointermove', onDrag);
          doc.removeEventListener('pointerup', stopDrag);
          doc.removeEventListener('pointercancel', stopDrag);
        };

        let resizeTimer = null;
        const resizeObserver = new ResizeObserver(() => {
          if (resizeTimer) window.clearTimeout(resizeTimer);
          resizeTimer = window.setTimeout(savePosSize, 120);
        });
        resizeObserver.observe(cardsCol);
        </script>
    """
    components.html(script.replace("__DEFAULT_VISIBLE__", visible_flag), height=0, scrolling=False)
