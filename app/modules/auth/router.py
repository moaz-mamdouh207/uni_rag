from __future__ import annotations
from typing import TYPE_CHECKING

from modules.auth.dependencies import get_auth_service

if TYPE_CHECKING:
    from modules.auth.service import AuthService

from fastapi import APIRouter, Depends, Response, status
from fastapi.security import OAuth2PasswordRequestForm

from modules.auth.dependencies import get_current_user
from db.relational.models.user import User
from modules.auth.schemas import (
    AccessToken,
    ChangePasswordRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest, 
    TokenPair,
    UserResponse,
)


auth_router = APIRouter(prefix="/auth", tags=["authentication"])



@auth_router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
async def register(
    req: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> UserResponse:
    user = await auth_service.register(req)
    return UserResponse.model_validate(user)


@auth_router.post(
    "/login",
    response_model=TokenPair,
    summary="Login and receive access + refresh tokens",
)
async def login(
    req: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenPair:
    return await auth_service.login(req)


@auth_router.post(
    "/login/form",
    response_model=TokenPair,
    include_in_schema=False,   # Swagger UI uses this but we hide it from docs
)
async def login_form(
    form: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service)
) -> TokenPair:
    """OAuth2 form-compatible login — used by Swagger's Authorize button."""
    req = LoginRequest(email=form.username, password=form.password)
    return await auth_service.login(req)


@auth_router.post(
    "/refresh",
    response_model=AccessToken,
    summary="Exchange a refresh token for a new access token",
)
async def refresh(
    req: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service)
) -> AccessToken:
    token_pair = await auth_service.refresh(req.refresh_token)
    return AccessToken(
        access_token=token_pair.access_token,
        expires_in=token_pair.expires_in,
    )


@auth_router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke the current refresh token (logout)",
)
async def logout(
    req: RefreshRequest,
    _: User = Depends(get_current_user),   # require valid access token
    auth_service: AuthService = Depends(get_auth_service)
) -> Response:
    await auth_service.revoke(req.refresh_token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.post(
    "/logout/all",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke all sessions for the current user",
)
async def logout_all(
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    await auth_service.revoke_all(current_user.id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@auth_router.get(
    "/me",
    response_model=UserResponse,
    summary="Return the currently authenticated user",
)
async def me(current_user: User = Depends(get_current_user)) -> UserResponse:
    return UserResponse.model_validate(current_user)


@auth_router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Change the current user's password",
)
async def change_password(
    req: ChangePasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
    current_user: User = Depends(get_current_user),
) -> Response:
    await auth_service.change_password(
        current_user, req.current_password, req.new_password
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
