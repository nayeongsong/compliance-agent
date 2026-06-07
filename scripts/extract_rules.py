#!/usr/bin/env python3
"""Extract compliance rules from raw regulatory sources and save to JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.extractor.pipeline import extract_rules_file, write_rules_json
from src.paths import RAW_SOURCES_DIR, RULES_JSON_PATH


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract structured compliance rules from raw regulatory markdown sources."
    )
    parser.add_argument(
        "--raw-sources",
        type=Path,
        default=RAW_SOURCES_DIR,
        help="Directory containing raw source markdown files",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=RULES_JSON_PATH,
        help="Path to write extracted rules JSON",
    )
    args = parser.parse_args()

    print(f"Extracting rules from: {args.raw_sources}")
    rules_file = extract_rules_file(raw_sources_dir=args.raw_sources)
    out_path = write_rules_json(rules_file=rules_file, output_path=args.output)
    print(f"Extracted {rules_file.metadata.rule_count} rules -> {out_path}")


if __name__ == "__main__":
    main()
