from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

FAKE_PDF = b"%PDF-1.4 fake pdf content for testing"
FAKE_DOCX = b"PK\x03\x04fake docx content here"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

JOB_ROW = {
    "id": "job-123",
    "org_id": "org-xyz",
    "title": "Python Developer",
    "description": "We need a Python dev",
    "status": "active",
}

APP_ROW = {
    "id": "app-abc",
    "job_id": "job-123",
    "org_id": "org-xyz",
    "candidate_name": "Alice Smith",
    "candidate_email": "alice@example.com",
    "cv_storage_path": "org-xyz/job-123/app-abc.pdf",
    "cv_filename": "resume.pdf",
    "status": "received",
}


@pytest.fixture
def mock_supabase():
    client = MagicMock()
    # Job lookup (GET and POST both use maybe_single)
    (
        client.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute.return_value.data
    ) = JOB_ROW
    # Application insert
    client.table.return_value.insert.return_value.execute.return_value.data = [APP_ROW]
    # Storage upload
    client.storage.from_.return_value.upload.return_value = MagicMock()
    return client


# ── GET /apply/{token} ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_apply_page_valid_token(mock_supabase):
    from intake_service.main import app

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_supabase):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/apply/valid-token")

    assert r.status_code == 200
    body = r.json()
    assert body["title"] == "Python Developer"
    assert "id" in body
    assert "encrypted" not in str(body)  # no leakage of internal fields


@pytest.mark.asyncio
async def test_get_apply_page_unknown_token():
    from intake_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute.return_value.data
    ) = None

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/apply/bad-token")

    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_apply_page_closed_job():
    from intake_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute.return_value.data
    ) = {**JOB_ROW, "status": "closed"}

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/apply/closed-token")

    assert r.status_code == 404


# ── POST /apply/{token} ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_submit_valid_pdf(mock_supabase):
    from intake_service.main import app

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_supabase), \
         patch("intake_service.routers.apply.publish_application_received", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/apply/valid-token",
                files={"cv_file": ("resume.pdf", FAKE_PDF, "application/pdf")},
                data={"candidate_name": "Alice Smith", "candidate_email": "alice@example.com"},
            )

    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "received"
    assert "job_id" in body
    assert "application_id" in body


@pytest.mark.asyncio
async def test_submit_valid_docx(mock_supabase):
    from intake_service.main import app

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_supabase), \
         patch("intake_service.routers.apply.publish_application_received", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/apply/valid-token",
                files={"cv_file": ("resume.docx", FAKE_DOCX, DOCX_MIME)},
                data={"candidate_name": "Bob Jones", "candidate_email": "bob@example.com"},
            )

    assert r.status_code == 201


@pytest.mark.asyncio
async def test_submit_invalid_file_type(mock_supabase):
    from intake_service.main import app

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_supabase):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/apply/valid-token",
                files={"cv_file": ("photo.png", b"\x89PNG fake image", "image/png")},
                data={"candidate_name": "Alice", "candidate_email": "alice@example.com"},
            )

    assert r.status_code == 422
    assert "pdf" in r.json()["detail"].lower() or "docx" in r.json()["detail"].lower()


@pytest.mark.asyncio
async def test_submit_oversized_file(mock_supabase):
    from intake_service.main import app

    big_file = b"%PDF-1.4 " + b"x" * (10 * 1024 * 1024 + 1)  # 10 MB + 1 byte

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_supabase):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/apply/valid-token",
                files={"cv_file": ("big.pdf", big_file, "application/pdf")},
                data={"candidate_name": "Alice", "candidate_email": "alice@example.com"},
            )

    assert r.status_code == 413


@pytest.mark.asyncio
async def test_submit_publisher_called_once(mock_supabase):
    from intake_service.main import app

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_supabase), \
         patch("intake_service.routers.apply.publish_application_received", new_callable=AsyncMock) as mock_pub:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post(
                "/apply/valid-token",
                files={"cv_file": ("resume.pdf", FAKE_PDF, "application/pdf")},
                data={"candidate_name": "Alice", "candidate_email": "alice@example.com"},
            )

    mock_pub.assert_called_once()
    kwargs = mock_pub.call_args[1]
    assert kwargs["org_id"] == JOB_ROW["org_id"]
    assert kwargs["job_id"] == JOB_ROW["id"]
    assert "application_id" in kwargs


@pytest.mark.asyncio
async def test_submit_unknown_token():
    from intake_service.main import app

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value
        .eq.return_value
        .maybe_single.return_value
        .execute.return_value.data
    ) = None

    with patch("intake_service.routers.apply.get_supabase", return_value=mock_client):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post(
                "/apply/bad-token",
                files={"cv_file": ("resume.pdf", FAKE_PDF, "application/pdf")},
                data={"candidate_name": "Alice", "candidate_email": "alice@example.com"},
            )

    assert r.status_code == 404
