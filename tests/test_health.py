import pytest
from httpx import ASGITransport, AsyncClient

from intake_service.main import app as intake_app
from processing_service.main import app as processing_app


@pytest.mark.asyncio
async def test_intake_health():
    async with AsyncClient(transport=ASGITransport(app=intake_app), base_url="http://test") as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "intake"}


@pytest.mark.asyncio
async def test_processing_health():
    async with AsyncClient(
        transport=ASGITransport(app=processing_app), base_url="http://test"
    ) as client:
        response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "processing"}
