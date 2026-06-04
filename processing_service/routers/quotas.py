"""Quota and rate limit endpoints — P5."""
import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Annotated

from ..db import get_supabase
from ..dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/quotas", tags=["quotas"])


class QuotaInfo(BaseModel):
    org_id: str
    concurrent_searches: int
    concurrent_searches_limit: int
    candidates_this_month: int
    candidates_this_month_limit: int
    searches_this_month: int
    searches_this_month_limit: int


@router.get("/", response_model=QuotaInfo)
async def get_quotas(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> QuotaInfo:
    """
    Return quota usage for this org.
    Limits: 10 concurrent searches, 50,000 candidates/month, 100 searches/month.
    """
    supabase = get_supabase()
    org_id = current_user.org_id
    now = datetime.now(timezone.utc)
    month_start = (now - timedelta(days=30)).isoformat()

    # Count concurrent (running/pending) searches
    concurrent = (
        supabase.table("searches")
        .select("id")
        .eq("org_id", org_id)
        .in_("status", ["pending", "running"])
        .execute()
    )
    concurrent_count = len(concurrent.data) if concurrent.data else 0

    # Count this month's searches
    searches_month = (
        supabase.table("searches")
        .select("id")
        .eq("org_id", org_id)
        .gte("created_at", month_start)
        .execute()
    )
    searches_count = len(searches_month.data) if searches_month.data else 0

    # Count this month's candidates
    candidates_month = (
        supabase.table("candidates")
        .select("id")
        .eq("org_id", org_id)
        .gte("created_at", month_start)
        .execute()
    )
    candidates_count = len(candidates_month.data) if candidates_month.data else 0

    return QuotaInfo(
        org_id=org_id,
        concurrent_searches=concurrent_count,
        concurrent_searches_limit=10,
        candidates_this_month=candidates_count,
        candidates_this_month_limit=50000,
        searches_this_month=searches_count,
        searches_this_month_limit=100,
    )


def check_quotas_before_search(supabase, org_id: str) -> str | None:
    """
    Check if org exceeds any quotas before starting a search.
    Returns error message if quota exceeded, None otherwise.
    """
    now = datetime.now(timezone.utc)
    month_start = (now - timedelta(days=30)).isoformat()

    concurrent = (
        supabase.table("searches")
        .select("id")
        .eq("org_id", org_id)
        .in_("status", ["pending", "running"])
        .execute()
    )
    if len(concurrent.data) >= 10:
        return "Max 10 concurrent searches. Wait for one to complete."

    searches_month = (
        supabase.table("searches")
        .select("id")
        .eq("org_id", org_id)
        .gte("created_at", month_start)
        .execute()
    )
    if len(searches_month.data) >= 100:
        return "Reached 100 searches/month limit. Contact support."

    return None
