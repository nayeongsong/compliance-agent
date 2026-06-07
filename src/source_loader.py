from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

import yaml

REQUIRED_METADATA_FIELDS = {
    "source_id",
    "source_name",
    "source_type",
    "article",
    "title",
    "url",
    "referenced_by",
    "retrieved_at",
    "jurisdiction",
    "domain",
    "purpose",
}


@dataclass(frozen=True)
class SourceSection:
    source_ref: str
    text: str
    metadata: dict[str, Any]
    source_file: str


def parse_frontmatter(path: Path) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter and return (metadata, body).

    Validates that all required metadata fields are present. `article` and
    `referenced_by` are allowed to be null (None).
    """
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---"):
        raise ValueError(f"Missing YAML frontmatter in {path}")

    end = raw.find("\n---", 3)
    if end == -1:
        raise ValueError(f"Unclosed YAML frontmatter in {path}")

    fm_text = raw[4:end]
    body = raw[end + 4 :].lstrip("\n")

    metadata = yaml.safe_load(fm_text) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Frontmatter must be a mapping in {path}")

    missing = REQUIRED_METADATA_FIELDS - set(metadata.keys())
    if missing:
        raise ValueError(f"Missing required metadata fields in {path}: {sorted(missing)}")

    # YAML may parse unquoted ISO dates as date objects. Normalize to strings.
    for key, value in list(metadata.items()):
        if isinstance(value, datetime):
            metadata[key] = value.date().isoformat()
        elif isinstance(value, date):
            metadata[key] = value.isoformat()

    _validate_nullable(metadata, "article", path)
    _validate_nullable(metadata, "referenced_by", path)

    for key in REQUIRED_METADATA_FIELDS - {"article", "referenced_by"}:
        value = metadata.get(key)
        if value is None:
            raise ValueError(f"Metadata field '{key}' cannot be null in {path}")
        if not isinstance(value, str):
            raise ValueError(
                f"Metadata field '{key}' must be a string in {path} (got {type(value).__name__})"
            )

    return metadata, body


def split_into_sections(
    *, body: str, metadata: dict[str, Any], source_file: str
) -> list[SourceSection]:
    """Split regulatory markdown into sections based on numeric/alphabetic/roman markers.

    Supports both explicit markdown headings:
      ### 1.
      #### (a)
      ##### (i)

    And the common EU legal-text style:
      1.   ...
      (a)
      (i)
    """
    article_num = _extract_article_number(metadata.get("article"))
    if article_num is None:
        return []

    source_name = metadata.get("source_name", "")

    lines = body.splitlines()
    events: list[_Event] = []

    for idx, line in enumerate(lines):
        heading = _parse_heading_marker(line)
        if heading:
            events.append(
                _Event(
                    line_index=idx,
                    level=heading.level,
                    token=heading.token,
                    inline_text=heading.inline,
                )
            )
            continue

        legal = _parse_legal_marker(line)
        if legal:
            events.append(
                _Event(
                    line_index=idx, level=legal.level, token=legal.token, inline_text=legal.inline
                )
            )

    if not events:
        return []

    sections: list[SourceSection] = []
    state = _RefState(article_num=article_num, source_name=source_name)

    for event_index, event in enumerate(events):
        state = state.apply(event.level, event.token)
        source_ref = state.to_source_ref()
        if not source_ref:
            continue

        start_line = event.line_index + 1
        first_line_extra = event.inline_text.strip()
        end_line = (
            events[event_index + 1].line_index if event_index + 1 < len(events) else len(lines)
        )

        content_lines: list[str] = []
        if first_line_extra:
            content_lines.append(first_line_extra)
        content_lines.extend(lines[start_line:end_line])

        text = "\n".join(content_lines).strip()
        if not text:
            continue

        sections.append(
            SourceSection(
                source_ref=source_ref,
                text=text,
                metadata=metadata,
                source_file=source_file,
            )
        )

    return sections


def _validate_nullable(metadata: dict[str, Any], key: str, path: Path) -> None:
    if key not in metadata:
        raise ValueError(f"Missing '{key}' in {path}")
    value = metadata.get(key)
    if value is not None and not isinstance(value, str):
        raise ValueError(f"Metadata field '{key}' must be a string or null in {path}")


def _extract_article_number(article: Any) -> int | None:
    if article is None:
        return None
    if isinstance(article, int):
        return article
    if not isinstance(article, str):
        return None
    match = re.search(r"Article\s+(\d+)", article)
    if match:
        return int(match.group(1))
    digits = re.search(r"(\d+)", article)
    return int(digits.group(1)) if digits else None


@dataclass(frozen=True)
class _Marker:
    level: int
    token: str
    inline: str


def _parse_heading_marker(line: str) -> _Marker | None:
    match = re.match(r"^(#{3,5})\s+(.+?)\s*$", line)
    if not match:
        return None
    level = len(match.group(1))
    text = match.group(2).strip()

    if level == 3:
        m = re.match(r"^(\d+)\.\s*(.*)$", text)
        if not m:
            return None
        return _Marker(level=3, token=m.group(1), inline=m.group(2))
    if level in {4, 5}:
        m = re.match(r"^\(([^)]+)\)\s*(.*)$", text)
        if not m:
            return None
        return _Marker(level=level, token=m.group(1), inline=m.group(2))
    return None


def _parse_legal_marker(line: str) -> _Marker | None:
    m_num = re.match(r"^\s*(\d+)\.\s*(.*)$", line)
    if m_num:
        return _Marker(level=3, token=m_num.group(1), inline=m_num.group(2))

    m_paren = re.match(r"^\s*\(([^)]+)\)\s*(.*)$", line)
    if not m_paren:
        return None

    token = m_paren.group(1).strip()
    inline = m_paren.group(2)

    # Choose level based on token shape.
    # In our sources, lettered subclauses are usually single letters (a), (b), (c)...
    # Roman-numeral subclauses are typically multi-character (ii), (iii), (iv)...
    if len(token) > 1 and re.fullmatch(r"[ivxlcdm]+", token):
        return _Marker(level=5, token=token, inline=inline)
    if re.fullmatch(r"[a-z]", token):
        return _Marker(level=4, token=token, inline=inline)
    return None


@dataclass(frozen=True)
class _Event:
    line_index: int
    level: int
    token: str
    inline_text: str


@dataclass(frozen=True)
class _RefState:
    article_num: int
    source_name: str = ""
    paragraph: str | None = None
    letter: str | None = None
    roman: str | None = None

    def apply(self, level: int, token: str) -> _RefState:
        if level == 3:
            return _RefState(
                article_num=self.article_num,
                source_name=self.source_name,
                paragraph=token,
            )
        if level == 4:
            return _RefState(
                article_num=self.article_num,
                source_name=self.source_name,
                paragraph=self.paragraph,
                letter=token,
            )
        if level == 5:
            return _RefState(
                article_num=self.article_num,
                source_name=self.source_name,
                paragraph=self.paragraph,
                letter=self.letter,
                roman=token,
            )
        raise ValueError(f"Unsupported heading level: {level}")

    def to_source_ref(self) -> str:
        if not self.paragraph:
            return ""
        article = f"Article {self.article_num}({self.paragraph})"
        if self.letter:
            article += f"({self.letter})"
        if self.roman:
            article += f"({self.roman})"
        if self.source_name:
            return f"{self.source_name}, {article}"
        return article
