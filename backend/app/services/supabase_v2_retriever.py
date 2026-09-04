"""Canonical Corpus V2 retrieval through llama.cpp and Supabase RPC.

The RPC is the only ranking and visibility implementation in this path.  This
client is deliberately small: it formats the query, validates the llama.cpp
vector, invokes ``public.match_policy_chunks`` through the trusted Supabase
REST endpoint, and validates/maps the returned citation contract.  It never
imports the legacy ``PolicyEmbedding`` or ``AgentKnowledgeBase`` models.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import json
import math
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from app.config import Settings, get_settings
from app.db.supabase_models import SUPPORTED_SPECIALIST_SCOPES
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter


class SupabaseV2RetrievalError(RuntimeError):
    """Raised when the canonical RPC cannot be called or returns bad data."""


@dataclass(frozen=True)
class CanonicalV2RetrievalResult:
    """One citation returned by the canonical V2 RPC."""

    canonical_chunk_id: str
    content: str
    similarity: float
    document_source_id: str
    document_version_id: str
    document_title: str
    heading_path: list[Any]
    locator: dict[str, Any]
    namespace: str
    visibility: str
    metadata: dict[str, Any]

    @property
    def source_type(self) -> str:
        """Return provenance without inventing a new source identity."""

        if self.metadata.get("provenance_kind") == "synthetic_internal_policy":
            return "synthetic_internal_policy"
        return "real_regulation"


@dataclass(frozen=True)
class CanonicalV2RetrievalTiming:
    embedding_ms: float
    retrieval_ms: float


RpcOpener = Callable[..., object]


def normalize_specialist_scope(scope: object) -> str:
    """Normalize supported specialist values and reject BankingOperations."""

    raw_scope = getattr(scope, "value", scope)
    if not isinstance(raw_scope, str):
        raise ValueError("specialist scope must be a supported string")
    if raw_scope in SUPPORTED_SPECIALIST_SCOPES:
        return raw_scope
    enum_to_scope = {
        "CustomerRelationship": "customer_relationship",
        "Credit": "credit",
        "RiskManagement": "risk_management",
        "LegalCompliance": "legal_compliance",
        "CollateralAppraisal": "collateral_appraisal",
    }
    normalized = enum_to_scope.get(raw_scope)
    if normalized is not None:
        return normalized
    raise ValueError(f"unsupported specialist scope: {raw_scope}")


class CanonicalV2Retriever:
    """Retrieve frozen Corpus V2 citations using the single authoritative RPC."""

    RPC_PATH = "/rest/v1/rpc/match_policy_chunks"
    MAX_MATCH_COUNT = 100

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        embedding_adapter: LlamaV2QueryEmbeddingAdapter | None = None,
        opener: RpcOpener = urlopen,
        timeout_seconds: float = 30.0,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.settings = settings or get_settings()
        self._embedding_adapter = embedding_adapter or LlamaV2QueryEmbeddingAdapter(
            base_url=self.settings.llama_embedding_base_url
        )
        self._opener = opener
        self._timeout_seconds = timeout_seconds

    @property
    def rpc_endpoint(self) -> str:
        if not self.settings.supabase_url:
            return ""
        return self.settings.supabase_url.rstrip("/") + self.RPC_PATH

    def retrieve(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> list[CanonicalV2RetrievalResult]:
        """Run query embedding then the canonical Supabase RPC."""

        results, _ = self.retrieve_with_timing(query, scope, k=k)
        return results

    def retrieve_with_query_vector(
        self,
        query_vector: list[float],
        scope: object,
        k: int = 5,
    ) -> list[CanonicalV2RetrievalResult]:
        """Run the canonical RPC with an already validated query vector.

        This is intentionally a small evaluation/runtime seam: callers that
        compare multiple candidate depths must be able to embed once and
        reuse the exact same vector.  Scope validation, vector validation,
        RPC invocation, and result mapping remain the canonical path.
        """

        requested_scope = normalize_specialist_scope(scope)
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= self.MAX_MATCH_COUNT:
            raise ValueError(f"k must be an integer between 1 and {self.MAX_MATCH_COUNT}")
        try:
            validated_vector = LlamaV2QueryEmbeddingAdapter._validate_server_vector(
                query_vector
            )
        except (TypeError, ValueError) as exc:
            raise SupabaseV2RetrievalError(
                "canonical query vector is invalid"
            ) from exc

        raw_results = self._call_rpc(
            {
                "query_embedding": validated_vector,
                "requested_scope": requested_scope,
                "match_count": k,
            }
        )
        mapped_results: list[CanonicalV2RetrievalResult] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(raw_results):
            mapped = self._map_result(item, index)
            if mapped.canonical_chunk_id in seen_ids:
                raise SupabaseV2RetrievalError(
                    "canonical Supabase RPC returned duplicate canonical_chunk_id"
                )
            seen_ids.add(mapped.canonical_chunk_id)
            mapped_results.append(mapped)
        return mapped_results

    def retrieve_with_timing(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> tuple[list[CanonicalV2RetrievalResult], CanonicalV2RetrievalTiming]:
        """Run retrieval and return naturally observed phase timings."""

        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        requested_scope = normalize_specialist_scope(scope)
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= self.MAX_MATCH_COUNT:
            raise ValueError(f"k must be an integer between 1 and {self.MAX_MATCH_COUNT}")

        embedding_started = time.perf_counter()
        query_vector = self._embedding_adapter.embed_query(query)
        embedding_finished = time.perf_counter()
        try:
            validated_vector = LlamaV2QueryEmbeddingAdapter._validate_server_vector(
                query_vector
            )
        except (TypeError, ValueError) as exc:
            raise SupabaseV2RetrievalError(
                "canonical query adapter returned an invalid vector"
            ) from exc

        payload = {
            "query_embedding": validated_vector,
            "requested_scope": requested_scope,
            "match_count": k,
        }
        retrieval_started = time.perf_counter()
        raw_results = self._call_rpc(payload)
        retrieval_finished = time.perf_counter()
        mapped_results: list[CanonicalV2RetrievalResult] = []
        seen_ids: set[str] = set()
        for index, item in enumerate(raw_results):
            mapped = self._map_result(item, index)
            if mapped.canonical_chunk_id in seen_ids:
                raise SupabaseV2RetrievalError(
                    "canonical Supabase RPC returned duplicate canonical_chunk_id"
                )
            seen_ids.add(mapped.canonical_chunk_id)
            mapped_results.append(mapped)
        return (
            mapped_results,
            CanonicalV2RetrievalTiming(
                embedding_ms=(embedding_finished - embedding_started) * 1000,
                retrieval_ms=(retrieval_finished - retrieval_started) * 1000,
            ),
        )

    def _call_rpc(self, payload: Mapping[str, object]) -> list[object]:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            raise SupabaseV2RetrievalError(
                "SUPABASE_URL and backend-only SUPABASE_SERVICE_ROLE_KEY are required"
            )
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode(
            "utf-8"
        )
        request = Request(
            self.rpc_endpoint,
            data=body,
            headers={
                "Accept": "application/json",
                "apikey": self.settings.supabase_service_role_key.get_secret_value(),
                "Authorization": (
                    "Bearer "
                    + self.settings.supabase_service_role_key.get_secret_value()
                ),
                "Content-Type": "application/json; charset=utf-8",
            },
            method="POST",
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:  # type: ignore[operator]
                status = getattr(response, "status", 200)
                if not isinstance(status, int) or not 200 <= status < 300:
                    raise SupabaseV2RetrievalError(
                        f"canonical Supabase RPC returned HTTP {status}"
                    )
                raw = response.read()
        except HTTPError as exc:
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC returned HTTP {exc.code}"
            ) from None
        except (URLError, TimeoutError, OSError) as exc:
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC request failed: {type(exc).__name__}"
            ) from None

        try:
            decoded = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SupabaseV2RetrievalError(
                "canonical Supabase RPC returned malformed UTF-8 JSON"
            ) from exc
        if not isinstance(decoded, list):
            raise SupabaseV2RetrievalError(
                "canonical Supabase RPC response must be a JSON array"
            )
        return decoded

    @classmethod
    def _map_result(cls, item: object, index: int) -> CanonicalV2RetrievalResult:
        if not isinstance(item, dict):
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} is not an object"
            )
        required = (
            "canonical_chunk_id",
            "content",
            "document_source_id",
            "document_version_id",
            "document_title",
            "heading_path",
            "locator",
            "namespace",
            "visibility",
            "metadata",
            "similarity",
        )
        missing = [key for key in required if key not in item]
        if missing:
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} is missing: {', '.join(missing)}"
            )
        string_fields = (
            "canonical_chunk_id",
            "content",
            "document_source_id",
            "document_version_id",
            "document_title",
            "namespace",
            "visibility",
        )
        if any(not isinstance(item[key], str) or not item[key] for key in string_fields):
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} has invalid identity fields"
            )
        if item["visibility"] not in {"SHARED", "SCOPED"}:
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} has invalid visibility"
            )
        if not isinstance(item["heading_path"], list) or not isinstance(item["locator"], dict):
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} has invalid citation location"
            )
        if not isinstance(item["metadata"], dict):
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} has invalid metadata"
            )
        similarity = item["similarity"]
        if isinstance(similarity, bool) or not isinstance(similarity, (int, float)):
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} has invalid similarity"
            )
        similarity_value = float(similarity)
        if not math.isfinite(similarity_value):
            raise SupabaseV2RetrievalError(
                f"canonical Supabase RPC result {index + 1} has non-finite similarity"
            )

        return CanonicalV2RetrievalResult(
            canonical_chunk_id=item["canonical_chunk_id"],
            content=item["content"],
            similarity=similarity_value,
            document_source_id=item["document_source_id"],
            document_version_id=item["document_version_id"],
            document_title=item["document_title"],
            heading_path=list(item["heading_path"]),
            locator=dict(item["locator"]),
            namespace=item["namespace"],
            visibility=item["visibility"],
            metadata=dict(item["metadata"]),
        )
