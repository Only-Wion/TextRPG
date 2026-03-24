from __future__ import annotations

from fastapi import APIRouter, Depends

from ...deps import get_session_service
from ...schemas.common import OkResponse
from ...schemas.game import (
    GameActionResponse,
    LoadGameRequest,
    SessionManagerResponse,
    StartGameRequest,
    StepRequest,
    TriggerUiGenerationRequest,
    UiAutoUpdateRequest,
    UiModeRequest,
)
from game.application.services import SessionService

router = APIRouter(prefix="/game", tags=["game"])


@router.post("/start", response_model=OkResponse)
def start_game(
    payload: StartGameRequest,
    service: SessionService = Depends(get_session_service),
) -> OkResponse:
    service.start_new_game(payload.save_slot, payload.pack_ids, language=payload.language)
    return OkResponse(ok=True)


@router.post("/load", response_model=OkResponse)
def load_game(
    payload: LoadGameRequest,
    service: SessionService = Depends(get_session_service),
) -> OkResponse:
    service.load_game(payload.save_slot, language=payload.language)
    return OkResponse(ok=True)


@router.post("/step", response_model=GameActionResponse)
def step_game(
    payload: StepRequest,
    service: SessionService = Depends(get_session_service),
) -> GameActionResponse:
    result = service.step(payload.input_text)
    return GameActionResponse(result=result, state_view=service.get_current_state_view())


@router.get("/state", response_model=dict)
def get_game_state(service: SessionService = Depends(get_session_service)) -> dict:
    return service.get_current_state_view()


@router.get("/sessions", response_model=SessionManagerResponse)
def get_sessions(service: SessionService = Depends(get_session_service)) -> SessionManagerResponse:
    return SessionManagerResponse(**service.list_sessions())


@router.patch("/ui-mode", response_model=OkResponse)
def set_ui_mode(
    payload: UiModeRequest,
    service: SessionService = Depends(get_session_service),
) -> OkResponse:
    service.set_ui_update_mode(payload.mode)
    return OkResponse(ok=True)


@router.patch("/ui-auto-update", response_model=OkResponse)
def set_ui_auto_update(
    payload: UiAutoUpdateRequest,
    service: SessionService = Depends(get_session_service),
) -> OkResponse:
    service.set_ui_auto_update_every(payload.turns)
    return OkResponse(ok=True)


@router.post("/ui/generate", response_model=OkResponse)
def trigger_ui_generation(
    payload: TriggerUiGenerationRequest,
    service: SessionService = Depends(get_session_service),
) -> OkResponse:
    service.trigger_ui_generation(force=payload.force)
    return OkResponse(ok=True)


@router.post("/ui/update", response_model=OkResponse)
def trigger_ui_update(service: SessionService = Depends(get_session_service)) -> OkResponse:
    service.trigger_ui_update()
    return OkResponse(ok=True)
