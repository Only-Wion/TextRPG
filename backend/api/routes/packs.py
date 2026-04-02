from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from ...deps import get_current_user, get_pack_service
from ...schemas.common import OkResponse
from ...schemas.packs import (
    CreateUiTemplateRequest,
    PackEnabledRequest,
    PackExportResponse,
    UiTemplateResponse,
)
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
    current_user: dict[str, Any] = Depends(get_current_user),
) -> OkResponse:
    service.remove_pack(current_user["id"], pack_id)
    return OkResponse(ok=True)


@router.post("/{pack_id}/export", response_model=PackExportResponse)
def export_pack(
    pack_id: str,
    service: PackService = Depends(get_pack_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> PackExportResponse:
    return PackExportResponse(
        **service.export_pack_to_runtime_exports(current_user["id"], pack_id)
    )


@router.get("/{pack_id}/ui-templates", response_model=list[UiTemplateResponse])
def list_ui_templates(
    pack_id: str,
    service: PackService = Depends(get_pack_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[UiTemplateResponse]:
    records = service.list_ui_templates(current_user["id"], pack_id)
    return [UiTemplateResponse(**record) for record in records]


@router.post("/{pack_id}/ui-templates", response_model=UiTemplateResponse)
def create_ui_template(
    pack_id: str,
    payload: CreateUiTemplateRequest,
    service: PackService = Depends(get_pack_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> UiTemplateResponse:
    record = service.create_ui_template(
        current_user["id"],
        pack_id,
        payload.name,
        payload.template,
        payload.variable_template,
    )
    return UiTemplateResponse(**record)


@router.delete("/{pack_id}/ui-templates/{template_id}", response_model=OkResponse)
def delete_ui_template(
    pack_id: str,
    template_id: str,
    service: PackService = Depends(get_pack_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> OkResponse:
    service.delete_ui_template(current_user["id"], pack_id, template_id)
    return OkResponse(ok=True)


@router.get("/market/public", response_model=list[dict[str, Any]])
def list_public_market_packs(
    _: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    raise HTTPException(status_code=501, detail="pack marketplace is not implemented")


@router.get("/market/public/{public_pack_id}", response_model=dict[str, Any])
def get_public_market_pack(
    public_pack_id: str,
    _: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    del public_pack_id
    raise HTTPException(status_code=501, detail="pack marketplace is not implemented")


@router.post("/{pack_id}/market/publish", response_model=OkResponse)
def publish_pack_to_market(
    pack_id: str,
    _: dict[str, Any] = Depends(get_current_user),
) -> OkResponse:
    del pack_id
    raise HTTPException(status_code=501, detail="pack marketplace is not implemented")


@router.post("/market/public/{public_pack_id}/download", response_model=OkResponse)
def download_public_market_pack(
    public_pack_id: str,
    _: dict[str, Any] = Depends(get_current_user),
) -> OkResponse:
    del public_pack_id
    raise HTTPException(status_code=501, detail="pack marketplace is not implemented")
