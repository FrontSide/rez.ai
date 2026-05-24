import os
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

SECRET_KEY = os.getenv("SECRET_KEY", "")
_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 30

_bearer = HTTPBearer(auto_error=False)


def create_token(user_id: str, email: str, name: str = "") -> str:
    payload = {
        "sub": user_id,
        "email": email,
        "name": name,
        "exp": datetime.now(timezone.utc) + timedelta(days=_TOKEN_EXPIRE_DAYS),
    }
    return pyjwt.encode(payload, SECRET_KEY, algorithm=_ALGORITHM)


def _decode(token: str) -> dict:
    if not SECRET_KEY:
        raise pyjwt.InvalidTokenError("SECRET_KEY not configured")
    return pyjwt.decode(token, SECRET_KEY, algorithms=[_ALGORITHM])


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def require_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return _decode(creds.credentials)
    except pyjwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    if not creds:
        return None
    try:
        return _decode(creds.credentials)
    except pyjwt.PyJWTError:
        return None
