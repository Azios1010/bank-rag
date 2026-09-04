from __future__ import annotations

import json
from urllib.error import HTTPError, URLError

import pytest

from app.config import Settings
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter
from app.schemas import AgentID
from app.services.supabase_v2_retriever import (
    CanonicalV2Retriever,
    SupabaseV2RetrievalError,
    normalize_specialist_scope,
)


def _vector(value: float = 1.0) -> list[float]:
    return [value] + [0.0] * (LlamaV2QueryEmbeddingAdapter.DIMENSION - 1)


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        embedding_provider="deterministic_test",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="server-only-test-secret",
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


class _Adapter:
    def __init__(self, vector: list[float] | None = None) -> None:
        self.vector = vector or _vector()
        self.queries: list[str] = []

    def embed_query(self, query: str) -> list[float]:
        self.queries.append(query)
        return self.vector


def _rpc_row(*, visibility: str = "SHARED") -> dict[str, object]:
    return {
        "canonical_chunk_id": "regulation-001",
        "content": "Nội dung quy định tiếng Việt.",
        "document_source_id": "real-source-001",
        "document_version_id": "real-source-001.2026",
        "document_title": "Quy định tín dụng",
        "heading_path": ["Chương I", "Điều 1"],
        "locator": {"article": "1", "page_start": 1},
        "namespace": "REGULATION",
        "visibility": visibility,
        "metadata": {"provenance_kind": "real_regulation"},
        "similarity": 0.91,
    }


def test_scope_normalization_and_banking_operations_rejection() -> None:
    assert normalize_specialist_scope("credit") == "credit"
    assert normalize_specialist_scope(AgentID.CREDIT) == "credit"
    assert normalize_specialist_scope("CollateralAppraisal") == "collateral_appraisal"
    with pytest.raises(ValueError, match="unsupported specialist scope"):
        normalize_specialist_scope("BankingOperations")


def test_v2_retriever_sends_exact_rpc_payload_and_maps_identity() -> None:
    observed: dict[str, object] = {}

    def opener(request, timeout):
        observed["url"] = request.full_url
        observed["timeout"] = timeout
        observed["content_type"] = request.get_header("Content-type")
        observed["authorization"] = request.get_header("Authorization")
        observed["body"] = json.loads(request.data.decode("utf-8"))
        return _Response([_rpc_row()])

    adapter = _Adapter()
    retriever = CanonicalV2Retriever(
        _settings(), embedding_adapter=adapter, opener=opener, timeout_seconds=7.0
    )
    results = retriever.retrieve("Doanh nghiệp cần đáp ứng điều kiện gì?", "credit", k=3)

    assert adapter.queries == ["Doanh nghiệp cần đáp ứng điều kiện gì?"]
    assert observed["url"] == "https://example.supabase.co/rest/v1/rpc/match_policy_chunks"
    assert observed["timeout"] == 7.0
    assert observed["content_type"] == "application/json; charset=utf-8"
    assert observed["authorization"] == "Bearer server-only-test-secret"
    payload = observed["body"]
    assert payload["requested_scope"] == "credit"
    assert payload["match_count"] == 3
    assert payload["query_embedding"] == _vector()
    assert results[0].canonical_chunk_id == "regulation-001"
    assert results[0].source_type == "real_regulation"
    assert results[0].document_version_id == "real-source-001.2026"
    assert results[0].heading_path == ["Chương I", "Điều 1"]


def test_evaluation_wrapper_preserves_full_v2_citation_metadata() -> None:
    from app.eval.contracts import RetrievalRequest
    from app.eval.retrievers import CanonicalV2EvaluationRetriever

    def opener(request, timeout):
        return _Response([_rpc_row()])

    execution = CanonicalV2EvaluationRetriever(
        CanonicalV2Retriever(_settings(), embedding_adapter=_Adapter(), opener=opener)
    ).retrieve(
        RetrievalRequest(
            evaluation_id="smoke",
            query="Doanh nghiệp cần điều kiện gì?",
            agent_scope="credit",
        ),
        k=1,
    )
    assert execution.results[0].retrieval_source == "supabase_rpc"
    assert execution.results[0].metadata["document_source_id"] == "real-source-001"
    assert execution.results[0].metadata["visibility"] == "SHARED"
    assert execution.embedding_latency_ms >= 0
    assert execution.retrieval_latency_ms >= 0


def test_v2_retriever_rejects_bad_rpc_records_without_legacy_fallback() -> None:
    def opener(request, timeout):
        return _Response([{"canonical_chunk_id": "not-enough-fields"}])

    with pytest.raises(SupabaseV2RetrievalError, match="missing"):
        CanonicalV2Retriever(_settings(), embedding_adapter=_Adapter(), opener=opener).retrieve(
            "query", "credit", k=1
        )


def test_v2_retriever_rejects_duplicate_canonical_ids() -> None:
    def opener(request, timeout):
        return _Response([_rpc_row(), _rpc_row()])

    with pytest.raises(SupabaseV2RetrievalError, match="duplicate canonical_chunk_id"):
        CanonicalV2Retriever(_settings(), embedding_adapter=_Adapter(), opener=opener).retrieve(
            "query", "credit", k=2
        )


@pytest.mark.parametrize(
    "failure",
    [
        URLError("offline"),
        HTTPError("https://example.supabase.co", 500, "error", {}, None),
    ],
)
def test_v2_retriever_surfaces_rpc_failures(failure: Exception) -> None:
    def opener(request, timeout):
        raise failure

    with pytest.raises(SupabaseV2RetrievalError, match="RPC"):
        CanonicalV2Retriever(_settings(), embedding_adapter=_Adapter(), opener=opener).retrieve(
            "query", "credit", k=1
        )


def test_v2_retriever_rejects_unsupported_scope_before_embedding_or_rpc() -> None:
    adapter = _Adapter()

    def opener(request, timeout):
        raise AssertionError("RPC must not be called")

    with pytest.raises(ValueError, match="unsupported specialist scope"):
        CanonicalV2Retriever(_settings(), embedding_adapter=adapter, opener=opener).retrieve(
            "query", "BankingOperations", k=1
        )
    assert adapter.queries == []


@pytest.mark.parametrize(
    "vector, message",
    [([0.0] * 1024, "non-zero"), ([2.0] + [0.0] * 1023, "unit-normalized")],
)
def test_v2_retriever_validates_custom_adapter_vectors(vector: list[float], message: str) -> None:
    def opener(request, timeout):
        raise AssertionError("RPC must not be called")

    with pytest.raises(SupabaseV2RetrievalError, match="invalid vector"):
        CanonicalV2Retriever(
            _settings(), embedding_adapter=_Adapter(vector), opener=opener
        ).retrieve("query", "credit", k=1)


def test_canonical_v2_path_does_not_import_sentence_transformers(monkeypatch) -> None:
    import builtins

    original_import = builtins.__import__

    def deny_legacy_model(name, *args, **kwargs):
        if name == "sentence_transformers" or name.startswith("sentence_transformers."):
            raise AssertionError("SentenceTransformer is forbidden in canonical V2 retrieval")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", deny_legacy_model)

    def opener(request, timeout):
        return _Response([_rpc_row()])

    result = CanonicalV2Retriever(
        _settings(), embedding_adapter=_Adapter(), opener=opener
    ).retrieve("query", AgentID.CREDIT, k=1)
    assert result[0].canonical_chunk_id == "regulation-001"


def test_v2_module_source_has_no_legacy_table_or_model_imports() -> None:
    from pathlib import Path

    source = Path(__file__).resolve().parents[1].joinpath(
        "app/services/supabase_v2_retriever.py"
    ).read_text(encoding="utf-8")
    assert "SentenceTransformer" not in source
    assert "from app.db.models" not in source
    assert "from app.services.rag" not in source
    assert "/rest/v1/rpc/match_policy_chunks" in source

    evaluation_source = Path(__file__).resolve().parents[1].joinpath(
        "app/eval/retrievers.py"
    ).read_text(encoding="utf-8")
    assert "from app.db.models" not in evaluation_source
    assert "from app.services.rag" not in evaluation_source
