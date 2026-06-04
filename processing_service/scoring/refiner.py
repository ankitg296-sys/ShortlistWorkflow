import json
import logging

import anthropic

from .rubric import Criterion

logger = logging.getLogger(__name__)

_REFINE_SYSTEM = """\
You are reviewing a pre-scored shortlist to confirm the final candidate ordering.
You have already seen each candidate's score and CV. Your job is to compare them
comparatively and return their IDs in your preferred order (best fit first).

Rules:
- Consider the scoring criteria and evidence carefully
- Look for differentiating evidence among close-scoring candidates
- Return ONLY a JSON array of candidate_id strings, ordered best to worst
- Include ALL candidate IDs provided — do not omit any
- No prose, no markdown, just the JSON array

Example: ["uuid-a", "uuid-c", "uuid-b"]"""


async def refine_top_n(
    top_candidates: list[dict],  # each: {candidate_id, overall_score, summary, cv_text}
    criteria: list[Criterion],
    jd_text: str,
    recruiter_prompt: str,
    client: anthropic.AsyncAnthropic,
    model: str,
    n: int = 15,
) -> list[str]:
    """
    One comparative model call over the top N candidates.
    Returns candidate_ids in refined order (best first).
    Falls back to score-based order on any failure — never crashes the pipeline.
    """
    candidates = top_candidates[:n]
    # Fallback: sort by score descending
    fallback = [c["candidate_id"] for c in sorted(candidates, key=lambda x: -x["overall_score"])]

    if len(candidates) <= 1:
        return fallback

    rubric_text = "\n".join(
        f"  - {c.name} (weight {c.weight:.2f}): {c.description}"
        for c in criteria
    )

    candidates_text = "\n\n".join(
        f"--- Candidate {c['candidate_id']} (score: {c['overall_score']:.3f}) ---\n"
        f"Summary: {c.get('summary', '')}\n\n"
        f"CV:\n{(c.get('cv_text') or '')[:3000]}"
        for c in candidates
    )

    user_content = (
        f"Job description:\n{jd_text}\n\n"
        f"Recruiter instructions:\n{recruiter_prompt}\n\n"
        f"Scoring criteria:\n{rubric_text}\n\n"
        f"Candidates to rank:\n{candidates_text}\n\n"
        "Return the candidate IDs in your preferred order (best fit first) as a JSON array."
    )

    try:
        response = await client.messages.create(
            model=model,
            max_tokens=512,
            system=_REFINE_SYSTEM,
            messages=[{"role": "user", "content": user_content}],
        )
        raw = response.content[0].text.strip()
        refined = json.loads(raw)

        if not isinstance(refined, list) or set(refined) != set(fallback):
            logger.warning("refiner returned unexpected IDs — using score-based order")
            return fallback

        logger.info("refine pass confirmed/adjusted ordering for %d candidates", len(refined))
        return refined

    except Exception as exc:
        logger.warning("refine pass failed (%s) — using score-based order", exc)
        return fallback
