"""Apply the final Stage 13E2 human corrections and freeze the 100-query gold.

The script is intentionally narrow.  It validates the pre-final R1 state,
changes only the three explicitly authorized records, preserves the corrected
75-record DRAFT artifact, promotes a separate released copy using the
canonical reviewed-gold serialization, and writes an auditable freeze note.

No retrieval, embedding runtime, model, FTS, reranker, or Supabase client is
used.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from app.eval.gold_v2 import (
    CanonicalGoldValidator,
    FrozenCorpusV2,
    export_reviewed_canonical_gold,
    leakage_flags,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
DRAFT_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.draft.jsonl"
RELEASE_PATH = PROJECT_ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
FREEZE_PATH = PROJECT_ROOT / "docs/STAGE-13E2-EXPANDED-GOLD-FREEZE.md"
PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
FREEZE_TIMESTAMP = "2026-09-04T00:00:00+07:00"
HUMAN_REVIEWER_ID = "human_manual_approval"
R2_REVIEW_NOTE = (
    "Explicit human approval for Stage 13E2: Stage 13E expansion APPROVE=75/75 "
    "after R2 minor corrections (038, 046, 059)."
)

EXPECTED_038_QUESTION = (
    "Trường hợp tổng mức phơi nhiễm trên 1 tỷ đồng và không quá 3 tỷ đồng, cấp nào "
    "có thể phê duyệt và hồ sơ phải đáp ứng những điều kiện gì?"
)
EXPECTED_038_RATIONALE = (
    "Quy tắc APR-TIER-2 áp dụng cho tổng mức phơi nhiễm trên 1 tỷ đồng và không quá "
    "3 tỷ đồng; chỉ hồ sơ Grade A/B không có ngoại lệ thuộc phạm vi này và phải có "
    "thẩm định Risk độc lập."
)
EXPECTED_038_GOLD = "7b94c1d235374306aa2b1ab6ab9da4a9d8335c288ad88515cc4e85463d30c02e"
EXPECTED_046_CATEGORY = "direct"
EXPECTED_059_CATEGORY = "direct"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write_records(path: Path, records: list[dict[str, Any]], preserve_seed_lines: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _write_corrected_draft(path: Path, records: list[dict[str, Any]], original_seed_lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for line in original_seed_lines:
            handle.write(line + "\n")
        for record in records[25:]:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


def _replace_tag_category(record: dict[str, Any], category: str) -> None:
    tags = list(record["tags"])
    if len(tags) < 3:
        raise ValueError(f"Missing category tag for {record['evaluation_id']}")
    tags[2] = category
    record["tags"] = tags


def _apply_r2_delta(records: list[dict[str, Any]]) -> dict[str, str]:
    by_id = {record["evaluation_id"]: record for record in records}
    required = {"stage13e-038", "stage13e-046", "stage13e-059"}
    if not required <= set(by_id):
        raise ValueError("One or more R2 IDs are missing")

    item038 = by_id["stage13e-038"]
    if item038["query"] != "Khoản cấp tín dụng trên 1 tỷ đồng đến 3 tỷ đồng có thể do cấp nào phê duyệt và phải đáp ứng những điều kiện gì?":
        raise ValueError("stage13e-038 is not in the expected pre-R2 state")
    if item038["question_category"] != "threshold" or item038["expected_canonical_chunk_ids"] != [EXPECTED_038_GOLD]:
        raise ValueError("stage13e-038 pre-R2 metadata or gold drifted")
    if "tổng dư nợ" not in item038["gold_evidence"][0]["rationale"]:
        raise ValueError("stage13e-038 pre-R2 rationale does not show the expected terminology defect")

    for record_id in ("stage13e-046", "stage13e-059"):
        if by_id[record_id]["question_category"] != "consequence":
            raise ValueError(f"{record_id} is not in the expected pre-R2 state")

    item038["query"] = EXPECTED_038_QUESTION
    item038["gold_evidence"][0]["rationale"] = EXPECTED_038_RATIONALE
    for record_id in ("stage13e-046", "stage13e-059"):
        by_id[record_id]["question_category"] = "direct"
        _replace_tag_category(by_id[record_id], "direct")
    return {
        "stage13e-038": EXPECTED_038_QUESTION,
        "stage13e-046": EXPECTED_046_CATEGORY,
        "stage13e-059": EXPECTED_059_CATEGORY,
    }


def _changed_paths(before: dict[str, Any], after: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for key in sorted(set(before) | set(after)):
        if before.get(key) != after.get(key):
            paths.add(key)
    return paths


def _validate_r2_delta(before: list[dict[str, Any]], after: list[dict[str, Any]]) -> None:
    before_by_id = {record["evaluation_id"]: record for record in before}
    after_by_id = {record["evaluation_id"]: record for record in after}
    if set(before_by_id) != set(after_by_id):
        raise ValueError("R2 changed the record ID set")
    allowed_top_level = {
        "stage13e-038": {"query", "gold_evidence"},
        "stage13e-046": {"question_category", "tags"},
        "stage13e-059": {"question_category", "tags"},
    }
    for record_id, old in before_by_id.items():
        new = after_by_id[record_id]
        if record_id not in allowed_top_level and new != old:
            raise ValueError(f"Unauthorized R2 mutation: {record_id}")
        if record_id in allowed_top_level:
            changed = _changed_paths(old, new)
            if changed != allowed_top_level[record_id]:
                raise ValueError(f"Unexpected R2 fields for {record_id}: {sorted(changed)}")
            for key in set(old) - allowed_top_level[record_id]:
                if old[key] != new[key]:
                    raise ValueError(f"Unauthorized nested R2 mutation in {record_id}.{key}")
            if record_id == "stage13e-038":
                old_evidence = copy.deepcopy(old["gold_evidence"][0])
                new_evidence = copy.deepcopy(new["gold_evidence"][0])
                old_evidence["rationale"] = None
                new_evidence["rationale"] = None
                if old_evidence != new_evidence:
                    raise ValueError("stage13e-038 changed evidence beyond rationale")
    if sum(before_by_id[item_id] != after_by_id[item_id] for item_id in allowed_top_level) != 3:
        raise ValueError("Expected exactly three R2 records to change")


def _validate_all(records: list[dict[str, Any]], corpus: FrozenCorpusV2, expect_reviewed: bool) -> None:
    validator = CanonicalGoldValidator(corpus)
    for line_no, record in enumerate(records, 1):
        validator.validate_record(record, records[: line_no - 1], line_no)
    if expect_reviewed:
        if Counter(record["status"] for record in records) != Counter({"REVIEWED": 100}):
            raise ValueError("Released artifact is not exactly 100 REVIEWED records")
    else:
        if Counter(record["status"] for record in records) != Counter({"REVIEWED": 25, "DRAFT": 75}):
            raise ValueError("Corrected draft is not 25 REVIEWED + 75 DRAFT")
    if any(leakage_flags(record, corpus) for record in records):
        raise ValueError("R2 artifact contains query leakage")
    if len({record["evaluation_id"] for record in records}) != 100:
        raise ValueError("Duplicate evaluation IDs")
    if len({record["query"] for record in records}) != 100:
        raise ValueError("Duplicate questions")
    if Counter(record["specialist_scope"] for record in records) != Counter({scope: 20 for scope in (
        "credit", "risk_management", "legal_compliance", "customer_relationship", "collateral_appraisal"
    )}):
        raise ValueError("Scope distribution drifted")
    if Counter("synthetic" if record["is_synthetic"] else "real_authoritative" for record in records) != Counter({
        "real_authoritative": 80, "synthetic": 20
    }):
        raise ValueError("Provenance distribution drifted")
    if Counter(record["visibility"] for record in records) != Counter({"SHARED": 80, "SCOPED": 20}):
        raise ValueError("Visibility distribution drifted")


def _review_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    reviewed = copy.deepcopy(records)
    for record in reviewed[25:]:
        record["status"] = "REVIEWED"
        record["review"] = {
            "reviewer_id": HUMAN_REVIEWER_ID,
            "reviewed_at": FREEZE_TIMESTAMP,
            "decision": "REVIEWED",
            "notes": R2_REVIEW_NOTE,
        }
    return reviewed


def _write_freeze_document(records: list[dict[str, Any]]) -> None:
    status = Counter(record["status"] for record in records)
    scopes = Counter(record["specialist_scope"] for record in records)
    provenance = Counter("synthetic" if record["is_synthetic"] else "real_authoritative" for record in records)
    visibility = Counter(record["visibility"] for record in records)
    sources = Counter(record["document"]["source_id"] for record in records)
    categories = Counter(record.get("question_category", "uncategorized") for record in records[25:])
    content = [
        "# Stage 13E2 — Expanded Gold Freeze",
        "",
        "## Purpose and authority",
        "",
        "This document freezes the human-approved 100-query retrieval gold set.",
        "The gold was authored evidence-first from frozen Corpus V2. No retrieval",
        "output, vector rank, FTS rank, RRF score, reranker score, or model judgment",
        "was used to select expected evidence IDs.",
        "",
        "Human review is authoritative:",
        "",
        "- Stage 12A seed: 25 / 25 REVIEWED.",
        "- Stage 13E expansion: 75 / 75 APPROVED after R2 minor corrections.",
        "- Total: 100 / 100 HUMAN-REVIEWED.",
        "- Reviewer representation: `human_manual_approval`.",
        "",
        "## Review history",
        "",
        "- R0: 75 evidence-first DRAFT records created.",
        "- R1: 5 evidence targets replaced, 6 substantive edits, 5 metadata/rationale edits; 59 drafts untouched.",
        "- R2: only `stage13e-038`, `stage13e-046`, and `stage13e-059` corrected; replacements=0, rejects=0.",
        "- R2 result: APPROVE AS-IS 72 / 75 plus 3 MINOR CORRECTIONS; final expansion approval 75 / 75.",
        "",
        "## Released artifact",
        "",
        f"- Path: `dataset/evaluation/retrieval-v2-gold-expanded.jsonl`",
        f"- Bytes: {RELEASE_PATH.stat().st_size}",
        f"- SHA-256: `{_sha256(RELEASE_PATH)}`",
        f"- Freeze timestamp: `{FREEZE_TIMESTAMP}`",
        f"- Status counts: `{dict(sorted(status.items()))}`",
        "",
        "## Distribution",
        "",
        f"- Scope: `{dict(sorted(scopes.items()))}`",
        f"- Provenance: `{dict(sorted(provenance.items()))}`",
        f"- Visibility: `{dict(sorted(visibility.items()))}`",
        f"- New-draft question categories at freeze: `{dict(sorted(categories.items()))}`",
        f"- Multi-gold records: `{sum(len(record['expected_canonical_chunk_ids']) > 1 for record in records)}`",
        "- `stage12a-004` retains both approved canonical gold IDs.",
        "- New Stage 13E multi-gold additions: 0.",
        "",
        "## Source coverage",
        "",
        f"- Real authoritative sources: {len([source for source in sources if not source.startswith('synthetic-')])} / 7.",
        f"- Synthetic sources: {len([source for source in sources if source.startswith('synthetic-')])} / 3.",
        f"- Total sources: {len(sources)} / 10.",
        "",
        "| Source ID | Records |",
        "|---|---:|",
    ]
    content.extend(f"| `{source_id}` | {count} |" for source_id, count in sorted(sources.items()))
    content.extend([
        "",
        "## Frozen identities",
        "",
        "- Stage 12A pilot SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`",
        "- Corpus manifest SHA-256: `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`",
        "- Embedding artifact SHA-256: `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`",
        "- Embedding manifest SHA-256: `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`",
        "- Corpus: `policy-corpus-v2`, 1,610 canonical chunks.",
        "- Embedding: `Qwen3-Embedding-0.6B`, 1,024 dimensions, llama.cpp / Vulkan.",
        "",
        "## Benchmark boundary",
        "",
        "No vector retrieval, reranker evaluation, FTS, hybrid search, Hit@K,",
        "Recall@K, MRR, or nDCG benchmark was run in Stage 13E2. Benchmarking begins",
        "in Stage 13E3.",
        "",
    ])
    FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    FREEZE_PATH.write_text("\n".join(content), encoding="utf-8", newline="\n")


def build() -> dict[str, Any]:
    if _sha256(PILOT_PATH) != PILOT_SHA256:
        raise ValueError("Frozen Stage 12A pilot SHA mismatch")
    before = _load(DRAFT_PATH)
    if len(before) != 100 or Counter(record["status"] for record in before) != Counter({"REVIEWED": 25, "DRAFT": 75}):
        raise ValueError("Expanded artifact is not in the expected pre-freeze state")
    pilot = _load(PILOT_PATH)
    if before[:25] != pilot:
        raise ValueError("Expanded seed differs from frozen Stage 12A pilot")

    corpus = FrozenCorpusV2()
    corrected = copy.deepcopy(before)
    _apply_r2_delta(corrected)
    _validate_r2_delta(before, corrected)
    _validate_all(corrected, corpus, expect_reviewed=False)

    original_seed_lines = DRAFT_PATH.read_text(encoding="utf-8").splitlines()[:25]
    _write_corrected_draft(DRAFT_PATH, corrected, original_seed_lines)

    released = _review_records(corrected)
    _validate_all(released, corpus, expect_reviewed=True)
    for line_no, record in enumerate(released, 1):
        CanonicalGoldValidator(corpus).validate_record(record, released[: line_no - 1], line_no)

    # Use the project's canonical reviewed-only exporter without introducing a
    # repository staging artifact.  The temporary input is outside the repo.
    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n", suffix="-stage13e2.jsonl", delete=False) as handle:
            temp_path = Path(handle.name)
            for record in released:
                handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
        export_reviewed_canonical_gold(temp_path, RELEASE_PATH)
    finally:
        if temp_path is not None:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                pass

    released_after = _load(RELEASE_PATH)
    _validate_all(released_after, corpus, expect_reviewed=True)
    if released_after[:25] != pilot:
        raise ValueError("Released seed differs semantically from frozen pilot")
    item004 = next(record for record in released_after if record["evaluation_id"] == "stage12a-004")
    if len(item004["expected_canonical_chunk_ids"]) != 2:
        raise ValueError("stage12a-004 multi-gold was collapsed")
    _write_freeze_document(released_after)
    return {
        "draft_records": len(_load(DRAFT_PATH)),
        "released_records": len(released_after),
        "released_bytes": RELEASE_PATH.stat().st_size,
        "released_sha256": _sha256(RELEASE_PATH),
        "freeze_document": str(FREEZE_PATH.relative_to(PROJECT_ROOT)),
    }


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, sort_keys=True))
