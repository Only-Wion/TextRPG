from __future__ import annotations

from fastapi import APIRouter

from ...schemas.common import OkResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=OkResponse)
def health_check() -> OkResponse:
    return OkResponse(status="ok")
