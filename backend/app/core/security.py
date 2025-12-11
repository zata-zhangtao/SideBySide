from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from passlib.context import CryptContext
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from .config import settings


ALGORITHM = "HS256"
# Prefer a built-in hash in dev to avoid native deps issues.
# Keep bcrypt as a secondary scheme for verifying existing hashes.
pwd_context = CryptContext(schemes=["pbkdf2_sha256", "bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def _get_serializer() -> URLSafeTimedSerializer:
    return URLSafeTimedSerializer(settings.SECRET_KEY, salt="auth")


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    # Use itsdangerous for signed tokens; no external crypto deps.
    s = _get_serializer()
    payload = data.copy()
    # Keep exp for compatibility/inspection; validation uses max_age when decoding.
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload.update({"exp": int(expire.timestamp())})
    return s.dumps(payload)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def decode_token(token: str) -> dict:
    try:
        s = _get_serializer()
        max_age = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        payload = s.loads(token, max_age=max_age)
        return payload
    except (BadSignature, SignatureExpired) as e:  # pragma: no cover
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token") from e
