# BizOps Compliance Agent

Automated compliance checker for financial marketing communications against EU MiFID II regulations.

```
Regulatory Sources (markdown)
        │
        ▼
Rule Extraction (one-time, LLM-powered)
        │
        ▼
Structured Rules JSON  ──►  Compliance Evaluator  ◄──  Marketing Copy
                                    │
                                    ▼
                          Evaluation Report (JSON)
                          verdict + reasoning + violated rules
```

## Quick Start

Requires [uv](https://docs.astral.sh/uv/) (Python 3.13+) and an [OpenAI API key](https://platform.openai.com/api-keys).

```bash
cp .env.example .env          # add your OPENAI_API_KEY
make install
make evaluate FILE=examples/non_compliant_copy.txt
```

See `make help` for all available commands, or run `uv run scripts/check_compliance.py` for full usage guide.

## Usage

The repo ships with pre-extracted rules in `data/processed/rules.json`. You can evaluate copy immediately, or regenerate rules from the raw sources first.

**Evaluate marketing copy** (uses existing `rules.json`):

```bash
make evaluate FILE=examples/non_compliant_copy.txt
make evaluate TEXT="Follow me here if you want to get rich"
```

**Regenerate rules** (optional — reads `data/raw_sources/*.md`, calls the LLM, overwrites `data/processed/rules.json`):

```bash
make extract
# or: uv run scripts/extract_rules.py
```

Then evaluate against the new rules:

```bash
make evaluate FILE=examples/compliant_copy.txt
```

To remove generated rules and start fresh: `make clean` (deletes `data/processed/rules.json`; run `make extract` to recreate).

## What I Built

**Two-stage pipeline: extract once, evaluate many.**

1. **Rule extraction** — Raw EU regulation text (markdown with YAML frontmatter) is split by article/paragraph and sent section-by-section to the LLM. The extraction prompt filters for text-content-evaluable marketing rules only, skipping operational obligations (durable medium, staff remuneration, timing, font/layout). Output: 32 structured rules in `data/processed/rules.json`, each with regulatory citation, exact source quote, severity, and evaluation scope.

2. **Compliance evaluation** — Marketing copy is checked against all 32 rules in batches. Each rule gets a four-state verdict (`PASS`, `FAIL`, `REVIEW_REQUIRED`, `NOT_APPLICABLE`) with reasoning, matched text, and confidence score. A final LLM call generates a plain-English summary.

Not every rule can be judged from the marketing text alone. For example, "is the 67% figure current?" requires outside evidence. To handle this, each rule is tagged with an **evaluation scope**:

   - **`text_evaluable`** — The copy is enough to decide PASS, FAIL, or NOT_APPLICABLE.
   - **`external_verification`** — The evaluator can spot the *claim* but can't verify it, so it flags `REVIEW_REQUIRED` instead of guessing.

   Each scope uses a different evaluation prompt. External-verification rules only trigger when the relevant claim is actually present in the text — a generic risk warning won't cause every external rule to fire.

### Source selection

Sources follow **CySEC Circular C574**, which names the specific MiFID II provisions for marketing supervision. Rather than ingesting the full directive, only the directly relevant articles are used:

| Source | Why |
|--------|-----|
| Delegated Regulation 2017/565, Art. 44 | Core content rules: fair/clear/not misleading, risk warnings, comparisons, performance claims |
| Delegated Regulation 2017/565, Art. 46(5)–(6) | Marketing consistency and offer/invitation disclosures (C574 only references these two paragraphs) |
| MiFID II Directive, Art. 24 | Parent directive — "all information shall be fair, clear and not misleading" |
| CySEC C574 | Background context only (not used for rule extraction) |

## What I Cut

- **OpenAI SDK, no framework** — No LangChain/CrewAI/etc. Direct API calls keep prompts clear and debugging simple.
- **No UI** — CLI-only; the deliverable is the pipeline and reasoning, not a dashboard
- **No RAG / vector DB** — 32 rules fit in a single LLM context window; retrieval adds complexity without value at this scale
- **No multi-agent orchestration** — Single-agent sequential pipeline is sufficient and easier to debug
- **No rule versioning or historical storage** — Rules are extracted fresh; evaluation results are printed, not persisted
- **No human review workflow** — `REVIEW_REQUIRED` is designed for a future loop where a compliance officer provides context and the system re-evaluates, but that loop isn't built

## Key Prompt Design Decisions

1. **Section-by-section extraction, not whole-document.** Sending the full regulation text in one call produced overlapping, low-quality rules. Splitting by paragraph and sending each with the supervisory context gave much better precision — the LLM focuses on one obligation at a time.

2. **Strict filtering in the extraction prompt.** The prompt now tells the LLM to skip non-marketing sections and only extract relevant rules, cutting the rule count in half and improving focus.

3. **Two separate evaluation prompts for text vs. external rules.** Initially all rules went through one prompt, and external-verification rules always came back as `REVIEW_REQUIRED` regardless of whether they were triggered. Splitting into two prompts with different instructions (text rules: PASS/FAIL/NOT_APPLICABLE; external rules: NOT_APPLICABLE or REVIEW_REQUIRED based on trigger presence) eliminated false flags.

4. **Plain-text-only evaluation scope.** Rules about font size, visual prominence, or page layout are excluded at extraction time. The evaluator cannot see formatting, so guessing about it would produce unreliable results.

## What I'd Do Differently With More Time

- **Automated source fetching** — Currently raw regulation text is manually copied into markdown files. I'd build a pipeline that pulls from EUR-Lex or the CySEC website directly.
- **Evaluation test suite** — Systematic test cases (compliant, non-compliant, edge cases) with expected verdicts to measure prompt quality over time.
- **Interactive review loop** — When the evaluator returns `REVIEW_REQUIRED`, let the user provide the missing context (e.g. "yes, 67% is current as of Q1 2025") and re-evaluate with that information incorporated.

## One Thing That Surprised Me

I didn't expect how much ambiguity exists in marketing copy evaluation. Many rules sound binary but in practice depend on context the text alone can't provide — is the firm name the legal entity? Is the performance figure current? This pushed me toward the `REVIEW_REQUIRED` + `external_verification` design rather than forcing every rule into pass/fail.
