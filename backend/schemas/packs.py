from __future__ import annotations

from pydantic import BaseModel, Field


class PackEnabledRequest(BaseModel):
    enabled: bool


class PackExportResponse(BaseModel):
    ok: bool = True
    pack_id: str
    export_path: str


class CreateUiTemplateRequest(BaseModel):
    name: str
    template: dict = Field(default_factory=dict)
    variable_template: dict = Field(default_factory=dict)


class UiTemplateResponse(BaseModel):
    template_id: str
    pack_id: str
    name: str
    template: dict
    variable_template: dict
    sessions_in_use: int = 0
    created_at: str | None = None
    updated_at: str | None = None
