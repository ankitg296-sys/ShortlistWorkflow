from unittest.mock import MagicMock, patch

import jwt as pyjwt
import pytest
from httpx import ASGITransport, AsyncClient

# Must match the SUPABASE_JWT_SECRET set in conftest.py
TEST_JWT_SECRET = "test-jwt-secret-for-unit-tests-long-enough-for-hs256-alg!!"


def make_token(user_id: str = "user-abc", email: str = "recruiter@example.com") -> str:
    return pyjwt.encode(
        {"sub": user_id, "email": email, "aud": "authenticated"},
        TEST_JWT_SECRET,
        algorithm="HS256",
    )


def make_mock_client(
    user_row: dict | None = None,
    org_row: dict | None = None,
    user_insert_row: dict | None = None,
    org_insert_row: dict | None = None,
) -> MagicMock:
    """
    Build a MagicMock Supabase client with per-table routing so that
    table("users") and table("orgs") return independent mocks.
    """
    table_mocks: dict[str, MagicMock] = {}

    def table_factory(name: str) -> MagicMock:
        if name not in table_mocks:
            table_mocks[name] = MagicMock()
        return table_mocks[name]

    client = MagicMock()
    client.table.side_effect = table_factory

    users = table_factory("users")
    orgs = table_factory("orgs")

    # users: read via maybe_single (dependency + idempotency check)
    users.select.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = (
        user_row
    )
    # users: read via single (not used currently but wired for safety)
    users.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        user_row
    )
    # users: insert
    users.insert.return_value.execute.return_value.data = (
        [user_insert_row] if user_insert_row else []
    )

    # orgs: read via single
    orgs.select.return_value.eq.return_value.single.return_value.execute.return_value.data = (
        org_row
    )
    # orgs: insert
    orgs.insert.return_value.execute.return_value.data = (
        [org_insert_row] if org_insert_row else []
    )

    return client


# ── Error path tests (no DB mock needed) ────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_no_token():
    """No Authorization header → HTTPBearer raises 401."""
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/auth/me")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_me_invalid_token():
    """Garbage Bearer token → 401."""
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_signup_invalid_token():
    """Signup with a bad token → 401."""
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        r = await client.post(
            "/auth/signup",
            json={"org_name": "Acme"},
            headers={"Authorization": "Bearer bad"},
        )
    assert r.status_code == 401


# ── Happy-path tests (DB mocked) ────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_me_no_profile_returns_403():
    """Valid JWT but no user row in DB → 403 with helpful message."""
    from processing_service.main import app

    mock_client = make_mock_client(user_row=None)

    with patch("processing_service.dependencies.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/auth/me", headers={"Authorization": f"Bearer {make_token()}"}
            )

    assert r.status_code == 403
    assert "signup" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_me_returns_profile():
    """Valid JWT + user row → 200 with user and org data."""
    from processing_service.main import app

    user_row = {
        "id": "user-abc",
        "org_id": "org-xyz",
        "email": "recruiter@example.com",
        "role": "recruiter",
        "full_name": "Test Recruiter",
    }
    org_row = {"id": "org-xyz", "name": "Acme Recruiting"}
    mock_client = make_mock_client(user_row=user_row, org_row=org_row)

    with patch("processing_service.dependencies.get_supabase", return_value=mock_client), \
         patch("processing_service.routers.auth.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.get(
                "/auth/me", headers={"Authorization": f"Bearer {make_token()}"}
            )

    assert r.status_code == 200
    body = r.json()
    assert body["id"] == "user-abc"
    assert body["email"] == "recruiter@example.com"
    assert body["org"]["name"] == "Acme Recruiting"


@pytest.mark.asyncio
async def test_signup_creates_org_and_user():
    """New user: org + user profile are created; 201 returned."""
    from processing_service.main import app

    org_insert = {"id": "org-new", "name": "New Org"}
    user_insert = {
        "id": "user-abc",
        "org_id": "org-new",
        "email": "recruiter@example.com",
        "role": "recruiter",
        "full_name": "Test Recruiter",
    }
    # user_row=None → idempotency check finds nothing → creates new
    mock_client = make_mock_client(
        user_row=None,
        org_insert_row=org_insert,
        user_insert_row=user_insert,
    )

    with patch("processing_service.routers.auth.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/auth/signup",
                json={"org_name": "New Org", "full_name": "Test Recruiter"},
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "user-abc"
    assert body["org"]["id"] == "org-new"
    assert body["org"]["name"] == "New Org"


@pytest.mark.asyncio
async def test_signup_is_idempotent():
    """Calling signup again returns the existing profile without duplicating rows."""
    from processing_service.main import app

    existing_user = {
        "id": "user-abc",
        "org_id": "org-xyz",
        "email": "recruiter@example.com",
        "role": "recruiter",
        "full_name": "Test Recruiter",
    }
    existing_org = {"id": "org-xyz", "name": "Acme Recruiting"}
    # user_row is set → idempotency check finds it → returns immediately
    mock_client = make_mock_client(user_row=existing_user, org_row=existing_org)

    with patch("processing_service.routers.auth.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            r = await client.post(
                "/auth/signup",
                json={"org_name": "Acme Recruiting"},
                headers={"Authorization": f"Bearer {make_token()}"},
            )

    assert r.status_code == 201
    body = r.json()
    assert body["id"] == "user-abc"
    assert body["org"]["name"] == "Acme Recruiting"
    # Confirm no insert was attempted
    mock_client.table("orgs").insert.assert_not_called()
