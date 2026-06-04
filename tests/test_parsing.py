"""
Tests for the P2 parsing pipeline.

Normaliser: pure-function tests, no mocking needed.
Extractor: pdfplumber/OCR mocked at module level; DOCX uses a real in-memory document.
Pipeline: DB + Storage mocked; extract/normalise patched to control quality.
"""
import io
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from processing_service.parsing.normaliser import normalise
from processing_service.parsing.extractor import ParseResult, extract


# ── Normaliser ────────────────────────────────────────────────────────────────


def test_normalise_empty_string():
    assert normalise("") == ""


def test_normalise_strips_surrounding_whitespace():
    assert normalise("  hello world  ") == "hello world"


def test_normalise_collapses_excess_blank_lines():
    text = "Section A\n\n\n\n\nSection B"
    result = normalise(text)
    assert "Section A" in result
    assert "Section B" in result
    assert "\n\n\n" not in result  # at most one blank line between sections


def test_normalise_strips_trailing_whitespace_per_line():
    result = normalise("line one   \nline two  \n")
    for line in result.splitlines():
        assert not line.endswith(" ")


def test_normalise_removes_null_bytes():
    result = normalise("hello\x00world")
    assert "\x00" not in result
    assert "hello" in result
    assert "world" in result


def test_normalise_removes_control_chars_keeps_newlines():
    result = normalise("line1\x01\x02line2\nline3")
    assert "\x01" not in result
    assert "\x02" not in result
    assert "line1" in result
    assert "line3" in result


def test_normalise_preserves_readable_text():
    cv = "John Smith\nSenior Python Developer\n\nExperience:\n- 5 years Django\n- AWS certified"
    result = normalise(cv)
    assert "John Smith" in result
    assert "Django" in result
    assert "AWS" in result


# ── Extractor: PDF ────────────────────────────────────────────────────────────


def _make_pdf_mock(text: str):
    """Build a pdfplumber context manager mock that returns `text` from one page."""
    mock_page = MagicMock()
    mock_page.extract_text.return_value = text
    mock_pdf = MagicMock()
    mock_pdf.__enter__ = MagicMock(return_value=mock_pdf)
    mock_pdf.__exit__ = MagicMock(return_value=False)
    mock_pdf.pages = [mock_page]
    return mock_pdf


def test_extract_pdf_good_text():
    long_text = "Senior Python Developer with Django and AWS experience. " * 5  # well over 100 chars
    mock_pdf = _make_pdf_mock(long_text)

    with patch("processing_service.parsing.extractor.pdfplumber") as mock_lib:
        mock_lib.open.return_value = mock_pdf
        result = extract(b"fake-pdf-bytes", "cv.pdf")

    assert result.quality == "good"
    assert long_text in result.text
    assert result.metadata["method"] == "pdfplumber"


def test_extract_pdf_short_text_triggers_ocr_fallback():
    """pdfplumber returns < 100 chars → OCR attempted."""
    mock_pdf = _make_pdf_mock("tiny")  # < 100 chars

    ocr_text = "John Smith Software Engineer Python AWS React 5 years experience " * 3
    mock_image = MagicMock()

    with patch("processing_service.parsing.extractor.pdfplumber") as mock_lib, \
         patch("processing_service.parsing.extractor._pdf2images", return_value=[mock_image]), \
         patch("processing_service.parsing.extractor.pytesseract") as mock_tess:
        mock_lib.open.return_value = mock_pdf
        mock_tess.image_to_string.return_value = ocr_text
        result = extract(b"fake-pdf-bytes", "cv.pdf")

    assert result.quality == "good"
    assert result.metadata["method"] == "ocr"


def test_extract_pdf_ocr_unavailable_marks_low_confidence():
    """pdfplumber returns empty AND OCR is unavailable → low_confidence."""
    mock_pdf = _make_pdf_mock("")

    with patch("processing_service.parsing.extractor.pdfplumber") as mock_lib, \
         patch("processing_service.parsing.extractor._HAS_OCR", False):
        mock_lib.open.return_value = mock_pdf
        result = extract(b"fake-pdf-bytes", "cv.pdf")

    assert result.quality in ("low_confidence", "failed")
    assert result.metadata.get("reason") == "ocr_unavailable"


def test_extract_pdf_pdfplumber_exception_falls_back_to_ocr():
    """If pdfplumber raises, OCR is tried next."""
    ocr_text = "Fallback OCR text from a scanned document with lots of words here. " * 3

    with patch("processing_service.parsing.extractor.pdfplumber") as mock_lib, \
         patch("processing_service.parsing.extractor._pdf2images", return_value=[MagicMock()]), \
         patch("processing_service.parsing.extractor.pytesseract") as mock_tess:
        mock_lib.open.side_effect = Exception("corrupt PDF")
        mock_tess.image_to_string.return_value = ocr_text
        result = extract(b"bad-pdf-bytes", "corrupt.pdf")

    assert result.quality == "good"
    assert result.metadata["method"] == "ocr"


def test_extract_unsupported_extension():
    result = extract(b"some bytes", "photo.png")
    assert result.quality == "failed"
    assert "unsupported" in result.metadata.get("reason", "")


# ── Extractor: DOCX ──────────────────────────────────────────────────────────


def _make_test_docx(text: str) -> bytes:
    """Create a minimal real DOCX in memory."""
    from docx import Document
    doc = Document()
    doc.add_paragraph(text)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_extract_docx_good_text():
    cv_text = "Alice Johnson — Senior Data Scientist. Skills: Python, SQL, TensorFlow. " * 3
    docx_bytes = _make_test_docx(cv_text)

    result = extract(docx_bytes, "cv.docx")

    assert result.quality == "good"
    assert "Alice Johnson" in result.text
    assert result.metadata["method"] == "python-docx"


def test_extract_docx_short_text_low_confidence():
    docx_bytes = _make_test_docx("Hi")  # < 100 chars
    result = extract(docx_bytes, "short.docx")
    assert result.quality == "low_confidence"


# ── Pipeline ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pipeline_upserts_candidates_row():
    """Happy path: application found, CV downloaded, parsed, candidates row upserted."""
    from processing_service.parsing.pipeline import parse_application

    app_row = {
        "id": "app-abc",
        "org_id": "org-xyz",
        "job_id": "job-123",
        "cv_storage_path": "org-xyz/job-123/app-abc.pdf",
        "cv_filename": "resume.pdf",
        "status": "received",
    }

    mock_client = MagicMock()
    # Application lookup
    (
        mock_client.table.return_value
        .select.return_value.eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value.data
    ) = app_row
    # Storage download
    mock_client.storage.from_.return_value.download.return_value = b"fake-cv-bytes"
    # All updates/upserts return empty data (we don't assert on them here)
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []
    mock_client.table.return_value.upsert.return_value.execute.return_value.data = []

    good_result = ParseResult(
        text="John Smith Senior Engineer Python Django AWS " * 5,
        quality="good",
        metadata={"method": "pdfplumber"},
    )

    with patch("processing_service.parsing.pipeline.get_supabase", return_value=mock_client), \
         patch("processing_service.parsing.pipeline.extract", return_value=good_result), \
         patch("processing_service.parsing.pipeline.normalise", side_effect=lambda t: t):
        await parse_application("app-abc", "org-xyz")

    # Verify upsert was called with correct fields
    upsert_call = mock_client.table.return_value.upsert.call_args
    upsert_data = upsert_call[0][0]
    assert upsert_data["application_id"] == "app-abc"
    assert upsert_data["parse_quality"] == "good"
    assert upsert_data["org_id"] == "org-xyz"


@pytest.mark.asyncio
async def test_pipeline_application_not_found():
    """If the application row is missing, pipeline exits silently."""
    from processing_service.parsing.pipeline import parse_application

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value.eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value.data
    ) = None  # not found

    with patch("processing_service.parsing.pipeline.get_supabase", return_value=mock_client):
        await parse_application("missing-app", "org-xyz")  # must not raise

    # No update or upsert should have been called
    mock_client.table.return_value.update.assert_not_called()


@pytest.mark.asyncio
async def test_pipeline_marks_error_on_extraction_failure():
    """If extraction raises unexpectedly, application status is set to 'error'."""
    from processing_service.parsing.pipeline import parse_application

    app_row = {
        "id": "app-abc", "org_id": "org-xyz", "job_id": "job-123",
        "cv_storage_path": "path/cv.pdf", "cv_filename": "cv.pdf", "status": "received",
    }

    mock_client = MagicMock()
    (
        mock_client.table.return_value
        .select.return_value.eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value.data
    ) = app_row
    mock_client.storage.from_.return_value.download.side_effect = Exception("storage error")

    update_calls: list[dict] = []
    def capture_update(data):
        update_calls.append(data)
        return mock_client.table.return_value.update.return_value
    mock_client.table.return_value.update.side_effect = capture_update
    mock_client.table.return_value.update.return_value.eq.return_value.execute.return_value.data = []

    with patch("processing_service.parsing.pipeline.get_supabase", return_value=mock_client):
        await parse_application("app-abc", "org-xyz")  # must not raise

    statuses = [c.get("status") for c in update_calls]
    assert "error" in statuses


# ── Internal endpoint: background task wired ─────────────────────────────────


@pytest.mark.asyncio
async def test_internal_event_queues_parse_task():
    """application.received event triggers parse_application as a background task."""
    from processing_service.main import app
    from httpx import ASGITransport, AsyncClient

    TEST_TOKEN = "test-internal-token-for-routing-tests"

    with patch(
        "processing_service.routers.internal.parse_application",
        new_callable=lambda: lambda *a, **kw: AsyncMock(),
    ):
        with patch(
            "processing_service.routers.internal.parse_application"
        ) as mock_parse:
            mock_parse.return_value = None
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                r = await c.post(
                    "/internal/events",
                    json={
                        "event": "application.received",
                        "org_id": "org-xyz",
                        "job_id": "job-123",
                        "application_id": "app-abc",
                    },
                    headers={"Authorization": f"Bearer {TEST_TOKEN}"},
                )

    assert r.status_code == 200
    assert r.json() == {"received": True}
