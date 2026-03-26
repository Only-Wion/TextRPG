from __future__ import annotations

from pydantic import BaseModel, Field


class UserResponse(BaseModel):
    id: str
    email: str
    username: str


class RegisterRequest(BaseModel):
    email: str = Field(min_length=5, max_length=256)
    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(BaseModel):
    email_or_username: str = Field(min_length=3, max_length=256)
    password: str = Field(min_length=8, max_length=256)


class AuthTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
