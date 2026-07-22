"""
Session authentication for the API Gateway.
Uses JWT tokens signed with the application SECRET_KEY.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from jose import JWTError, jwt

from app.config import get_settings
from app.observability.logging_config import get_logger

logger = get_logger(__name__)

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_HOURS = 24

_bearer_scheme = HTTPBearer(auto_error=False)


def create_session_token(session_id: str, user_id: Optional[str] = None) -> str:
    """
    Create a signed JWT for the given session.
    Returns the encoded token string.
    """
    settings = get_settings()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": session_id,
        "iat": now,
        "exp": now + timedelta(hours=_TOKEN_EXPIRE_HOURS),
        "jti": str(uuid4()),
    }
    if user_id:
        payload["uid"] = user_id

    token = jwt.encode(payload, settings.secret_key, algorithm=_ALGORITHM)
    logger.debug("session_token_created", session_id=session_id)
    return token


def verify_session_token(token: str) -> dict:
    """
    Verify and decode a session JWT.
    Returns the decoded payload dict.
    Raises HTTPException 401 on invalid or expired tokens.
    """
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
        session_id: str = payload.get("sub", "")
        if not session_id:
            raise JWTError("Missing subject claim")
        return payload
    except JWTError as exc:
        logger.warning("token_verification_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_session(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> dict:
    """
    FastAPI dependency that extracts and validates the Bearer token.
    Returns the decoded JWT payload (includes session_id as 'sub').
    Raises HTTP 401 if no token or invalid token.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return verify_session_token(credentials.credentials)
