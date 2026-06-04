import asyncio
import logging
from datetime import datetime, timezone

from ..db import get_supabase
from ..provider.client import get_anthropic_client
from ..vault.crypto import decrypt
from ..config import get_settings
from .rubric import Criterion
from .scorer import score_candidate

logger = logging.getLogger(__name__)


async def run_search(search_id: str, org_id: str) -> None:
    """
    Full scoring pipeline for one search. Runs as a BackgroundTask.

    1. Fetch search config + org API key
    2. Decrypt key, build Anthropic client
    3. Fetch all parsed candidates for the job
    4. Score every candidate in parallel (one model call each)
    5. Store score rows + audit_log
    6. Mark search complete
    """
    settings = get_settings()
    supabase = get_supabase()

    # 1. Fetch search row
    search_row = (
        supabase.table("searches")
        .select("id, org_id, job_id, prompt, jd_text, criteria, model_used, status")
        .eq("id", search_id)
        .eq("org_id", org_id)
        .maybe_single()
        .execute()
    )
    if search_row.data is None:
        logger.error("run_search: search %s not found", search_id)
        return

    search = search_row.data

    # Mark as running
    supabase.table("searches").update({
        "status": "running",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }).eq("id", search_id).execute()

    try:
        # 2. Fetch and decrypt the org's active API key
        key_row = (
            supabase.table("api_keys")
            .select("encrypted_key, model_config")
            .eq("org_id", org_id)
            .eq("is_active", True)
            .maybe_single()
            .execute()
        )
        if key_row.data is None:
            raise RuntimeError("No active API key found for org — add one via POST /keys/")

        plaintext_key = decrypt(key_row.data["encrypted_key"], settings.encryption_master_key)
        model = (
            (key_row.data["model_config"] or {}).get("scoring_model")
            or search["model_used"]
            or settings.default_model
        )
        client = get_anthropic_client(plaintext_key)

        # 3. Fetch all parsed candidates for this job
        candidates = (
            supabase.table("candidates")
            .select("id, application_id, parsed_text, parse_quality")
            .eq("org_id", org_id)
            .execute()
        )
        # Filter to candidates belonging to this job and with usable text
        app_ids = _get_job_application_ids(supabase, search["job_id"], org_id)
        scoreable = [
            c for c in candidates.data
            if c["application_id"] in app_ids and c["parse_quality"] != "failed"
            and c.get("parsed_text")
        ]

        if not scoreable:
            raise RuntimeError("No scoreable candidates found for this search")

        logger.info("run_search %s: scoring %d candidates", search_id, len(scoreable))

        # Rebuild Criterion objects from stored JSON
        criteria = [Criterion(**c) for c in search["criteria"]]

        # 4. Score all candidates in parallel
        tasks = [
            score_candidate(
                cv_text=c["parsed_text"],
                candidate_id=c["id"],
                criteria=criteria,
                jd_text=search["jd_text"] or "",
                recruiter_prompt=search["prompt"],
                client=client,
                model=model,
            )
            for c in scoreable
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 5. Store score rows
        scored = 0
        errors = 0
        for candidate, result in zip(scoreable, results):
            if isinstance(result, Exception):
                logger.error("candidate %s scoring failed: %s", candidate["id"], result)
                errors += 1
                continue
            supabase.table("scores").upsert(
                {
                    "org_id": org_id,
                    "search_id": search_id,
                    "candidate_id": str(result.candidate_id),
                    "overall_score": float(result.overall_score),
                    "criteria_scores": [cs.model_dump() for cs in result.criteria],
                    "summary": result.summary,
                    "flags": result.flags,
                },
                on_conflict="search_id,candidate_id",
            ).execute()
            scored += 1

        # 6. Write audit log
        supabase.table("audit_log").insert({
            "org_id": org_id,
            "search_id": search_id,
            "event_type": "search_complete",
            "payload": {
                "model": model,
                "candidates_scored": scored,
                "candidates_errored": errors,
                "prompt_preview": search["prompt"][:200],
            },
        }).execute()

        # 7. Mark complete
        supabase.table("searches").update({
            "status": "complete",
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", search_id).execute()

        logger.info(
            "run_search %s complete: %d scored, %d errors",
            search_id, scored, errors,
        )

    except Exception as exc:
        logger.error("run_search %s failed: %s", search_id, exc)
        supabase.table("searches").update({"status": "error"}).eq("id", search_id).execute()


def _get_job_application_ids(supabase, job_id: str, org_id: str) -> set[str]:
    rows = (
        supabase.table("applications")
        .select("id")
        .eq("job_id", job_id)
        .eq("org_id", org_id)
        .execute()
    )
    return {r["id"] for r in rows.data}
