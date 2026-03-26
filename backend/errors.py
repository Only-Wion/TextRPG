from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse


def _payload(detail: str) -> dict[str, object]:
    return {"ok": False, "detail": detail}


async def handle_value_error(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=400, content=_payload(str(exc)))


async def handle_runtime_error(_: Request, exc: RuntimeError) -> JSONResponse:
    detail = str(exc)
    status = 409 if detail == "game not started" else 500
    return JSONResponse(status_code=status, content=_payload(detail))


async def handle_permission_error(_: Request, exc: PermissionError) -> JSONResponse:
    return JSONResponse(status_code=401, content=_payload(str(exc) or "authentication required"))


async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content=_payload(str(exc) or "internal server error"))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ValueError, handle_value_error)
    app.add_exception_handler(RuntimeError, handle_runtime_error)
    app.add_exception_handler(PermissionError, handle_permission_error)
    app.add_exception_handler(Exception, handle_unexpected)
