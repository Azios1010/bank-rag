"""Offline contract tests for the dedicated llama.cpp reranker adapter."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.llama_v2_reranker import (  # noqa: E402
    LlamaRerankerResponseError,
    LlamaV2RerankerAdapter,
)
from scripts.run_stage13b_reranker import (  # noqa: E402
    CANDIDATE_DEPTH,
    RERANKER_MODEL_BYTES,
    RERANKER_MODEL_SHA256,
    _rank_status,
    load_frozen_top20_traces,
    rerank_one,
)


class FakeResponse:
    status = 200

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def fake_opener(payload: object):
    def opener(request, timeout):
        assert request.full_url.endswith("/v1/rerank")
        assert request.headers["Content-type"] == "application/json; charset=utf-8"
        body = json.loads(request.data.decode("utf-8"))
        assert body["query"] == "Câu hỏi tiếng Việt?"
        assert body["documents"] == ["Tài liệu một", "Tài liệu hai"]
        return FakeResponse(payload)

    return opener


def test_exact_document_format_and_utf8_payload() -> None:
    document = LlamaV2RerankerAdapter.format_document(
        title="Văn bản tín dụng",
        heading_path=["Điều 7", "Điểm a"],
        content="Nội dung tiếng Việt.",
    )
    assert document == 'Title: Văn bản tín dụng\nSection: ["Điều 7","Điểm a"]\nText:\nNội dung tiếng Việt.'
    adapter = LlamaV2RerankerAdapter(base_url="http://127.0.0.1:8082", opener=fake_opener({"results": [{"index": 0, "relevance_score": 0.8}, {"index": 1, "relevance_score": 0.2}]}))
    assert adapter.rerank("Câu hỏi tiếng Việt?", ["Tài liệu một", "Tài liệu hai"])[0].index == 0


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"results": [{"index": 0, "relevance_score": 0.8}]},
        {"results": [{"index": 0, "relevance_score": 0.8}, {"index": 0, "relevance_score": 0.2}]},
        {"results": [{"index": 0, "relevance_score": float("nan")}, {"index": 1, "relevance_score": 0.2}]},
        {"results": [{"index": 0, "relevance_score": 0.8}, {"index": 2, "relevance_score": 0.2}]},
    ],
)
def test_malformed_or_unsafe_result_is_rejected(payload: object) -> None:
    adapter = LlamaV2RerankerAdapter(opener=fake_opener(payload))
    with pytest.raises(LlamaRerankerResponseError):
        adapter.rerank("Câu hỏi tiếng Việt?", ["Tài liệu một", "Tài liệu hai"])


def test_index_mapping_and_identity_set_contract() -> None:
    adapter = LlamaV2RerankerAdapter(
        opener=fake_opener(
            {"results": [{"index": 1, "relevance_score": 0.9}, {"index": 0, "relevance_score": 0.1}]}
        )
    )
    results = adapter.rerank("Câu hỏi tiếng Việt?", ["Tài liệu một", "Tài liệu hai"])
    mapped = [(["chunk-a", "chunk-b"])[item.index] for item in results]
    assert mapped == ["chunk-b", "chunk-a"]
    assert {item.index for item in results} == {0, 1}


def test_frozen_experiment_contract_and_model_identity() -> None:
    assert CANDIDATE_DEPTH == 20
    assert RERANKER_MODEL_BYTES == 639153184
    assert len(RERANKER_MODEL_SHA256) == 64
    traces = load_frozen_top20_traces()
    assert len(traces) == 25
    assert all(len(item["candidate_canonical_chunk_ids"]) == 20 for item in traces.values())
    multi = traces.get("stage12a-004")
    assert multi is not None
    assert len(multi["gold_canonical_chunk_ids"]) == 2


def test_rank_status_and_candidate_unrecoverable_contract() -> None:
    assert _rank_status(10, 3) == "IMPROVED"
    assert _rank_status(3, 7) == "WORSENED"
    assert _rank_status(">20", 20) == "UNRECOVERABLE-CANDIDATE"


def test_rerank_one_preserves_exact_20_ids_and_uses_no_vector_score_blend() -> None:
    from app.eval.gold_v2 import FrozenCorpusV2

    corpus = FrozenCorpusV2()
    records = json.loads("[" + ",".join(ROOT.joinpath("dataset/evaluation/retrieval-v2-gold-pilot.jsonl").read_text(encoding="utf-8").splitlines()) + "]")
    record = next(item for item in records if item["evaluation_id"] == "stage12a-001")
    frozen = load_frozen_top20_traces()[record["evaluation_id"]]

    class FakeAdapter:
        def rerank(self, query, documents):
            assert query == record["query"]
            assert len(documents) == CANDIDATE_DEPTH
            # Equal relevance scores must be resolved by canonical ID, not by
            # vector score or input rank.
            return [
                type("Score", (), {"index": index, "relevance_score": 0.5 if index < 2 else 0.1})
                for index in range(CANDIDATE_DEPTH)
            ]

    trace = rerank_one(record, frozen, corpus, FakeAdapter(), 1)
    assert len(trace["reranked_canonical_chunk_ids"]) == CANDIDATE_DEPTH
    assert set(trace["reranked_canonical_chunk_ids"]) == set(frozen["candidate_canonical_chunk_ids"])
    tied = sorted(frozen["candidate_canonical_chunk_ids"][:2])
    assert trace["reranked_canonical_chunk_ids"][:2] == tied
    assert trace["vector_score_blended"] is False


def test_rerank_one_rejects_missing_or_duplicate_api_indexes() -> None:
    from app.eval.gold_v2 import FrozenCorpusV2
    from scripts.run_stage13b_reranker import Stage13BRerankerError

    corpus = FrozenCorpusV2()
    records = [json.loads(line) for line in ROOT.joinpath("dataset/evaluation/retrieval-v2-gold-pilot.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
    record = records[0]
    frozen = load_frozen_top20_traces()[record["evaluation_id"]]

    class BadAdapter:
        def rerank(self, query, documents):
            return [type("Score", (), {"index": 0, "relevance_score": 0.5}) for _ in documents]

    with pytest.raises(Stage13BRerankerError, match="candidate index set"):
        rerank_one(record, frozen, corpus, BadAdapter(), 1)
