from __future__ import annotations

from fastapi import APIRouter, Depends

from ...deps import get_auth_service, get_current_token, get_current_user
from ...schemas.auth import AuthTokenResponse, LoginRequest, RegisterRequest, UserResponse
from ...schemas.common import OkResponse
from game.application.services import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=AuthTokenResponse)
def register(
    payload: RegisterRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    return AuthTokenResponse(**service.register(payload.email, payload.username, payload.password))


@router.post("/login", response_model=AuthTokenResponse)
def login(
    payload: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> AuthTokenResponse:
    return AuthTokenResponse(**service.login(payload.email_or_username, payload.password))


@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return UserResponse(**current_user)


@router.post("/logout", response_model=OkResponse)
def logout(
    token: str = Depends(get_current_token),
    service: AuthService = Depends(get_auth_service),
) -> OkResponse:
    service.logout(token)
    return OkResponse(ok=True)
