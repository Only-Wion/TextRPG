from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from ui.core.services import get_service


def render_pack_manager_page() -> None:
    st.title("Pack Manager")
    service = get_service()
    packs = service.list_packs()

    st.subheader("Installed Packs")
    for p in packs:
        col1, col2, col3, col4 = st.columns(4)
        col1.write(f"{p['name']} ({p['pack_id']})")
        col2.write(f"v{p['version']} by {p['author']}")
        enabled = col3.checkbox("Enabled", value=p.get("enabled", False), key=f"enable_{p['pack_id']}")
        if enabled != p.get("enabled", False):
            service.enable_pack(p["pack_id"], enabled)
        if col4.button("Remove", key=f"remove_{p['pack_id']}"):
            service.remove_pack(p["pack_id"])
            st.rerun()

    st.subheader("Install from URL")
    url = st.text_input("Pack ZIP URL")
    if st.button("Download & Install"):
        if url.strip():
            service.install_pack_from_url(url.strip())
            st.rerun()

    st.subheader("Install from ZIP")
    uploaded = st.file_uploader("Upload pack zip", type=["zip"])
    if uploaded is not None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pack.zip"
            path.write_bytes(uploaded.read())
            service.install_pack_from_zip(path)
            st.rerun()

    st.subheader("Export Pack")
    pack_to_export = st.selectbox("Pack", options=[p["pack_id"] for p in packs] or [""])
    if st.button("Export"):
        if pack_to_export:
            with tempfile.TemporaryDirectory() as td:
                out = Path(td) / f"{pack_to_export}.zip"
                service.export_pack(pack_to_export, out)
                st.download_button("Download ZIP", data=out.read_bytes(), file_name=out.name)

