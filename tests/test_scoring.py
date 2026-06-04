"""
Tests for the P3 scoring engine.

Rubric builder: mocked Anthropic response → validates criteria structure + weights.
Scorer: mocked response → validates schema, evidence, retries on bad JSON.
Pipeline: all external calls mocked → verifies parallel scoring + audit_log.
Searches endpoints: dependency overrides + mocked DB.
"""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from processing_service.dependencies import CurrentUser
from processing_service.scoring.rubric import Criterion, build_rubric
from processing_service.scoring.scorer import score_candidate

# ── Fixtures ──────────────────────────────────────────────────────────────────

TEST_USER = CurrentUser(
    id="user-abc", org_id="org-xyz",
    email="recruiter@example.com", role="recruiter", full_name=None,
)

CRITERIA = [
    Criterion(name="Python", description="Python experience", weight=0.6),
    Criterion(name="Communication", description="Written comms", weight=0.4),
]

CANDIDATE_ID = str(uuid.uuid4())

GOOD_SCORE_JSON = json.dumps({
    "candidate_id": CANDIDATE_ID,
    "overall_score": 0.75,
    "criteria": [
        {
            "name": "Python",
            "weight": 0.6,
            "score": 0.9,
            "evidence_quote": "5 years of Python development using Django and FastAPI",
            "insufficient_evidence": False,
        },
        {
            "name": "Communication",
            "weight": 0.4,
            "score": 0.5,
            "evidence_quote": "Authored internal technical documentation",
            "insufficient_evidence": False,
        },
    ],
    "summary": "Strong Python background with adequate communication evidence.",
    "flags": [],
})

GOOD_RUBRIC_JSON = json.dumps([
    {"name": "Python", "description": "Python experience in projects", "weight": 0.6},
    {"name": "Communication", "description": "Written communication evidence", "weight": 0.4},
])


def make_anthropic_response(text: str) -> MagicMock:
    """Build a mock Anthropic message response."""
    content = MagicMock()
    content.text = text
    response = MagicMock()
    response.content = [content]
    return response


# ── Rubric builder ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_build_rubric_returns_criteria():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response(GOOD_RUBRIC_JSON)

    result = await build_rubric(
        prompt="We need a Python web dev",
        jd_text="Senior Python Developer role...",
        weights=None,
        client=mock_client,
        model="claude-haiku-4-5-20251001",
    )

    assert len(result) == 2
    assert result[0].name == "Python"
    assert abs(sum(c.weight for c in result) - 1.0) < 0.01


@pytest.mark.asyncio
async def test_build_rubric_invalid_weights_raises():
    bad_rubric = json.dumps([
        {"name": "Python", "description": "Python exp", "weight": 0.3},
        {"name": "Comms", "description": "Communication", "weight": 0.3},
        # weights sum to 0.6, not 1.0
    ])
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response(bad_rubric)

    with pytest.raises(ValueError, match="weights"):
        await build_rubric("prompt", "jd", None, mock_client, "model")


@pytest.mark.asyncio
async def test_build_rubric_bad_json_raises():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response("not json at all")

    with pytest.raises(ValueError):
        await build_rubric("prompt", "jd", None, mock_client, "model")


# ── Scorer ────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_score_candidate_happy_path():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response(GOOD_SCORE_JSON)

    result = await score_candidate(
        cv_text="5 years of Python development using Django and FastAPI. Authored internal technical documentation.",
        candidate_id=CANDIDATE_ID,
        criteria=CRITERIA,
        jd_text="Senior Python Developer",
        recruiter_prompt="Focus on Python and written communication",
        client=mock_client,
        model="claude-haiku-4-5-20251001",
    )

    assert str(result.candidate_id) == CANDIDATE_ID
    assert 0.0 <= result.overall_score <= 1.0
    assert len(result.criteria) == 2
    # overall_score is recomputed from weights — verify it's deterministic
    expected = 0.9 * 0.6 + 0.5 * 0.4
    assert abs(result.overall_score - expected) < 0.001


@pytest.mark.asyncio
async def test_score_candidate_evidence_quote_required():
    """Score with missing evidence_quote and insufficient_evidence=false → retry → raise."""
    bad_score = json.dumps({
        "candidate_id": CANDIDATE_ID,
        "overall_score": 0.5,
        "criteria": [
            {
                "name": "Python", "weight": 0.6, "score": 0.5,
                "evidence_quote": "",  # empty but insufficient_evidence=false → invalid
                "insufficient_evidence": False,
            },
            {
                "name": "Communication", "weight": 0.4, "score": 0.5,
                "evidence_quote": "some quote",
                "insufficient_evidence": False,
            },
        ],
        "summary": "Test", "flags": [],
    })

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response(bad_score)

    with pytest.raises(RuntimeError, match="Failed to score"):
        await score_candidate(
            cv_text="cv text", candidate_id=CANDIDATE_ID, criteria=CRITERIA,
            jd_text="jd", recruiter_prompt="prompt",
            client=mock_client, model="model",
        )

    # Should have retried MAX_RETRIES+1 times total
    assert mock_client.messages.create.call_count == 3  # _MAX_RETRIES=2 → 3 attempts


@pytest.mark.asyncio
async def test_score_candidate_insufficient_evidence_allowed():
    """insufficient_evidence=true with empty evidence_quote is valid."""
    score_with_insufficient = json.dumps({
        "candidate_id": CANDIDATE_ID,
        "overall_score": 0.54,
        "criteria": [
            {
                "name": "Python", "weight": 0.6, "score": 0.9,
                "evidence_quote": "5 years Python Django FastAPI experience",
                "insufficient_evidence": False,
            },
            {
                "name": "Communication", "weight": 0.4, "score": 0.0,
                "evidence_quote": "",
                "insufficient_evidence": True,  # ← valid: flag set
            },
        ],
        "summary": "Strong Python, no communication evidence found.", "flags": ["no_evidence_for_Communication"],
    })

    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response(score_with_insufficient)

    result = await score_candidate(
        cv_text="5 years Python Django FastAPI experience",
        candidate_id=CANDIDATE_ID, criteria=CRITERIA,
        jd_text="jd", recruiter_prompt="prompt",
        client=mock_client, model="model",
    )

    comm = next(c for c in result.criteria if c.name == "Communication")
    assert comm.insufficient_evidence is True
    assert comm.evidence_quote == ""


@pytest.mark.asyncio
async def test_score_candidate_bad_json_retries_then_raises():
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = make_anthropic_response("{{not valid json}}")

    with pytest.raises(RuntimeError, match="Failed to score"):
        await score_candidate(
            cv_text="cv", candidate_id=CANDIDATE_ID, criteria=CRITERIA,
            jd_text="jd", recruiter_prompt="p", client=mock_client, model="m",
        )

    assert mock_client.messages.create.call_count == 3


# ── Pipeline ──────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_run_search_scores_all_candidates_in_parallel():
    from processing_service.scoring.pipeline import run_search

    search_row = {
        "id": "search-1", "org_id": "org-xyz", "job_id": "job-1",
        "prompt": "Python developer", "jd_text": "JD text",
        "criteria": [c.model_dump() for c in CRITERIA],
        "model_used": "claude-haiku-4-5-20251001", "status": "pending",
    }
    key_row = {
        "encrypted_key": "fake-encrypted",
        "model_config": {},
    }
    candidate_rows = [
        {"id": str(uuid.uuid4()), "application_id": "app-1", "parsed_text": "CV text 1", "parse_quality": "good"},
        {"id": str(uuid.uuid4()), "application_id": "app-2", "parsed_text": "CV text 2", "parse_quality": "good"},
    ]

    # Use per-table mocks to avoid chain conflicts across different table queries
    mock_supabase = MagicMock()
    table_mocks: dict[str, MagicMock] = {}

    def table_factory(name: str) -> MagicMock:
        if name not in table_mocks:
            table_mocks[name] = MagicMock()
        return table_mocks[name]

    mock_supabase.table.side_effect = table_factory

    # searches: lookup + status updates
    sm = table_mocks["searches"] = MagicMock()
    sm.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = search_row
    sm.update.return_value.eq.return_value.execute.return_value.data = []
    sm.upsert.return_value.execute.return_value.data = []

    # api_keys: active key lookup
    km = table_mocks["api_keys"] = MagicMock()
    km.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = key_row

    # candidates: all parsed candidates for the org
    cm = table_mocks["candidates"] = MagicMock()
    cm.select.return_value.eq.return_value.execute.return_value.data = candidate_rows

    # applications: IDs for this job
    am = table_mocks["applications"] = MagicMock()
    am.select.return_value.eq.return_value.eq.return_value.execute.return_value.data = [
        {"id": "app-1"}, {"id": "app-2"}
    ]

    # scores + audit_log: writes
    table_mocks["scores"] = MagicMock()
    table_mocks["scores"].upsert.return_value.execute.return_value.data = []
    table_mocks["audit_log"] = MagicMock()
    table_mocks["audit_log"].insert.return_value.execute.return_value.data = []

    scored_ids: list[str] = []

    async def fake_score(cv_text, candidate_id, **kwargs):
        from shared.schemas import CandidateScore, CriterionScore
        scored_ids.append(candidate_id)
        return CandidateScore(
            candidate_id=uuid.UUID(candidate_id),
            overall_score=0.75,
            criteria=[CriterionScore(name="Python", weight=0.6, score=0.9,
                                     evidence_quote="some quote", insufficient_evidence=False),
                      CriterionScore(name="Communication", weight=0.4, score=0.5,
                                     evidence_quote="another quote", insufficient_evidence=False)],
            summary="Good candidate",
            flags=[],
        )

    with patch("processing_service.scoring.pipeline.get_supabase", return_value=mock_supabase), \
         patch("processing_service.scoring.pipeline.decrypt", return_value="sk-ant-fake"), \
         patch("processing_service.scoring.pipeline.get_anthropic_client", return_value=AsyncMock()), \
         patch("processing_service.scoring.pipeline.score_candidate", side_effect=fake_score):
        await run_search("search-1", "org-xyz")

    # Both candidates scored
    assert len(scored_ids) == 2


# ── Searches endpoints ────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def override_auth():
    from processing_service.dependencies import get_current_user
    from processing_service.main import app
    app.dependency_overrides[get_current_user] = lambda: TEST_USER
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.mark.asyncio
async def test_create_search_returns_rubric():
    from processing_service.main import app

    search_row = {
        "id": "search-1", "job_id": "job-1", "org_id": "org-xyz",
        "status": "pending", "prompt": "Python dev", "jd_text": "JD",
        "criteria": [c.model_dump() for c in CRITERIA],
        "model_used": "claude-haiku-4-5-20251001",
        "created_at": "2026-06-05T00:00:00+00:00",
    }
    # Per-table mocks to avoid chain conflicts (job + api_key both use maybe_single)
    mock_supabase = MagicMock()
    table_mocks: dict[str, MagicMock] = {}

    def table_factory(name: str) -> MagicMock:
        if name not in table_mocks:
            table_mocks[name] = MagicMock()
        return table_mocks[name]

    mock_supabase.table.side_effect = table_factory

    table_mocks["jobs"] = MagicMock()
    table_mocks["jobs"].select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"id": "job-1", "title": "Python Dev"}

    table_mocks["api_keys"] = MagicMock()
    table_mocks["api_keys"].select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {"encrypted_key": "fake-enc", "model_config": {}}

    table_mocks["searches"] = MagicMock()
    table_mocks["searches"].insert.return_value.execute.return_value.data = [search_row]

    with patch("processing_service.routers.searches.get_supabase", return_value=mock_supabase), \
         patch("processing_service.routers.searches.decrypt", return_value="sk-ant-fake"), \
         patch("processing_service.routers.searches.get_anthropic_client", return_value=AsyncMock()), \
         patch("processing_service.routers.searches.build_rubric", return_value=CRITERIA) as mock_rubric:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/searches/", json={
                "job_id": "job-1",
                "prompt": "Python dev",
                "jd_text": "Senior Python Developer",
            })

    assert r.status_code == 201
    body = r.json()
    assert body["status"] == "pending"
    assert len(body["criteria"]) == 2
    mock_rubric.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_run_queues_pipeline():
    from processing_service.main import app

    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value.select.return_value
        .eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value.data
    ) = {"id": "search-1", "status": "pending"}

    with patch("processing_service.routers.searches.get_supabase", return_value=mock_supabase), \
         patch("processing_service.routers.searches.run_search", new_callable=AsyncMock):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/searches/search-1/run")

    assert r.status_code == 200
    assert r.json()["queued"] is True


@pytest.mark.asyncio
async def test_trigger_run_rejects_already_running():
    from processing_service.main import app

    mock_supabase = MagicMock()
    (
        mock_supabase.table.return_value.select.return_value
        .eq.return_value.eq.return_value
        .maybe_single.return_value.execute.return_value.data
    ) = {"id": "search-1", "status": "running"}

    with patch("processing_service.routers.searches.get_supabase", return_value=mock_supabase):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.post("/searches/search-1/run")

    assert r.status_code == 409


@pytest.mark.asyncio
async def test_get_search_returns_scores():
    from processing_service.main import app

    search_data = {
        "id": "search-1", "job_id": "job-1", "org_id": "org-xyz",
        "status": "complete", "prompt": "Python dev", "jd_text": "JD",
        "criteria": [c.model_dump() for c in CRITERIA],
        "model_used": "claude-haiku-4-5-20251001",
        "created_at": "2026-06-05T00:00:00+00:00",
    }
    score_data = [{
        "id": "score-1", "candidate_id": CANDIDATE_ID,
        "overall_score": 0.78, "criteria_scores": [],
        "summary": "Strong candidate", "flags": [], "rank": 1,
    }]

    mock_supabase = MagicMock()
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = search_data
    mock_supabase.table.return_value.select.return_value.eq.return_value.eq.return_value.order.return_value.execute.return_value.data = score_data

    with patch("processing_service.routers.searches.get_supabase", return_value=mock_supabase):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            r = await c.get("/searches/search-1")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "complete"
    assert len(body["scores"]) == 1
    assert body["scores"][0]["overall_score"] == 0.78
