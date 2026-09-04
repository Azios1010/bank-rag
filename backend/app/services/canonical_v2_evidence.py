"""Frozen Corpus V2 evidence retrieval contract.

This module is the production-facing seam for the retrieval architecture
frozen in Stage 13F.  Candidate generation remains exclusively the canonical
llama.cpp query embedding plus Supabase vector RPC.  A dedicated llama.cpp
reranker orders those candidates; it cannot add or remove candidate identity.

The returned objects contain source and locator information needed by a later
grounded-generation stage.  They intentionally do not contain evaluation
gold, rationale, or benchmark metadata.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from app.eval.llama_v2_reranker import LlamaV2RerankerAdapter
from app.services.supabase_v2_retriever import (
    CanonicalV2RetrievalResult,
    CanonicalV2Retriever,
    normalize_specialist_scope,
)


class CanonicalV2EvidenceError(RuntimeError):
    """Raised when the frozen evidence-retrieval contract is violated."""


@dataclass(frozen=True)
class CanonicalV2EvidenceResult:
    """One final, citation-ready result from the frozen V2 architecture."""

    rank: int
    canonical_chunk_id: str
    content: str
    document_source_id: str
    document_version_id: str
    document_title: str
    heading_path: list[Any]
    locator: dict[str, Any]
    namespace: str
    visibility: str
    provenance: str
    specialist_scope: str
    vector_rank: int
    vector_similarity: float
    reranker_score: float

    @property
    def citation_key(self) -> str:
        """Return the stable presentation key for this result position."""

        return f"E{self.rank}"

    @property
    def source_type(self) -> str:
        """Alias used by existing V2 citation consumers."""

        return self.provenance

    @property
    def article(self) -> Any:
        return self.locator.get("article")

    @property
    def clause(self) -> Any:
        return self.locator.get("clause")

    @property
    def point(self) -> Any:
        return self.locator.get("point")


def serialize_citations(
    results: Sequence[CanonicalV2EvidenceResult],
) -> list[dict[str, Any]]:
    """Serialize final evidence as E1..E5 without changing result order.

    This is a presentation contract only.  It does not add gold labels or
    other evaluation fields and rejects duplicate/invalid final identities.
    """

    if len(results) > CanonicalV2EvidenceRetriever.FINAL_K:
        raise CanonicalV2EvidenceError("citation serialization accepts at most five results")
    seen_ids: set[str] = set()
    serialized: list[dict[str, Any]] = []
    for rank, result in enumerate(results, start=1):
        if result.rank != rank:
            raise CanonicalV2EvidenceError("citation ranks must be contiguous from E1")
        if result.canonical_chunk_id in seen_ids:
            raise CanonicalV2EvidenceError("duplicate canonical_chunk_id in final evidence")
        if not math.isfinite(result.reranker_score) or not math.isfinite(result.vector_similarity):
            raise CanonicalV2EvidenceError("evidence scores must be finite")
        seen_ids.add(result.canonical_chunk_id)
        serialized.append(
            {
                "citation_id": result.citation_key,
                "canonical_chunk_id": result.canonical_chunk_id,
                "document_source_id": result.document_source_id,
                "document_version_id": result.document_version_id,
                "title": result.document_title,
                "heading_path": list(result.heading_path),
                "locator": dict(result.locator),
                "content": result.content,
                "namespace": result.namespace,
                "visibility": result.visibility,
                "provenance": result.provenance,
                "specialist_scope": result.specialist_scope,
                "vector_rank": result.vector_rank,
                "vector_similarity": result.vector_similarity,
                "reranker_score": result.reranker_score,
            }
        )
    return serialized


class CanonicalV2EvidenceRetriever:
    """Frozen query -> vector top20 -> reranker -> evidence top5 service."""

    CANDIDATE_K = 20
    FINAL_K = 5
    KNOWN_CANDIDATE_GENERATION_FAILURES = (
        "stage12a-024",
        "stage13e-040",
        "stage13e-042",
    )

    def __init__(
        self,
        vector_retriever: CanonicalV2Retriever | None = None,
        reranker: LlamaV2RerankerAdapter | None = None,
    ) -> None:
        self.vector_retriever = vector_retriever or CanonicalV2Retriever()
        self.reranker = reranker or LlamaV2RerankerAdapter()

    def retrieve_evidence(
        self,
        query: str,
        specialist_scope: object,
        candidate_k: int = CANDIDATE_K,
        final_k: int = FINAL_K,
    ) -> list[CanonicalV2EvidenceResult]:
        """Return the frozen final evidence set for one specialist query.

        ``candidate_k`` and ``final_k`` remain explicit for interface clarity,
        but the canonical production contract permits only 20 and 5.  This
        prevents accidental reintroduction of the pilot's Top10/Top50 arms.
        """

        if candidate_k != self.CANDIDATE_K:
            raise ValueError("canonical V2 candidate_k is frozen at 20")
        if final_k != self.FINAL_K:
            raise ValueError("canonical V2 final_k is frozen at 5")
        requested_scope = normalize_specialist_scope(specialist_scope)

        candidates, _timing = self.vector_retriever.retrieve_with_timing(
            query,
            requested_scope,
            k=self.CANDIDATE_K,
        )
        return self.rerank_candidates(query, requested_scope, candidates)

    def rerank_candidates(
        self,
        query: str,
        specialist_scope: object,
        candidates: Sequence[CanonicalV2RetrievalResult],
    ) -> list[CanonicalV2EvidenceResult]:
        """Rerank an already-frozen canonical vector candidate list.

        This phase seam lets local model processes be swapped sequentially on
        constrained hardware while preserving the exact candidate identities
        produced by the canonical vector path.  It is not an alternate
        candidate generator: every output identity must originate in
        ``candidates``.
        """

        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        requested_scope = normalize_specialist_scope(specialist_scope)
        self._validate_candidates(candidates)

        documents = [
            self.reranker.format_document(
                title=candidate.document_title,
                heading_path=candidate.heading_path,
                content=candidate.content,
            )
            for candidate in candidates
        ]
        scores = self.reranker.rerank(query, documents)
        if len(scores) != len(candidates):
            raise CanonicalV2EvidenceError(
                "reranker must return exactly one score per vector candidate"
            )

        by_index: dict[int, float] = {}
        for score in scores:
            if isinstance(score.index, bool) or not isinstance(score.index, int):
                raise CanonicalV2EvidenceError("reranker returned an invalid candidate index")
            if score.index in by_index or not 0 <= score.index < len(candidates):
                raise CanonicalV2EvidenceError("reranker candidate index set is invalid")
            if not math.isfinite(float(score.relevance_score)):
                raise CanonicalV2EvidenceError("reranker returned a non-finite relevance score")
            by_index[score.index] = float(score.relevance_score)
        if set(by_index) != set(range(len(candidates))):
            raise CanonicalV2EvidenceError("reranker did not cover every vector candidate")

        ordered = sorted(
            enumerate(candidates),
            key=lambda item: (-by_index[item[0]], item[1].canonical_chunk_id),
        )
        final: list[CanonicalV2EvidenceResult] = []
        for rank, (candidate_index, candidate) in enumerate(ordered[: self.FINAL_K], start=1):
            final.append(
                self._to_evidence_result(
                    candidate,
                    rank=rank,
                    vector_rank=candidate_index + 1,
                    specialist_scope=requested_scope,
                    reranker_score=by_index[candidate_index],
                )
            )
        if len({item.canonical_chunk_id for item in final}) != len(final):
            raise CanonicalV2EvidenceError("final evidence contains duplicate canonical IDs")
        return final

    @staticmethod
    def _validate_candidates(candidates: Sequence[CanonicalV2RetrievalResult]) -> None:
        if not 1 <= len(candidates) <= CanonicalV2EvidenceRetriever.CANDIDATE_K:
            raise CanonicalV2EvidenceError(
                "canonical vector retrieval must return between one and twenty candidates"
            )
        ids = [candidate.canonical_chunk_id for candidate in candidates]
        if len(set(ids)) != len(ids):
            raise CanonicalV2EvidenceError("vector candidates contain duplicate canonical IDs")
        if any(not isinstance(candidate.canonical_chunk_id, str) for candidate in candidates):
            raise CanonicalV2EvidenceError("vector candidate identity is invalid")

    @staticmethod
    def _to_evidence_result(
        candidate: CanonicalV2RetrievalResult,
        *,
        rank: int,
        vector_rank: int,
        specialist_scope: str,
        reranker_score: float,
    ) -> CanonicalV2EvidenceResult:
        return CanonicalV2EvidenceResult(
            rank=rank,
            canonical_chunk_id=candidate.canonical_chunk_id,
            content=candidate.content,
            document_source_id=candidate.document_source_id,
            document_version_id=candidate.document_version_id,
            document_title=candidate.document_title,
            heading_path=list(candidate.heading_path),
            locator=dict(candidate.locator),
            namespace=candidate.namespace,
            visibility=candidate.visibility,
            provenance=candidate.source_type,
            specialist_scope=specialist_scope,
            vector_rank=vector_rank,
            vector_similarity=candidate.similarity,
            reranker_score=reranker_score,
        )


def retrieve_evidence(
    query: str,
    specialist_scope: object,
    candidate_k: int = CanonicalV2EvidenceRetriever.CANDIDATE_K,
    final_k: int = CanonicalV2EvidenceRetriever.FINAL_K,
) -> list[CanonicalV2EvidenceResult]:
    """Convenience entry point for the frozen canonical retrieval contract."""

    return CanonicalV2EvidenceRetriever().retrieve_evidence(
        query,
        specialist_scope,
        candidate_k=candidate_k,
        final_k=final_k,
    )
