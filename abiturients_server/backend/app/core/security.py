from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings


def hash_password(password: str) -> str:
    encoded = password.encode("utf-8")
    if len(encoded) > 72:
        raise ValueError("Password is too long")
    return bcrypt.hashpw(encoded, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_access_token(subject: str, extra: dict[str, Any] | None = None) -> str:
    settings = get_settings()
    expires_at = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {"sub": subject, "exp": expires_at}
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict[str, Any]:
    settings = get_settings()
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid token") from exc
