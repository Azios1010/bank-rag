"""Create the isolated Supabase RAG V2 foundation; no corpus data is migrated.

Revision ID: 20260831_0004
Revises: 20260718_0003
Create Date: 2026-08-31
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql


revision: str = "20260831_0004"
down_revision: str | None = "20260718_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # The existing legacy migration already requires pgvector. Keep this
    # idempotent so a Supabase database has the prerequisite explicitly.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE SCHEMA IF NOT EXISTS rag_v2")

    op.create_table(
        "corpus_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corpus_name", sa.String(length=255), nullable=False),
        sa.Column("version", sa.String(length=255), nullable=False),
        sa.Column("manifest_sha256", sa.String(length=64), nullable=True),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_rag_v2_corpus_versions"),
        sa.UniqueConstraint("corpus_name", "version", name="uq_rag_v2_corpus_versions_name_version"),
        schema="rag_v2",
    )
    op.create_table(
        "embedding_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("model_id", sa.String(length=255), nullable=False),
        sa.Column("model_revision", sa.String(length=255), nullable=True),
        sa.Column("dimension", sa.Integer(), server_default=sa.text("1024"), nullable=False),
        sa.Column("similarity", sa.String(length=16), server_default=sa.text("'cosine'"), nullable=False),
        sa.Column("is_unit_normalized", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("dimension = 1024", name="ck_rag_v2_embedding_profiles_dimension_1024"),
        sa.CheckConstraint("similarity = 'cosine'", name="ck_rag_v2_embedding_profiles_similarity_cosine"),
        sa.PrimaryKeyConstraint("id", name="pk_rag_v2_embedding_profiles"),
        sa.UniqueConstraint("model_id", "model_revision", name="uq_rag_v2_embedding_profiles_model_revision"),
        schema="rag_v2",
    )
    op.create_table(
        "policy_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("corpus_version_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.String(length=255), nullable=False),
        sa.Column("version_id", sa.String(length=255), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("issuer", sa.String(length=512), nullable=True),
        sa.Column("document_type", sa.String(length=128), nullable=True),
        sa.Column("effective_from", sa.Date(), nullable=True),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.Column("storage_bucket", sa.String(length=255), nullable=True),
        sa.Column("storage_path", sa.String(length=1024), nullable=True),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=True),
        sa.Column("namespace", sa.String(length=128), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('SHARED', 'SCOPED')", name="ck_rag_v2_policy_documents_visibility"),
        sa.CheckConstraint("byte_size IS NULL OR byte_size >= 0", name="ck_rag_v2_policy_documents_byte_size_non_negative"),
        sa.ForeignKeyConstraint(["corpus_version_id"], ["rag_v2.corpus_versions.id"], name="fk_rag_v2_policy_documents_corpus_version_id_corpus_versions", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_rag_v2_policy_documents"),
        sa.UniqueConstraint("corpus_version_id", "source_id", "version_id", name="uq_rag_v2_documents_corpus_source_version"),
        schema="rag_v2",
    )
    op.create_index("ix_rag_v2_policy_documents_source_version", "policy_documents", ["source_id", "version_id"], schema="rag_v2")
    op.create_table(
        "policy_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("embedding_profile_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("canonical_chunk_id", sa.String(length=255), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("heading_path", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("locator", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("namespace", sa.String(length=128), nullable=False),
        sa.Column("visibility", sa.String(length=16), nullable=False),
        sa.Column("is_synthetic", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("embedding", Vector(dim=1024), nullable=False),
        sa.Column("metadata", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("visibility IN ('SHARED', 'SCOPED')", name="ck_rag_v2_policy_chunks_visibility"),
        sa.ForeignKeyConstraint(["document_id"], ["rag_v2.policy_documents.id"], name="fk_rag_v2_policy_chunks_document_id_policy_documents", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["embedding_profile_id"], ["rag_v2.embedding_profiles.id"], name="fk_rag_v2_policy_chunks_embedding_profile_id_embedding_profiles", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_rag_v2_policy_chunks"),
        sa.UniqueConstraint("canonical_chunk_id", name="uq_rag_v2_policy_chunks_canonical_chunk_id"),
        schema="rag_v2",
    )
    op.create_index("ix_rag_v2_policy_chunks_document_id", "policy_chunks", ["document_id"], schema="rag_v2")
    op.execute("CREATE INDEX ix_rag_v2_policy_chunks_embedding_hnsw ON rag_v2.policy_chunks USING hnsw (embedding vector_cosine_ops)")
    op.create_table(
        "chunk_scope_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("policy_chunk_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("scope", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("scope IN ('credit', 'risk_management', 'legal_compliance', 'customer_relationship', 'collateral_appraisal')", name="ck_rag_v2_chunk_scope_access_supported_scope"),
        sa.ForeignKeyConstraint(["policy_chunk_id"], ["rag_v2.policy_chunks.id"], name="fk_rag_v2_chunk_scope_access_policy_chunk_id_policy_chunks", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_rag_v2_chunk_scope_access"),
        sa.UniqueConstraint("policy_chunk_id", "scope", name="uq_rag_v2_chunk_scope_access_chunk_scope"),
        schema="rag_v2",
    )
    op.create_index("ix_rag_v2_chunk_scope_access_scope_chunk", "chunk_scope_access", ["scope", "policy_chunk_id"], schema="rag_v2")

    # Backend-only dense retrieval contract. EXISTS is intentional: access rows
    # must filter a single chunk vector, never fan it out into duplicate rows.
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.match_policy_chunks(
            query_embedding extensions.vector(1024), requested_scope text, match_count integer
        )
        RETURNS TABLE(
            canonical_chunk_id text, content text, document_source_id text,
            document_version_id text, document_title text, heading_path jsonb,
            locator jsonb, namespace text, visibility text, metadata jsonb,
            similarity double precision
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = pg_catalog, rag_v2
        AS $$
            SELECT
                c.canonical_chunk_id,
                c.content,
                d.source_id AS document_source_id,
                d.version_id AS document_version_id,
                d.title AS document_title,
                c.heading_path,
                c.locator,
                c.namespace,
                c.visibility,
                c.metadata,
                1 - (c.embedding OPERATOR(extensions.<=>) query_embedding) AS similarity
            FROM rag_v2.policy_chunks AS c
            JOIN rag_v2.policy_documents AS d ON d.id = c.document_id
            WHERE c.visibility = 'SHARED'
               OR EXISTS (
                   SELECT 1
                   FROM rag_v2.chunk_scope_access AS access
                   WHERE access.policy_chunk_id = c.id
                     AND access.scope = requested_scope
               )
                ORDER BY c.embedding OPERATOR(extensions.<=>) query_embedding, c.canonical_chunk_id
            LIMIT LEAST(GREATEST(COALESCE(match_count, 10), 1), 100)
        $$;
        """
    )
    op.execute("REVOKE ALL ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer) FROM PUBLIC")
    # Supabase normally provides this role. Keep non-Supabase development
    # databases migratable by granting only when the role is present.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT USAGE ON SCHEMA rag_v2 TO service_role;
                GRANT SELECT ON rag_v2.policy_documents, rag_v2.policy_chunks,
                    rag_v2.chunk_scope_access TO service_role;
                GRANT EXECUTE ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer)
                    TO service_role;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS public.match_policy_chunks(extensions.vector, text, integer)")
    op.drop_index("ix_rag_v2_chunk_scope_access_scope_chunk", table_name="chunk_scope_access", schema="rag_v2")
    op.drop_table("chunk_scope_access", schema="rag_v2")
    op.execute("DROP INDEX IF EXISTS rag_v2.ix_rag_v2_policy_chunks_embedding_hnsw")
    op.drop_index("ix_rag_v2_policy_chunks_document_id", table_name="policy_chunks", schema="rag_v2")
    op.drop_table("policy_chunks", schema="rag_v2")
    op.drop_index("ix_rag_v2_policy_documents_source_version", table_name="policy_documents", schema="rag_v2")
    op.drop_table("policy_documents", schema="rag_v2")
    op.drop_table("embedding_profiles", schema="rag_v2")
    op.drop_table("corpus_versions", schema="rag_v2")
    op.execute("DROP SCHEMA IF EXISTS rag_v2")
