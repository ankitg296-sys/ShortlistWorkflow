"""Tests for ranking and refining — P4."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from processing_service.scoring.ranker import rank_scores
from processing_service.scoring.refiner import refine_top_n


# ── Ranker ────────────────────────────────────────────────────────────────────


def test_rank_scores_deterministic_sort():
    """Scores sorted by overall_score desc, ties broken by candidate_id."""
    id1, id2, id3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    scores = [
        {"candidate_id": id1, "overall_score": 0.7},
        {"candidate_id": id2, "overall_score": 0.9},
        {"candidate_id": id3, "overall_score": 0.7},
    ]
    result = rank_scores(scores)

    assert result[0]["rank"] == 1
    assert result[0]["overall_score"] == 0.9
    assert result[1]["rank"] == 2
    assert result[2]["rank"] == 3


def test_rank_scores_assigns_ranks_starting_at_one():
    """Ranks are 1-based, contiguous."""
    scores = [
        {"candidate_id": str(uuid.uuid4()), "overall_score": s}
        for s in [0.5, 0.7, 0.9, 0.6]
    ]
    result = rank_scores(scores)

    ranks = [s["rank"] for s in result]
    assert ranks == [1, 2, 3, 4]


def test_rank_scores_handles_ties():
    """Same score — broken by candidate_id (stable)."""
    id1, id2 = str(uuid.uuid4()), str(uuid.uuid4())
    scores = [
        {"candidate_id": id1, "overall_score": 0.7},
        {"candidate_id": id2, "overall_score": 0.7},
    ]
    result = rank_scores(scores)

    assert result[0]["rank"] == 1
    assert result[1]["rank"] == 2
    # Order deterministic due to candidate_id tie-break


def test_rank_scores_empty():
    """Empty list returns empty."""
    assert rank_scores([]) == []


# ── Refiner ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_refine_top_n_returns_reordered_ids():
    """Refiner returns candidate IDs in refined order."""
    import json
    ids = [str(uuid.uuid4()) for _ in range(5)]
    candidates = [
        {
            "candidate_id": cid,
            "overall_score": 0.7 + i * 0.05,
            "summary": f"Candidate {i}",
            "cv_text": f"CV text {i}",
        }
        for i, cid in enumerate(ids)
    ]

    refined_order = [ids[2], ids[0], ids[4], ids[1], ids[3]]
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps(refined_order))]  # JSON array
    )

    result = await refine_top_n(
        candidates, [], "jd", "prompt", mock_client, "model", n=5
    )

    assert result == refined_order


@pytest.mark.asyncio
async def test_refine_single_candidate_returns_as_is():
    """Only one candidate — no refine needed."""
    cid = str(uuid.uuid4())
    candidates = [
        {"candidate_id": cid, "overall_score": 0.8, "summary": "Solo", "cv_text": "cv"}
    ]
    mock_client = AsyncMock()

    result = await refine_top_n(
        candidates, [], "jd", "prompt", mock_client, "model", n=1
    )

    assert result == [cid]
    # Model should not be called
    mock_client.messages.create.assert_not_called()


@pytest.mark.asyncio
async def test_refine_bad_json_falls_back_to_score_order():
    """Model returns invalid JSON — fall back to score-based order."""
    ids = [str(uuid.uuid4()) for _ in range(3)]
    candidates = [
        {
            "candidate_id": ids[0],
            "overall_score": 0.9,
            "summary": "C0",
            "cv_text": "cv",
        },
        {
            "candidate_id": ids[1],
            "overall_score": 0.7,
            "summary": "C1",
            "cv_text": "cv",
        },
        {
            "candidate_id": ids[2],
            "overall_score": 0.8,
            "summary": "C2",
            "cv_text": "cv",
        },
    ]
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text="not json at all")]
    )

    result = await refine_top_n(
        candidates, [], "jd", "prompt", mock_client, "model", n=3
    )

    # Should fall back to score order (desc): 0.9, 0.8, 0.7
    assert result == [ids[0], ids[2], ids[1]]


@pytest.mark.asyncio
async def test_refine_mismatched_ids_falls_back():
    """Model returns different IDs than provided — fall back."""
    import json
    ids = [str(uuid.uuid4()) for _ in range(3)]
    candidates = [
        {
            "candidate_id": cid,
            "overall_score": 0.7 + i * 0.05,
            "summary": f"C{i}",
            "cv_text": "cv",
        }
        for i, cid in enumerate(ids)
    ]
    other_id = str(uuid.uuid4())
    mock_client = AsyncMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(text=json.dumps([ids[0], other_id, ids[1]]))]  # Wrong ID
    )

    result = await refine_top_n(
        candidates, [], "jd", "prompt", mock_client, "model", n=3
    )

    # Fall back to score order (desc): 0.85, 0.80, 0.75
    assert result == [ids[2], ids[1], ids[0]]


@pytest.mark.asyncio
async def test_refine_model_exception_falls_back():
    """Model call raises exception — fall back gracefully."""
    ids = [str(uuid.uuid4()) for _ in range(3)]
    candidates = [
        {"candidate_id": cid, "overall_score": s, "summary": f"C{i}", "cv_text": "cv"}
        for i, (cid, s) in enumerate(zip(ids, [0.9, 0.7, 0.8]))
    ]
    mock_client = AsyncMock()
    mock_client.messages.create.side_effect = Exception("API error")

    result = await refine_top_n(
        candidates, [], "jd", "prompt", mock_client, "model", n=3
    )

    # Fall back to score order
    assert result == [ids[0], ids[2], ids[1]]
