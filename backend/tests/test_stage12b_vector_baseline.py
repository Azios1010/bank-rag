"""Offline contract tests for the Stage 12B vector-only pilot artifacts."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.eval.gold_v2 import FrozenCorpusV2
from app.services.supabase_v2_retriever import (
    CanonicalV2RetrievalResult,
    normalize_specialist_scope,
)
from scripts.run_stage12b_vector_v2_baseline import (
    EXPECTED_GOLD_SHA256,
    GOLD_PATH,
    MAX_K,
    TRACE_PATH,
    validate_gold_identity,
    validate_result_contract,
    score_results,
)


def test_metrics_preserve_multi_gold_recall_and_cutoffs() -> None:
    gold = ["gold-a", "gold-b"]
    retrieved = ["other", "gold-b", "other-2", "gold-a"]

    scores = score_results(retrieved, gold)

    assert scores["hit@1"] == 0
    assert scores["hit@3"] == 1
    assert scores["recall@1"] == 0.0
    assert scores["recall@3"] == 0.5
    assert scores["recall@5"] == 1.0
    assert scores["mrr@1"] == 0.0
    assert scores["mrr@3"] == 0.5
    assert scores["mrr@5"] == 0.5
    assert 0.0 < float(scores["ndcg@3"]) < 1.0


def test_released_gold_sha_and_identity_are_frozen() -> None:
    corpus = FrozenCorpusV2()
    records = validate_gold_identity(corpus)

    assert len(records) == 25
    assert all(record["status"] == "REVIEWED" for record in records)
    assert EXPECTED_GOLD_SHA256 == (
        "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
    )
    assert GOLD_PATH.exists()


def test_stage12a_004_two_gold_ids_are_retained_in_trace() -> None:
    traces = [
        json.loads(line)
        for line in TRACE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    trace = next(item for item in traces if item["evaluation_id"] == "stage12a-004")

    assert trace["gold_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_trace_count_ids_order_and_serialized_latency() -> None:
    traces = [
        json.loads(line)
        for line in TRACE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    ids = [trace["evaluation_id"] for trace in traces]

    assert len(traces) == 25
    assert len(set(ids)) == 25
    assert ids == [f"stage12a-{index:03d}" for index in range(1, 26)]
    for trace in traces:
        assert len(trace["retrieved_canonical_chunk_ids"]) == MAX_K
        assert all(
            0.0 <= float(value) <= 1.0 for value in trace["metrics"].values()
        )
        assert all(float(value) >= 0.0 for value in trace["latency_ms"].values())


def test_v2_result_contract_rejects_an_unknown_canonical_id() -> None:
    result = CanonicalV2RetrievalResult(
        canonical_chunk_id="not-in-frozen-corpus",
        content="content",
        similarity=0.5,
        document_source_id="source",
        document_version_id="version",
        document_title="title",
        heading_path=[],
        locator={},
        namespace="REGULATION",
        visibility="SHARED",
        metadata={},
    )

    with pytest.raises(RuntimeError, match="non-V2 canonical ID"):
        validate_result_contract(result, FrozenCorpusV2(), "credit")


def test_banking_operations_is_not_a_supported_scope() -> None:
    with pytest.raises(ValueError, match="unsupported specialist scope"):
        normalize_specialist_scope("BankingOperations")
