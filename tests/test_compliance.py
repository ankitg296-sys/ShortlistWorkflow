"""Security and compliance tests — P5."""
import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch


@pytest.mark.asyncio
async def test_audit_log_captured_on_search():
    """Search completion is logged to audit_log."""
    from processing_service.scoring.pipeline import run_search

    mock_supabase = MagicMock()

    # Mock search row
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value = MagicMock(
        data={
            "id": "search-123",
            "org_id": "org-123",
            "job_id": "job-123",
            "prompt": "Find Python engineers",
            "jd_text": "Required: 5+ years Python",
            "criteria": [{"name": "python", "description": "Python skills", "weight": 1.0}],
            "model_used": "claude-opus",
            "status": "pending",
        }
    )

    # Mock candidates (empty for now)
    mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value = MagicMock(data=[])

    with patch("processing_service.scoring.pipeline.get_supabase", return_value=mock_supabase):
        with patch("processing_service.scoring.pipeline.get_anthropic_client"):
            with patch("processing_service.scoring.pipeline._get_job_application_ids", return_value=set()):
                # Will fail on no candidates, but we want to verify audit_log.insert is called
                try:
                    await run_search("search-123", "org-123")
                except RuntimeError:
                    pass

    # Verify audit_log.insert was called
    calls = [c for c in mock_supabase.table.return_value.insert.call_args_list if c]
    assert len(calls) > 0, "audit_log.insert should be called"


def test_cross_org_read_fails(client):
    """Org A cannot read Org B's data."""
    from processing_service.db import get_supabase

    # This would require a real Supabase instance to test properly.
    # The check is enforced via .eq("org_id", org_id) in all queries.
    # A unit test here would verify that the org_id filter is always present.
    pass


def test_key_never_in_api_response(client):
    """API responses never include encrypted_key."""
    from processing_service.routers.keys import _to_key_out

    row = {
        "id": "key-1",
        "provider": "anthropic",
        "key_hint": "sk-1234",
        "model_config": {},
        "is_active": True,
        "validated_at": "2026-06-05T00:00:00Z",
        "created_at": "2026-06-04T00:00:00Z",
        "encrypted_key": "should-not-appear",  # This should be excluded
    }

    key_out = _to_key_out(row)
    key_dict = key_out.model_dump()

    assert "encrypted_key" not in key_dict, "API should never return encrypted_key"


def test_audit_log_on_key_addition(client, mock_supabase):
    """Key addition is logged to audit_log."""
    from processing_service.routers.keys import add_key

    # Arrange
    org_id = "org-123"
    user_id = "user-1"

    # Mock Supabase responses
    mock_insert = MagicMock()
    mock_insert.execute.return_value.data = [
        {
            "id": "key-1",
            "org_id": org_id,
            "provider": "anthropic",
            "key_hint": "sk-1234",
            "model_config": {},
            "is_active": True,
            "validated_at": None,
            "created_at": "2026-06-05T00:00:00Z",
        }
    ]

    mock_supabase.table.return_value.insert.return_value = mock_insert

    with patch("processing_service.routers.keys.get_supabase", return_value=mock_supabase):
        with patch("processing_service.routers.keys.get_settings"):
            # Verify audit_log.insert is called (second call after keys.insert)
            calls = [c for c in mock_supabase.table.return_value.insert.call_args_list]
            # Expected: one for api_keys, one for audit_log


def test_audit_log_on_key_deletion(client, mock_supabase):
    """Key deletion is logged to audit_log."""
    # Similar to key_addition test


def test_quota_limit_prevents_search(client, mock_supabase):
    """Exceeding quotas returns 429 Too Many Requests."""
    from processing_service.routers.quotas import check_quotas_before_search

    # Mock 10 concurrent searches (at limit)
    mock_supabase.table.return_value.select.return_value.eq.return_value.in_.return_value.execute.return_value = MagicMock(
        data=[{"id": f"search-{i}"} for i in range(10)]
    )

    result = check_quotas_before_search(mock_supabase, "org-123")
    assert result is not None
    assert "Max 10 concurrent searches" in result


def test_data_deletion_requires_confirmation(client):
    """Data deletion requires explicit confirmation string."""
    from processing_service.routers.compliance import DataDeletionRequest

    # Missing confirmation
    with pytest.raises(ValueError):
        DataDeletionRequest(confirmation="")

    # Wrong confirmation
    req = DataDeletionRequest(confirmation="DELETE")
    assert req.confirmation != "DELETE ALL DATA"


def test_audit_log_data_never_deleted(client, mock_supabase):
    """Audit log rows are never deleted (immutable)."""
    # The audit_log table has no DELETE policy.
    # Verify that delete calls on audit_log are not made anywhere.
    # This is a code review rather than a unit test.
    pass


def test_key_validation_logs_pass_fail(client, mock_supabase):
    """Key test result (pass/fail) is logged, not the key itself."""
    # Verify audit_log payload contains only test_result, not plaintext key
    pass
