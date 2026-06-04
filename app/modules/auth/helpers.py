from __future__ import annotations
import hashlib
from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt
from passlib.context import CryptContext

from core.config import settings as ss
from modules.auth.exceptions import (
    CredentialsException,
    TokenExpiredException,
)
from db.relational.models.user import User
from modules.auth.schemas import TokenPayload


settings = ss.auth

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")



def hash_password(plain: str) -> str:
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return _pwd_context.verify(plain, hashed)


def _hash_token(raw_token: str) -> str:
    """SHA-256 hash of a refresh token for safe DB storage."""
    return hashlib.sha256(raw_token.encode()).hexdigest()


def _make_access_token(user: User) -> tuple[str, int]:
    """Returns (encoded_jwt, expires_in_seconds)."""
    expire_seconds = settings.jwt_access_token_expire_minutes * 60
    exp = datetime.now(timezone.utc) + timedelta(seconds=expire_seconds)
    payload = {
        "sub": str(user.id),
        "role": user.role,
        "exp": exp,
        "type": "access",
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm), expire_seconds


def decode_access_token(token: str) -> TokenPayload:
    """Decode and validate a JWT access token. Raises CredentialsException on failure."""
    try:
        raw = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
        payload = TokenPayload(**raw)
        if payload.type != "access":
            raise CredentialsException("Invalid token type")
        return payload
    except JWTError as exc:
        if "expired" in str(exc).lower():
            raise TokenExpiredException()
        raise CredentialsException() from exc