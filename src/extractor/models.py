from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from src.models import CheckType, EvaluationScope, Severity


class ExtractedRuleDraft(BaseModel):
    """LLM response schema for a single extracted rule from one regulatory section."""

    model_config = ConfigDict(str_strip_whitespace=True)

    category: str = Field(min_length=1)
    rule: str = Field(min_length=1)
    applicability: str = Field(min_length=1)
    source_ref: str = Field(min_length=1)
    source_quote: str = Field(min_length=1)
    severity: Severity
    check_type: CheckType = CheckType.SEMANTIC
    evaluation_scope: EvaluationScope = EvaluationScope.TEXT_EVALUABLE


class SectionRulesPayload(BaseModel):
    """Top-level LLM response envelope for section extraction."""

    rules: list[ExtractedRuleDraft] = Field(default_factory=list)
