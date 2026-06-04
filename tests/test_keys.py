from unittest.mock import MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from processing_service.dependencies import CurrentUser
from processing_service.vault.crypto import encrypt

# Must match ENCRYPTION_MASTER_KEY in tests/conftest.py
TEST_MASTER_KEY = "dGVzdGtleXRlc3RrZXl0ZXN0a2V5dGVzdGtleXRlc3Q="

TEST_USER = CurrentUser(
    id="user-abc",
    org_id="org-xyz",
    email="recruiter@example.com",
    role="recruiter",
    full_name=None,
)


@pytest.fixture(autouse=True)
def override_auth():
    """Bypass JWT/DB auth for all tests in this file."""
    from processing_service.dependencies import get_current_user
    from processing_service.main import app

    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def key_row_with_ciphertext():
    """A DB row containing an encrypted API key."""
    return {
        "id": "key-111",
        "org_id": "org-xyz",
        "provider": "anthropic",
        "encrypted_key": encrypt("sk-ant-real-key-7890", TEST_MASTER_KEY),
        "model_config": {},
    }


def make_key_meta_row(**overrides) -> dict:
    """A DB row as returned by list_keys (no encrypted_key column)."""
    row = {
        "id": "key-111",
        "provider": "anthropic",
        "key_hint": "7890",
        "model_config": {},
        "is_active": True,
        "validated_at": None,
        "created_at": "2026-06-05T00:00:00+00:00",
    }
    row.update(overrides)
    return row


# ── POST /keys/ ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_key_stores_ciphertext_not_plaintext():
    from processing_service.main import app

    inserted: list[dict] = []

    def insert_side_effect(data: dict):
        inserted.append(data)
        m = MagicMock()
        m.execute.return_value.data = [
            {
                **data,
                "id": "key-111",
                "is_active": True,
                "validated_at": None,
                "created_at": "2026-06-05T00:00:00+00:00",
            }
        ]
        return m

    mock_client = MagicMock()
    mock_client.table.return_value.insert.side_effect = insert_side_effect

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/keys/",
                json={"provider": "anthropic", "api_key": "sk-ant-real-key-7890"},
            )

    assert r.status_code == 201
    stored = inserted[0]
    # Plaintext must NOT be stored verbatim
    assert stored["encrypted_key"] != "sk-ant-real-key-7890"
    # Key hint is last 4 chars
    assert stored["key_hint"] == "7890"
    # Response must not expose the ciphertext
    assert "encrypted_key" not in r.json()


@pytest.mark.asyncio
async def test_add_key_unsupported_provider():
    from processing_service.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r = await c.post(
            "/keys/",
            json={"provider": "openai", "api_key": "sk-openai-key"},
        )
    assert r.status_code == 400


# ── GET /keys/ ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_list_keys_excludes_encrypted_key():
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.execute.return_value.data
    ) = [make_key_meta_row()]

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/keys/")

    assert r.status_code == 200
    for key in r.json():
        assert "encrypted_key" not in key
        assert key["key_hint"] == "7890"


# ── DELETE /keys/{key_id} ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_key_success():
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data
    ) = [make_key_meta_row()]

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete("/keys/key-111")

    assert r.status_code == 204


@pytest.mark.asyncio
async def test_delete_key_not_found():
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value.delete.return_value.eq.return_value.eq.return_value.execute.return_value.data
    ) = []

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.delete("/keys/key-ghost")

    assert r.status_code == 404


# ── POST /keys/{key_id}/test ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_test_key_returns_ok_true(key_row_with_ciphertext):
    from processing_service.main import app

    mock_client = MagicMock()
    # Lookup chain: select().eq().eq().maybe_single().execute()
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
    ) = key_row_with_ciphertext
    # Update chain: update().eq().eq().execute()
    (
        mock_client.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data
    ) = []

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client), \
         patch("processing_service.routers.keys.test_api_key", return_value=True):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/keys/key-111/test")

    assert r.status_code == 200
    assert r.json() == {"ok": True}
    # The raw key must never appear in the response
    assert "sk-ant" not in r.text


@pytest.mark.asyncio
async def test_test_key_returns_ok_false(key_row_with_ciphertext):
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
    ) = key_row_with_ciphertext

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client), \
         patch("processing_service.routers.keys.test_api_key", return_value=False):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/keys/key-111/test")

    assert r.status_code == 200
    assert r.json() == {"ok": False}


@pytest.mark.asyncio
async def test_test_key_not_found():
    from processing_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data
    ) = None

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/keys/key-ghost/test")

    assert r.status_code == 404
