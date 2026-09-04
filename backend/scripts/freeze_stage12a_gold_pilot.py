"""Promote the explicitly human-approved Stage 12A pilot and freeze it.

The DRAFT review input is retained unchanged.  This script creates the
canonical REVIEWED release by adding only human review provenance, then uses
the existing V2 exporter to validate and serialize the release.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

from app.eval.gold_v2 import CanonicalGoldError, CanonicalGoldValidator, export_reviewed_canonical_gold


ROOT = Path(__file__).resolve().parents[2]
DRAFT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.draft.jsonl"
RELEASED_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
FREEZE_PATH = ROOT / "docs/STAGE-12A-GOLD-PILOT-FREEZE.md"
RUNTIME_FREEZE_PATH = ROOT / "docs/STAGE-11D-RUNTIME-FREEZE.md"

# No person identity was supplied in the approval message.  This is an event
# role, not an invented individual identity.
REVIEWER_ID = "human_manual_approval"
APPROVED_AT = "2026-09-03T00:00:00+07:00"
APPROVAL_NOTE = (
    "Explicit human approval for Stage 12A-FINAL: APPROVE=25, EDIT=0, "
    "REJECT=0."
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl_bytes(records: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
        for record in records
    )


def _read_draft(validator: CanonicalGoldValidator) -> list[dict[str, Any]]:
    records = validator.parse_file(DRAFT_PATH)
    expected_ids = [f"stage12a-{index:03d}" for index in range(1, 26)]
    if [record["evaluation_id"] for record in records] != expected_ids:
        raise CanonicalGoldError("approved draft IDs are not in canonical 001-025 order")
    if any(record["status"] != "DRAFT" or record["review"] is not None for record in records):
        raise CanonicalGoldError("promotion input must contain only unrevised DRAFT records")
    return records


def _promote(records: list[dict[str, Any]], validator: CanonicalGoldValidator) -> list[dict[str, Any]]:
    promoted: list[dict[str, Any]] = []
    for record in records:
        reviewed = copy.deepcopy(record)
        reviewed["status"] = "REVIEWED"
        reviewed["review"] = {
            "reviewer_id": REVIEWER_ID,
            "reviewed_at": APPROVED_AT,
            "decision": "REVIEWED",
            "notes": APPROVAL_NOTE,
        }
        validator.validate_record(reviewed, promoted)
        promoted.append(reviewed)
    return promoted


def _write_collision_safe(path: Path, content: bytes) -> None:
    if path.exists():
        if path.read_bytes() != content:
            raise CanonicalGoldError(f"release collision at {path}; refusing to overwrite different content")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _freeze_document(records: list[dict[str, Any]], released_sha256: str, released_bytes: int) -> str:
    corpus = records[0]["corpus_identity"]
    embedding = records[0]["embedding_identity"]
    scope_counts = Counter(record["specialist_scope"] for record in records)
    source_counts = Counter(record["document"]["source_id"] for record in records)
    return "\n".join(
        [
            "# Stage 12A-FINAL — Gold Pilot Freeze",
            "",
            "This document freezes the explicitly human-approved retrieval gold pilot. It records identity and release metadata only; the released JSONL contains the canonical evidence records.",
            "",
            "## Approval",
            "",
            f"- Approval state: **HUMAN_APPROVED**",
            f"- Decision: **APPROVE=25, EDIT=0, REJECT=0**",
            f"- Reviewer representation: `{REVIEWER_ID}` (manual approval event role; no individual identity was supplied)",
            f"- Freeze timestamp: `{APPROVED_AT}`",
            "",
            "## Released artifact",
            "",
            f"- Path: `{RELEASED_PATH.relative_to(ROOT).as_posix()}`",
            f"- Bytes: `{released_bytes}`",
            f"- SHA-256: `{released_sha256}`",
            "- Records: `25`",
            "- REVIEWED: `25`",
            "- DRAFT: `0`",
            "- REJECTED: `0`",
            "",
            "## Corpus identity",
            "",
            f"- Version/name: `{corpus['version']} / {corpus['corpus_name']}`",
            f"- Chunk count: `{corpus['chunk_count']}`",
            f"- Corpus JSONL SHA-256: `{corpus['corpus_jsonl_sha256']}`",
            f"- Corpus manifest SHA-256: `{corpus['corpus_manifest_sha256']}`",
            f"- Corpus V2 hash: `{corpus['corpus_v2_hash']}`",
            f"- Manifest identity hash: `{corpus['manifest_hash']}`",
            "",
            "## Embedding identity",
            "",
            f"- Model: `{embedding['model']}`",
            f"- Format: `{embedding['format']}`",
            f"- Dimension/dtype: `{embedding['dimension']} / {embedding['dtype']}`",
            f"- Runtime/backend: `{embedding['runtime']} / {embedding['backend']}`",
            f"- Pooling/normalization: `{embedding['pooling']} / {embedding['normalization']}`",
            f"- Embedding artifact SHA-256: `{embedding['embedding_artifact_sha256']}`",
            f"- Embedding manifest SHA-256: `{embedding['embedding_manifest_sha256']}`",
            "",
            "## Runtime freeze identity",
            "",
            f"- Contract: `{RUNTIME_FREEZE_PATH.relative_to(ROOT).as_posix()}`",
            f"- Contract SHA-256: `{_sha256(RUNTIME_FREEZE_PATH)}`",
            "",
            "## Distribution",
            "",
            "### By scope",
            "",
            *[f"- `{scope}`: `{scope_counts[scope]}`" for scope in sorted(scope_counts)],
            "",
            "### By source",
            "",
            *[f"- `{source_id}`: `{source_counts[source_id]}`" for source_id in sorted(source_counts)],
            "",
            "The Stage 12A DRAFT review input and local frozen Corpus V2 artifacts were retained unchanged. No benchmark or retrieval run was performed.",
            "",
        ]
    )


def freeze() -> tuple[int, str]:
    validator = CanonicalGoldValidator()
    draft = _read_draft(validator)
    promoted = _promote(draft, validator)
    candidate = _jsonl_bytes(promoted)
    _write_collision_safe(RELEASED_PATH, candidate)

    # The exporter is authoritative for the released representation and also
    # guarantees that no DRAFT or REJECTED record can enter frozen gold.
    exported = export_reviewed_canonical_gold(RELEASED_PATH, RELEASED_PATH)
    if exported != 25 or RELEASED_PATH.read_bytes() != candidate:
        raise CanonicalGoldError("released exporter output differs from the deterministic reviewed candidate")

    released = validator.parse_file(RELEASED_PATH)
    if len(released) != 25 or any(record["status"] != "REVIEWED" for record in released):
        raise CanonicalGoldError("released artifact is not exactly 25 REVIEWED records")
    freeze_text = _freeze_document(released, _sha256(RELEASED_PATH), RELEASED_PATH.stat().st_size)
    _write_collision_safe(FREEZE_PATH, freeze_text.encode("utf-8"))
    return len(released), _sha256(RELEASED_PATH)


if __name__ == "__main__":
    count, digest = freeze()
    print(f"froze {count} REVIEWED records; sha256={digest}")
