from __future__ import annotations

import json
from pathlib import Path

from src.constants import DEFAULT_BATCH_SIZE
from src.evaluator.evaluator import (
    determine_overall_verdict,
    evaluate_rules_batch,
    summarize_evaluation,
)
from src.evaluator.models import EvaluationOutput
from src.llm_client import LLMClient
from src.paths import RULES_JSON_PATH, now_iso


def load_rules(path: Path | None = None) -> list[dict]:
    """Load marketing rules from rules.json as plain dicts."""
    rules_path = path or RULES_JSON_PATH
    data = json.loads(rules_path.read_text(encoding="utf-8"))
    return data["rules"]


def evaluate_marketing_copy(
    marketing_text: str,
    rules_path: Path | None = None,
    llm: LLMClient | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
) -> EvaluationOutput:
    """Full evaluation pipeline: load rules → evaluate → summarize → return output."""
    client = llm or LLMClient()
    rules = load_rules(rules_path)

    results = evaluate_rules_batch(
        marketing_text=marketing_text,
        rules=rules,
        llm=client,
        batch_size=batch_size,
    )

    verdict = determine_overall_verdict(results)
    summary = summarize_evaluation(marketing_text=marketing_text, results=results, llm=client)

    return EvaluationOutput(
        overall_verdict=verdict,
        summary=summary,
        evaluated_at=now_iso(),
        input_text=marketing_text,
        results=results,
    )
