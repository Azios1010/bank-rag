"""Offline contract tests for the Stage 13E3 confirmation artifacts."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import pytest

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2
from app.eval.metrics import binary_ndcg_at_k, hit_at_k, mrr_at_k, recall_at_k


ROOT = Path(__file__).resolve().parents[2]
GOLD = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
PILOT = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
CANDIDATES = ROOT / "dataset/evaluation/results/vector-top20-v2-expanded-candidates.jsonl"
SUMMARY = ROOT / "dataset/evaluation/results/reranker-depth-confirmation-v2-expanded-summary.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_frozen_expanded_gold_and_pilot_identity() -> None:
    assert _sha256(GOLD) == "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
    assert _sha256(PILOT) == "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
    records = CanonicalGoldValidator().parse_file(GOLD)
    assert len(records) == 100
    assert {record["status"] for record in records} == {"REVIEWED"}


def test_one_top20_candidate_list_and_exact_top10_prefix_per_query() -> None:
    corpus = FrozenCorpusV2()
    records = CanonicalGoldValidator(corpus).parse_file(GOLD)
    traces = _jsonl(CANDIDATES)
    assert len(traces) == 100
    assert [trace["evaluation_id"] for trace in traces] == [record["evaluation_id"] for record in records]
    assert sum(len(trace["vector_candidate_canonical_chunk_ids"]) for trace in traces) == 2000
    for trace in traces:
        ids = trace["vector_candidate_canonical_chunk_ids"]
        assert trace["candidate_depth"] == 20
        assert len(ids) == 20
        assert len(set(ids)) == 20
        assert set(ids) <= set(corpus.by_id)
        assert trace["rpc"] == "public.match_policy_chunks"
        assert trace["fts_used"] is False
        assert trace["hybrid_used"] is False
        assert len(ids[:10]) == 10


def test_stage12a004_keeps_both_gold_ids() -> None:
    records = CanonicalGoldValidator().parse_file(GOLD)
    record = next(record for record in records if record["evaluation_id"] == "stage12a-004")
    assert record["expected_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_frozen_metric_definitions_preserve_multi_gold_behavior() -> None:
    retrieved = ["noise", "gold-a", "gold-b", "other"]
    gold = {"gold-a", "gold-b"}
    assert hit_at_k(retrieved, gold, 1) == 0
    assert hit_at_k(retrieved, gold, 3) == 1
    assert recall_at_k(retrieved, gold, 3) == pytest.approx(1.0)
    assert mrr_at_k(retrieved, gold, 3) == pytest.approx(0.5)
    assert binary_ndcg_at_k(retrieved, gold, 3) == pytest.approx(
        (1 / math.log2(3) + 1 / math.log2(4))
        / (1 + 1 / math.log2(3)),
        rel=1e-12,
    )


def test_confirmation_summary_contract() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["identity"]["gold_sha256"] == "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
    assert summary["identity"]["hnsw_ef_search"] == "40"
    assert summary["candidate_trace_count"] == 100
    assert summary["candidate_rows"] == 2000
    assert summary["retrieval"]["top10_definition"] == "same ordered top20 result prefix [0:10]"
    assert summary["constraints"]["no_fts"] is True
    assert summary["constraints"]["no_hybrid"] is True
    assert summary["constraints"]["no_top50"] is True
    assert summary["arms"]["top10"]["pair_workload_per_run"] == 1000
    assert summary["arms"]["top20"]["pair_workload_per_run"] == 2000
    assert summary["reranker"]["score_blended"] is False
    assert summary["reranker"]["tie_ordering"] == "relevance_score DESC, canonical_chunk_id ASC"
    assert summary["query_level"]["top10_improved"] == [
        "stage12a-013",
        "stage13e-094",
        "stage13e-098",
    ]
    assert summary["query_level"]["top20_improved"] == [
        "stage13e-041",
        "stage13e-067",
    ]
