"""P6: Pilot onboarding flow."""
import logging
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..db import get_supabase
from ..dependencies import CurrentUser, get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])


class OnboardingStep(BaseModel):
    step: int  # 1=add key, 2=create job, 3=share link, 4=run search
    completed: bool
    completed_at: str | None = None


class OnboardingStatus(BaseModel):
    org_id: str
    onboarding_complete: bool
    steps: list[OnboardingStep]
    first_search_id: str | None = None


class FeedbackSubmission(BaseModel):
    search_id: str
    rating: int  # 1-5
    comment: str = ""
    would_use_again: bool


@router.get("/status", response_model=OnboardingStatus)
async def get_onboarding_status(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> OnboardingStatus:
    """
    Return onboarding progress: which steps completed.
    Steps: 1=add key, 2=create job, 3=share link, 4=run search.
    """
    supabase = get_supabase()
    org_id = current_user.org_id

    # Check step 1: API key added
    keys = (
        supabase.table("api_keys")
        .select("id, created_at")
        .eq("org_id", org_id)
        .execute()
    )
    step_1_done = len(keys.data) > 0 if keys.data else False

    # Check step 2: Job created
    jobs = (
        supabase.table("jobs")
        .select("id, created_at")
        .eq("org_id", org_id)
        .execute()
    )
    step_2_done = len(jobs.data) > 0 if jobs.data else False

    # Check step 3: Application received (link shared + candidate applied)
    apps = (
        supabase.table("applications")
        .select("id, created_at")
        .eq("org_id", org_id)
        .execute()
    )
    step_3_done = len(apps.data) > 0 if apps.data else False

    # Check step 4: Search run (first search exists)
    searches = (
        supabase.table("searches")
        .select("id, created_at")
        .eq("org_id", org_id)
        .order("created_at", desc=True)
        .limit(1)
        .execute()
    )
    step_4_done = len(searches.data) > 0 if searches.data else False
    first_search = searches.data[0]["id"] if step_4_done else None

    steps = [
        OnboardingStep(step=1, completed=step_1_done, completed_at=keys.data[0]["created_at"] if step_1_done and keys.data else None),
        OnboardingStep(step=2, completed=step_2_done, completed_at=jobs.data[0]["created_at"] if step_2_done and jobs.data else None),
        OnboardingStep(step=3, completed=step_3_done, completed_at=apps.data[0]["created_at"] if step_3_done and apps.data else None),
        OnboardingStep(step=4, completed=step_4_done, completed_at=searches.data[0]["created_at"] if step_4_done else None),
    ]

    return OnboardingStatus(
        org_id=org_id,
        onboarding_complete=all(s.completed for s in steps),
        steps=steps,
        first_search_id=first_search,
    )


@router.post("/feedback", status_code=status.HTTP_204_NO_CONTENT)
async def submit_feedback(
    body: FeedbackSubmission,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> None:
    """
    Submit feedback after a search (pilot iteration loop).
    Rating: 1-5 (1=poor, 5=excellent).
    Stored in audit_log for review.
    """
    supabase = get_supabase()

    # Verify search belongs to org
    search = (
        supabase.table("searches")
        .select("id")
        .eq("id", body.search_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if search.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")

    # Log feedback
    supabase.table("audit_log").insert({
        "org_id": current_user.org_id,
        "search_id": body.search_id,
        "event_type": "pilot_feedback",
        "payload": {
            "rating": body.rating,
            "comment": body.comment,
            "would_use_again": body.would_use_again,
            "submitted_by": current_user.id,
        },
    }).execute()

    logger.info(
        "pilot feedback: org=%s search=%s rating=%d",
        current_user.org_id, body.search_id, body.rating,
    )
