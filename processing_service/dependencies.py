from dataclasses import dataclass
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import get_settings
from .db import get_supabase

_bearer = HTTPBearer()


@dataclass
class TokenClaims:
    """Verified JWT claims only — no database lookup. Used at /auth/signup."""

    user_id: str
    email: str


@dataclass
class CurrentUser:
    """Authenticated recruiter with a completed org profile."""

    id: str
    org_id: str
    email: str
    role: str
    full_name: str | None


def _decode_supabase_jwt(token: str) -> dict:
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            audience="authenticated",
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")


async def get_token_claims(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> TokenClaims:
    """Verify the Supabase JWT without a DB lookup. Used for the initial signup endpoint."""
    payload = _decode_supabase_jwt(credentials.credentials)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token: missing sub"
        )
    return TokenClaims(user_id=user_id, email=payload.get("email", ""))


async def get_current_user(
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
) -> CurrentUser:
    """Verify JWT and load the recruiter profile. Raises 403 if signup not completed."""
    result = (
        get_supabase()
        .table("users")
        .select("id, org_id, email, role, full_name")
        .eq("id", claims.user_id)
        .maybe_single()
        .execute()
    )
    if result.data is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User profile not found. Complete signup via POST /auth/signup.",
        )
    return CurrentUser(**result.data)
