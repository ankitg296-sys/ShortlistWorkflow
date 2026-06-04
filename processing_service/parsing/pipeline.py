import logging

from ..db import get_supabase
from .extractor import extract
from .normaliser import normalise

logger = logging.getLogger(__name__)


async def parse_application(application_id: str, org_id: str) -> None:
    """
    Full parse pipeline for one application. Designed to run as a BackgroundTask.

    Fetch application → download CV from Storage → extract → normalise
    → upsert candidates row → update application status.
    Never raises — all errors are logged and the application status is set to "error".
    """
    supabase = get_supabase()

    # 1. Fetch application row
    app_result = (
        supabase.table("applications")
        .select("id, org_id, job_id, cv_storage_path, cv_filename, status")
        .eq("id", application_id)
        .eq("org_id", org_id)
        .maybe_single()
        .execute()
    )
    if app_result.data is None:
        logger.error("parse_application: application %s not found in org %s", application_id, org_id)
        return

    app = app_result.data

    # 2. Mark as in-progress
    supabase.table("applications").update({"status": "parsing"}).eq("id", application_id).execute()

    try:
        # 3. Download CV bytes from Supabase Storage
        file_bytes: bytes = supabase.storage.from_("cvs").download(app["cv_storage_path"])

        # 4. Extract text
        result = extract(file_bytes, app["cv_filename"])

        # 5. Normalise
        clean_text = normalise(result.text)

        # 6. Upsert candidates row (idempotent — safe to re-parse)
        supabase.table("candidates").upsert(
            {
                "org_id": org_id,
                "application_id": application_id,
                "parsed_text": clean_text,
                "parse_quality": result.quality,
                "parse_metadata": result.metadata,
            },
            on_conflict="application_id",
        ).execute()

        # 7. Update application status
        final_status = "parsed" if result.quality != "failed" else "error"
        supabase.table("applications").update({"status": final_status}).eq("id", application_id).execute()

        logger.info(
            "parsed application=%s quality=%s chars=%d",
            application_id, result.quality, len(clean_text),
        )

    except Exception as exc:
        logger.error("parse_application failed for %s: %s", application_id, exc)
        supabase.table("applications").update({"status": "error"}).eq("id", application_id).execute()
