from __future__ import annotations
from typing import TYPE_CHECKING
from uuid import UUID


from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import settings

from modules.auth.service import AuthService

from db.relational.session import get_async_db

from db.relational.repositories.user_repository import AsyncUserRepository
from db.relational.repositories.token_repository import AsyncTokenRepository

from modules.auth.exceptions import CredentialsException, InactiveUserException, PermissionDeniedException

from modules.auth.helpers import  decode_access_token


if TYPE_CHECKING:
    from db.relational.models.user import User


# Points to the login endpoint — used by Swagger UI "Authorize" button
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login/form")


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_async_db)
) -> User:
    """
    Decode the Bearer token and return the authenticated User.
    Raises 401 if the token is missing, invalid, or expired.
    Raises 403 if the user account is inactive.
    """
    payload = decode_access_token(token)

    try:
        user_id = UUID(payload.sub)
    except ValueError:
        raise CredentialsException()

    user_repo = AsyncUserRepository(db)
    user = await user_repo.get_by_id(user_id)
    if not user.is_active:
        raise InactiveUserException()
    return user


async def get_current_active_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """Like get_current_user but also requires email verification."""
    if not current_user.is_verified:
        raise PermissionDeniedException("Email address not verified")
    return current_user


def require_role(*roles: str):
    """
    Factory dependency — restricts a route to users with the given role(s).

    Usage:
        @router.delete("/admin/users/{id}", dependencies=[Depends(require_role("admin"))])
    """
    async def checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in roles:
            raise PermissionDeniedException(
                f"Required role: {' or '.join(roles)}"
            )
        return current_user
    return checker


# Convenience aliases
AdminUser = Depends(require_role("admin"))


def get_auth_service(
        db: AsyncSession = Depends(get_async_db),
) -> AuthService:
    return AuthService(
        user_repository=AsyncUserRepository(db),
        token_repository=AsyncTokenRepository(db),
        settings=settings.auth,
    )