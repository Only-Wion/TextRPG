from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, Query
import yaml

from ...deps import get_card_designer_service, get_current_user
from ...schemas.card_designer import (
    CardValidationResponse,
    CreateCardTemplateRequest,
    CreateDesignerPackRequest,
    CreateDesignerSessionRequest,
    DesignerAgentMessageRequest,
    DesignerAgentMessageResponse,
    DesignerAgentSessionResponse,
    DesignerCardPayloadResponse,
    DesignerCardSummaryResponse,
    SaveDesignerCardRequest,
    ValidateDesignerCardRequest,
)
from game.application.services import CardDesignerService

router = APIRouter(prefix="/card-designer", tags=["card-designer"])


def _coerce_frontmatter(
    payload: SaveDesignerCardRequest | ValidateDesignerCardRequest,
) -> dict[str, Any]:
    if payload.frontmatter is not None:
        return payload.frontmatter
    if payload.frontmatter_text:
        loaded = yaml.safe_load(payload.frontmatter_text) or {}
        if not isinstance(loaded, dict):
            raise ValueError("frontmatter must parse to an object")
        return loaded
    return {}


@router.get("/packs", response_model=list[dict[str, Any]])
def list_designer_packs(
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[dict[str, Any]]:
    return service.list_packs(current_user["id"])


@router.post("/packs", response_model=dict[str, Any])
def create_designer_pack(
    payload: CreateDesignerPackRequest,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    return service.create_pack(current_user["id"], payload.model_dump())


@router.get("/packs/{pack_id}/card-types", response_model=list[str])
def list_pack_card_types(
    pack_id: str,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[str]:
    return service.list_card_types(current_user["id"], pack_id)


@router.get("/packs/{pack_id}/cards", response_model=list[DesignerCardSummaryResponse])
def list_pack_cards(
    pack_id: str,
    category: str | None = Query(default=None),
    keyword: str | None = Query(default=None),
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> list[DesignerCardSummaryResponse]:
    return [
        DesignerCardSummaryResponse(**item)
        for item in service.list_cards(current_user["id"], pack_id, category, keyword)
    ]


@router.get(
    "/packs/{pack_id}/cards/{card_path:path}",
    response_model=DesignerCardPayloadResponse,
)
def load_pack_card(
    pack_id: str,
    card_path: str,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> DesignerCardPayloadResponse:
    return DesignerCardPayloadResponse(
        **service.load_card(current_user["id"], pack_id, card_path)
    )


@router.post("/packs/{pack_id}/cards/template", response_model=dict[str, Any])
def create_card_template(
    pack_id: str,
    payload: CreateCardTemplateRequest,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    del pack_id
    return service.get_card_template(current_user["id"], payload.card_type)


@router.post("/packs/{pack_id}/cards", response_model=DesignerCardPayloadResponse)
def save_pack_card(
    pack_id: str,
    payload: SaveDesignerCardRequest,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> DesignerCardPayloadResponse:
    return DesignerCardPayloadResponse(
        **service.save_card(
            current_user["id"],
            pack_id,
            payload.card_type,
            payload.card_id,
            payload.folder_path,
            _coerce_frontmatter(payload),
            payload.body,
            original_path=payload.original_path,
        )
    )


@router.post("/cards/validate", response_model=CardValidationResponse)
def validate_pack_card(
    payload: ValidateDesignerCardRequest,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CardValidationResponse:
    service.validate_card(
        current_user["id"], _coerce_frontmatter(payload), payload.body
    )
    return CardValidationResponse(ok=True)


@router.delete(
    "/packs/{pack_id}/cards/{card_path:path}", response_model=CardValidationResponse
)
def delete_pack_card(
    pack_id: str,
    card_path: str,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> CardValidationResponse:
    service.delete_card(current_user["id"], pack_id, card_path)
    return CardValidationResponse(ok=True)


@router.post("/agent/sessions", response_model=DesignerAgentSessionResponse)
def create_designer_agent_session(
    payload: CreateDesignerSessionRequest,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> DesignerAgentSessionResponse:
    return DesignerAgentSessionResponse(
        **service.create_agent_session(current_user["id"], payload.pack_id)
    )


@router.get("/agent/sessions/{session_id}", response_model=DesignerAgentSessionResponse)
def get_designer_agent_session(
    session_id: str,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> DesignerAgentSessionResponse:
    return DesignerAgentSessionResponse(
        **service.get_agent_session(current_user["id"], session_id)
    )


@router.post(
    "/agent/sessions/{session_id}/messages", response_model=DesignerAgentMessageResponse
)
def send_designer_agent_message(
    session_id: str,
    payload: DesignerAgentMessageRequest,
    service: CardDesignerService = Depends(get_card_designer_service),
    current_user: dict[str, Any] = Depends(get_current_user),
) -> DesignerAgentMessageResponse:
    return DesignerAgentMessageResponse(
        **service.send_agent_message(current_user["id"], session_id, payload.message)
    )
