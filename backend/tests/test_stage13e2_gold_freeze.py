import hashlib
import json
from collections import Counter
from pathlib import Path

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2, leakage_flags


ROOT = Path(__file__).resolve().parents[2]
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
DRAFT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.draft.jsonl"
RELEASE_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
FREEZE_PATH = ROOT / "docs/STAGE-13E2-EXPANDED-GOLD-FREEZE.md"
PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
RELEASE_SHA256 = "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
EXPECTED_038_GOLD = "7b94c1d235374306aa2b1ab6ab9da4a9d8335c288ad88515cc4e85463d30c02e"


def _load(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_seed_and_pre_freeze_statuses_are_preserved():
    pilot = _load(PILOT_PATH)
    draft = CanonicalGoldValidator().parse_file(DRAFT_PATH)
    assert hashlib.sha256(PILOT_PATH.read_bytes()).hexdigest() == PILOT_SHA256
    assert draft[:25] == pilot
    assert Counter(record["status"] for record in draft) == {"REVIEWED": 25, "DRAFT": 75}
    assert all(record["review"] is None for record in draft[25:])


def test_exact_three_r2_corrections_are_represented():
    records = _load(DRAFT_PATH)
    by_id = {record["evaluation_id"]: record for record in records}
    assert by_id["stage13e-038"]["query"] == (
        "Trường hợp tổng mức phơi nhiễm trên 1 tỷ đồng và không quá 3 tỷ đồng, cấp nào "
        "có thể phê duyệt và hồ sơ phải đáp ứng những điều kiện gì?"
    )
    assert by_id["stage13e-038"]["expected_canonical_chunk_ids"] == [EXPECTED_038_GOLD]
    assert "tổng mức phơi nhiễm" in by_id["stage13e-038"]["gold_evidence"][0]["rationale"]
    assert "tổng dư nợ" not in by_id["stage13e-038"]["gold_evidence"][0]["rationale"]
    assert by_id["stage13e-046"]["question_category"] == "direct"
    assert by_id["stage13e-059"]["question_category"] == "direct"
    assert by_id["stage13e-046"]["status"] == "DRAFT"
    assert by_id["stage13e-059"]["status"] == "DRAFT"


def test_released_artifact_is_exactly_100_reviewed_and_valid():
    pilot = _load(PILOT_PATH)
    released = CanonicalGoldValidator().parse_file(RELEASE_PATH)
    corpus = FrozenCorpusV2()
    assert len(released) == 100
    assert Counter(record["status"] for record in released) == {"REVIEWED": 100}
    assert released[:25] == pilot
    assert all(record["review"]["decision"] == "REVIEWED" for record in released)
    assert all(not leakage_flags(record, corpus) for record in released)
    assert next(record for record in released if record["evaluation_id"] == "stage12a-004")[
        "expected_canonical_chunk_ids"
    ] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_released_distribution_and_source_coverage():
    records = _load(RELEASE_PATH)
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
    assert Counter(record["visibility"] for record in records) == {"SHARED": 80, "SCOPED": 20}
    assert len({record["document"]["source_id"] for record in records}) == 10
    assert all(record["specialist_scope"] != "BankingOperations" for record in records)


def test_release_hash_and_deterministic_serialization_are_recorded():
    assert hashlib.sha256(RELEASE_PATH.read_bytes()).hexdigest() == RELEASE_SHA256
    for line in RELEASE_PATH.read_text(encoding="utf-8").splitlines():
        record = json.loads(line)
        assert line == json.dumps(record, ensure_ascii=False, sort_keys=True)
    freeze = FREEZE_PATH.read_text(encoding="utf-8")
    assert RELEASE_SHA256 in freeze
    assert "75 / 75 APPROVED after R2 minor corrections" in freeze
    assert "100 / 100 HUMAN-REVIEWED" in freeze
