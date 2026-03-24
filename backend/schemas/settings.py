from __future__ import annotations

from pydantic import BaseModel


class LLMSettingsUpdateRequest(BaseModel):
    provider: str = "custom"
    model_name: str = ""
    embedding_model: str = ""
    base_url: str = ""
    api_key: str = ""
    use_mock_llm: bool = False
    force_fake_embeddings: bool = False
