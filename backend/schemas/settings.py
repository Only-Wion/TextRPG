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


class LLMPlanSelectRequest(BaseModel):
    plan_id: str


class CoinRedeemRequest(BaseModel):
    redeem_key: str


class CoinConsumptionQuery(BaseModel):
    limit: int = 100
