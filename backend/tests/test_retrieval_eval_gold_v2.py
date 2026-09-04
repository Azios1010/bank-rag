import copy
import json
from pathlib import Path

import pytest

from app.eval.gold_v2 import (
    CanonicalGoldError,
    CanonicalGoldValidator,
    FrozenCorpusV2,
    export_reviewed_canonical_gold,
)


ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.draft.jsonl"


def _records() -> list[dict]:
    return CanonicalGoldValidator().parse_file(PILOT_PATH)


def _write(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records),
        encoding="utf-8",
    )


def test_stage12a_pilot_is_evidence_first_and_draft_only():
    records = _records()
    assert len(records) == 25
    assert {record["status"] for record in records} == {"DRAFT"}
    assert all(record["review"] is None for record in records)
    assert all(record["creation_provenance"]["retrieval_used"] is False for record in records)
    assert all(record["gold_evidence"] for record in records)


def test_stage12a_004_uses_complete_two_chunk_evidence():
    record = next(item for item in _records() if item["evaluation_id"] == "stage12a-004")
    assert record["expected_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]
    assert [item["canonical_chunk_id"] for item in record["gold_evidence"]] == record[
        "expected_canonical_chunk_ids"
    ]
    CanonicalGoldValidator().validate_record(record)


def test_evidence_list_must_align_with_expected_ids():
    record = copy.deepcopy(
        next(item for item in _records() if item["evaluation_id"] == "stage12a-004")
    )
    record["gold_evidence"] = list(reversed(record["gold_evidence"]))
    with pytest.raises(CanonicalGoldError, match="match evidence IDs in order"):
        CanonicalGoldValidator().validate_record(record)


def test_missing_direct_evidence_excerpt_is_rejected():
    record = copy.deepcopy(
        next(item for item in _records() if item["evaluation_id"] == "stage12a-008")
    )
    record["gold_evidence"][0]["excerpt"] = ""
    with pytest.raises(CanonicalGoldError, match="evidence excerpt missing"):
        CanonicalGoldValidator().validate_record(record)


def test_reviewed_and_rejected_states_are_valid_but_draft_cannot_self_review():
    validator = CanonicalGoldValidator()
    draft = _records()[0]
    validator.validate_record(draft)

    reviewed = copy.deepcopy(draft)
    reviewed["status"] = "REVIEWED"
    reviewed["review"] = {
        "reviewer_id": "human-reviewer-1",
        "reviewed_at": "2026-09-03T10:00:00+07:00",
        "decision": "REVIEWED",
        "notes": "Evidence and question accepted.",
    }
    validator.validate_record(reviewed)

    rejected = copy.deepcopy(draft)
    rejected["status"] = "REJECTED"
    rejected["review"] = {
        "reviewer_id": "human-reviewer-1",
        "reviewed_at": "2026-09-03T10:00:00+07:00",
        "decision": "REJECTED",
        "notes": "Needs a narrower question.",
    }
    validator.validate_record(rejected)

    self_review = copy.deepcopy(draft)
    self_review["review"] = {
        "reviewer_id": "stage12a_gold_pilot_builder",
        "reviewed_at": "2026-09-03T10:00:00+07:00",
        "decision": "REVIEWED",
    }
    with pytest.raises(CanonicalGoldError, match="DRAFT cannot self-review"):
        validator.validate_record(self_review)


def test_only_reviewed_records_are_exportable(tmp_path):
    record = copy.deepcopy(_records()[0])
    record["status"] = "REVIEWED"
    record["review"] = {
        "reviewer_id": "human-reviewer-1",
        "reviewed_at": "2026-09-03T10:00:00+07:00",
        "decision": "REVIEWED",
    }
    reviewed_input = tmp_path / "reviewed.jsonl"
    output = tmp_path / "frozen.jsonl"
    _write(reviewed_input, [record])
    assert export_reviewed_canonical_gold(reviewed_input, output) == 1
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "REVIEWED"

    mixed_input = tmp_path / "mixed.jsonl"
    _write(mixed_input, [record, _records()[1]])
    with pytest.raises(CanonicalGoldError, match="only REVIEWED records"):
        export_reviewed_canonical_gold(mixed_input, tmp_path / "should-not-exist.jsonl")


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("expected_canonical_chunk_ids", ["0" * 64], "invalid Corpus V2 ID"),
        ("specialist_scope", "BankingOperations", "unsupported specialist scope"),
    ],
)
def test_invalid_target_or_scope_is_rejected(field, value, message):
    record = copy.deepcopy(_records()[0])
    if field == "expected_canonical_chunk_ids":
        record[field] = value
        record["gold_evidence"][0]["canonical_chunk_id"] = value[0]
    else:
        record[field] = value
    with pytest.raises(CanonicalGoldError, match=message):
        CanonicalGoldValidator().validate_record(record)


def test_missing_embedding_identity_is_rejected():
    record = copy.deepcopy(_records()[0])
    del record["embedding_identity"]
    with pytest.raises(CanonicalGoldError, match="embedding_identity"):
        CanonicalGoldValidator().validate_record(record)


def test_duplicate_questions_and_missing_evidence_provenance_are_rejected():
    validator = CanonicalGoldValidator()
    first, second = _records()[:2]
    duplicate = copy.deepcopy(second)
    duplicate["query"] = first["query"]
    with pytest.raises(CanonicalGoldError, match="duplicate question"):
        validator.validate_record(duplicate, [first])

    no_evidence = copy.deepcopy(first)
    no_evidence["gold_evidence"] = []
    no_evidence["expected_canonical_chunk_ids"] = []
    with pytest.raises(CanonicalGoldError, match="expected canonical IDs"):
        validator.validate_record(no_evidence)


def test_frozen_identity_is_local_and_not_a_runtime_dependency():
    corpus = FrozenCorpusV2()
    assert len(corpus.rows) == 1610
    assert corpus.corpus_identity["chunk_count"] == 1610
    assert corpus.embedding_identity["dimension"] == 1024
    assert corpus.embedding_identity["runtime"] == "llama.cpp"
