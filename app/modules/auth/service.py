from __future__ import annotations
from typing import  TYPE_CHECKING
from uuid import UUID
import secrets
from datetime import datetime, timedelta, timezone

from db.relational.schemas import TokenCreate, TokenUpdate, UserCreate, UserUpdate
from db.relational.models.user import User

from modules.auth.schemas import (
    LoginRequest,
    RegisterRequest,
    TokenPair,
)

from modules.auth.helpers import (
    hash_password,
    verify_password,
    _hash_token,
    _make_access_token,
)

from modules.auth.exceptions import (
    CredentialsException,
    ConflictException,
    InactiveUserException,
)


if TYPE_CHECKING:
    from db.relational.repositories.user_repository import AsyncUserRepository
    from db.relational.repositories.token_repository import AsyncTokenRepository
    from modules.auth.config import AuthSettings



class AuthService:
    def __init__(
        self, 
        user_repository: AsyncUserRepository, 
        token_repository: AsyncTokenRepository,
        settings: AuthSettings
    ):
        self._user_repo = user_repository
        self._token_repo = token_repository
        self._settings = settings


    async def register(self, req: RegisterRequest) -> User:
        user = await self._user_repo.get_by_email(req.email)
        if user:
            raise ConflictException("An account with this email already exists")

        user = UserCreate(
            email=req.email,
            hashed_password=hash_password(req.password),
            full_name=req.full_name,
        )
        user = await self._user_repo.add(user)
        return user


    async def login(self, req: LoginRequest) -> TokenPair:
        user = await self._user_repo.get_by_email(req.email)
        if not user:
            raise CredentialsException("Incorrect email or password")
        if not user.is_active:
            raise InactiveUserException()
        if not verify_password(req.password, user.hashed_password):
            raise CredentialsException("Incorrect email or password")

        return await self._issue_token_pair(user)


    async def refresh(self, raw_token: str) -> TokenPair:
        token_hash = _hash_token(raw_token)
        record = await self._token_repo.get_by_hash(token_hash)
        if not record or not record.is_valid:
            raise CredentialsException("Invalid or expired refresh token")

        # Rotate: revoke old token, issue new pair
        await self._token_repo.update(TokenUpdate(revoked=True), record)

        user = await self._user_repo.get_by_id(record.user_id)
        if not user or not user.is_active:
            raise InactiveUserException()

        return await self._issue_token_pair(user)


    async def revoke(self, raw_token: str) -> None:
        token_hash = _hash_token(raw_token)
        record = await self._token_repo.get_by_hash(token_hash)
        if record:
            await self._token_repo.update(TokenUpdate(revoked=True), record)


    async def revoke_all(self, user_id: UUID) -> None:
        tokens = await self._token_repo.get_all_by_user(user_id)
        for t in tokens:
            await self._token_repo.update(TokenUpdate(revoked=True), t)


    async def change_password(
        self, user: User, current_password: str, new_password: str
    ) -> None:
        if not verify_password(current_password, user.hashed_password):
            raise CredentialsException("Current password is incorrect")
        
        user_update = UserUpdate(hashed_password=hash_password(new_password))
        await self._user_repo.update(user_update, user)
        # Revoke all sessions so re-login is forced on other devices
        await self.revoke_all(user.id)


    # ── Internal helpers ──────────────────────────────────────────────────────

    async def _issue_token_pair(self, user: User) -> TokenPair:
        access_token, expires_in = _make_access_token(user)

        # Generate a cryptographically random refresh token
        raw_refresh = secrets.token_urlsafe(64)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=self._settings.jwt_refresh_token_expire_days
        )
        record = TokenCreate(
            user_id=user.id,
            token_hash=_hash_token(raw_refresh),
            expires_at=expires_at,
        )
        await self._token_repo.add(record)

        return TokenPair(
            access_token=access_token,
            refresh_token=raw_refresh,
            expires_in=expires_in,
        )
