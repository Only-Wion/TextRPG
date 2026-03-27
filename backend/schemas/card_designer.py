from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class CreateDesignerPackRequest(BaseModel):
    pack_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    version: str = Field(min_length=1, default="0.1.0")
    author: str = Field(min_length=1)
    description: str = ""
    cards_root: str = Field(default="cards", min_length=1)


class CreateCardTemplateRequest(BaseModel):
    card_type: str = Field(min_length=1)


class SaveDesignerCardRequest(BaseModel):
    card_type: str = Field(min_length=1)
    card_id: str = Field(min_length=1)
    frontmatter: dict[str, Any] | None = None
    frontmatter_text: str | None = None
    body: str = ""
    original_path: str | None = None


class ValidateDesignerCardRequest(BaseModel):
    frontmatter: dict[str, Any] | None = None
    frontmatter_text: str | None = None
    body: str = ""


class CreateDesignerSessionRequest(BaseModel):
    pack_id: str | None = None


class DesignerAgentMessageRequest(BaseModel):
    message: str = Field(min_length=1)


class DesignerCardSummaryResponse(BaseModel):
    path: str
    card_id: str
    card_type: str
    category: str
    title: str


class DesignerCardPayloadResponse(BaseModel):
    path: str
    pack_id: str
    card_type: str
    card_id: str
    frontmatter: dict[str, Any]
    body: str


class CardValidationResponse(BaseModel):
    ok: bool


class DesignerAgentSessionResponse(BaseModel):
    session_id: str
    selected_pack_id: str
    mode: str
    state: dict[str, Any]
    updated_at: str | None = None


class DesignerAgentMessageResponse(BaseModel):
    session_id: str
    assistant: str
    tool_logs: list[str]
    selected_pack_id: str
    state: dict[str, Any]
