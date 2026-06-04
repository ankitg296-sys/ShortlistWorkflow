import json
import logging
from uuid import UUID

import anthropic

from shared.schemas import CandidateScore, CriterionScore
from .rubric import Criterion

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2

_SCORING_SYSTEM = """\
You are a fair, evidence-based CV screener. Score a single candidate against a hiring rubric.

Rules you must follow:
- Score ONLY the candidate whose CV is in the user message. Never reference other candidates.
- Every score must be backed by a verbatim quote from this CV — copy it exactly.
- If a criterion cannot be assessed from this CV, set insufficient_evidence to true and use an empty string for evidence_quote.
- overall_score is the weighted average of per-criterion scores.
- Be conservative: do not infer or invent qualifications not present in the CV.

Return ONLY valid JSON matching this schema — no prose, no markdown fences:
{
  "candidate_id": "<uuid>",
  "overall_score": 0.0,
  "criteria": [
    {
      "name": "<criterion name>",
      "weight": 0.0,
      "score": 0.0,
      "evidence_quote": "<verbatim text from CV or empty string>",
      "insufficient_evidence": false
    }
  ],
  "summary": "<2-3 sentence evidence-grounded rationale>",
  "flags": ["<optional flag strings>"]
}"""


def _build_scoring_prompt(
    candidate_id: str,
    cv_text: str,
    criteria: list[Criterion],
    jd_text: str,
    recruiter_prompt: str,
) -> list[dict]:
    """
    Returns the messages list for a single scoring call.
    The system message (rubric + JD) is prompt-cached; the user message (CV) is not.
    """
    # Shared context — cached across all candidates in the same search
    shared_context = (
        f"Job description:\n{jd_text}\n\n"
        f"Recruiter instructions:\n{recruiter_prompt}\n\n"
        f"Scoring rubric:\n"
        + "\n".join(
            f"  - {c.name} (weight {c.weight:.2f}): {c.description}"
            for c in criteria
        )
    )

    return [
        {
            "role": "user",
            "content": [
                # Prompt-cache the shared rubric/JD across the whole search batch
                {
                    "type": "text",
                    "text": shared_context,
                    "cache_control": {"type": "ephemeral"},
                },
                # Per-candidate CV — NOT cached (unique per call)
                {
                    "type": "text",
                    "text": (
                        f"Candidate ID: {candidate_id}\n\n"
                        f"CV:\n{cv_text}\n\n"
                        "Return the JSON score for this candidate only."
                    ),
                },
            ],
        }
    ]


async def score_candidate(
    cv_text: str,
    candidate_id: str,
    criteria: list[Criterion],
    jd_text: str,
    recruiter_prompt: str,
    client: anthropic.AsyncAnthropic,
    model: str,
) -> CandidateScore:
    """
    Score a single candidate CV against the rubric.
    One model call — NEVER called with more than one candidate's CV.
    Retries up to _MAX_RETRIES times on invalid JSON before raising.
    """
    messages = _build_scoring_prompt(candidate_id, cv_text, criteria, jd_text, recruiter_prompt)
    last_exc: Exception = RuntimeError("no attempts made")

    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = await client.messages.create(
                model=model,
                max_tokens=2048,
                system=_SCORING_SYSTEM,
                messages=messages,
                extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
            )
            raw = response.content[0].text.strip()
            return _parse_score(raw, candidate_id, criteria)

        except (ValueError, KeyError) as exc:
            last_exc = exc
            logger.warning(
                "scoring attempt %d/%d failed for candidate %s: %s",
                attempt + 1, _MAX_RETRIES + 1, candidate_id, exc,
            )

    raise RuntimeError(
        f"Failed to score candidate {candidate_id} after {_MAX_RETRIES + 1} attempts"
    ) from last_exc


def _parse_score(raw: str, candidate_id: str, criteria: list[Criterion]) -> CandidateScore:
    """Parse and validate the model's JSON output against the CandidateScore schema."""
    data = json.loads(raw)  # raises ValueError on bad JSON

    # Force candidate_id to match what we sent (model must not substitute)
    data["candidate_id"] = candidate_id

    # Validate each criterion entry
    parsed_criteria = []
    criteria_by_name = {c.name.lower(): c for c in criteria}

    for item in data.get("criteria", []):
        # evidence_quote must be present (can be empty string only if insufficient_evidence=True)
        quote = item.get("evidence_quote", "")
        insufficient = item.get("insufficient_evidence", False)
        if not insufficient and not quote:
            raise ValueError(
                f"Criterion '{item.get('name')}' has no evidence_quote but insufficient_evidence=false"
            )
        parsed_criteria.append(CriterionScore(**item))

    # Recompute overall_score deterministically from weights × scores
    # (do not trust the model's arithmetic)
    crit_map = {c.name.lower(): c for c in criteria}
    overall = sum(
        cs.score * crit_map[cs.name.lower()].weight
        for cs in parsed_criteria
        if cs.name.lower() in crit_map
    )

    return CandidateScore(
        candidate_id=UUID(candidate_id),
        overall_score=round(overall, 4),
        criteria=parsed_criteria,
        summary=data.get("summary", ""),
        flags=data.get("flags", []),
    )
