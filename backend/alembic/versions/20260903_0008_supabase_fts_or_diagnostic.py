"""Add a backend-only OR lexical diagnostic RPC over the existing FTS index.

The Stage 13A FTS RPC intentionally remains unchanged.  This additive
function accepts a mechanically generated OR ``tsquery`` expression so a
natural-language question does not require every token to match.  It reads
the existing ``search_document`` index and does not alter canonical content,
vectors, visibility, or scope mappings.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260903_0008"
down_revision: str | None = "20260903_0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION = "public.match_policy_chunks_fts_or(text, text, integer)"


def upgrade() -> None:
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.match_policy_chunks_fts_or(
            query_text text, requested_scope text, match_count integer
        )
        RETURNS TABLE(
            canonical_chunk_id text, content text, document_source_id text,
            document_version_id text, document_title text, heading_path jsonb,
            locator jsonb, namespace text, visibility text, metadata jsonb,
            lexical_score real
        )
        LANGUAGE sql
        STABLE
        SECURITY INVOKER
        SET search_path = pg_catalog, rag_v2
        AS $$
            WITH query AS (
                SELECT CASE
                    WHEN pg_catalog.btrim(coalesce(query_text, '')) = ''
                        THEN NULL::tsquery
                    ELSE pg_catalog.to_tsquery(
                        'simple'::regconfig, query_text
                    )
                END AS terms
            )
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
                pg_catalog.ts_rank_cd(c.search_document, query.terms)::real
                    AS lexical_score
            FROM rag_v2.policy_chunks AS c
            JOIN rag_v2.policy_documents AS d ON d.id = c.document_id
            CROSS JOIN query
            WHERE query.terms IS NOT NULL
              AND c.search_document @@ query.terms
              AND (
                  c.visibility = 'SHARED'
                  OR EXISTS (
                      SELECT 1
                      FROM rag_v2.chunk_scope_access AS access
                      WHERE access.policy_chunk_id = c.id
                        AND access.scope = requested_scope
                  )
              )
            ORDER BY lexical_score DESC, c.canonical_chunk_id ASC
            LIMIT LEAST(GREATEST(coalesce(match_count, 10), 1), 100)
        $$;
        """
    )
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC, anon, authenticated")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT EXECUTE ON FUNCTION public.match_policy_chunks_fts_or(text, text, integer)
                    TO service_role;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC, anon, authenticated")
    op.execute(f"DROP FUNCTION IF EXISTS {FUNCTION}")
