"""Offline contract tests for the Stage 13D top-10 ablation."""

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
from scripts.run_stage12b_vector_v2_baseline import (  # noqa: E402
    validate_gold_identity,
)
from scripts.run_stage13d_reranker_top10 import (  # noqa: E402
    CANDIDATE_DEPTH,
    Stage13DError,
    _load_top20_candidates,
    _rerank_one,
    score_results,
)


def _records() -> list[dict]:
    path = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_frozen_top20_provides_25_top10_prefixes() -> None:
    traces = _load_top20_candidates()
    assert len(traces) == 25
    assert all(len(item["candidate_canonical_chunk_ids"][:CANDIDATE_DEPTH]) == 10 for item in traces.values())


def test_top10_candidate_contract_and_known_miss() -> None:
    records = {item["evaluation_id"]: item for item in _records()}
    traces = _load_top20_candidates()
    for evaluation_id, expected_rank in {
        "stage12a-007": 10,
        "stage12a-008": 8,
        "stage12a-013": 7,
    }.items():
        ids = traces[evaluation_id]["candidate_canonical_chunk_ids"][:10]
        assert ids.index(records[evaluation_id]["expected_canonical_chunk_ids"][0]) + 1 == expected_rank
    assert records["stage12a-024"]["expected_canonical_chunk_ids"][0] not in traces["stage12a-024"]["candidate_canonical_chunk_ids"][:10]


def test_multi_gold_metric_semantics_are_preserved() -> None:
    gold = ["gold-a", "gold-b"]
    metrics = score_results(["gold-a", "other", "gold-b"], gold)
    assert metrics["hit@1"] == 1
    assert metrics["recall@1"] == 0.5
    assert metrics["recall@3"] == 1.0
    assert metrics["mrr@5"] == 1.0


def test_rerank_one_scores_exactly_ten_and_does_not_blend_vector_score() -> None:
    corpus = FrozenCorpusV2()
    records = _records()
    record = next(item for item in records if item["evaluation_id"] == "stage12a-001")
    top20 = _load_top20_candidates()[record["evaluation_id"]]
    candidate = {
        **top20,
        "candidate_canonical_chunk_ids": top20["candidate_canonical_chunk_ids"][:10],
        "candidate_similarity_scores": top20["candidate_similarity_scores"][:10],
        "candidate_results": top20["candidate_results"][:10],
    }

    class FakeAdapter:
        def rerank(self, query: str, documents: list[str]):
            assert query == record["query"]
            assert len(documents) == 10
            return [type("Score", (), {"index": index, "relevance_score": 0.5 if index < 2 else 0.1}) for index in range(10)]

    trace = _rerank_one(record, candidate, corpus, FakeAdapter(), 1)
    assert trace["pair_count"] == 10
    assert len(trace["reranked_canonical_chunk_ids"]) == 10
    assert set(trace["reranked_canonical_chunk_ids"]) == set(candidate["candidate_canonical_chunk_ids"])
    assert trace["vector_score_blended"] is False
    assert trace["reranked_canonical_chunk_ids"][:2] == sorted(candidate["candidate_canonical_chunk_ids"][:2])


@pytest.mark.parametrize(
    "scores",
    [
        [type("Score", (), {"index": 0, "relevance_score": 0.5}) for _ in range(10)],
        [type("Score", (), {"index": index, "relevance_score": 0.5}) for index in range(9)] + [type("Score", (), {"index": 10, "relevance_score": 0.5})],
    ],
)
def test_reranker_index_set_must_be_exact(scores) -> None:
    corpus = FrozenCorpusV2()
    record = next(item for item in _records() if item["evaluation_id"] == "stage12a-001")
    top20 = _load_top20_candidates()[record["evaluation_id"]]
    candidate = {
        **top20,
        "candidate_canonical_chunk_ids": top20["candidate_canonical_chunk_ids"][:10],
        "candidate_similarity_scores": top20["candidate_similarity_scores"][:10],
        "candidate_results": top20["candidate_results"][:10],
    }

    class BadAdapter:
        def rerank(self, query: str, documents: list[str]):
            return scores

    with pytest.raises(Stage13DError, match="exact 10-index set"):
        _rerank_one(record, candidate, corpus, BadAdapter(), 1)


def test_gold_identity_still_validates_as_25_reviewed() -> None:
    corpus = FrozenCorpusV2()
    records = validate_gold_identity(corpus)
    assert len(records) == 25
    multi = next(item for item in records if item["evaluation_id"] == "stage12a-004")
    assert len(multi["expected_canonical_chunk_ids"]) == 2
