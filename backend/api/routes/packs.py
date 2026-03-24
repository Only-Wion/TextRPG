from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...deps import get_pack_service
from ...schemas.common import OkResponse
from ...schemas.packs import PackEnabledRequest
from game.application.services import PackService

router = APIRouter(prefix="/packs", tags=["packs"])


@router.get("", response_model=list[dict[str, Any]])
def list_packs(service: PackService = Depends(get_pack_service)) -> list[dict[str, Any]]:
    return service.list_packs()


@router.patch("/{pack_id}/enabled", response_model=OkResponse)
def set_pack_enabled(
    pack_id: str,
    payload: PackEnabledRequest,
    service: PackService = Depends(get_pack_service),
) -> OkResponse:
    service.enable_pack(pack_id, payload.enabled)
    return OkResponse(ok=True)
