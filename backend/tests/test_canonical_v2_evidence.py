"""Focused contract tests for the frozen Stage 13F evidence service."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.canonical_v2_evidence import (
    CanonicalV2EvidenceError,
    CanonicalV2EvidenceRetriever,
    serialize_citations,
)
from app.services.supabase_v2_retriever import (
    CanonicalV2RetrievalResult,
    CanonicalV2RetrievalTiming,
)


def _candidate(index: int, *, similarity: float | None = None) -> CanonicalV2RetrievalResult:
    return CanonicalV2RetrievalResult(
        canonical_chunk_id=f"chunk-{index:02d}",
        content=f"Nội dung quy định {index}.",
        similarity=similarity if similarity is not None else 1.0 - index / 100,
        document_source_id="source-001",
        document_version_id="source-001.v1",
        document_title="Quy định tín dụng",
        heading_path=["Chương I", f"Điều {index}"],
        locator={"article": str(index), "clause": "1", "point": "a"},
        namespace="REGULATION",
        visibility="SHARED",
        metadata={"provenance_kind": "real_regulation"},
    )


class _VectorStub:
    def __init__(self, candidates: list[CanonicalV2RetrievalResult]) -> None:
        self.candidates = candidates
        self.calls: list[tuple[str, str, int]] = []

    def retrieve_with_timing(self, query: str, scope: str, *, k: int):
        self.calls.append((query, scope, k))
        return self.candidates, CanonicalV2RetrievalTiming(0.0, 0.0)


class _RerankerStub:
    def __init__(self, scores: list[float] | None = None) -> None:
        self.scores = scores
        self.documents: list[str] = []

    @staticmethod
    def format_document(*, title: str, heading_path: list[object], content: str) -> str:
        return f"Title: {title}\nSection: {heading_path}\nText:\n{content}"

    def rerank(self, query: str, documents: list[str]):
        self.documents = documents
        scores = self.scores or [float(len(documents) - index) for index in range(len(documents))]
        return [
            SimpleNamespace(index=index, relevance_score=score)
            for index, score in enumerate(scores)
        ]


def test_frozen_service_uses_exact_top20_and_returns_reranked_top5() -> None:
    candidates = [_candidate(index, similarity=0.99 - index / 100) for index in range(20)]
    vector = _VectorStub(candidates)
    scores = [0.01] * 20
    scores[0] = 0.20
    scores[19] = 0.95
    reranker = _RerankerStub(scores)

    results = CanonicalV2EvidenceRetriever(vector, reranker).retrieve_evidence(
        "Câu hỏi tiếng Việt?", "credit"
    )

    assert vector.calls == [("Câu hỏi tiếng Việt?", "credit", 20)]
    assert len(reranker.documents) == 20
    assert len(results) == 5
    assert results[0].canonical_chunk_id == "chunk-19"
    assert results[0].vector_rank == 20
    assert results[0].reranker_score == pytest.approx(0.95)
    assert [result.rank for result in results] == [1, 2, 3, 4, 5]
    assert all("gold" not in document.lower() for document in reranker.documents)
    assert all("rationale" not in document.lower() for document in reranker.documents)


def test_frozen_service_rejects_noncanonical_depths() -> None:
    service = CanonicalV2EvidenceRetriever(_VectorStub([_candidate(0)]), _RerankerStub())
    with pytest.raises(ValueError, match="candidate_k is frozen at 20"):
        service.retrieve_evidence("query", "credit", candidate_k=10)
    with pytest.raises(ValueError, match="final_k is frozen at 5"):
        service.retrieve_evidence("query", "credit", final_k=3)


def test_reranker_score_orders_results_without_vector_score_blending() -> None:
    candidates = [_candidate(0, similarity=0.99), _candidate(1, similarity=0.10)]
    reranker = _RerankerStub([0.10, 0.90])
    results = CanonicalV2EvidenceRetriever(_VectorStub(candidates), reranker).retrieve_evidence(
        "query", "credit"
    )
    assert [result.canonical_chunk_id for result in results] == ["chunk-01", "chunk-00"]


@pytest.mark.parametrize(
    "scores, message",
    [
        ([0.1] * 19, "exactly one score"),
        ([0.1] * 20, "candidate index set"),
    ],
)
def test_reranker_identity_contract_rejects_missing_or_duplicate_indexes(
    scores: list[float], message: str
) -> None:
    candidates = [_candidate(index) for index in range(20)]
    reranker = _RerankerStub(scores)
    if len(scores) == 20:
        reranker.rerank = lambda query, documents: [
            SimpleNamespace(index=0, relevance_score=0.1) for _ in documents
        ]
    with pytest.raises(CanonicalV2EvidenceError, match=message):
        CanonicalV2EvidenceRetriever(_VectorStub(candidates), reranker).retrieve_evidence(
            "query", "credit"
        )


def test_scope_contract_rejects_banking_operations_before_vector_call() -> None:
    vector = _VectorStub([_candidate(0)])
    with pytest.raises(ValueError, match="unsupported specialist scope"):
        CanonicalV2EvidenceRetriever(vector, _RerankerStub()).retrieve_evidence(
            "query", "BankingOperations"
        )
    assert vector.calls == []


def test_citation_serialization_is_contiguous_e1_to_e5_and_preserves_metadata() -> None:
    candidates = [_candidate(index) for index in range(20)]
    results = CanonicalV2EvidenceRetriever(_VectorStub(candidates), _RerankerStub()).retrieve_evidence(
        "query", "collateral_appraisal"
    )
    citations = serialize_citations(results)
    assert [item["citation_id"] for item in citations] == ["E1", "E2", "E3", "E4", "E5"]
    assert citations[0]["canonical_chunk_id"] == results[0].canonical_chunk_id
    assert citations[0]["locator"] == {"article": "0", "clause": "1", "point": "a"}
    assert citations[0]["visibility"] == "SHARED"
    assert "gold" not in citations[0]
    assert "rationale" not in citations[0]


def test_known_failure_registry_is_exact_and_not_special_cased() -> None:
    assert CanonicalV2EvidenceRetriever.KNOWN_CANDIDATE_GENERATION_FAILURES == (
        "stage12a-024",
        "stage13e-040",
        "stage13e-042",
    )


def test_frozen_evidence_module_has_no_legacy_or_alternative_retrieval_path() -> None:
    source = Path(__file__).resolve().parents[1].joinpath(
        "app/services/canonical_v2_evidence.py"
    ).read_text(encoding="utf-8")
    assert "SentenceTransformer" not in source
    assert "PolicyEmbedding" not in source
    assert "AgentKnowledgeBase" not in source
    assert "hybrid_v2_retriever" not in source
    assert "supabase_fts_retriever" not in source
    assert "match_policy_chunks" not in source
