from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class Severity(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class CheckType(StrEnum):
    SEMANTIC = "semantic"
    REGEX = "regex"
    PRESENCE = "presence"


class EvaluationScope(StrEnum):
    TEXT_EVALUABLE = "text_evaluable"
    EXTERNAL_VERIFICATION = "external_verification"


class MarketingRule(BaseModel):
    id: str
    category: str
    rule: str
    applicability: str
    source_id: str
    source_file: str
    source_ref: str
    source_quote: str
    severity: Severity
    check_type: CheckType
    evaluation_scope: EvaluationScope = EvaluationScope.TEXT_EVALUABLE


class RulesMetadata(BaseModel):
    generated_at: str
    domain: str
    source_files: list[str]
    excluded_context_files: list[str]
    rule_count: int


class RulesFile(BaseModel):
    metadata: RulesMetadata
    rules: list[MarketingRule]
