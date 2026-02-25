from __future__ import annotations

import streamlit as st


def apply_global_theme() -> None:
    st.set_page_config(page_title="TextRPG UI", page_icon=":book:", layout="wide")
    st.markdown(
        """
        <style>
        :root {
          --bg-a: #f5f7fb;
          --bg-b: #eef4ff;
          --panel: rgba(255,255,255,.9);
          --line: #dbe3f0;
          --text: #22324a;
          --muted: #60748f;
          --brand: #2f6fed;
        }

        .stApp {
          background:
            radial-gradient(1200px 500px at 100% -20%, #d7e7ff 0%, transparent 60%),
            radial-gradient(1000px 500px at -10% 110%, #e8f7ef 0%, transparent 60%),
            linear-gradient(180deg, var(--bg-a), var(--bg-b));
        }

        .main .block-container {
          max-width: none !important;
          padding-top: 1rem;
          padding-left: 1.2rem;
          padding-right: 1.2rem;
        }

        .stSidebar {
          border-right: 1px solid var(--line);
          background: linear-gradient(180deg, #f8fbff, #f2f6ff);
        }
        [data-testid="stSidebarNav"] {
          display: none;
        }

        h1, h2, h3 {
          color: var(--text);
          letter-spacing: .2px;
        }

        div[data-testid="stVerticalBlock"] > div:has(> div[data-testid="stChatMessage"]) {
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 12px;
          padding: 8px;
        }

        .stButton > button, .stDownloadButton > button {
          border-radius: 10px;
          border: 1px solid #bfd0ef;
          background: linear-gradient(180deg, #ffffff, #f3f7ff);
        }
        .stButton > button:hover, .stDownloadButton > button:hover {
          border-color: #7ea3e8;
          color: #1a3f86;
        }

        .stTextInput input, .stTextArea textarea {
          border-radius: 10px !important;
        }

        [data-testid="stForm"] {
          border: 1px solid var(--line);
          border-radius: 12px;
          padding: 14px;
          background: var(--panel);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
