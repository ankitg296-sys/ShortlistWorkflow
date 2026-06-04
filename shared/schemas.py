from uuid import UUID

from pydantic import BaseModel, Field


class CriterionScore(BaseModel):
    name: str
    weight: float = Field(ge=0.0, le=1.0)
    score: float = Field(ge=0.0, le=1.0)
    evidence_quote: str  # must appear verbatim in the candidate's CV
    insufficient_evidence: bool


class CandidateScore(BaseModel):
    """Scoring output contract per SPEC §7.4. One instance per candidate per search."""

    candidate_id: UUID
    overall_score: float = Field(ge=0.0, le=1.0)
    criteria: list[CriterionScore]
    summary: str
    flags: list[str] = []
