from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_SOURCES_DIR = PROJECT_ROOT / "data" / "raw_sources"
RULES_JSON_PATH = PROJECT_ROOT / "data" / "processed" / "rules.json"


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
