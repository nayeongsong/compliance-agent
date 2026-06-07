from __future__ import annotations

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field


class EvaluationStatus(StrEnum):
    """
    The status of a single rule evaluation result.
    - PASS: the copy clearly satisfies the rule or the rule is met by omission (nothing prohibited is present)
    - FAIL: the copy clearly breaches the rule
    - REVIEW_REQUIRED: the claim is ambiguous, or partially satisfies the rule but needs human judgement
    - NOT_APPLICABLE: the rule condition is not triggered at all (e.g., a rule about comparison claims when the copy makes no comparisons)
    """

    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    NOT_APPLICABLE = "NOT_APPLICABLE"


class RuleEvaluationResult(BaseModel):
    """
    A single rule evaluation result.
    """

    rule_id: str
    status: EvaluationStatus
    reason: str
    matched_text: str | None = None
    source_ref: str
    source_quote: str
    confidence: float = Field(ge=0.0, le=1.0)


class EvaluationOutput(BaseModel):
    """
    The overall evaluation output.
    """

    overall_verdict: Literal["PASS", "FAIL", "REVIEW_REQUIRED"]
    summary: str
    evaluated_at: str
    input_text: str
    results: list[RuleEvaluationResult]
