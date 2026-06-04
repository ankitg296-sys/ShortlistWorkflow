from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from processing_service.dependencies import CurrentUser

TEST_USER = CurrentUser(
    id="user-abc",
    org_id="org-xyz",
    email="recruiter@example.com",
    role="recruiter",
    full_name=None,
)

JOB_ROW = {
    "id": "job-123",
    "org_id": "org-xyz",
    "created_by": "user-abc",
    "title": "Python Developer",
    "description": "We need a Python dev",
    "apply_link_token": "tok_abc123def456",
    "status": "active",
    "created_at": "2026-06-05T00:00:00+00:00",
    "updated_at": "2026-06-05T00:00:00+00:00",
}


@pytest.fixture(autouse=True)
def override_auth():
    from processing_service.dependencies import get_current_user
    from processing_service.main import app

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_job_returns_token():
    from processing_service.main import app

    inserted: list[dict] = []

    def insert_side(data: dict):
        inserted.append(data)
        m = MagicMock()
        m.execute.return_value.data = [
            {**data, "id": "job-123", "status": "active", "created_at": "2026-06-05T00:00:00+00:00", "updated_at": "2026-06-05T00:00:00+00:00"}
        ]
        return m

    mock_client = MagicMock()
    mock_client.table.return_value.insert.side_effect = insert_side

    with patch("processing_service.routers.jobs.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/jobs/", json={"title": "Python Developer", "description": "We need a Python dev"})

    assert r.status_code == 201
    body = r.json()
    assert body["title"] == "Python Developer"
    assert len(body["apply_link_token"]) > 8  # non-trivial token
    assert inserted[0]["org_id"] == "org-xyz"
    assert inserted[0]["created_by"] == "user-abc"


@pytest.mark.asyncio
async def test_create_job_token_is_unique():
    """Two jobs get different tokens."""
    from processing_service.main import app

    tokens: list[str] = []

    def insert_side(data: dict):
        tokens.append(data["apply_link_token"])
        m = MagicMock()
        m.execute.return_value.data = [
            {**data, "id": f"job-{len(tokens)}", "status": "active", "created_at": "2026-06-05T00:00:00+00:00", "updated_at": "2026-06-05T00:00:00+00:00"}
        ]
        return m

    mock_client = MagicMock()
    mock_client.table.return_value.insert.side_effect = insert_side

    with patch("processing_service.routers.jobs.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/jobs/", json={"title": "Job A"})
            await c.post("/jobs/", json={"title": "Job B"})

    assert len(tokens) == 2
    assert tokens[0] != tokens[1]


@pytest.mark.asyncio
async def test_list_jobs():
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .order.return_value
        .execute.return_value.data
    ) = [JOB_ROW]

    with patch("processing_service.routers.jobs.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/jobs/")

    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["title"] == "Python Developer"


@pytest.mark.asyncio
async def test_get_job_detail_with_count():
    from processing_service.main import app

    mock_client = MagicMock()
    chain = mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value
    # Job lookup (via maybe_single)
    chain.maybe_single.return_value.execute.return_value.data = JOB_ROW
    # Application count (direct execute — same chain prefix, different terminus)
    chain.execute.return_value.data = [{"id": "app-1"}, {"id": "app-2"}]

    with patch("processing_service.routers.jobs.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/jobs/job-123")

    assert r.status_code == 200
    assert r.json()["application_count"] == 2


@pytest.mark.asyncio
async def test_get_job_not_found():
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute.return_value.data
    ) = None

    with patch("processing_service.routers.jobs.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/jobs/nonexistent")

    assert r.status_code == 404
