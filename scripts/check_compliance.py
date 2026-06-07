#!/usr/bin/env python3
"""Evaluate marketing copy against MiFID II compliance rules.

Usage:
    uv run scripts/check_compliance.py --text "Your marketing copy here"
    uv run scripts/check_compliance.py --file path/to/copy.txt
    OPENAI_API_KEY=sk-... uv run scripts/check_compliance.py --text "Your copy"
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from src.constants import DEFAULT_BATCH_SIZE, DEFAULT_MODEL, JSON_INDENT
from src.paths import RULES_JSON_PATH

USAGE_GUIDE = f"""
  Marketing Compliance Checker — evaluate copy against MiFID II rules.

  Usage:
    uv run scripts/check_compliance.py --text "Install our app and get rich tomorrow"
    uv run scripts/check_compliance.py --file path/to/copy.txt

  API key (one of):
    export OPENAI_API_KEY=sk-...                          # environment variable
    echo 'OPENAI_API_KEY=sk-...' > .env                   # .env file (auto-loaded)
    uv run scripts/check_compliance.py --api-key sk-...   # command-line argument

  Options:
    --text TEXT        Marketing copy as a string
    --file FILE        Path to a text file with marketing copy
    --api-key KEY      OpenAI API key (overrides env / .env)
    --model MODEL      OpenAI model name (default: {DEFAULT_MODEL})
    --rules FILE       Path to rules.json (default: data/processed/rules.json)
    --batch-size N     Rules per LLM call (default: {DEFAULT_BATCH_SIZE})

  Examples:
    uv run scripts/check_compliance.py --text "Guaranteed 50%% returns, zero risk!"
    uv run scripts/check_compliance.py --file path/to/copy.txt
"""


def main() -> None:
    if len(sys.argv) == 1:
        print(USAGE_GUIDE, file=sys.stderr)
        sys.exit(1)

    parser = argparse.ArgumentParser(
        description="Evaluate marketing copy against MiFID II compliance rules.",
        add_help=True,
    )

    text_group = parser.add_mutually_exclusive_group(required=True)
    text_group.add_argument("--text", help="Marketing copy as a string")
    text_group.add_argument("--file", type=Path, metavar="FILE", help="Path to a text file")

    parser.add_argument("--api-key", metavar="KEY", help="OpenAI API key")
    parser.add_argument("--model", metavar="MODEL", help="OpenAI model name")
    parser.add_argument(
        "--rules", type=Path, default=RULES_JSON_PATH, metavar="FILE", help="Path to rules.json"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        metavar="N",
        help=f"Rules per LLM call (default: {DEFAULT_BATCH_SIZE})",
    )
    args = parser.parse_args()

    if args.api_key:
        os.environ["OPENAI_API_KEY"] = args.api_key
    if args.model:
        os.environ["OPENAI_MODEL"] = args.model

    if args.file:
        if not args.file.exists():
            parser.error(f"File not found: {args.file}")
        marketing_text = args.file.read_text(encoding="utf-8").strip()
    else:
        marketing_text = args.text.strip()

    if not marketing_text:
        parser.error("Marketing text is empty.")

    from src.evaluator.pipeline import evaluate_marketing_copy

    print(f"Evaluating copy against rules: {args.rules}", file=sys.stderr)
    output = evaluate_marketing_copy(
        marketing_text=marketing_text,
        rules_path=args.rules,
        batch_size=args.batch_size,
    )

    print(json.dumps(output.model_dump(), indent=JSON_INDENT, ensure_ascii=False))


if __name__ == "__main__":
    main()
