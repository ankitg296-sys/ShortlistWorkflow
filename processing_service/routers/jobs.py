import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..db import get_supabase
from ..dependencies import CurrentUser, get_current_user

router = APIRouter(prefix="/jobs", tags=["jobs"])


class CreateJobRequest(BaseModel):
    title: str
    description: str | None = None


class JobOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    org_id: str
    title: str
    description: str | None
    apply_link_token: str
    status: str
    created_at: str
    application_count: int = 0


@router.post("/", response_model=JobOut, status_code=status.HTTP_201_CREATED)
async def create_job(
    body: CreateJobRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobOut:
    """Create a job and return a shareable apply-link token."""
    row = (
        get_supabase()
        .table("jobs")
        .insert(
            {
                "org_id": current_user.org_id,
                "created_by": current_user.id,
                "title": body.title,
                "description": body.description,
                "apply_link_token": secrets.token_urlsafe(16),
            }
        )
        .execute()
        .data[0]
    )
    return JobOut(**row, application_count=0)


@router.get("/", response_model=list[JobOut])
async def list_jobs(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> list[JobOut]:
    """List all active jobs for the org."""
    rows = (
        get_supabase()
        .table("jobs")
        .select("*")
        .eq("org_id", current_user.org_id)
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
        .data
    )
    return [JobOut(**row, application_count=0) for row in rows]


@router.get("/{job_id}", response_model=JobOut)
async def get_job(
    job_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> JobOut:
    """Job detail with application count."""
    supabase = get_supabase()

    row = (
        supabase.table("jobs")
        .select("*")
        .eq("id", job_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if row.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    apps = (
        supabase.table("applications")
        .select("id")
        .eq("job_id", job_id)
        .eq("org_id", current_user.org_id)
        .execute()
    )
    return JobOut(**row.data, application_count=len(apps.data))
