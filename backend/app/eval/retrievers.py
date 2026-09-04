"""Canonical Corpus V2 evaluation retrievers.

Historical R01 retrieval helpers live in ``legacy_retrievers.py`` so importing
this module cannot load legacy table models or query-routing code.
"""

from app.eval.contracts import (
    RankedRetrievalResult,
    RetrievalExecution,
    RetrievalRequest,
)
from app.services.supabase_v2_retriever import CanonicalV2Retriever


class CanonicalV2EvaluationRetriever:
    """Evaluation adapter over the canonical llama.cpp/Supabase retriever.

    The returned ``RetrievalExecution`` preserves the existing evaluation
    contract while citation identity remains in each result's metadata.
    Ranking and scope filtering stay exclusively inside the Supabase RPC.
    """

    def __init__(self, retriever: CanonicalV2Retriever | None = None) -> None:
        self._retriever = retriever or CanonicalV2Retriever()

    def retrieve(self, request: RetrievalRequest, k: int = 5) -> RetrievalExecution:
        results, timing = self._retriever.retrieve_with_timing(
            request.query, request.agent_scope, k=k
        )
        ranked = [
            RankedRetrievalResult(
                canonical_chunk_id=result.canonical_chunk_id,
                rank=rank,
                score=result.similarity,
                score_semantics="cosine_similarity",
                retrieval_source="supabase_rpc",
                metadata={
                    "content": result.content,
                    "document_source_id": result.document_source_id,
                    "document_version_id": result.document_version_id,
                    "document_title": result.document_title,
                    "heading_path": result.heading_path,
                    "locator": result.locator,
                    "namespace": result.namespace,
                    "visibility": result.visibility,
                    "metadata": result.metadata,
                    "source_type": result.source_type,
                },
            )
            for rank, result in enumerate(results, start=1)
        ]
        return RetrievalExecution(
            results=ranked,
            embedding_latency_ms=timing.embedding_ms,
            retrieval_latency_ms=timing.retrieval_ms,
            total_latency_ms=timing.embedding_ms + timing.retrieval_ms,
        )
