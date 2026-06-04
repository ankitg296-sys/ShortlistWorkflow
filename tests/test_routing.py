from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

# Must match INTERNAL_AUTH_TOKEN set in conftest.py
TEST_INTERNAL_TOKEN = "test-internal-token-for-routing-tests"

VALID_EVENT = {
    "event": "application.received",
    "org_id": "org-abc",
    "job_id": "job-xyz",
    "application_id": "app-123",
}


def make_httpx_mock(raise_error: Exception | None = None):
    """
    Build a mock for `async with httpx.AsyncClient(...) as client`.
    Returns (mock_class, mock_client) where mock_class replaces httpx.AsyncClient.
    """
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    mock_client = AsyncMock()
    if raise_error:
        mock_client.post.side_effect = raise_error
    else:
        mock_client.post.return_value = mock_response

    mock_class = MagicMock()
    mock_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_class.return_value.__aexit__ = AsyncMock(return_value=False)

    return mock_class, mock_client


# ── Publisher unit tests ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_publisher_sends_correct_payload():
    """Publisher posts the right event payload with the shared auth token."""
    from intake_service.publisher import publish_application_received

    mock_class, mock_client = make_httpx_mock()

    with patch("intake_service.publisher.httpx.AsyncClient", mock_class):
        await publish_application_received(
            org_id="org-abc", job_id="job-xyz", application_id="app-123"
        )

    mock_client.post.assert_called_once()
    _, kwargs = mock_client.post.call_args
    assert kwargs["json"]["event"] == "application.received"
    assert kwargs["json"]["application_id"] == "app-123"
    assert kwargs["json"]["org_id"] == "org-abc"
    assert kwargs["headers"]["Authorization"] == f"Bearer {TEST_INTERNAL_TOKEN}"


@pytest.mark.asyncio
async def test_publisher_posts_to_processing_service_url():
    """Publisher targets the configured processing-service URL."""
    from intake_service.publisher import publish_application_received

    mock_class, mock_client = make_httpx_mock()

    with patch("intake_service.publisher.httpx.AsyncClient", mock_class):
        await publish_application_received("org-1", "job-2", "app-3")

    url = mock_client.post.call_args[0][0]
    assert "/internal/events" in url


@pytest.mark.asyncio
async def test_publisher_does_not_raise_on_connection_failure():
    """If processing-service is unreachable, the publisher swallows the error."""
    import httpx as httpx_lib
    from intake_service.publisher import publish_application_received

    mock_class, _ = make_httpx_mock(raise_error=httpx_lib.ConnectError("refused"))

    with patch("intake_service.publisher.httpx.AsyncClient", mock_class):
        # Must not raise — intake submissions must always succeed
        await publish_application_received("org-1", "job-2", "app-3")


@pytest.mark.asyncio
async def test_publisher_does_not_raise_on_http_error():
    """A non-2xx response from processing-service is also swallowed."""
    import httpx as httpx_lib
    from intake_service.publisher import publish_application_received

    mock_class, mock_client = make_httpx_mock()
    mock_client.post.return_value.raise_for_status.side_effect = httpx_lib.HTTPStatusError(
        "500", request=MagicMock(), response=MagicMock()
    )

    with patch("intake_service.publisher.httpx.AsyncClient", mock_class):
        await publish_application_received("org-1", "job-2", "app-3")


# ── /internal/events endpoint tests ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_internal_events_valid_token():
    """Valid token + valid payload → 200 {"received": true}."""
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/internal/events",
            json=VALID_EVENT,
            headers={"Authorization": f"Bearer {TEST_INTERNAL_TOKEN}"},
        )

    assert r.status_code == 200
    assert r.json() == {"received": True}


@pytest.mark.asyncio
async def test_internal_events_missing_token():
    """No Authorization header → 401."""
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post("/internal/events", json=VALID_EVENT)

    assert r.status_code == 401


@pytest.mark.asyncio
async def test_internal_events_wrong_token():
    """Wrong token → 401."""
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/internal/events",
            json=VALID_EVENT,
            headers={"Authorization": "Bearer wrong-token"},
        )

    assert r.status_code == 401
    assert "invalid" in r.json()["detail"].lower()


# ── End-to-end demo endpoint ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_demo_submit_calls_publisher():
    """POST /demo/submit triggers publish_application_received."""
    from intake_service.main import app

    with patch(
        "intake_service.main.publish_application_received", new_callable=AsyncMock
    ) as mock_pub:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/demo/submit")

    assert r.status_code == 200
    body = r.json()
    assert body["submitted"] is True
    mock_pub.assert_called_once_with(
        org_id="demo-org",
        job_id="demo-job",
        application_id="demo-application",
    )


@pytest.mark.asyncio
async def test_demo_submit_accepts_custom_ids():
    """Custom query params are forwarded to the publisher."""
    from intake_service.main import app

    with patch(
        "intake_service.main.publish_application_received", new_callable=AsyncMock
    ) as mock_pub:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/demo/submit",
                params={"org_id": "my-org", "job_id": "my-job", "application_id": "my-app"},
            )

    assert r.status_code == 200
    mock_pub.assert_called_once_with(
        org_id="my-org", job_id="my-job", application_id="my-app"
    )
