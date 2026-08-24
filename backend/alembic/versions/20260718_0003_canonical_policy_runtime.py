"""canonical policy runtime

Revision ID: 20260718_0003
Revises: 20260718_0002
Create Date: 2026-08-24
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260718_0003"
down_revision: str | None = "20260718_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # PolicyDocument changes
    op.add_column("policy_documents", sa.Column("canonical_source_id", sa.String(length=255), nullable=True))
    op.add_column("policy_documents", sa.Column("canonical_version_id", sa.String(length=255), nullable=True))
    op.add_column("policy_documents", sa.Column("canonical_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=True))

    # PolicyEmbedding changes
    op.add_column("policy_embeddings", sa.Column("canonical_chunk_id", sa.String(length=255), nullable=True))

    # Replace constraint with partial indexes
    op.drop_constraint("uq_policy_embeddings_document_content_hash", "policy_embeddings", type_="unique")
    
    op.create_index(
        "uq_policy_embeddings_canonical",
        "policy_embeddings",
        ["policy_document_id", "canonical_chunk_id"],
        unique=True,
        postgresql_where=sa.text("canonical_chunk_id IS NOT NULL")
    )
    op.create_index(
        "uq_policy_embeddings_legacy",
        "policy_embeddings",
        ["policy_document_id", "content_hash"],
        unique=True,
        postgresql_where=sa.text("canonical_chunk_id IS NULL")
    )


def downgrade() -> None:
    # Need to handle duplicate content_hash rows where canonical_chunk_id is NULL before we restore the constraint
    # We will explicitly leave this to the DBA or delete them, but since we are just removing the constraint
    # we can try to re-create it. If it fails, it fails explicitly.
    # "either make downgrade safe or fail explicitly with a clear explanation if canonical duplicate-content rows prevent restoration"
    
    # Reverse PolicyEmbedding changes
    op.drop_index("uq_policy_embeddings_legacy", table_name="policy_embeddings")
    op.drop_index("uq_policy_embeddings_canonical", table_name="policy_embeddings")
    
    # Attempt to recreate the unique constraint. This may fail if there are canonical_chunk duplicates that share content hash.
    try:
        op.create_unique_constraint(
            "uq_policy_embeddings_document_content_hash",
            "policy_embeddings",
            ["policy_document_id", "content_hash"]
        )
    except Exception as e:
        raise RuntimeError("Failed to restore legacy unique constraint due to duplicate content hashes. Clear canonical data first.") from e

    op.drop_column("policy_embeddings", "canonical_chunk_id")

    # Reverse PolicyDocument changes
    op.drop_column("policy_documents", "canonical_metadata")
    op.drop_column("policy_documents", "canonical_version_id")
    op.drop_column("policy_documents", "canonical_source_id")
