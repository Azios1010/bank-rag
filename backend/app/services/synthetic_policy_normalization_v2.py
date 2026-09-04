"""Normalize the complete Stage 8 synthetic Markdown policies for Stage 9."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.services.policy_normalization_v2 import get_hash, normalize_text


RULE_RE = re.compile(r"^Rule ID: ([A-Z]+-[A-Z0-9-]+)\.(?:\s*)(.*)$")
H1_RE = re.compile(r"^#\s+(.+?)\s*$")
H2_RE = re.compile(r"^##\s+(\d+)\.\s+(.+?)\s*$")
PARSER_VERSION = "bank-rag-v2-pymupdf-structure-1.0.0"
SELECTION_REASON = (
    "Complete Rule ID section selected from the synthetic Markdown source; "
    "all rule text, thresholds, exception authority, and linked constraints are retained."
)


def load_manifest(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return json.load(handle)


def _source_path(manifest_path: Path, record: dict[str, Any]) -> Path:
    return (manifest_path.resolve().parents[4] / record["path"]).resolve()


def parse_markdown_rules(text: str, record: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract each complete Rule ID paragraph in deterministic source order."""
    text = normalize_text(text)
    lines = text.split("\n")
    title = next((m.group(1) for line in lines if (m := H1_RE.match(line))), None)
    if title != record["title"]:
        raise ValueError(f"{record['source_id']}: Markdown title does not match manifest")

    chapter: str | None = None
    section: str | None = None
    heading_path: list[str] = [title]
    provisions: list[dict[str, Any]] = []
    current_rule: str | None = None
    current_lines: list[str] = []
    current_chapter: str | None = None
    current_section: str | None = None
    current_heading: list[str] = heading_path

    def flush() -> None:
        nonlocal current_rule, current_lines
        if current_rule is None:
            return
        content = "\n".join(current_lines)
        if not content:
            raise ValueError(f"{record['source_id']}: empty Rule ID section {current_rule}")
        ordinal = len(provisions) + 1
        provisions.append(
            {
                "source_id": record["source_id"],
                "version_id": record["version_id"],
                "chapter": current_chapter,
                "section": current_section,
                "article": current_rule,
                "clause": None,
                "point": None,
                "heading_path": list(current_heading),
                "content": content,
                "page_start": 0,
                "page_end": 0,
                "content_hash": get_hash(content),
                "inventory_type": "SELECTED",
                "selection_reason": SELECTION_REASON,
            }
        )
        current_rule = None
        current_lines = []

    for line in lines:
        if match := H2_RE.match(line):
            flush()
            chapter, section = match.group(1), match.group(2)
            heading_path = [title, line]
            continue
        if match := RULE_RE.match(line):
            flush()
            current_rule = match.group(1)
            current_lines = [line]
            current_chapter = chapter
            current_section = section
            current_heading = list(heading_path)
            continue
        if current_rule is not None:
            current_lines.append(line)
    flush()
    if not provisions:
        raise ValueError(f"{record['source_id']}: no Rule ID sections found")
    return provisions


def normalize_synthetic_manifest(manifest_path: Path) -> list[dict[str, Any]]:
    manifest = load_manifest(manifest_path)
    records = manifest.get("records", [])
    provisions: list[dict[str, Any]] = []
    for record in records:
        source = _source_path(manifest_path, record)
        with source.open("r", encoding="utf-8", newline="") as handle:
            text = handle.read()
        normalized = normalize_text(text)
        if get_hash(normalized) != record["content_hash"]:
            raise ValueError(f"{record['source_id']}: source manifest content hash mismatch")
        provisions.extend(parse_markdown_rules(normalized, record))
    return provisions


def write_jsonl(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = "".join(json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for item in records)
    path.write_text(payload, encoding="utf-8", newline="\n")
