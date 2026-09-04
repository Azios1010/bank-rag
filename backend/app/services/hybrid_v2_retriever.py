"""Canonical Corpus V2 vector + PostgreSQL FTS retrieval with fixed RRF."""

from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any

from app.config import Settings
from app.services.supabase_fts_retriever import (
    CanonicalV2LexicalResult,
    CanonicalV2LexicalRetriever,
)
from app.services.supabase_v2_retriever import (
    CanonicalV2RetrievalResult,
    CanonicalV2Retriever,
    normalize_specialist_scope,
)


class SupabaseHybridRetrievalError(RuntimeError):
    """Raised when the two canonical branches cannot be fused safely."""


@dataclass(frozen=True)
class CanonicalV2HybridResult:
    canonical_chunk_id: str
    content: str
    rrf_score: float
    vector_rank: int | None
    lexical_rank: int | None
    vector_similarity: float | None
    lexical_score: float | None
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
        if self.metadata.get("provenance_kind") == "synthetic_internal_policy":
            return "synthetic_internal_policy"
        return "real_regulation"


@dataclass(frozen=True)
class CanonicalV2HybridTiming:
    vector_embedding_ms: float
    vector_retrieval_ms: float
    lexical_ms: float
    fusion_ms: float
    total_ms: float


class CanonicalV2HybridRetriever:
    """Sequential vector + FTS candidate retrieval followed by fixed RRF."""

    CANDIDATE_DEPTH = 20
    RRF_K = 60

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        vector_retriever: CanonicalV2Retriever | None = None,
        lexical_retriever: CanonicalV2LexicalRetriever | None = None,
    ) -> None:
        self.vector_retriever = vector_retriever or CanonicalV2Retriever(settings)
        self.lexical_retriever = lexical_retriever or CanonicalV2LexicalRetriever(settings)

    def retrieve(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> list[CanonicalV2HybridResult]:
        results, _ = self.retrieve_with_timing(query, scope, k=k)
        return results

    def retrieve_with_timing(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> tuple[list[CanonicalV2HybridResult], CanonicalV2HybridTiming]:
        results, _, _, timing = self.retrieve_with_candidates_with_timing(
            query, scope, k=k
        )
        return results, timing

    def retrieve_with_candidates_with_timing(
        self,
        query: str,
        scope: object,
        k: int = 5,
    ) -> tuple[
        list[CanonicalV2HybridResult],
        list[CanonicalV2RetrievalResult],
        list[CanonicalV2LexicalResult],
        CanonicalV2HybridTiming,
    ]:
        """Return fused results plus the fixed-depth branch candidates.

        The additional branch detail is for auditable evaluation traces.  The
        branch calls and fusion formula remain owned by this canonical
        retriever; callers do not reimplement routing or ranking.
        """
        requested_scope = normalize_specialist_scope(scope)
        if isinstance(k, bool) or not isinstance(k, int) or not 1 <= k <= 100:
            raise ValueError("k must be an integer between 1 and 100")
        total_started = time.perf_counter()
        vector_results, vector_timing = self.vector_retriever.retrieve_with_timing(
            query, requested_scope, k=self.CANDIDATE_DEPTH
        )
        lexical_results, lexical_timing = self.lexical_retriever.retrieve_with_timing(
            query, requested_scope, k=self.CANDIDATE_DEPTH
        )

        fusion_started = time.perf_counter()
        vector_by_id = {
            item.canonical_chunk_id: (rank, item)
            for rank, item in enumerate(vector_results, start=1)
        }
        lexical_by_id = {
            item.canonical_chunk_id: (rank, item)
            for rank, item in enumerate(lexical_results, start=1)
        }
        fused: list[CanonicalV2HybridResult] = []
        for chunk_id in sorted(set(vector_by_id) | set(lexical_by_id)):
            vector_rank, vector_item = vector_by_id.get(chunk_id, (None, None))
            lexical_rank, lexical_item = lexical_by_id.get(chunk_id, (None, None))
            if vector_item is not None and lexical_item is not None:
                self._validate_shared_identity(vector_item, lexical_item)
                base = vector_item
            elif vector_item is not None:
                base = vector_item
            elif lexical_item is not None:
                base = lexical_item
            else:  # pragma: no cover - union construction makes this unreachable
                raise SupabaseHybridRetrievalError("empty RRF candidate")
            rrf_score = 0.0
            if vector_rank is not None:
                rrf_score += 1.0 / (self.RRF_K + vector_rank)
            if lexical_rank is not None:
                rrf_score += 1.0 / (self.RRF_K + lexical_rank)
            fused.append(
                CanonicalV2HybridResult(
                    canonical_chunk_id=chunk_id,
                    content=base.content,
                    rrf_score=rrf_score,
                    vector_rank=vector_rank,
                    lexical_rank=lexical_rank,
                    vector_similarity=(
                        vector_item.similarity if vector_item is not None else None
                    ),
                    lexical_score=(
                        lexical_item.lexical_score if lexical_item is not None else None
                    ),
                    document_source_id=base.document_source_id,
                    document_version_id=base.document_version_id,
                    document_title=base.document_title,
                    heading_path=list(base.heading_path),
                    locator=dict(base.locator),
                    namespace=base.namespace,
                    visibility=base.visibility,
                    metadata=dict(base.metadata),
                )
            )
        fused.sort(key=lambda item: (-item.rrf_score, item.canonical_chunk_id))
        fusion_ms = (time.perf_counter() - fusion_started) * 1000
        total_ms = (time.perf_counter() - total_started) * 1000
        return (
            fused[:k],
            vector_results,
            lexical_results,
            CanonicalV2HybridTiming(
                vector_embedding_ms=vector_timing.embedding_ms,
                vector_retrieval_ms=vector_timing.retrieval_ms,
                lexical_ms=lexical_timing.retrieval_ms,
                fusion_ms=fusion_ms,
                total_ms=total_ms,
            ),
        )

    @staticmethod
    def _validate_shared_identity(
        vector_item: CanonicalV2RetrievalResult,
        lexical_item: CanonicalV2LexicalResult,
    ) -> None:
        fields = (
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
        )
        for field in fields:
            if getattr(vector_item, field) != getattr(lexical_item, field):
                raise SupabaseHybridRetrievalError(
                    f"vector and FTS identity mismatch at {field} for {vector_item.canonical_chunk_id}"
                )
