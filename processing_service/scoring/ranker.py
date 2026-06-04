import logging

logger = logging.getLogger(__name__)


def rank_scores(scores: list[dict]) -> list[dict]:
    """
    Sort scores by overall_score descending and assign 1-based ranks.
    Pure Python — no model call, no randomness. Ties broken by candidate_id (stable sort).
    Mutates the rank field on each dict and returns the sorted list.
    """
    sorted_scores = sorted(
        scores,
        key=lambda s: (-s["overall_score"], s["candidate_id"]),
    )
    for i, score in enumerate(sorted_scores, start=1):
        score["rank"] = i
    logger.info("ranked %d candidates", len(sorted_scores))
    return sorted_scores
