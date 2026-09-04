import copy
import hashlib
import json
from pathlib import Path

import pytest

from app.eval.gold_v2 import CanonicalGoldError, CanonicalGoldValidator, export_reviewed_canonical_gold


ROOT = Path(__file__).resolve().parents[2]
DRAFT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.draft.jsonl"
RELEASED_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
FREEZE_PATH = ROOT / "docs/STAGE-12A-GOLD-PILOT-FREEZE.md"


def _write(path: Path, records: list[dict]) -> None:
    path.write_bytes(
        b"".join(
            (json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
            for record in records
        )
    )


def test_released_gold_is_exactly_25_reviewed_and_preserves_multigold():
    records = CanonicalGoldValidator().parse_file(RELEASED_PATH)
    assert len(records) == 25
    assert {record["status"] for record in records} == {"REVIEWED"}
    assert all(record["review"]["decision"] == "REVIEWED" for record in records)
    assert next(
        record for record in records if record["evaluation_id"] == "stage12a-004"
    )["expected_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_draft_input_is_not_released_as_frozen_gold():
    draft = CanonicalGoldValidator().parse_file(DRAFT_PATH)
    released = CanonicalGoldValidator().parse_file(RELEASED_PATH)
    assert {record["status"] for record in draft} == {"DRAFT"}
    assert {record["status"] for record in released} == {"REVIEWED"}


def test_rejected_record_cannot_enter_released_gold(tmp_path):
    records = CanonicalGoldValidator().parse_file(RELEASED_PATH)
    rejected = copy.deepcopy(records[0])
    rejected["status"] = "REJECTED"
    rejected["review"]["decision"] = "REJECTED"
    rejected_input = tmp_path / "rejected.jsonl"
    _write(rejected_input, [rejected])
    with pytest.raises(CanonicalGoldError, match="only REVIEWED records"):
        export_reviewed_canonical_gold(rejected_input, tmp_path / "released.jsonl")


def test_released_identity_is_required(tmp_path):
    record = copy.deepcopy(CanonicalGoldValidator().parse_file(RELEASED_PATH)[0])
    del record["embedding_identity"]
    invalid_input = tmp_path / "invalid.jsonl"
    _write(invalid_input, [record])
    with pytest.raises(CanonicalGoldError, match="embedding_identity"):
        export_reviewed_canonical_gold(invalid_input, tmp_path / "released.jsonl")


def test_export_ordering_is_deterministic(tmp_path):
    records = CanonicalGoldValidator().parse_file(RELEASED_PATH)
    input_path = tmp_path / "reviewed.jsonl"
    output_path = tmp_path / "exported.jsonl"
    _write(input_path, records)
    assert export_reviewed_canonical_gold(input_path, output_path) == 25
    assert output_path.read_bytes() == RELEASED_PATH.read_bytes()
    assert [record["evaluation_id"] for record in records] == sorted(
        record["evaluation_id"] for record in records
    )


def test_freeze_document_records_released_hash_and_counts():
    released_hash = hashlib.sha256(RELEASED_PATH.read_bytes()).hexdigest()
    freeze = FREEZE_PATH.read_text(encoding="utf-8")
    assert f"SHA-256: `{released_hash}`" in freeze
    assert "Records: `25`" in freeze
    assert "REVIEWED: `25`" in freeze
    assert "APPROVE=25, EDIT=0, REJECT=0" in freeze
