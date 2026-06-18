"""Authentication endpoints for the password login gate.

Exposes two unprotected endpoints:
- GET  /api/v1/auth/status  -> whether a password gate is enabled
- POST /api/v1/auth/login   -> exchange the gate password for a session token

The actual enforcement happens in the password-gate middleware (see main.py).
"""

from __future__ import annotations

from fastapi import APIRouter
from fastapi import HTTPException
from pydantic import BaseModel

from ..auth import auth_required
from ..auth import get_session_token
from ..auth import verify_password

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


class AuthStatus(BaseModel):
    auth_required: bool


class LoginRequest(BaseModel):
    password: str


class LoginResponse(BaseModel):
    token: str


@router.get("/status")
async def auth_status() -> AuthStatus:
    """Report whether a password gate is enabled."""
    return AuthStatus(auth_required=auth_required())


@router.post("/login")
async def login(request: LoginRequest) -> LoginResponse:
    """Exchange the gate password for a session token."""
    if not verify_password(request.password):
        raise HTTPException(status_code=401, detail="Invalid password")
    return LoginResponse(token=get_session_token())
