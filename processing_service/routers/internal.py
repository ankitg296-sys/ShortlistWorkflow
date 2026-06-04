import hmac
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from ..config import get_settings
from ..parsing.pipeline import parse_application

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)

_bearer = HTTPBearer()


class IncomingEvent(BaseModel):
    event: str
    org_id: str
    job_id: str
    application_id: str


def _verify_internal_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(_bearer)],
) -> None:
    """Validate the shared service-to-service token. Uses compare_digest to prevent timing attacks."""
    if not hmac.compare_digest(
        credentials.credentials, get_settings().internal_auth_token
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal auth token",
        )


@router.post(
    "/events",
    dependencies=[Depends(_verify_internal_token)],
    include_in_schema=False,  # service-to-service only — hide from public docs
)
async def receive_event(event: IncomingEvent, background_tasks: BackgroundTasks) -> dict:
    """
    Receive a routing event from intake-service.
    Acknowledges immediately; dispatches work as a background task.
    """
    logger.info(
        "received event=%s application=%s job=%s org=%s",
        event.event,
        event.application_id,
        event.job_id,
        event.org_id,
    )

    if event.event == "application.received":
        background_tasks.add_task(parse_application, event.application_id, event.org_id)

    return {"received": True}
