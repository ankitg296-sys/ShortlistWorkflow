from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from ..config import get_settings
from ..db import get_supabase
from ..dependencies import CurrentUser, get_current_user
from ..provider.client import get_anthropic_client
from ..scoring.pipeline import run_search
from ..scoring.rubric import Criterion, build_rubric
from ..vault.crypto import decrypt
from .quotas import check_quotas_before_search

router = APIRouter(prefix="/searches", tags=["searches"])


# ── Request / response models ─────────────────────────────────────────────────


class CreateSearchRequest(BaseModel):
    job_id: str
    prompt: str
    jd_text: str | None = None
    weights: dict[str, float] | None = None  # optional recruiter-supplied weight hints


class CriterionOut(BaseModel):
    name: str
    description: str
    weight: float


class SearchOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    job_id: str
    status: str
    prompt: str
    criteria: list[CriterionOut]
    model_used: str
    created_at: str


class ScoreOut(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    candidate_id: str
    overall_score: float
    criteria_scores: list[dict]
    summary: str
    flags: list[str]
    rank: int | None


class SearchDetailOut(SearchOut):
    scores: list[ScoreOut] = []


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post("/", response_model=SearchOut, status_code=status.HTTP_201_CREATED)
async def create_search(
    body: CreateSearchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SearchOut:
    """
    Build a scoring rubric from the JD + recruiter prompt and create a search row.
    Returns the rubric for the recruiter to review before triggering the run.
    """
    settings = get_settings()
    supabase = get_supabase()

    # Verify the job belongs to this org
    job = (
        supabase.table("jobs")
        .select("id, title")
        .eq("id", body.job_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if job.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    # Fetch org's active API key for rubric building
    key_row = (
        supabase.table("api_keys")
        .select("encrypted_key, model_config")
        .eq("org_id", current_user.org_id)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if key_row.data is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No active API key found. Add one via POST /keys/ first.",
        )

    plaintext_key = decrypt(key_row.data["encrypted_key"], settings.encryption_master_key)
    model = (key_row.data["model_config"] or {}).get("scoring_model") or settings.default_model
    client = get_anthropic_client(plaintext_key)

    # Build rubric
    criteria: list[Criterion] = await build_rubric(
        prompt=body.prompt,
        jd_text=body.jd_text or "",
        weights=body.weights,
        client=client,
        model=model,
    )

    # Persist search row (status=pending until /run is called)
    row = (
        supabase.table("searches")
        .insert(
            {
                "org_id": current_user.org_id,
                "job_id": body.job_id,
                "created_by": current_user.id,
                "prompt": body.prompt,
                "jd_text": body.jd_text,
                "criteria": [c.model_dump() for c in criteria],
                "model_used": model,
                "status": "pending",
            }
        )
        .execute()
        .data[0]
    )

    return SearchOut(**row)


@router.post("/{search_id}/run", response_model=dict)
async def trigger_run(
    search_id: str,
    background_tasks: BackgroundTasks,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict:
    """
    Kick off the scoring pipeline. Returns immediately; scoring runs in the background.
    Poll GET /searches/{id} for status and results.
    """
    supabase = get_supabase()

    # Check quotas before starting
    quota_error = check_quotas_before_search(supabase, current_user.org_id)
    if quota_error:
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=quota_error)

    row = (
        supabase.table("searches")
        .select("id, status")
        .eq("id", search_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if row.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    if row.data["status"] not in ("pending", "error"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Search is already {row.data['status']}",
        )

    background_tasks.add_task(run_search, search_id, current_user.org_id)
    return {"queued": True, "search_id": search_id}


@router.get("/{search_id}", response_model=SearchDetailOut)
async def get_search(
    search_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SearchDetailOut:
    """Return search status, rubric, and all scores (once complete)."""
    supabase = get_supabase()

    row = (
        supabase.table("searches")
        .select("*")
        .eq("id", search_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if row.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")

    scores = (
        supabase.table("scores")
        .select("id, candidate_id, overall_score, criteria_scores, summary, flags, rank")
        .eq("search_id", search_id)
        .eq("org_id", current_user.org_id)
        .order("rank", desc=False)
        .execute()
        .data
    )

    return SearchDetailOut(**row.data, scores=[ScoreOut(**s) for s in scores])


@router.get("/{search_id}/shortlist", response_model=list[ScoreOut])
async def get_shortlist(
    search_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    top_n: int = 10,
) -> list[ScoreOut]:
    """
    Return the top N ranked candidates from a completed search.
    Ordered by rank (1 = best). Includes evidence quotes and per-criterion breakdown.
    """
    if top_n < 1 or top_n > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="top_n must be between 1 and 100",
        )

    supabase = get_supabase()

    # Verify search belongs to org and is complete
    search = (
        supabase.table("searches")
        .select("id, status")
        .eq("id", search_id)
        .eq("org_id", current_user.org_id)
        .maybe_single()
        .execute()
    )
    if search.data is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search not found")
    if search.data["status"] != "complete":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Search is {search.data['status']}, not ready for shortlist yet",
        )

    scores = (
        supabase.table("scores")
        .select("id, candidate_id, overall_score, criteria_scores, summary, flags, rank")
        .eq("search_id", search_id)
        .eq("org_id", current_user.org_id)
        .order("rank", desc=False)
        .limit(top_n)
        .execute()
        .data
    )

    return [ScoreOut(**s) for s in scores]
