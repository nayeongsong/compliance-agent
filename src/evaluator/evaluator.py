from __future__ import annotations

import json
from typing import Literal

from pydantic import BaseModel, Field

from src.constants import DEFAULT_BATCH_SIZE, DEFAULT_TEMPERATURE, JSON_INDENT
from src.evaluator.models import EvaluationStatus, RuleEvaluationResult
from src.evaluator.prompts import (
    BATCH_EVALUATION_SYSTEM_PROMPT,
    EXTERNAL_EVALUATION_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
)
from src.llm_client import LLMClient
from src.models import EvaluationScope


class _BatchResultItem(BaseModel):
    rule_id: str
    status: EvaluationStatus
    reason: str
    matched_text: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)


class _BatchPayload(BaseModel):
    results: list[_BatchResultItem]


class _SummaryPayload(BaseModel):
    summary: str


def evaluate_rules_batch(
    marketing_text: str,
    rules: list[dict],
    llm: LLMClient | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> list[RuleEvaluationResult]:
    """Evaluate marketing_text against all rules, in batches of batch_size.

    text_evaluable rules are evaluated with the standard prompt (PASS/FAIL/REVIEW_REQUIRED/NOT_APPLICABLE).
    external_verification rules use a dedicated prompt that first checks applicability,
    returning NOT_APPLICABLE when the trigger is absent and REVIEW_REQUIRED when present.
    Results are returned with all text_evaluable rules first, then external_verification rules.
    """
    client = llm or LLMClient()
    results: list[RuleEvaluationResult] = []

    text_rules = [
        r for r in rules if r.get("evaluation_scope") != EvaluationScope.EXTERNAL_VERIFICATION
    ]
    external_rules = [
        r for r in rules if r.get("evaluation_scope") == EvaluationScope.EXTERNAL_VERIFICATION
    ]

    for i in range(0, len(text_rules), batch_size):
        batch = text_rules[i : i + batch_size]
        results.extend(_evaluate_batch(marketing_text=marketing_text, batch=batch, llm=client))

    for i in range(0, len(external_rules), batch_size):
        batch = external_rules[i : i + batch_size]
        results.extend(
            _evaluate_batch(
                marketing_text=marketing_text,
                batch=batch,
                llm=client,
                system_prompt=EXTERNAL_EVALUATION_SYSTEM_PROMPT,
            )
        )

    return results


def determine_overall_verdict(
    results: list[RuleEvaluationResult],
) -> Literal["PASS", "FAIL", "REVIEW_REQUIRED"]:
    """FAIL > REVIEW_REQUIRED > PASS. NOT_APPLICABLE results are ignored."""
    statuses = {r.status for r in results}
    if EvaluationStatus.FAIL in statuses:
        return "FAIL"
    if EvaluationStatus.REVIEW_REQUIRED in statuses:
        return "REVIEW_REQUIRED"
    return "PASS"


def summarize_evaluation(
    marketing_text: str,
    results: list[RuleEvaluationResult],
    llm: LLMClient | None = None,
) -> str:
    """Ask the LLM for a short plain-English summary of the evaluation."""
    client = llm or LLMClient()
    results_for_prompt = [
        {
            "rule_id": r.rule_id,
            "status": r.status.value,
            "reason": r.reason,
            "matched_text": r.matched_text,
        }
        for r in results
        if r.status != EvaluationStatus.NOT_APPLICABLE
    ]
    user_prompt = f"""MARKETING COPY:
{marketing_text}

EVALUATION RESULTS:
{json.dumps(results_for_prompt, indent=JSON_INDENT)}

Return JSON only.
"""
    payload = client.complete_json(
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=_SummaryPayload,
        temperature=DEFAULT_TEMPERATURE,
    )
    return payload.summary


def _evaluate_batch(
    marketing_text: str,
    batch: list[dict],
    llm: LLMClient,
    system_prompt: str = BATCH_EVALUATION_SYSTEM_PROMPT,
) -> list[RuleEvaluationResult]:
    rules_block = json.dumps(
        [
            {
                "rule_id": r["id"],
                "rule": r["rule"],
                "applicability": r["applicability"],
                "source_ref": r["source_ref"],
                "source_quote": r["source_quote"],
            }
            for r in batch
        ],
        indent=JSON_INDENT,
    )

    user_prompt = f"""MARKETING COPY:
{marketing_text}

RULES TO EVALUATE:
{rules_block}

Return JSON only.
"""
    payload = llm.complete_json(
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        response_model=_BatchPayload,
        temperature=DEFAULT_TEMPERATURE,
    )

    # Index batch rules by id so we can attach source_ref / source_quote.
    rule_lookup = {r["id"]: r for r in batch}

    return [
        RuleEvaluationResult(
            rule_id=item.rule_id,
            status=item.status,
            reason=item.reason,
            matched_text=item.matched_text,
            source_ref=rule_lookup.get(item.rule_id, {}).get("source_ref", ""),
            source_quote=rule_lookup.get(item.rule_id, {}).get("source_quote", ""),
            confidence=item.confidence,
        )
        for item in payload.results
        if item.rule_id in rule_lookup
    ]
