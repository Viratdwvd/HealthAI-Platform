"""
JWT bearer-token authentication middleware.
"""

from __future__ import annotations
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel

bearer_scheme = HTTPBearer()


class TokenData(BaseModel):
    username:  str
    tenant_id: str
    exp:       Optional[datetime] = None


def create_access_token(
    data:       Dict[str, Any],
    secret_key: str,
    expires_s:  int = 3600,
) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(seconds=expires_s)
    return jwt.encode(payload, secret_key, algorithm="HS256")


def _get_secret() -> str:
    import os
    return os.getenv("SECRET_KEY", "change-me-in-production")


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> TokenData:
    token = credentials.credentials
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, _get_secret(), algorithms=["HS256"])
        username:  str = payload.get("sub", "")
        tenant_id: str = payload.get("tenant_id", "")
        if not username or not tenant_id:
            raise credentials_exception
        return TokenData(username=username, tenant_id=tenant_id)
    except JWTError:
        raise credentials_exception
