from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query

from ...deps import get_current_user, get_settings_service
from ...schemas.settings import (
    CoinRedeemRequest,
    LLMPlanSelectRequest,
    LLMSettingsUpdateRequest,
)
from game.application.services import SettingsService

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("/llm", response_model=dict[str, Any])
def get_llm_settings(
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.get_llm_settings(current_user["id"])


@router.put("/llm", response_model=dict[str, Any])
def update_llm_settings(
    payload: LLMSettingsUpdateRequest,
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.update_llm_settings(current_user["id"], payload.model_dump())


@router.get("/overview", response_model=dict[str, Any])
def get_settings_overview(
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.get_settings_overview(current_user["id"])


@router.get("/llm/plans", response_model=list[dict[str, Any]])
def list_llm_plans(
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return service.list_llm_plans(current_user["id"])


@router.get("/llm/selection", response_model=dict[str, Any])
def get_llm_plan_selection(
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.get_selected_llm_plan(current_user["id"])


@router.put("/llm/selection", response_model=dict[str, Any])
def set_llm_plan_selection(
    payload: LLMPlanSelectRequest,
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.set_selected_llm_plan(current_user["id"], payload.plan_id)


@router.get("/coins/balance", response_model=dict[str, Any])
def get_coin_balance(
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.get_coin_balance(current_user["id"])


@router.post("/coins/redeem", response_model=dict[str, Any])
def redeem_coin_key(
    payload: CoinRedeemRequest,
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.redeem_coin_key(current_user["id"], payload.redeem_key)


@router.get("/coins/consumptions", response_model=list[dict[str, Any]])
def list_coin_consumptions(
    limit: int = Query(default=100, ge=1, le=200),
    service: SettingsService = Depends(get_settings_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return service.list_coin_consumptions(current_user["id"], limit=limit)
