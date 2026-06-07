from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path

from src.constants import DEDUPE_SIMILARITY_THRESHOLD, JSON_INDENT
from src.extractor.extractor import extract_rules_from_section
from src.extractor.models import ExtractedRuleDraft
from src.llm_client import LLMClient
from src.models import MarketingRule, RulesFile, RulesMetadata
from src.paths import RAW_SOURCES_DIR, RULES_JSON_PATH, now_iso
from src.source_loader import SourceSection, parse_frontmatter, split_into_sections

RULE_EXTRACTION_PURPOSE = "rule_extraction"
SUPERVISORY_CONTEXT_PURPOSE = "supervisory_context"

# Categories that represent process/timing obligations rather than marketing-copy rules.
# Kept only if the rule text explicitly mentions "marketing communication".
_BLOCKED_CATEGORIES = {
    "timely_information_provision",
    "material_change_notification",
    "durable_medium",
    "client_agreement_terms",
    "research_payments",
    "staff_remuneration",
    "portfolio_management",
}


def load_supervisory_context(raw_sources_dir: Path) -> list[dict]:
    return [
        {
            "source_file": path.name,
            "title": metadata.get("title", ""),
            "source_name": metadata.get("source_name", ""),
            "body": body.strip(),
        }
        for path in sorted(raw_sources_dir.glob("*.md"))
        for metadata, body in [parse_frontmatter(path)]
        if metadata.get("purpose") == SUPERVISORY_CONTEXT_PURPOSE
    ]


def load_rule_sections(
    raw_sources_dir: Path,
) -> tuple[list[SourceSection], list[str], list[str], str]:
    sections: list[SourceSection] = []
    source_files: list[str] = []
    excluded_context_files: list[str] = []
    domains: set[str] = set()

    for path in sorted(raw_sources_dir.glob("*.md")):
        metadata, body = parse_frontmatter(path)
        purpose = metadata.get("purpose")

        if purpose == SUPERVISORY_CONTEXT_PURPOSE:
            excluded_context_files.append(path.name)
            continue
        if purpose != RULE_EXTRACTION_PURPOSE:
            continue

        domains.add(str(metadata.get("domain")))
        source_files.append(path.name)
        sections.extend(split_into_sections(body=body, metadata=metadata, source_file=path.name))

    if not source_files:
        raise ValueError(f"No rule extraction sources found under {raw_sources_dir}")
    if len(domains) != 1:
        raise ValueError(f"Expected exactly one domain across sources, got: {sorted(domains)}")

    return sections, source_files, excluded_context_files, next(iter(domains))


def extract_rules_file(
    *,
    raw_sources_dir: Path | None = None,
    llm: LLMClient | None = None,
) -> RulesFile:
    raw_dir = raw_sources_dir or RAW_SOURCES_DIR
    sections, source_files, excluded_context_files, domain = load_rule_sections(raw_dir)
    context_docs = load_supervisory_context(raw_dir)
    client = llm or LLMClient()

    extracted: list[MarketingRule] = []
    for section in sections:
        for draft in extract_rules_from_section(
            section=section, supervisory_context=context_docs, llm=client
        ):
            if draft.source_quote not in section.text:
                continue
            extracted.append(_to_marketing_rule(draft=draft, section=section))

    rules = _assign_stable_ids(_dedupe(_filter(extracted)))

    return RulesFile(
        metadata=RulesMetadata(
            generated_at=now_iso(),
            domain=domain,
            source_files=sorted(source_files),
            excluded_context_files=sorted(excluded_context_files),
            rule_count=len(rules),
        ),
        rules=rules,
    )


def write_rules_json(*, rules_file: RulesFile, output_path: Path | None = None) -> Path:
    out = output_path or RULES_JSON_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(rules_file.model_dump(), indent=JSON_INDENT, ensure_ascii=False),
        encoding="utf-8",
    )
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _to_marketing_rule(*, draft: ExtractedRuleDraft, section: SourceSection) -> MarketingRule:
    return MarketingRule(
        id="",
        category=draft.category,
        rule=draft.rule,
        applicability=draft.applicability,
        source_id=str(section.metadata["source_id"]),
        source_file=section.source_file,
        source_ref=section.source_ref,
        source_quote=draft.source_quote,
        severity=draft.severity,
        check_type=draft.check_type,
        evaluation_scope=draft.evaluation_scope,
    )


def _filter(rules: list[MarketingRule]) -> list[MarketingRule]:
    """Drop non-marketing-copy categories unless the rule text mentions 'marketing communication'."""
    return [
        r
        for r in rules
        if r.category.lower() not in _BLOCKED_CATEGORIES
        or "marketing communication" in r.rule.lower()
    ]


def _dedupe(rules: list[MarketingRule]) -> list[MarketingRule]:
    """Drop exact duplicates and near-duplicates within the same category."""
    unique: list[MarketingRule] = []
    for candidate in rules:
        if not candidate.source_ref or not candidate.source_quote:
            continue
        key = (candidate.category.lower(), _norm(candidate.rule))
        if any((r.category.lower(), _norm(r.rule)) == key for r in unique):
            continue
        if any(
            r.category.lower() == candidate.category.lower()
            and SequenceMatcher(None, _norm(r.rule), _norm(candidate.rule)).ratio()
            >= DEDUPE_SIMILARITY_THRESHOLD
            for r in unique
        ):
            continue
        unique.append(candidate)
    return unique


def _assign_stable_ids(rules: list[MarketingRule]) -> list[MarketingRule]:
    ordered = sorted(rules, key=lambda r: (r.category, r.source_id, r.source_ref, r.rule))
    return [r.model_copy(update={"id": f"MKT-{i:03d}"}) for i, r in enumerate(ordered, start=1)]


def _norm(s: str) -> str:
    return " ".join(s.lower().split())
