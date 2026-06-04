import os
import uuid
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from ..db import get_supabase
from ..limiter import limiter
from ..publisher import publish_application_received

router = APIRouter(prefix="/apply", tags=["apply"])

_MAX_FILE_BYTES = 10 * 1024 * 1024  # 10 MB

_ALLOWED_EXT = {".pdf", ".docx"}
_ALLOWED_MIME = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}


class JobInfo(BaseModel):
    id: str
    title: str
    description: str | None


class ApplicationOut(BaseModel):
    application_id: str
    job_id: str
    status: str


@router.get("/{token}", response_model=JobInfo)
async def get_apply_page(token: str) -> JobInfo:
    """Return job info for the apply form. Public — no auth required."""
    row = (
        get_supabase()
        .table("jobs")
        .select("id, title, description, status")
        .eq("apply_link_token", token)
        .maybe_single()
        .execute()
    )
    if row.data is None or row.data["status"] != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobInfo(
        id=row.data["id"],
        title=row.data["title"],
        description=row.data.get("description"),
    )


@router.post("/{token}", response_model=ApplicationOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def submit_application(
    request: Request,  # required by slowapi
    token: str,
    candidate_name: Annotated[str, Form()],
    candidate_email: Annotated[str, Form()],
    cv_file: Annotated[UploadFile, File()],
) -> ApplicationOut:
    """
    Candidate submits name, email, and CV.
    Public — no auth, no API keys anywhere in this service.
    """
    supabase = get_supabase()

    # Resolve job from token
    job_row = (
        supabase.table("jobs")
        .select("id, org_id, status")
        .eq("apply_link_token", token)
        .maybe_single()
        .execute()
    )
    if job_row.data is None or job_row.data["status"] != "active":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    job = job_row.data

    # Validate file type
    ext = os.path.splitext((cv_file.filename or "").lower())[1]
    content_type = cv_file.content_type or ""
    if ext not in _ALLOWED_EXT and content_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Only PDF and DOCX files are accepted",
        )

    # Validate file size
    file_bytes = await cv_file.read()
    if len(file_bytes) > _MAX_FILE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 10 MB limit",
        )

    # Upload to Supabase Storage
    application_id = str(uuid.uuid4())
    storage_path = f"{job['org_id']}/{job['id']}/{application_id}{ext or '.pdf'}"

    supabase.storage.from_("cvs").upload(
        path=storage_path,
        file=file_bytes,
        file_options={"content-type": content_type or "application/octet-stream"},
    )

    # Create application row
    app_row = (
        supabase.table("applications")
        .insert(
            {
                "id": application_id,
                "org_id": job["org_id"],
                "job_id": job["id"],
                "candidate_name": candidate_name,
                "candidate_email": candidate_email,
                "cv_storage_path": storage_path,
                "cv_filename": cv_file.filename or f"cv{ext}",
                "status": "received",
            }
        )
        .execute()
        .data[0]
    )

    # Route to processing-service (best-effort — never fails the submission)
    await publish_application_received(
        org_id=job["org_id"],
        job_id=job["id"],
        application_id=application_id,
    )

    return ApplicationOut(
        application_id=app_row["id"],
        job_id=app_row["job_id"],
        status=app_row["status"],
    )
