"""Offline contract tests for the frozen Stage 13B0-R1 top-20 audit."""

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
from app.services.supabase_v2_retriever import CanonicalV2RetrievalTiming, normalize_specialist_scope  # noqa: E402
from scripts.run_stage12b_vector_v2_baseline import EXPECTED_GOLD_SHA256  # noqa: E402
from scripts.run_stage13b0_r1_top20 import (  # noqa: E402
    CANDIDATE_DEPTH,
    COVERAGE_K,
    FROZEN_MISS_IDS,
    Stage13B0R1Error,
    _classify,
    coverage_for_ids,
    gold_ranks,
    sha256_file,
    validate_identity,
    _trace_run,
)


def test_top20_contract_and_coverage_metrics() -> None:
    assert CANDIDATE_DEPTH == 20
    assert COVERAGE_K == (5, 10, 20)
    values = coverage_for_ids(["a", "gold", "b", "c", "other"], ["gold", "other"])
    assert values == {
        "hit@5": 1,
        "hit@10": 1,
        "hit@20": 1,
        "recall@5": 1.0,
        "recall@10": 1.0,
        "recall@20": 1.0,
    }


def test_exact_rank_and_over_20_representation() -> None:
    assert gold_ranks(["a", "gold", "b"], ["gold", "missing"]) == {
        "gold": 2,
        "missing": None,
    }
    assert _classify(6).startswith("A")
    assert _classify(10).startswith("A")
    assert _classify(11).startswith("B")
    assert _classify(20).startswith("B")
    assert _classify(None).startswith("D")


def test_multi_gold_stage12a_004_is_preserved() -> None:
    records = validate_identity(FrozenCorpusV2())
    record = next(item for item in records if item["evaluation_id"] == "stage12a-004")
    assert record["expected_canonical_chunk_ids"] == [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]


def test_frozen_gold_sha_and_miss_ids() -> None:
    path = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
    assert sha256_file(path) == EXPECTED_GOLD_SHA256
    records = validate_identity(FrozenCorpusV2())
    assert {item["evaluation_id"] for item in records} >= set(FROZEN_MISS_IDS)


def test_top20_result_count_guard() -> None:
    corpus = FrozenCorpusV2()
    records = validate_identity(corpus)

    class TooShortRetriever:
        def retrieve_with_timing(self, query: str, scope: str, k: int):
            return [], CanonicalV2RetrievalTiming(0.0, 0.0)

    with pytest.raises(Stage13B0R1Error, match="expected 20"):
        _trace_run(records[:1], corpus, TooShortRetriever(), 1)


def test_unsupported_banking_operations_scope_is_rejected() -> None:
    with pytest.raises(ValueError, match="unsupported specialist scope"):
        normalize_specialist_scope("BankingOperations")


def test_written_top20_artifacts_have_25_records_if_present() -> None:
    path = ROOT / "dataset/evaluation/results/vector-v2-top20-candidate-traces.jsonl"
    if not path.exists():
        pytest.skip("top20 audit has not run yet")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert len(records) == 25
    assert len({item["evaluation_id"] for item in records}) == 25
    assert all(len(item["candidate_canonical_chunk_ids"]) == 20 for item in records)
    multi = next(item for item in records if item["evaluation_id"] == "stage12a-004")
    assert len(multi["gold_canonical_chunk_ids"]) == 2
