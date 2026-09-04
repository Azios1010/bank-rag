"""Offline contract tests for the additive Stage 13A retrieval arms."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.config import Settings
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter
from app.eval.metrics import binary_ndcg_at_k, hit_at_k, mrr_at_k, recall_at_k
from app.services.hybrid_v2_retriever import (
    CanonicalV2HybridRetriever,
    CanonicalV2HybridTiming,
)
from app.services.supabase_fts_retriever import (
    CanonicalV2LexicalRetriever,
    SupabaseFTSRetrievalError,
    build_or_tsquery,
    normalize_fts_tokens,
)
from app.services.supabase_v2_retriever import (
    CanonicalV2RetrievalResult,
    CanonicalV2RetrievalTiming,
    normalize_specialist_scope,
)
from scripts.run_stage13a_hybrid_v2 import (
    FTS_CONFIG,
    FTS_FIELDS,
    LEXICAL_CANDIDATE_DEPTH,
    RRF_K,
    VECTOR_CANDIDATE_DEPTH,
    repeatability,
    score_results,
)


class _Response:
    status = 200

    def __init__(self, payload: object) -> None:
        self.payload = payload

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload, ensure_ascii=False).encode("utf-8")


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        embedding_provider="deterministic_test",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="server-only-test-secret",
    )


def _vector_result(chunk_id: str, similarity: float) -> CanonicalV2RetrievalResult:
    return CanonicalV2RetrievalResult(
        canonical_chunk_id=chunk_id,
        content=f"content-{chunk_id}",
        similarity=similarity,
        document_source_id="source",
        document_version_id="version",
        document_title="title",
        heading_path=[],
        locator={"article": "1"},
        namespace="REGULATION",
        visibility="SHARED",
        metadata={"provenance_kind": "real_regulation"},
    )


def _lexical_row(chunk_id: str, score: float) -> dict[str, object]:
    return {
        "canonical_chunk_id": chunk_id,
        "content": f"content-{chunk_id}",
        "document_source_id": "source",
        "document_version_id": "version",
        "document_title": "title",
        "heading_path": [],
        "locator": {"article": "1"},
        "namespace": "REGULATION",
        "visibility": "SHARED",
        "metadata": {"provenance_kind": "real_regulation"},
        "lexical_score": score,
    }


class _StubVector:
    def __init__(self, results: list[CanonicalV2RetrievalResult]) -> None:
        self.results = results

    def retrieve_with_timing(self, query, scope, k):
        assert k == VECTOR_CANDIDATE_DEPTH
        return self.results, CanonicalV2RetrievalTiming(1.0, 2.0)


class _StubLexical:
    def __init__(self, results) -> None:
        self.results = results

    def retrieve_with_timing(self, query, scope, k):
        assert k == LEXICAL_CANDIDATE_DEPTH
        return self.results, type("Timing", (), {"retrieval_ms": 3.0})()


def test_fixed_experiment_configuration_is_rank_only_rrf() -> None:
    assert FTS_CONFIG == "simple"
    assert FTS_FIELDS == ("title", "heading_path", "content")
    assert VECTOR_CANDIDATE_DEPTH == 20
    assert LEXICAL_CANDIDATE_DEPTH == 20
    assert RRF_K == 60

    vector = [_vector_result("b", 0.01), _vector_result("a", 0.99)]
    lexical = [_lexical_row("c", 999.0), _lexical_row("b", 0.001)]
    # The branch scores are deliberately incomparable and are not used by RRF.
    lexical_results = CanonicalV2LexicalRetriever._map_result(lexical[0], 0), CanonicalV2LexicalRetriever._map_result(lexical[1], 1)
    fused = CanonicalV2HybridRetriever(
        vector_retriever=_StubVector(vector),
        lexical_retriever=_StubLexical(list(lexical_results)),
    ).retrieve("query", "credit", k=3)

    assert [item.canonical_chunk_id for item in fused] == ["b", "c", "a"]
    assert fused[0].rrf_score == pytest.approx(1 / (RRF_K + 1) + 1 / (RRF_K + 2))
    assert fused[1].rrf_score == pytest.approx(1 / (RRF_K + 1))
    assert fused[2].rrf_score == pytest.approx(1 / (RRF_K + 2))


def test_rrf_ties_use_canonical_chunk_id() -> None:
    vector = [_vector_result("z", 0.1), _vector_result("a", 0.9)]
    lexical = [CanonicalV2LexicalRetriever._map_result(_lexical_row("z", 1), 0), CanonicalV2LexicalRetriever._map_result(_lexical_row("a", 1), 1)]
    # Each candidate appears in one branch at rank 1 and therefore ties.
    fused = CanonicalV2HybridRetriever(
        vector_retriever=_StubVector(vector[:1]),
        lexical_retriever=_StubLexical(lexical[1:]),
    ).retrieve("query", "credit", k=2)
    assert [item.canonical_chunk_id for item in fused] == ["a", "z"]


def test_lexical_rpc_uses_original_utf8_query_and_canonical_payload() -> None:
    observed: dict[str, object] = {}

    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["content_type"] = request.get_header("Content-type")
        observed["body"] = json.loads(request.data.decode("utf-8"))
        return _Response([_lexical_row("chunk-a", 0.5)])

    query = "Điều kiện cấp tín dụng cho khách hàng?"
    results = CanonicalV2LexicalRetriever(
        _settings(), opener=opener, timeout_seconds=4.0
    ).retrieve(query, "credit", k=7)

    assert observed["url"] == "https://example.supabase.co/rest/v1/rpc/match_policy_chunks_fts"
    assert observed["content_type"] == "application/json; charset=utf-8"
    assert observed["body"] == {
        "query_text": query,
        "requested_scope": "credit",
        "match_count": 7,
    }
    assert results[0].canonical_chunk_id == "chunk-a"


def test_lexical_rpc_malformed_records_and_failures_fail_closed() -> None:
    def malformed(request, timeout):
        return _Response([{"canonical_chunk_id": "only-id"}])

    with pytest.raises(SupabaseFTSRetrievalError, match="missing"):
        CanonicalV2LexicalRetriever(_settings(), opener=malformed).retrieve(
            "query", "credit", k=1
        )

    def failing(request, timeout):
        raise OSError("offline")

    with pytest.raises(SupabaseFTSRetrievalError, match="request failed"):
        CanonicalV2LexicalRetriever(_settings(), opener=failing).retrieve(
            "query", "credit", k=1
        )


def test_or_fts_normalization_is_deterministic_and_preserves_accents() -> None:
    query = "Điều kiện, ĐIỀU kiện cấp tín dụng?"
    assert normalize_fts_tokens(query) == ["điều", "kiện", "cấp", "tín", "dụng"]
    assert build_or_tsquery(query) == "điều | kiện | cấp | tín | dụng"


def test_or_fts_uses_a_separate_rpc_and_not_plain_to_tsquery() -> None:
    retriever = CanonicalV2LexicalRetriever(_settings())
    assert retriever._query_text_for_rpc("điều kiện cấp tín dụng") == "điều kiện cấp tín dụng"
    from app.services.supabase_fts_retriever import CanonicalV2OrLexicalRetriever

    or_retriever = CanonicalV2OrLexicalRetriever(_settings())
    assert or_retriever.rpc_endpoint.endswith("/rest/v1/rpc/match_policy_chunks_fts_or")
    assert or_retriever._query_text_for_rpc("điều kiện cấp tín dụng") == "điều | kiện | cấp | tín | dụng"


def test_scope_contract_rejects_banking_operations_for_both_paths() -> None:
    with pytest.raises(ValueError, match="unsupported specialist scope"):
        normalize_specialist_scope("BankingOperations")

    with pytest.raises(ValueError, match="unsupported specialist scope"):
        CanonicalV2LexicalRetriever(_settings()).retrieve("query", "BankingOperations", k=1)


def test_multi_gold_r02_metrics_are_unchanged() -> None:
    retrieved = ["other", "gold-b", "other-2", "gold-a"]
    assert score_results(retrieved, ["gold-a", "gold-b"])["recall@3"] == 0.5
    assert recall_at_k(retrieved, {"gold-a", "gold-b"}, 5) == 1.0
    assert hit_at_k(retrieved, {"gold-a", "gold-b"}, 3) == 1
    assert mrr_at_k(retrieved, {"gold-a", "gold-b"}, 3) == 0.5
    assert binary_ndcg_at_k(retrieved, {"gold-a", "gold-b"}, 3) > 0.0


def test_repeatability_treats_two_valid_empty_fts_results_as_equal() -> None:
    metrics = {
        f"{metric}@{k}": 0.0
        for metric in ("hit", "recall", "mrr", "ndcg")
        for k in (1, 3, 5)
    }
    first = [{"evaluation_id": "q", "retrieved_canonical_chunk_ids": [], "retrieved_results": [], "metrics": metrics}]
    second = [{"evaluation_id": "q", "retrieved_canonical_chunk_ids": [], "retrieved_results": [], "metrics": metrics}]
    report = repeatability(first, second, "lexical_score")
    assert report["ordered_top5_agreement"] == 1.0
    assert report["top1_agreement"] == 1.0
    assert report["top5_set_agreement"] == 1.0


def test_migration_is_additive_simple_fts_and_has_no_evaluation_fields() -> None:
    migration = Path(__file__).resolve().parents[1].joinpath(
        "alembic/versions/20260903_0006_supabase_fts_hybrid.py"
    ).read_text(encoding="utf-8")
    assert "ADD COLUMN search_document tsvector" in migration
    assert "USING gin (search_document)" in migration
    assert "'simple'::regconfig" in migration
    assert "title" in migration and "heading_path" in migration and "content" in migration
    assert "gold" not in migration.lower()
    assert "match_policy_chunks_fts" in migration
