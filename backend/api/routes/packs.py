from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends

from ...deps import get_current_user, get_pack_service
from ...schemas.common import OkResponse
from ...schemas.packs import PackEnabledRequest, PackExportResponse
from game.application.services import PackService

router = APIRouter(prefix="/packs", tags=["packs"])


@router.get("", response_model=list[dict[str, Any]])
def list_packs(
    service: PackService = Depends(get_pack_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return service.list_packs(current_user["id"])


@router.patch("/{pack_id}/enabled", response_model=OkResponse)
def set_pack_enabled(
    pack_id: str,
    payload: PackEnabledRequest,
    service: PackService = Depends(get_pack_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> OkResponse:
    service.enable_pack(current_user["id"], pack_id, payload.enabled)
    return OkResponse(ok=True)


@router.delete("/{pack_id}", response_model=OkResponse)
def remove_pack(
    pack_id: str,
    service: PackService = Depends(get_pack_service),
    _: dict[str, Any] = Depends(get_current_user),
) -> OkResponse:
    service.remove_pack(pack_id)
    return OkResponse(ok=True)


@router.post("/{pack_id}/export", response_model=PackExportResponse)
def export_pack(
    pack_id: str,
    service: PackService = Depends(get_pack_service),
    _: dict[str, Any] = Depends(get_current_user),
) -> PackExportResponse:
    return PackExportResponse(**service.export_pack_to_runtime_exports(pack_id))
