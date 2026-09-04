import hashlib
import json
from collections import Counter
from pathlib import Path

from app.eval.gold_v2 import CanonicalGoldValidator, SUPPORTED_SCOPES


ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
EXPANDED_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.draft.jsonl"
REVIEW_PATH = ROOT / "docs/STAGE-13E-EXPANDED-GOLD-REVIEW.md"
PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"


def _records() -> list[dict]:
    return CanonicalGoldValidator().parse_file(EXPANDED_PATH)


def test_expanded_gold_has_frozen_seed_and_75_new_drafts():
    records = _records()
    assert len(records) == 100
    assert Counter(record["status"] for record in records) == {"REVIEWED": 25, "DRAFT": 75}
    assert [record["evaluation_id"] for record in records[:25]] == [
        f"stage12a-{number:03d}" for number in range(1, 26)
    ]
    assert [record["evaluation_id"] for record in records[25:]] == [
        f"stage13e-{number:03d}" for number in range(26, 101)
    ]
    assert all(record["review"] is None for record in records[25:])


def test_frozen_pilot_is_byte_for_byte_unchanged():
    assert hashlib.sha256(PILOT_PATH.read_bytes()).hexdigest() == PILOT_SHA256


def test_expanded_distribution_and_source_coverage_are_balanced():
    records = _records()
    assert Counter(record["specialist_scope"] for record in records) == {
        "credit": 20,
        "risk_management": 20,
        "legal_compliance": 20,
        "customer_relationship": 20,
        "collateral_appraisal": 20,
    }
    assert Counter("synthetic" if record["is_synthetic"] else "real" for record in records) == {
        "real": 80,
        "synthetic": 20,
    }
    assert Counter(record["visibility"] for record in records) == {"SHARED": 80, "SCOPED": 20}
    assert len({record["document"]["source_id"] for record in records}) == 10
    assert all(record["specialist_scope"] in SUPPORTED_SCOPES for record in records)
    assert all(record["specialist_scope"] != "BankingOperations" for record in records)


def test_new_drafts_have_requested_question_taxonomy_and_provenance():
    new_records = _records()[25:]
    expected_categories = {
        "direct",
        "threshold",
        "exception",
        "procedural",
        "role",
        "multi-condition",
        "distinction",
        "consequence",
        "customer-facing",
        "internal-policy",
    }
    assert {record["question_category"] for record in new_records} == expected_categories
    assert {record["difficulty"] for record in new_records} == {"EASY", "MEDIUM", "HARD"}
    assert all(record["creation_provenance"]["retrieval_used"] is False for record in new_records)
    assert all("human" in record["creation_provenance"]["method"] for record in new_records)
    assert all(record["status"] == "DRAFT" for record in new_records)
    assert all(len(record["expected_canonical_chunk_ids"]) == 1 for record in new_records)


def test_evidence_ids_are_grounded_and_aligned_for_all_records():
    records = _records()
    corpus_ids = set(CanonicalGoldValidator().corpus.by_id)
    for record in records:
        ids = record["expected_canonical_chunk_ids"]
        evidence_ids = [item["canonical_chunk_id"] for item in record["gold_evidence"]]
        assert set(ids) <= corpus_ids
        assert evidence_ids == ids
        assert record["corpus_identity"]["chunk_count"] == 1610
        assert record["embedding_identity"]["model"] == "Qwen3-Embedding-0.6B"
        assert record["embedding_identity"]["dimension"] == 1024


def test_seed_multigold_and_new_draft_ids_are_preserved():
    records = _records()
    seed_multigold = next(record for record in records if record["evaluation_id"] == "stage12a-004")
    assert seed_multigold["expected_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]
    assert sum(len(record["expected_canonical_chunk_ids"]) > 1 for record in records[25:]) == 0


def test_review_pack_lists_every_new_draft():
    review = REVIEW_PATH.read_text(encoding="utf-8")
    for number in range(26, 101):
        assert f"### stage13e-{number:03d}" in review
    assert review.count("- **Status:** `DRAFT`") == 75
