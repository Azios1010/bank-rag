import hashlib
import importlib.util
import json
from collections import Counter
from pathlib import Path

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2, leakage_flags


ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
EXPANDED_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.draft.jsonl"
REVIEW_PATH = ROOT / "docs/STAGE-13E-EXPANDED-GOLD-REVIEW-R1.md"
PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"

_SPEC = importlib.util.spec_from_file_location(
    "stage13e_r1_corrections", ROOT / "backend/scripts/apply_stage13e_r1_corrections.py"
)
assert _SPEC and _SPEC.loader
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
AUTHORIZED_IDS = _MODULE.AUTHORIZED_IDS
CHANGE_NOTES = _MODULE.CHANGE_NOTES
OLD_REJECTED_TARGETS = _MODULE.OLD_REJECTED_TARGETS


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_r1_has_frozen_seed_and_exact_status_distribution():
    pilot = _load(PILOT_PATH)
    expanded = _load(EXPANDED_PATH)
    assert hashlib.sha256(PILOT_PATH.read_bytes()).hexdigest() == PILOT_SHA256
    assert expanded[:25] == pilot
    assert len(expanded) == 100
    assert Counter(record["status"] for record in expanded) == {"REVIEWED": 25, "DRAFT": 75}
    assert all(record["review"] is None for record in expanded[25:])


def test_r1_only_authorized_records_have_r1_change_manifest():
    assert len(AUTHORIZED_IDS) == 16
    assert set(CHANGE_NOTES) == AUTHORIZED_IDS
    assert set(AUTHORIZED_IDS) == {
        "stage13e-032",
        "stage13e-037",
        "stage13e-038",
        "stage13e-039",
        "stage13e-046",
        "stage13e-050",
        "stage13e-053",
        "stage13e-058",
        "stage13e-059",
        "stage13e-062",
        "stage13e-067",
        "stage13e-069",
        "stage13e-075",
        "stage13e-079",
        "stage13e-083",
        "stage13e-098",
    }


def test_replacements_use_new_evidence_targets_and_keep_draft_status():
    by_id = {record["evaluation_id"]: record for record in _load(EXPANDED_PATH)}
    for record_id, old_id in OLD_REJECTED_TARGETS.items():
        record = by_id[record_id]
        assert record["status"] == "DRAFT"
        assert record["expected_canonical_chunk_ids"] != [old_id]
    assert by_id["stage13e-037"]["expected_canonical_chunk_ids"] == [
        "1ad078503e952d4c010471185961e8f00a5580e6ecb80b7b46efff824a9a9f09"
    ]
    assert by_id["stage13e-038"]["expected_canonical_chunk_ids"] == [
        "7b94c1d235374306aa2b1ab6ab9da4a9d8335c288ad88515cc4e85463d30c02e"
    ]
    assert by_id["stage13e-039"]["expected_canonical_chunk_ids"] == [
        "964bf8d08a30cdc684c80f3d672844e92d7cca27879e9cc2b055c3206eeacc42"
    ]
    assert by_id["stage13e-067"]["expected_canonical_chunk_ids"] == [
        "dcaaa7a6994303d7850c83a21693a418aba2420b7928337993e6be84a1842c21"
    ]
    assert by_id["stage13e-083"]["expected_canonical_chunk_ids"] == [
        "40cc0096b54df95d426fdf7c249200893e39320e287bce97205a7e751213b465"
    ]


def test_r1_specific_question_and_metadata_corrections_are_present():
    by_id = {record["evaluation_id"]: record for record in _load(EXPANDED_PATH)}
    assert by_id["stage13e-046"]["query"].startswith("Quy định nội bộ phải đặt ra yêu cầu quản lý")
    assert "trước khi đề xuất" not in by_id["stage13e-050"]["query"]
    assert "đúng một ngoại lệ mềm" in by_id["stage13e-053"]["query"]
    assert "Grade C-EXCEPTION-2" not in by_id["stage13e-053"]["query"]
    assert "180 ngày" in by_id["stage13e-062"]["gold_evidence"][0]["rationale"]
    assert "60 ngày" in by_id["stage13e-062"]["gold_evidence"][0]["rationale"]
    assert by_id["stage13e-098"]["query"].startswith("Thế chấp quyền sử dụng đất")
    assert by_id["stage13e-032"]["question_category"] == "direct"
    assert by_id["stage13e-058"]["question_category"] == "direct"
    assert by_id["stage13e-075"]["question_category"] == "direct"
    assert by_id["stage13e-079"]["question_category"] == "role"


def test_r1_evidence_and_distribution_invariants():
    records = CanonicalGoldValidator().parse_file(EXPANDED_PATH)
    corpus = FrozenCorpusV2()
    assert Counter(record["specialist_scope"] for record in records) == {
        "credit": 20,
        "risk_management": 20,
        "legal_compliance": 20,
        "customer_relationship": 20,
        "collateral_appraisal": 20,
    }
    assert Counter("synthetic" if record["is_synthetic"] else "real_authoritative" for record in records) == {
        "real_authoritative": 80,
        "synthetic": 20,
    }
    assert all(not leakage_flags(record, corpus) for record in records)
    assert sum(len(record["expected_canonical_chunk_ids"]) > 1 for record in records) == 1
    assert next(record for record in records if record["evaluation_id"] == "stage12a-004")[
        "expected_canonical_chunk_ids"
    ] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_r1_review_pack_contains_all_drafts_and_specific_change_notes():
    review = REVIEW_PATH.read_text(encoding="utf-8")
    assert review.count("- **Status:** `DRAFT`") == 75
    for record_id, note in CHANGE_NOTES.items():
        assert f"### {record_id}" in review
        assert f"- **Change note:** {note}" in review
    record_059_start = review.index("### stage13e-059")
    record_060_start = review.index("### stage13e-060")
    evidence_059 = review[record_059_start:record_060_start]
    assert "gắn việc bán sản phẩm bảo hiểm không bắt buộc" in evidence_059
