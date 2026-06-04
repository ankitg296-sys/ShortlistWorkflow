"""Compliance and data deletion endpoints — P5."""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Annotated

from ..config import get_settings
from ..db import get_supabase
from ..dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/compliance", tags=["compliance"])


class DataDeletionRequest(BaseModel):
    confirmation: str  # User must type "DELETE ALL DATA" to confirm


class AuditLogEntry(BaseModel):
    id: str
    org_id: str
    search_id: str | None
    event_type: str
    payload: dict
    created_at: str


@router.get("/audit-log", response_model=list[AuditLogEntry])
async def get_audit_log(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    days: int = 90,
) -> list[AuditLogEntry]:
    """
    Return immutable audit log for this org (last N days).
    Includes all searches, key operations, deletions.
    """
    supabase = get_supabase()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    rows = (
        supabase.table("audit_log")
        .select("*")
        .eq("org_id", current_user.org_id)
        .gte("created_at", cutoff)
        .order("created_at", desc=True)
        .execute()
        .data
    )

    return [AuditLogEntry(**r) for r in rows]


@router.delete("/data", status_code=status.HTTP_204_NO_CONTENT)
async def delete_org_data(
    body: DataDeletionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """
    Permanently delete all org data (searches, candidates, scores, applications, keys).
    Requires explicit confirmation: confirmation="DELETE ALL DATA".
    Logs to audit_log before deletion.
    """
    if body.confirmation != "DELETE ALL DATA":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Confirmation must be exactly "DELETE ALL DATA"',
        )

    supabase = get_supabase()
    org_id = current_user.org_id

    # Log the deletion request before it happens
    supabase.table("audit_log").insert({
        "org_id": org_id,
        "event_type": "org_data_deletion_requested",
        "payload": {
            "requested_by": current_user.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }).execute()

    # Delete all org data (CASCADE via RLS policies or explicit delete)
    supabase.table("searches").delete().eq("org_id", org_id).execute()
    supabase.table("scores").delete().eq("org_id", org_id).execute()
    supabase.table("candidates").delete().eq("org_id", org_id).execute()
    supabase.table("applications").delete().eq("org_id", org_id).execute()
    supabase.table("jobs").delete().eq("org_id", org_id).execute()
    supabase.table("api_keys").delete().eq("org_id", org_id).execute()

    # Log the completion
    supabase.table("audit_log").insert({
        "org_id": org_id,
        "event_type": "org_data_deletion_completed",
        "payload": {
            "deleted_by": current_user.id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    }).execute()

    logger.info("org %s data deleted by user %s", org_id, current_user.id)
