from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...deps import get_settings_service
from ...schemas.settings import LLMSettingsUpdateRequest
from game.application.services import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm", response_model=dict[str, Any])
def get_llm_settings(service: SettingsService = Depends(get_settings_service)) -> dict[str, Any]:
    return service.get_llm_settings()


@router.put("/llm", response_model=dict[str, Any])
def update_llm_settings(
    payload: LLMSettingsUpdateRequest,
    service: SettingsService = Depends(get_settings_service),
) -> dict[str, Any]:
    return service.update_llm_settings(payload.model_dump())
