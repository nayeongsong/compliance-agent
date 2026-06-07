from __future__ import annotations

from typing import Any

from src.constants import DEFAULT_TEMPERATURE
from src.extractor.models import ExtractedRuleDraft, SectionRulesPayload
from src.extractor.prompts import SECTION_EXTRACTION_SYSTEM_PROMPT
from src.llm_client import LLMClient
from src.source_loader import SourceSection


def extract_rules_from_section(
    *,
    section: SourceSection,
    supervisory_context: list[dict[str, Any]] | None = None,
    llm: LLMClient | None = None,
) -> list[ExtractedRuleDraft]:
    """Call the LLM to extract marketing-copy rules from a single regulatory section."""
    client = llm or LLMClient()

    ctx_text = _build_context_text(supervisory_context)
    user_prompt = _build_user_prompt(section=section, ctx_text=ctx_text)

    payload = client.complete_json(
        system_prompt=SECTION_EXTRACTION_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        response_model=SectionRulesPayload,
        temperature=DEFAULT_TEMPERATURE,
    )

    # Drop any draft missing required fields, and force the canonical source_ref.
    return [
        rule.model_copy(update={"source_ref": section.source_ref})
        for rule in payload.rules
        if rule.source_ref.strip() and rule.source_quote.strip()
    ]


def _build_context_text(supervisory_context: list[dict[str, Any]] | None) -> str:
    if not supervisory_context:
        return "(none)"
    chunks = [
        f"[{item.get('source_file', '')}] {item.get('title') or item.get('source_name') or 'Context'}\n{item.get('body', '')}".strip()
        for item in supervisory_context
        if item.get("body")
    ]
    return "\n\n".join(chunks) if chunks else "(none)"


def _build_user_prompt(*, section: SourceSection, ctx_text: str) -> str:
    return f"""Background supervisory context (do NOT extract rules from this section):
{ctx_text}

--- REGULATORY SECTION (extract rules ONLY from below) ---
Source file: {section.source_file}
Source id: {section.metadata.get("source_id")}
Source name: {section.metadata.get("source_name")}
Section reference: {section.source_ref}

SECTION TEXT:
{section.text}
--- END ---

Return JSON only.
"""
