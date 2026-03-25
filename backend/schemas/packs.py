from __future__ import annotations

from pydantic import BaseModel


class PackEnabledRequest(BaseModel):
    enabled: bool


class PackExportResponse(BaseModel):
    ok: bool = True
    pack_id: str
    export_path: str
