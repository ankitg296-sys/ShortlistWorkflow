import logging

import httpx

from .config import get_settings

logger = logging.getLogger(__name__)


async def publish_application_received(
    org_id: str,
    job_id: str,
    application_id: str,
) -> None:
    """
    Notify processing-service that a new application is ready to process.

    Fire-and-forget: a delivery failure is logged but never propagates to the
    caller — the candidate's submission always succeeds regardless of routing.
    Swap this function body for a queue publish when the time comes; the
    interface stays the same.
    """
    settings = get_settings()
    payload = {
        "event": "application.received",
        "org_id": org_id,
        "job_id": job_id,
        "application_id": application_id,
    }
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.post(
                f"{settings.processing_service_url}/internal/events",
                json=payload,
                headers={"Authorization": f"Bearer {settings.internal_auth_token}"},
            )
            r.raise_for_status()
        logger.info(
            "routed event=application.received application=%s", application_id
        )
    except Exception:
        # Routing is best-effort — never fail the intake submission over this
        logger.warning(
            "failed to route event for application %s — processing-service may be unavailable",
            application_id,
        )
