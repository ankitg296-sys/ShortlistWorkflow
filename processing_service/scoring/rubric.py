import json
import logging

import anthropic
from pydantic import BaseModel, Field, model_validator

logger = logging.getLogger(__name__)

_RUBRIC_SYSTEM = """\
You are an expert recruiter building a structured scoring rubric.
Given a job description and a recruiter's prompt, produce a JSON array of scoring criteria.

Rules:
- 4 to 6 criteria total
- Each criterion has: name (short label), description (what to look for), weight (0.0–1.0)
- Weights must sum to exactly 1.0
- Focus on skills and experience that can be verified from a CV
- Avoid criteria that require subjective judgement or information not in a CV

Return ONLY a JSON array. No prose, no markdown fences.

Example output:
[
  {"name": "Python proficiency", "description": "Evidence of Python use in projects or roles", "weight": 0.35},
  {"name": "System design", "description": "Experience designing or architecting systems", "weight": 0.30},
  {"name": "Leadership", "description": "Team lead or mentoring experience", "weight": 0.20},
  {"name": "Communication", "description": "Written communication: blogs, docs, open-source", "weight": 0.15}
]"""


class Criterion(BaseModel):
    name: str
    description: str
    weight: float = Field(ge=0.0, le=1.0)


class Rubric(BaseModel):
    criteria: list[Criterion]

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "Rubric":
        total = sum(c.weight for c in self.criteria)
        if not (0.99 <= total <= 1.01):
            raise ValueError(f"Criterion weights must sum to 1.0, got {total:.3f}")
        return self


async def build_rubric(
    prompt: str,
    jd_text: str,
    weights: dict[str, float] | None,
    client: anthropic.AsyncAnthropic,
    model: str,
) -> list[Criterion]:
    """
    One model call: JD + recruiter prompt → validated scoring criteria.
    If `weights` is provided the model is asked to honour them; otherwise it chooses.
    """
    weight_hint = ""
    if weights:
        lines = "\n".join(f"  - {k}: {v}" for k, v in weights.items())
        weight_hint = f"\n\nThe recruiter wants these approximate weights:\n{lines}\nAdjust to sum to 1.0 if needed."

    user_content = (
        f"Job description:\n{jd_text}\n\n"
        f"Recruiter prompt:\n{prompt}"
        f"{weight_hint}"
    )

    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=_RUBRIC_SYSTEM,
        messages=[{"role": "user", "content": user_content}],
    )

    raw = response.content[0].text.strip()

    try:
        data = json.loads(raw)
        rubric = Rubric(criteria=[Criterion(**c) for c in data])
        logger.info("built rubric with %d criteria", len(rubric.criteria))
        return rubric.criteria
    except Exception as exc:
        logger.error("rubric builder failed to parse model output: %s\nRaw: %s", exc, raw)
        raise ValueError(f"Rubric builder returned invalid JSON: {exc}") from exc
