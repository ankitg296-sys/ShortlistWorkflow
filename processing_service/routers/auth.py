from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict

from ..db import get_supabase
from ..dependencies import CurrentUser, TokenClaims, get_current_user, get_token_claims

router = APIRouter(prefix="/auth", tags=["auth"])


class SignupRequest(BaseModel):
    org_name: str
    full_name: str | None = None


class OrgOut(BaseModel):
    id: str
    name: str


class UserOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    org_id: str
    email: str
    role: str
    full_name: str | None
    org: OrgOut


@router.post("/signup", response_model=UserOut, status_code=status.HTTP_201_CREATED)
async def signup(
    body: SignupRequest,
    claims: Annotated[TokenClaims, Depends(get_token_claims)],
) -> UserOut:
    """
    Create an org and recruiter profile after Supabase Auth sign-up.
    Idempotent — returns the existing profile if called a second time.

    Client flow: Supabase Auth signUp() → JWT → POST /auth/signup
    """
    supabase = get_supabase()

    # Idempotency: return the existing profile without creating duplicates
    existing = (
        supabase.table("users")
        .select("id, org_id, email, role, full_name")
        .eq("id", claims.user_id)
        .maybe_single()
        .execute()
    )
    if existing.data:
        org = (
            supabase.table("orgs")
            .select("id, name")
            .eq("id", existing.data["org_id"])
            .single()
            .execute()
        )
        return UserOut(**existing.data, org=OrgOut(**org.data))

    # Create org row
    org_row = supabase.table("orgs").insert({"name": body.org_name}).execute().data[0]

    # Create user profile linked to the Supabase Auth UID
    user_row = (
        supabase.table("users")
        .insert(
            {
                "id": claims.user_id,
                "org_id": org_row["id"],
                "email": claims.email,
                "full_name": body.full_name,
                "role": "recruiter",
            }
        )
        .execute()
        .data[0]
    )

    return UserOut(
        id=user_row["id"],
        org_id=user_row["org_id"],
        email=user_row["email"],
        role=user_row["role"],
        full_name=user_row.get("full_name"),
        org=OrgOut(id=org_row["id"], name=org_row["name"]),
    )


@router.get("/me", response_model=UserOut)
async def me(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> UserOut:
    """Return the authenticated recruiter's profile and org."""
    org = (
        get_supabase()
        .table("orgs")
        .select("id, name")
        .eq("id", current_user.org_id)
        .single()
        .execute()
    )
    return UserOut(
        id=current_user.id,
        org_id=current_user.org_id,
        email=current_user.email,
        role=current_user.role,
        full_name=current_user.full_name,
        org=OrgOut(**org.data),
    )
