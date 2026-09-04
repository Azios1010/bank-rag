"""Isolated SQLAlchemy scaffolding for the future Supabase-backed RAG V2 path.

These models deliberately share the existing Base metadata, but use the rag_v2
schema so they cannot collide with the active public.policy_documents tables.
They are not imported by the legacy R01/runtime services.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.models import Base, EMBEDDING_DIMENSIONS


RAG_V2_SCHEMA = "rag_v2"
SUPPORTED_SPECIALIST_SCOPES = (
    "credit",
    "risk_management",
    "legal_compliance",
    "customer_relationship",
    "collateral_appraisal",
)
VISIBILITY_VALUES = ("SHARED", "SCOPED")


class CorpusVersion(Base):
    __tablename__ = "corpus_versions"
    __table_args__ = (
        UniqueConstraint("corpus_name", "version", name="uq_rag_v2_corpus_versions_name_version"),
        {"schema": RAG_V2_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    corpus_name: Mapped[str] = mapped_column(String(255), nullable=False)
    version: Mapped[str] = mapped_column(String(255), nullable=False)
    manifest_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class EmbeddingProfile(Base):
    __tablename__ = "embedding_profiles"
    __table_args__ = (
        CheckConstraint("dimension = 1024", name="dimension_1024"),
        CheckConstraint("similarity = 'cosine'", name="similarity_cosine"),
        UniqueConstraint("model_id", "model_revision", name="uq_rag_v2_embedding_profiles_model_revision"),
        {"schema": RAG_V2_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    model_id: Mapped[str] = mapped_column(String(255), nullable=False)
    model_revision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False, default=EMBEDDING_DIMENSIONS, server_default=text("1024"))
    similarity: Mapped[str] = mapped_column(String(16), nullable=False, default="cosine", server_default=text("'cosine'"))
    is_unit_normalized: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class V2PolicyDocument(Base):
    __tablename__ = "policy_documents"
    __table_args__ = (
        CheckConstraint("visibility IN ('SHARED', 'SCOPED')", name="visibility"),
        CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="byte_size_non_negative"),
        UniqueConstraint("corpus_version_id", "source_id", "version_id", name="uq_rag_v2_documents_corpus_source_version"),
        Index("ix_rag_v2_policy_documents_source_version", "source_id", "version_id"),
        {"schema": RAG_V2_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    corpus_version_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("rag_v2.corpus_versions.id", ondelete="RESTRICT"), nullable=False)
    source_id: Mapped[str] = mapped_column(String(255), nullable=False)
    version_id: Mapped[str] = mapped_column(String(255), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    issuer: Mapped[str | None] = mapped_column(String(512), nullable=True)
    document_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    byte_size: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class PolicyChunk(Base):
    __tablename__ = "policy_chunks"
    __table_args__ = (
        CheckConstraint("visibility IN ('SHARED', 'SCOPED')", name="visibility"),
        UniqueConstraint("canonical_chunk_id", name="uq_rag_v2_policy_chunks_canonical_chunk_id"),
        Index("ix_rag_v2_policy_chunks_document_id", "document_id"),
        Index("ix_rag_v2_policy_chunks_embedding_hnsw", "embedding", postgresql_using="hnsw", postgresql_ops={"embedding": "vector_cosine_ops"}),
        {"schema": RAG_V2_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("rag_v2.policy_documents.id", ondelete="RESTRICT"), nullable=False)
    embedding_profile_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("rag_v2.embedding_profiles.id", ondelete="RESTRICT"), nullable=False)
    canonical_chunk_id: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    heading_path: Mapped[list[object]] = mapped_column(JSONB, nullable=False, default=list, server_default=text("'[]'::jsonb"))
    locator: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"))
    namespace: Mapped[str] = mapped_column(String(128), nullable=False)
    visibility: Mapped[str] = mapped_column(String(16), nullable=False)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=text("false"))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSIONS), nullable=False)
    search_document: Mapped[object] = mapped_column(TSVECTOR, nullable=False)
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ChunkScopeAccess(Base):
    __tablename__ = "chunk_scope_access"
    __table_args__ = (
        CheckConstraint(
            "scope IN ('credit', 'risk_management', 'legal_compliance', "
            "'customer_relationship', 'collateral_appraisal')",
            name="supported_scope",
        ),
        UniqueConstraint("policy_chunk_id", "scope", name="uq_rag_v2_chunk_scope_access_chunk_scope"),
        Index("ix_rag_v2_chunk_scope_access_scope_chunk", "scope", "policy_chunk_id"),
        {"schema": RAG_V2_SCHEMA},
    )

    id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4)
    policy_chunk_id: Mapped[UUID] = mapped_column(PostgreSQLUUID(as_uuid=True), ForeignKey("rag_v2.policy_chunks.id", ondelete="CASCADE"), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
