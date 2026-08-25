from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RetrievalRequest:
    evaluation_id: str
    query: str
    agent_scope: str


@dataclass(frozen=True)
class RankedRetrievalResult:
    canonical_chunk_id: str
    rank: int
    score: float
    score_semantics: str  # e.g., "cosine_similarity"
    retrieval_source: str # e.g., "vector"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RetrievalExecution:
    results: list[RankedRetrievalResult]
    embedding_latency_ms: float
    retrieval_latency_ms: float
    total_latency_ms: float
