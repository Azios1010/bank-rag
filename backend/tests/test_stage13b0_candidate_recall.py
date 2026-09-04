"""Offline contract tests for the Stage 13B0 candidate-recall audit."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.services.supabase_v2_retriever import normalize_specialist_scope  # noqa: E402
from scripts.run_stage13b0_candidate_recall import (  # noqa: E402
    CANDIDATE_DEPTH,
    COVERAGE_K,
    EXPECTED_GOLD_SHA256,
    FROZEN_MISS_IDS,
    Stage13B0CandidateRecallError,
    classify_rank,
    coverage_for_ids,
    gold_ranks,
    sha256_file,
    validate_identity,
)


def test_candidate_depths_and_coverage_include_requested_k_values() -> None:
    assert CANDIDATE_DEPTH == 50
    assert COVERAGE_K == (5, 10, 20, 50)
    values = coverage_for_ids(["a", "gold", "b", "c", "other"], ["gold", "other"])
    assert values["hit@5"] == 1
    assert values["recall@5"] == 1.0


def test_exact_gold_ranks_and_absent_rank() -> None:
    ranks = gold_ranks(["a", "gold", "b"], ["gold", "missing"])
    assert ranks == {"gold": 2, "missing": None}
    assert classify_rank(6).startswith("A")
    assert classify_rank(11).startswith("B")
    assert classify_rank(21).startswith("C")
    assert classify_rank(None).startswith("D")


def test_multi_gold_stage12a_004_uses_both_ids() -> None:
    corpus = FrozenCorpusV2()
    records = validate_identity(corpus)
    record = next(item for item in records if item["evaluation_id"] == "stage12a-004")
    assert record["expected_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_frozen_gold_sha_is_enforced() -> None:
    path = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
    assert sha256_file(path) == EXPECTED_GOLD_SHA256


def test_v2_identity_contains_25_reviewed_records() -> None:
    records = validate_identity(FrozenCorpusV2())
    assert len(records) == 25
    assert {record["status"] for record in records} == {"REVIEWED"}
    assert {record["evaluation_id"] for record in records} >= set(FROZEN_MISS_IDS)


def test_unsupported_banking_operations_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported specialist scope"):
        normalize_specialist_scope("BankingOperations")


def test_candidate_trace_output_contract_if_artifact_exists() -> None:
    path = ROOT / "dataset/evaluation/results/vector-v2-candidate-recall-traces.jsonl"
    if not path.exists():
        pytest.skip("candidate audit has not been run yet")
    traces = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(traces) == 25
    assert len({trace["evaluation_id"] for trace in traces}) == 25
    trace = next(item for item in traces if item["evaluation_id"] == "stage12a-004")
    assert len(trace["gold_canonical_chunk_ids"]) == 2
    assert len(trace["candidate_canonical_chunk_ids"]) == 50
