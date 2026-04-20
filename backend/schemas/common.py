from __future__ import annotations

from pydantic import BaseModel


class OkResponse(BaseModel):
    ok: bool = True
    status: str | None = None
