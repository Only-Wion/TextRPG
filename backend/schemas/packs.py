from __future__ import annotations

from pydantic import BaseModel


class PackEnabledRequest(BaseModel):
    enabled: bool
