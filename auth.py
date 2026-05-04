import os
from typing import Optional

import httpx
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwk, jwt

SUPABASE_URL = os.getenv("SUPABASE_URL", "")

_bearer = HTTPBearer(auto_error=False)
_jwks_cache: Optional[dict] = None


async def _get_jwks() -> dict:
    global _jwks_cache
    if _jwks_cache:
        return _jwks_cache
    if not SUPABASE_URL:
        raise JWTError("SUPABASE_URL not configured")
    async with httpx.AsyncClient() as client:
        r = await client.get(f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json", timeout=5)
        r.raise_for_status()
        _jwks_cache = r.json()
    return _jwks_cache


async def _decode(token: str) -> dict:
    headers = jwt.get_unverified_headers(token)
    kid = headers.get("kid")

    jwks = await _get_jwks()
    matching = [k for k in jwks.get("keys", []) if k.get("kid") == kid]
    if not matching:
        # Key may have rotated — bust cache and retry once
        global _jwks_cache
        _jwks_cache = None
        jwks = await _get_jwks()
        matching = [k for k in jwks.get("keys", []) if k.get("kid") == kid]
    if not matching:
        raise JWTError(f"No matching signing key (kid={kid})")

    public_key = jwk.construct(matching[0])
    return jwt.decode(token, public_key, algorithms=["ES256"], audience="authenticated")


async def require_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        return await _decode(creds.credentials)
    except (JWTError, httpx.HTTPError):
        raise HTTPException(status_code=401, detail="Invalid token")


async def optional_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(_bearer),
) -> Optional[dict]:
    if not creds:
        return None
    try:
        return await _decode(creds.credentials)
    except (JWTError, httpx.HTTPError):
        return None
