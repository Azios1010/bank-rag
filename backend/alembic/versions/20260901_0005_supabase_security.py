"""Harden the isolated Supabase RAG V2 foundation.

Revision ID: 20260901_0005
Revises: 20260831_0004
Create Date: 2026-09-01

This migration intentionally leaves the legacy public schema untouched.  The
new RAG tables are deny-by-default for public and authenticated clients; the
trusted backend role is granted the minimum database access needed for the
future import and retrieval paths.
"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260901_0005"
down_revision: str | None = "20260831_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


RAG_TABLES = (
    "rag_v2.corpus_versions",
    "rag_v2.embedding_profiles",
    "rag_v2.policy_documents",
    "rag_v2.policy_chunks",
    "rag_v2.chunk_scope_access",
)


def upgrade() -> None:
    for table in RAG_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")

    # No public or user-facing role receives access to the canonical policy
    # tables.  The application will use the trusted backend path for these
    # operations, while the RPC remains explicitly backend-only.
    op.execute("REVOKE ALL ON SCHEMA rag_v2 FROM PUBLIC")
    for table in RAG_TABLES:
        op.execute(f"REVOKE ALL ON TABLE {table} FROM PUBLIC")

    op.execute(
        """
        DO $$
        DECLARE role_name text;
        BEGIN
            FOR role_name IN
                SELECT rolname FROM pg_roles
                WHERE rolname IN ('anon', 'authenticated', 'service_role')
            LOOP
                EXECUTE format('REVOKE ALL ON SCHEMA rag_v2 FROM %I', role_name);
                EXECUTE format(
                    'REVOKE ALL ON TABLE rag_v2.corpus_versions,
                        rag_v2.embedding_profiles, rag_v2.policy_documents,
                        rag_v2.policy_chunks, rag_v2.chunk_scope_access FROM %I',
                    role_name
                );
            END LOOP;
        END $$;
        """
    )

    # Keep access conditional so the migration remains renderable on local
    # PostgreSQL installations that do not define Supabase's service_role.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT USAGE ON SCHEMA rag_v2 TO service_role;
                GRANT SELECT, INSERT, UPDATE, DELETE ON
                    rag_v2.corpus_versions,
                    rag_v2.embedding_profiles,
                    rag_v2.policy_documents,
                    rag_v2.policy_chunks,
                    rag_v2.chunk_scope_access
                    TO service_role;
            END IF;
        END $$;
        """
    )

    # RLS policies are explicit for the trusted backend role.  anon and
    # authenticated have no table grants and therefore cannot reach these
    # policies or mutate canonical data.
    op.execute(
        """
        DO $$
        DECLARE table_name text;
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                FOREACH table_name IN ARRAY ARRAY[
                    'corpus_versions',
                    'embedding_profiles',
                    'policy_documents',
                    'policy_chunks',
                    'chunk_scope_access'
                ]
                LOOP
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policy p
                        JOIN pg_class c ON c.oid = p.polrelid
                        JOIN pg_namespace n ON n.oid = c.relnamespace
                        WHERE p.polname = 'rag_v2_service_role_all'
                          AND c.relname = table_name
                          AND n.nspname = 'rag_v2'
                    ) THEN
                        EXECUTE format(
                            'CREATE POLICY rag_v2_service_role_all ON rag_v2.%I
                             FOR ALL TO service_role USING (true) WITH CHECK (true)',
                            table_name
                        );
                    END IF;
                END LOOP;
            END IF;
        END $$;
        """
    )

    op.execute(
        "REVOKE ALL ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer) FROM PUBLIC"
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
                REVOKE ALL ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer) FROM anon;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
                REVOKE ALL ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer) FROM authenticated;
            END IF;
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT EXECUTE ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer) TO service_role;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE table_name text;
        BEGIN
            FOREACH table_name IN ARRAY ARRAY[
                'corpus_versions',
                'embedding_profiles',
                'policy_documents',
                'policy_chunks',
                'chunk_scope_access'
            ]
            LOOP
                EXECUTE format(
                    'DROP POLICY IF EXISTS rag_v2_service_role_all ON rag_v2.%I',
                    table_name
                );
            END LOOP;
        END $$;
        """
    )
    op.execute(
        "REVOKE ALL ON FUNCTION public.match_policy_chunks(extensions.vector, text, integer) FROM PUBLIC"
    )
    for table in reversed(RAG_TABLES):
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
