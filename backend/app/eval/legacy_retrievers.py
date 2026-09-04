"""Historical R01 retrieval helpers, isolated from the canonical V2 path."""

import time

from app.db.models import AgentKnowledgeBase, PolicyDocument, PolicyEmbedding
from app.eval.contracts import (
    RankedRetrievalResult,
    RetrievalExecution,
    RetrievalRequest,
)
from app.services.rag import AGENT_KNOWLEDGE_KEYS
from sqlalchemy import select
from sqlalchemy.orm import Session


class LegacyPolicyEmbeddingRetriever:
    """Historical R01 retriever; never use this for Corpus V2 evaluation."""

    def __init__(self, db: Session, embedding_adapter):
        self._db = db
        self._embedding_adapter = embedding_adapter

    def retrieve(self, request: RetrievalRequest, k: int = 5) -> RetrievalExecution:
        start_embed = time.perf_counter()
        query_embeddings = self._embedding_adapter.embed_queries([request.query])
        query_vector = query_embeddings[0]
        end_embed = time.perf_counter()

        start_retrieve = time.perf_counter()
        agent_key = request.agent_scope
        if hasattr(agent_key, "value"):
            agent_key = agent_key.value

        from app.schemas import AgentID

        try:
            enum_val = AgentID(agent_key)
            mapped_key = AGENT_KNOWLEDGE_KEYS.get(enum_val, agent_key)
        except ValueError:
            mapped_key = agent_key

        distance = PolicyEmbedding.embedding.cosine_distance(query_vector)
        statement = (
            select(
                PolicyEmbedding.canonical_chunk_id,
                distance.label("distance"),
            )
            .join(
                AgentKnowledgeBase,
                PolicyEmbedding.knowledge_base_id == AgentKnowledgeBase.id,
            )
            .join(
                PolicyDocument,
                PolicyEmbedding.policy_document_id == PolicyDocument.id,
            )
            .where(
                AgentKnowledgeBase.agent_key == mapped_key,
                PolicyDocument.active.is_(False),
                PolicyEmbedding.canonical_chunk_id.is_not(None),
                PolicyDocument.canonical_source_id.is_not(None),
                PolicyDocument.canonical_version_id.is_not(None),
            )
            .order_by(distance, PolicyEmbedding.canonical_chunk_id)
            .limit(k * 4)
        )

        rows = self._db.execute(statement).all()
        seen = set()
        results = []
        rank = 1
        for row in rows:
            chunk_id = row.canonical_chunk_id
            if chunk_id in seen:
                continue
            seen.add(chunk_id)
            raw_distance = float(row.distance)
            similarity = max(0.0, min(1.0, 1.0 - raw_distance))
            results.append(
                RankedRetrievalResult(
                    canonical_chunk_id=chunk_id,
                    rank=rank,
                    score=similarity,
                    score_semantics="cosine_similarity",
                    retrieval_source="legacy_policy_embeddings",
                    metadata={},
                )
            )
            rank += 1
            if len(results) >= k:
                break

        end_retrieve = time.perf_counter()
        return RetrievalExecution(
            results=results,
            embedding_latency_ms=(end_embed - start_embed) * 1000,
            retrieval_latency_ms=(end_retrieve - start_retrieve) * 1000,
            total_latency_ms=(end_retrieve - start_embed) * 1000,
        )
