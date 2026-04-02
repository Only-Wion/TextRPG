from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from ...deps import get_current_user, get_session_service
from ...schemas.common import OkResponse
from ...schemas.game import (
    BindSessionUiTemplateRequest,
    DuplicateSessionRequest,
    GameActionResponse,
    LoadGameRequest,
    SessionManagerResponse,
    StartGameRequest,
    StepRequest,
    TriggerUiGenerationRequest,
    UiAutoUpdateRequest,
    UiModeRequest,
    UiPanelVisibilityRequest,
)
from game.application.services import SessionService

router = APIRouter(prefix="/game", tags=["game"])


def _sse(event_name: str, payload: dict) -> str:
    return f"event: {event_name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.post("/start", response_model=OkResponse)
def start_game(
    payload: StartGameRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.start_new_game(
        current_user["id"],
        payload.save_slot,
        payload.pack_ids,
        language=payload.language,
        ui_template_id=payload.ui_template_id,
    )
    return OkResponse(ok=True)


@router.post("/load", response_model=OkResponse)
def load_game(
    payload: LoadGameRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.load_game(current_user["id"], payload.save_slot, language=payload.language)
    return OkResponse(ok=True)


@router.post("/step", response_model=GameActionResponse)
def step_game(
    payload: StepRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> GameActionResponse:
    result = service.step(current_user["id"], payload.input_text)
    return GameActionResponse(
        result=result, state_view=service.get_current_state_view(current_user["id"])
    )


@router.post("/step/stream")
def step_game_stream(
    payload: StepRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    def event_stream():
        try:
            for event in service.step_stream(current_user["id"], payload.input_text):
                if event.get("type") == "narration_delta":
                    yield _sse(
                        "narration_delta", {"delta": str(event.get("delta", ""))}
                    )
                elif event.get("type") == "done":
                    yield _sse(
                        "done",
                        {
                            "result": event.get("result", {}),
                            "state_view": event.get("state_view", {}),
                        },
                    )
        except Exception as exc:
            yield _sse("error", {"detail": str(exc) or "stream step failed"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/state", response_model=dict)
def get_game_state(
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return service.get_current_state_view(current_user["id"])


@router.get("/sessions", response_model=SessionManagerResponse)
def get_sessions(
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> SessionManagerResponse:
    return SessionManagerResponse(**service.list_sessions(current_user["id"]))


@router.post("/sessions/{slot_id}/duplicate", response_model=SessionManagerResponse)
def duplicate_session(
    slot_id: str,
    payload: DuplicateSessionRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> SessionManagerResponse:
    return SessionManagerResponse(
        **service.duplicate_session(current_user["id"], slot_id, payload.target_slot)
    )


@router.post("/sessions/{slot_id}/archive", response_model=SessionManagerResponse)
def archive_session(
    slot_id: str,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> SessionManagerResponse:
    return SessionManagerResponse(
        **service.archive_session(current_user["id"], slot_id)
    )


@router.patch("/ui-mode", response_model=OkResponse)
def set_ui_mode(
    payload: UiModeRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.set_ui_update_mode(current_user["id"], payload.mode)
    return OkResponse(ok=True)


@router.patch("/ui-auto-update", response_model=OkResponse)
def set_ui_auto_update(
    payload: UiAutoUpdateRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.set_ui_auto_update_every(current_user["id"], payload.turns)
    return OkResponse(ok=True)


@router.post("/ui/generate", response_model=OkResponse)
def trigger_ui_generation(
    payload: TriggerUiGenerationRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.trigger_ui_generation(current_user["id"], force=payload.force)
    return OkResponse(ok=True)


@router.post("/ui/update", response_model=OkResponse)
def trigger_ui_update(
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.trigger_ui_update(current_user["id"])
    return OkResponse(ok=True)


@router.patch("/ui/visibility", response_model=OkResponse)
def set_ui_panel_visibility(
    payload: UiPanelVisibilityRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> OkResponse:
    service.set_ui_panel_visibility(
        current_user["id"], payload.panel_id, payload.visible
    )
    return OkResponse(ok=True)


@router.post("/ui/template/bind", response_model=dict)
def bind_session_ui_template(
    payload: BindSessionUiTemplateRequest,
    service: SessionService = Depends(get_session_service),
    current_user: dict = Depends(get_current_user),
) -> dict:
    return service.bind_session_ui_template(
        current_user["id"],
        payload.save_slot,
        payload.pack_id,
        payload.template_id,
    )
