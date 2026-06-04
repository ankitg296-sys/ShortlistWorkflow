import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import auth as auth_router
from .routers import compliance as compliance_router
from .routers import internal as internal_router
from .routers import jobs as jobs_router
from .routers import keys as keys_router
from .routers import onboarding as onboarding_router
from .routers import quotas as quotas_router
from .routers import searches as searches_router

settings = get_settings()
logging.basicConfig(level=settings.log_level)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("processing-service starting")
    yield
    logger.info("processing-service stopped")


app = FastAPI(
    title="ShortList Processing Service",
    description="Private AI engine and recruiter dashboard. Holds the encrypted BYOK key vault.",
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


app.include_router(auth_router.router)
app.include_router(compliance_router.router)
app.include_router(keys_router.router)
app.include_router(jobs_router.router)
app.include_router(onboarding_router.router)
app.include_router(quotas_router.router)
app.include_router(searches_router.router)
app.include_router(internal_router.router)


@app.get("/health")
async def health():
    return {"status": "ok", "service": "processing"}
