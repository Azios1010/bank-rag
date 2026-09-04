"""Legacy R01 application RAG services.

These services intentionally remain available for the existing application
runtime.  They use the legacy public policy tables and are not part of the
canonical Corpus V2 evaluation path; V2 callers must use
``CanonicalV2Retriever``.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Protocol
from uuid import UUID, uuid4

from openai import OpenAI
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.models import AgentKnowledgeBase, PolicyDocument, PolicyEmbedding
from app.schemas import AgentCitation, AgentID


_TOKEN_PATTERN = re.compile(r"[\wÀ-ỹ]+", flags=re.UNICODE)


class EmbeddingProvider(Protocol):
    dimension: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


class DeterministicEmbeddingProvider:
    """Token-hashing test double; runtime settings forbid it outside tests."""

    def __init__(self, dimension: int = 1024) -> None:
        if dimension < 1:
            raise ValueError("embedding dimension must be positive")
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        vector = [0.0] * self.dimension
        tokens = _TOKEN_PATTERN.findall(text.casefold())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            first_index = int.from_bytes(digest[:4], "big") % self.dimension
            second_index = int.from_bytes(digest[4:8], "big") % self.dimension
            vector[first_index] += 1.0 if digest[8] & 1 else -1.0
            vector[second_index] += 0.5 if digest[9] & 1 else -0.5

        norm = math.sqrt(sum(value * value for value in vector))
        if norm == 0:
            return vector
        return [value / norm for value in vector]


class OpenAICompatibleEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str,
        dimension: int,
        base_url: str | None = None,
    ) -> None:
        self.dimension = dimension
        self._model = model
        self._client = OpenAI(api_key=api_key, base_url=base_url)

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        embeddings: list[list[float]] = []
        for start in range(0, len(texts), 32):
            batch = texts[start : start + 32]
            response = self._client.embeddings.create(
                model=self._model,
                input=batch,
            )
            ordered = sorted(response.data, key=lambda item: item.index)
            embeddings.extend(item.embedding for item in ordered)
        if any(len(embedding) != self.dimension for embedding in embeddings):
            raise ValueError(
                f"embedding provider must return {self.dimension} dimensions"
            )
        return embeddings


@dataclass(frozen=True)
class TextChunk:
    index: int
    content: str


def split_text(
    text: str,
    *,
    chunk_size: int = 1200,
    overlap: int = 150,
) -> list[TextChunk]:
    """Split policy text on paragraphs while preserving a bounded overlap."""

    if chunk_size < 100:
        raise ValueError("chunk_size must be at least 100 characters")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between zero and chunk_size")

    normalized = "\n".join(
        line.strip() for line in text.replace("\r\n", "\n").split("\n")
    ).strip()
    if not normalized:
        return []

    chunks: list[TextChunk] = []
    start = 0
    index = 0
    while start < len(normalized):
        end = min(start + chunk_size, len(normalized))
        if end < len(normalized):
            paragraph_break = normalized.rfind("\n", start, end)
            sentence_break = normalized.rfind(". ", start, end)
            preferred_break = max(paragraph_break, sentence_break)
            if preferred_break > start + chunk_size // 2:
                end = preferred_break + (2 if preferred_break == sentence_break else 1)
        content = normalized[start:end].strip()
        if content:
            chunks.append(TextChunk(index=index, content=content))
            index += 1
        if end >= len(normalized):
            break
        start = end - overlap
    return chunks


def create_embedding_provider(
    settings: Settings | None = None,
) -> EmbeddingProvider:
    current = settings or get_settings()
    if current.embedding_provider == "deterministic_test":
        return DeterministicEmbeddingProvider(current.embedding_dimension)

    if (
        not current.embedding_api_key
        or not current.embedding_api_key.get_secret_value().strip()
    ):
        raise ValueError("EMBEDDING_API_KEY is required for openai-compatible embeddings")
    return OpenAICompatibleEmbeddingProvider(
        api_key=current.embedding_api_key.get_secret_value(),
        base_url=current.embedding_api_base,
        model=current.embedding_model,
        dimension=current.embedding_dimension,
    )


AGENT_KNOWLEDGE_KEYS: dict[AgentID, str] = {
    AgentID.CUSTOMER_RELATIONSHIP: "customer_relationship",
    AgentID.CREDIT: "credit",
    AgentID.RISK_MANAGEMENT: "risk_management",
    AgentID.LEGAL_COMPLIANCE: "legal_compliance",
    AgentID.COLLATERAL_APPRAISAL: "collateral_appraisal",
}


@dataclass(frozen=True)
class PolicyIngestionResult:
    policy_document_id: UUID
    chunks_created: int
    duplicate_chunks: int


class AgentPolicyRetriever:
    """Legacy retriever bound to one specialist knowledge-base scope."""

    def __init__(
        self,
        db: Session,
        agent_id: AgentID,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        if agent_id not in AGENT_KNOWLEDGE_KEYS:
            raise ValueError(f"Agent {agent_id.value} has no private policy scope")
        self._db = db
        self._agent_id = agent_id
        self._agent_key = AGENT_KNOWLEDGE_KEYS[agent_id]
        self._embedding_provider = embedding_provider

    @property
    def agent_id(self) -> AgentID:
        return self._agent_id

    def retrieve(
        self,
        query: str,
        limit: int = 3,
        *,
        min_similarity: float = 0.0,
    ) -> list[AgentCitation]:
        if not query.strip():
            raise ValueError("RAG query cannot be empty")
        if limit < 1 or limit > 20:
            raise ValueError("RAG result limit must be between 1 and 20")
        if not 0 <= min_similarity <= 1:
            raise ValueError("RAG minimum similarity must be between zero and one")

        query_embedding = self._embedding_provider.embed([query])[0]
        distance = PolicyEmbedding.embedding.cosine_distance(query_embedding)
        statement = (
            select(
                PolicyEmbedding,
                PolicyDocument,
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
                AgentKnowledgeBase.agent_key == self._agent_key,
                AgentKnowledgeBase.active.is_(True),
                PolicyDocument.active.is_(True),
                (
                    PolicyDocument.effective_at.is_(None)
                    | (PolicyDocument.effective_at <= datetime.now(timezone.utc))
                ),
            )
            .order_by(distance)
            .limit(min(80, limit * 4))
        )
        rows = self._db.execute(statement).all()

        citations: list[AgentCitation] = []
        for embedding, policy_document, raw_distance in rows:
            metadata = embedding.metadata_
            similarity = max(0.0, min(1.0, 1.0 - float(raw_distance)))
            if similarity < min_similarity:
                continue
            citations.append(
                AgentCitation(
                    policy_chunk_id=embedding.id,
                    document_name=str(
                        metadata.get("document_name", policy_document.title)
                    ),
                    document_version=str(
                        metadata.get("document_version", policy_document.version)
                    ),
                    page_number=int(metadata.get("page_number", 1)),
                    section_id=str(metadata.get("section_id", "UNSPECIFIED")),
                    quote=embedding.content_chunk,
                    similarity_score=Decimal(str(round(similarity, 6))),
                )
            )
            if len(citations) >= limit:
                break
        return citations


class PolicyIngestionService:
    def __init__(
        self,
        db: Session,
        embedding_provider: EmbeddingProvider,
    ) -> None:
        self._db = db
        self._embedding_provider = embedding_provider

    def ingest(
        self,
        *,
        agent_id: AgentID,
        title: str,
        version: str,
        content: str,
        source_sha256: str,
        source_object_key: str | None,
        section_id: str,
        page_number: int,
        effective_at: datetime | None = None,
    ) -> PolicyIngestionResult:
        agent_key = AGENT_KNOWLEDGE_KEYS.get(agent_id)
        if agent_key is None:
            raise ValueError("Policies can only be assigned to specialist agents")

        knowledge_base = self._db.scalar(
            select(AgentKnowledgeBase).where(
                AgentKnowledgeBase.agent_key == agent_key,
                AgentKnowledgeBase.active.is_(True),
            )
        )
        if knowledge_base is None:
            raise LookupError(f"Knowledge base {agent_key} is not bootstrapped")

        existing_document = self._db.scalar(
            select(PolicyDocument).where(
                PolicyDocument.knowledge_base_id == knowledge_base.id,
                PolicyDocument.title == title,
                PolicyDocument.version == version,
            )
        )
        if existing_document is not None:
            if existing_document.sha256 != source_sha256:
                raise ValueError(
                    "A policy with this title/version already has different content"
                )
            document = existing_document
        else:
            document = PolicyDocument(
                id=uuid4(),
                knowledge_base_id=knowledge_base.id,
                title=title,
                version=version,
                source_object_key=source_object_key,
                sha256=source_sha256,
                effective_at=effective_at,
                active=True,
            )
            self._db.add(document)
            self._db.flush()

        chunks = split_text(content)
        if not chunks:
            raise ValueError("Policy document contains no indexable text")
        vectors = self._embedding_provider.embed(
            [chunk.content for chunk in chunks]
        )
        chunks_created = 0
        duplicate_chunks = 0
        for chunk, vector in zip(chunks, vectors, strict=True):
            content_hash = hashlib.sha256(chunk.content.encode("utf-8")).hexdigest()
            existing_chunk = self._db.scalar(
                select(PolicyEmbedding.id).where(
                    PolicyEmbedding.policy_document_id == document.id,
                    PolicyEmbedding.content_hash == content_hash,
                )
            )
            if existing_chunk is not None:
                duplicate_chunks += 1
                continue
            self._db.add(
                PolicyEmbedding(
                    id=uuid4(),
                    knowledge_base_id=knowledge_base.id,
                    policy_document_id=document.id,
                    chunk_index=chunk.index,
                    content_chunk=chunk.content,
                    content_hash=content_hash,
                    embedding=vector,
                    metadata_={
                        "document_name": title,
                        "document_version": version,
                        "section_id": section_id,
                        "page_number": page_number,
                        "agent_scope": agent_key,
                        "demo_only": False,
                    },
                )
            )
            chunks_created += 1

        return PolicyIngestionResult(
            policy_document_id=document.id,
            chunks_created=chunks_created,
            duplicate_chunks=duplicate_chunks,
        )
