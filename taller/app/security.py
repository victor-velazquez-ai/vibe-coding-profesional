from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    result: bool = pwd_context.verify(plain_password, hashed_password)
    return result


def hash_password(password: str) -> str:
    result: str = pwd_context.hash(password)
    return result


def create_access_token(subject: str) -> str:
    settings = get_settings()
    expire = datetime.now(UTC) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": expire}
    token: str = jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)
    return token


def decode_access_token(token: str) -> str | None:
    settings = get_settings()
    try:
        payload: dict[str, Any] = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except JWTError:
        return None
    subject = payload.get("sub")
    return subject if isinstance(subject, str) else None
