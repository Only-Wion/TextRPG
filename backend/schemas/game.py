from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class StartGameRequest(BaseModel):
    save_slot: str
    pack_ids: list[str] | None = None
    language: str | None = None
    ui_template_id: str | None = None


class LoadGameRequest(BaseModel):
    save_slot: str
    language: str | None = None


class DuplicateSessionRequest(BaseModel):
    target_slot: str | None = None


class StepRequest(BaseModel):
    input_text: str = Field(min_length=1)


class UiModeRequest(BaseModel):
    mode: Literal["manual", "auto"]


class UiAutoUpdateRequest(BaseModel):
    turns: int = Field(ge=1)


class TriggerUiGenerationRequest(BaseModel):
    force: bool = False


class UiPanelVisibilityRequest(BaseModel):
    panel_id: str
    visible: bool


class BindSessionUiTemplateRequest(BaseModel):
    save_slot: str
    pack_id: str
    template_id: str


class GameActionResponse(BaseModel):
    result: dict[str, Any]
    state_view: dict[str, Any]


class SessionSummaryResponse(BaseModel):
    slot_id: str
    language: str
    enabled_packs: list[str]
    location_label: str
    turn_count: int
    updated_label: str
    ui_generation_status: str = "ready"


class SessionManagerResponse(BaseModel):
    selected_slot: str
    backend_status: str
    storage_backend: str
    last_sync_label: str
    sessions: list[SessionSummaryResponse]
