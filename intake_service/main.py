import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .publisher import publish_application_received

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("intake-service starting")
    yield
    logger.info("intake-service stopped")


app = FastAPI(
    title="ShortList Intake Service",
    description="Candidate-facing application intake. Holds no API keys and does no AI work.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "intake"}


# P0 demo only — remove / replace with real candidate apply flow in P1
@app.post("/demo/submit")
async def demo_submit(
    org_id: str = "demo-org",
    job_id: str = "demo-job",
    application_id: str = "demo-application",
) -> dict:
    """Trigger a dummy routing event to prove the intake→processing transport works."""
    await publish_application_received(
        org_id=org_id,
        job_id=job_id,
        application_id=application_id,
    )
    return {"submitted": True, "org_id": org_id, "job_id": job_id, "application_id": application_id}
