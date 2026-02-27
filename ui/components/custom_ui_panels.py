from __future__ import annotations

import json
from typing import Any

import streamlit as st
import streamlit.components.v1 as components


def render_custom_ui_panels(state_view: dict[str, Any]) -> None:
    panels = state_view.get("custom_ui_panels", [])
    save_slot = state_view.get("save_slot", "default")

    st.sidebar.markdown("---")
    st.sidebar.subheader("Custom UI Panels")

    for panel in panels:
        key = f"panel_visible_{panel.get('panel_id')}"
        if key not in st.session_state:
            st.session_state[key] = bool(panel.get("visible_by_default", True))
        st.session_state[key] = st.sidebar.checkbox(
            panel.get("title", panel.get("panel_id", "panel")),
            value=st.session_state[key],
            key=f"checkbox_{panel.get('panel_id')}",
        )

    floating = [p for p in panels if st.session_state.get(f"panel_visible_{p.get('panel_id')}", True)]
    payload = json.dumps(floating, ensure_ascii=False)

    components.html(
        f"""
        <script>
        const panels = {payload};
        const SAVE_SLOT = {json.dumps(str(save_slot))};
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

          const storageKey = `textrpg-ui-layout-${{SAVE_SLOT}}-${{panel.panel_id}}`;
          try {{
            const cached = JSON.parse(localStorage.getItem(storageKey) || 'null');
            if (cached && typeof cached === 'object') {{
              if (cached.x != null) layout.x = cached.x;
              if (cached.y != null) layout.y = cached.y;
              if (cached.width != null) layout.width = cached.width;
              if (cached.height != null) layout.height = cached.height;
            }}
          }} catch (e) {{}}

          const panelEl = doc.createElement('div');
          panelEl.className = 'custom-ui-panel';
          panelEl.style.left = `${{Number(layout.x ?? x)}}px`;
          panelEl.style.top = `${{Number(layout.y ?? y)}}px`;
          panelEl.style.width = `${{Number(layout.width ?? w)}}px`;
          panelEl.style.height = `${{Number(layout.height ?? h)}}px`;

          const header = doc.createElement('div');
          header.className = 'custom-ui-header';
          header.textContent = String(panel.title ?? panel.panel_id ?? 'panel');

          const body = doc.createElement('div');
          body.className = 'custom-ui-body';
          body.style.whiteSpace = 'pre-line';

          if (panel.html) {{
            body.innerHTML = String(panel.html);
          }} else {{
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

          const saveLayout = () => {{
            const payload = {{
              x: panelEl.offsetLeft,
              y: panelEl.offsetTop,
              width: panelEl.offsetWidth,
              height: panelEl.offsetHeight,
            }};
            try {{ localStorage.setItem(storageKey, JSON.stringify(payload)); }} catch (e) {{}}
          }};

          header.addEventListener('pointerup', saveLayout);
          header.addEventListener('pointercancel', saveLayout);

          if (window.ResizeObserver) {{
            const ro = new ResizeObserver(() => saveLayout());
            ro.observe(panelEl);
          }}
        }}
        </script>
        """,
        height=0,
        scrolling=False,
    )


def clear_custom_ui_panels() -> None:
    components.html(
        """
        <script>
        const doc = window.parent.document;
        const root = doc.getElementById('textrpg-custom-ui-root');
        if (root) root.remove();
        </script>
        """,
        height=0,
        scrolling=False,
    )
