"""Mechanical checks for the authoritative Stage 14B human-review freeze."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "dataset/evaluation/results"
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
SUMMARY_PATH = RESULTS / "rag-answer-v2-expanded-human-review-summary.json"
KNOWN_LABELS_PATH = RESULTS / "rag-answer-v2-expanded-human-review-known-labels.jsonl"
ORIGINAL_REVIEW_PATH = ROOT / "docs/STAGE-14A-RAG-ANSWER-REVIEW.md"
COMPLETE_LABEL_PATH = RESULTS / "rag-answer-v2-expanded-human-review.jsonl"

PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
GOLD_SHA256 = "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"

PARTIAL_IDS = {
    "stage12a-004",
    "stage12a-011",
    "stage12a-013",
    "stage12a-014",
    "stage13e-037",
    "stage13e-043",
    "stage13e-049",
    "stage13e-050",
    "stage13e-059",
    "stage13e-065",
    "stage13e-068",
    "stage13e-073",
    "stage13e-080",
    "stage13e-083",
    "stage13e-084",
    "stage13e-090",
    "stage13e-091",
    "stage13e-099",
}
CITATION_IDS = {
    "stage12a-003",
    "stage12a-008",
    "stage12a-019",
    "stage13e-034",
    "stage13e-036",
    "stage13e-038",
}
TRUNCATION_IDS = {
    "stage12a-004",
    "stage12a-013",
    "stage12a-024",
    "stage13e-050",
    "stage13e-059",
    "stage13e-091",
    "stage13e-099",
}
FULL_FAILURE_IDS = {
    "stage12a-002",
    "stage12a-024",
    "stage13e-040",
    "stage13e-042",
}


def _load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_frozen_gold_hashes_and_stage14a_review_pack_preserved() -> None:
    assert hashlib.sha256(PILOT_PATH.read_bytes()).hexdigest() == PILOT_SHA256
    assert hashlib.sha256(GOLD_PATH.read_bytes()).hexdigest() == GOLD_SHA256
    assert "Status: `DRAFT`" in ORIGINAL_REVIEW_PATH.read_text(encoding="utf-8")
    assert not COMPLETE_LABEL_PATH.exists()


def test_human_summary_counts_are_authoritative_and_sum_to_100() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["human_review_authoritative"] is True
    assert summary["semantic_judge"] == "human"
    assert "llm_judge" not in summary
    assert summary["record_count"] == 100
    assert summary["correctness"] == {"PASS": 78, "PARTIAL": 18, "FAIL": 4}
    assert summary["groundedness"] == {
        "FULLY_GROUNDED": 87,
        "PARTIALLY_GROUNDED": 12,
        "UNGROUNDED": 1,
    }
    assert summary["citation_quality"] == {"CORRECT": 81, "PARTIAL": 12, "INCORRECT": 7}
    assert summary["abstention"] == {
        "APPROPRIATE": 0,
        "UNNECESSARY": 0,
        "MISSING_WHEN_REQUIRED": 4,
        "N/A": 96,
    }
    assert summary["failure_source"] == {
        "NONE": 72,
        "GENERATION": 19,
        "CITATION": 6,
        "MIXED": 3,
        "RETRIEVAL": 0,
        "RERANKING": 0,
    }
    assert summary["clean_answers"] == 72
    assert summary["gold_present_subset"] == {"count": 97, "PASS": 78, "PARTIAL": 18, "FAIL": 1}
    assert summary["gold_absent_subset"]["count"] == 3
    assert summary["gold_absent_subset"]["correct_abstentions"] == 0


def test_known_explicit_labels_are_incomplete_and_cover_only_supplied_ids() -> None:
    rows = _load_jsonl(KNOWN_LABELS_PATH)
    ids = {row["evaluation_id"] for row in rows}
    expected_ids = PARTIAL_IDS | CITATION_IDS | TRUNCATION_IDS | FULL_FAILURE_IDS
    assert len(rows) == len(ids) == 28
    assert ids == expected_ids
    assert len(rows) < 100
    assert all(row["artifact_status"] == "INCOMPLETE_EXPLICIT_HUMAN_ANNOTATIONS_ONLY" for row in rows)
    assert all(row["human_review_authoritative"] is True for row in rows)
    assert all("groundedness" in row["unassigned_semantic_fields"] for row in rows)


def test_explicit_failure_lists_and_structural_status_are_exact() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert set(summary["partial_ids"]) == PARTIAL_IDS
    assert set(summary["citation_primary_ids"]) == CITATION_IDS
    assert set(summary["truncation_ids"]) == TRUNCATION_IDS
    assert set(summary["full_failure_ids"]) == FULL_FAILURE_IDS
    assert summary["stage14a_structural"] == {
        "answers_attempted": 100,
        "answers_generated": 100,
        "technical_failures": 0,
        "technical_retries": 0,
        "answers_with_valid_citations": 94,
        "answers_with_zero_citations": 4,
        "answers_with_invalid_citation_ids": 2,
        "abstentions_detected": 0,
        "gold_present_in_top5": 97,
        "gold_absent_in_top5": 3,
    }


def test_summary_scope_totals_are_balanced_and_no_unsupported_scope_is_present() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert all(sum(values.values()) == 20 for values in summary["per_scope_correctness"].values())
    assert set(summary["per_scope_correctness"]) == {
        "credit",
        "risk_management",
        "legal_compliance",
        "customer_relationship",
        "collateral_appraisal",
    }
    records = _load_jsonl(GOLD_PATH)
    assert len(records) == 100
    assert Counter(row["status"] for row in records) == {"REVIEWED": 100}
    assert all(row["specialist_scope"] != "BankingOperations" for row in records)
