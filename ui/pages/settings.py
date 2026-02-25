from __future__ import annotations

import streamlit as st

from ui.core.constants import LLM_PROVIDER_PRESETS
from ui.core.services import get_service, load_api_key_for_update


def render_settings_page() -> None:
    st.title("Settings")
    st.caption("Settings apply to subsequent chat and pack-builder tasks.")

    service = get_service()
    current = service.get_llm_settings()

    provider_keys = list(LLM_PROVIDER_PRESETS.keys())
    if current.get("provider") not in provider_keys:
        provider_keys.append(str(current.get("provider")))
        LLM_PROVIDER_PRESETS[str(current.get("provider"))] = {
            "label": f"Custom ({current.get('provider')})",
            "base_url": current.get("base_url", ""),
            "model_name": current.get("model_name", ""),
            "embedding_model": current.get("embedding_model", ""),
            "force_fake_embeddings": current.get("force_fake_embeddings", False),
        }

    provider_index = provider_keys.index(current.get("provider", "custom")) if current.get("provider", "custom") in provider_keys else provider_keys.index("custom")
    provider = st.selectbox(
        "LLM Platform",
        options=provider_keys,
        index=provider_index,
        format_func=lambda key: LLM_PROVIDER_PRESETS.get(key, {}).get("label", key),
    )

    preset = LLM_PROVIDER_PRESETS.get(provider, LLM_PROVIDER_PRESETS["custom"])

    with st.form("llm_settings_form"):
        api_key = st.text_input("API Key", value="", type="password", placeholder="API Key")
        keep_existing_key = st.checkbox("Keep existing key", value=True)
        base_url = st.text_input("Base URL", value=current.get("base_url") or preset.get("base_url", ""))
        model_name = st.text_input("Chat Model", value=current.get("model_name") or preset.get("model_name", ""))
        embedding_model = st.text_input("Embedding Model", value=current.get("embedding_model") or preset.get("embedding_model", ""))
        use_mock_llm = st.checkbox("Use Mock LLM", value=bool(current.get("use_mock_llm", False)))
        force_fake_embeddings = st.checkbox(
            "Force Fake Embeddings",
            value=bool(current.get("force_fake_embeddings", preset.get("force_fake_embeddings", False))),
        )
        submitted = st.form_submit_button("Save Settings")

    if submitted:
        payload = {
            "provider": provider,
            "base_url": base_url.strip(),
            "model_name": model_name.strip(),
            "embedding_model": embedding_model.strip(),
            "use_mock_llm": use_mock_llm,
            "force_fake_embeddings": force_fake_embeddings,
        }
        if api_key.strip():
            payload["api_key"] = api_key.strip()
        elif keep_existing_key and current.get("api_key_set"):
            payload["api_key"] = load_api_key_for_update()
        else:
            payload["api_key"] = ""

        saved = service.update_llm_settings(payload)
        st.success(LLM_PROVIDER_PRESETS.get(saved.get("provider", ""), {}).get("label", saved.get("provider")))

    st.markdown("---")
    st.subheader("Current Settings")
    st.json(current)

