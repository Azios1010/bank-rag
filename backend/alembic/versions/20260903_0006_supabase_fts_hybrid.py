"""Add the canonical Corpus V2 PostgreSQL simple-config FTS index and RPC.

This is deliberately additive.  It stores only a derived tsvector over the
existing document title, heading path, and chunk content; canonical content,
vectors, visibility, and scope rows are not changed.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260903_0006"
down_revision: str | None = "20260901_0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FTS_FUNCTION = "rag_v2.refresh_policy_chunk_search_document"
DOCUMENT_FTS_FUNCTION = "rag_v2.refresh_document_chunks_search_document"
CHUNK_TRIGGER = "rag_v2_policy_chunks_search_document_biu"
DOCUMENT_TRIGGER = "rag_v2_policy_documents_search_document_au"
FTS_INDEX = "ix_rag_v2_policy_chunks_search_document_gin"
FTS_RPC = "public.match_policy_chunks_fts"


def upgrade() -> None:
    op.execute(
        "ALTER TABLE rag_v2.policy_chunks "
        "ADD COLUMN search_document tsvector"
    )
    # The lexical representation is deterministic and is derived only from
    # approved canonical fields.  Title gets the strongest weight, followed by
    # heading path and then the chunk content.
    op.execute(
        """
        UPDATE rag_v2.policy_chunks AS c
        SET search_document =
              pg_catalog.setweight(
                  pg_catalog.to_tsvector(
                      'simple'::regconfig, coalesce(d.title, '')
                  ), 'A'
              )
            || pg_catalog.setweight(
                  pg_catalog.to_tsvector(
                      'simple'::regconfig,
                      coalesce(
                          (
                              SELECT pg_catalog.string_agg(item.value, ' ')
                              FROM pg_catalog.jsonb_array_elements_text(
                                  coalesce(c.heading_path, '[]'::jsonb)
                              ) AS item(value)
                          ), ''
                      )
                  ), 'B'
              )
            || pg_catalog.setweight(
                  pg_catalog.to_tsvector(
                      'simple'::regconfig, coalesce(c.content, '')
                  ), 'C'
              )
        FROM rag_v2.policy_documents AS d
        WHERE d.id = c.document_id
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1 FROM rag_v2.policy_chunks
                WHERE search_document IS NULL
            ) THEN
                RAISE EXCEPTION 'canonical FTS derivation left NULL search_document rows';
            END IF;
        END $$;
        """
    )
    op.execute(
        "ALTER TABLE rag_v2.policy_chunks ALTER COLUMN search_document SET NOT NULL"
    )
    op.execute(
        f"CREATE INDEX {FTS_INDEX} ON rag_v2.policy_chunks USING gin (search_document)"
    )

    # Keep the derived index representation correct if a trusted canonical
    # maintenance operation changes source fields in the future.  These
    # triggers never alter canonical content or embeddings.
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FTS_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, rag_v2
        AS $$
        DECLARE
            document_title text;
            heading_text text;
        BEGIN
            SELECT d.title INTO document_title
            FROM rag_v2.policy_documents AS d
            WHERE d.id = NEW.document_id;

            SELECT pg_catalog.string_agg(item.value, ' ')
            INTO heading_text
            FROM pg_catalog.jsonb_array_elements_text(
                coalesce(NEW.heading_path, '[]'::jsonb)
            ) AS item(value);

            NEW.search_document :=
                  pg_catalog.setweight(
                      pg_catalog.to_tsvector(
                          'simple'::regconfig, coalesce(document_title, '')
                      ), 'A'
                  )
                || pg_catalog.setweight(
                      pg_catalog.to_tsvector(
                          'simple'::regconfig, coalesce(heading_text, '')
                      ), 'B'
                  )
                || pg_catalog.setweight(
                      pg_catalog.to_tsvector(
                          'simple'::regconfig, coalesce(NEW.content, '')
                      ), 'C'
                  );
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {CHUNK_TRIGGER}
        BEFORE INSERT OR UPDATE OF content, heading_path, document_id
        ON rag_v2.policy_chunks
        FOR EACH ROW EXECUTE FUNCTION {FTS_FUNCTION}()
        """
    )
    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {DOCUMENT_FTS_FUNCTION}()
        RETURNS trigger
        LANGUAGE plpgsql
        SECURITY INVOKER
        SET search_path = pg_catalog, rag_v2
        AS $$
        BEGIN
            UPDATE rag_v2.policy_chunks AS c
            SET search_document =
                  pg_catalog.setweight(
                      pg_catalog.to_tsvector(
                          'simple'::regconfig, coalesce(NEW.title, '')
                      ), 'A'
                  )
                || pg_catalog.setweight(
                      pg_catalog.to_tsvector(
                          'simple'::regconfig,
                          coalesce(
                              (
                                  SELECT pg_catalog.string_agg(item.value, ' ')
                                  FROM pg_catalog.jsonb_array_elements_text(
                                      coalesce(c.heading_path, '[]'::jsonb)
                                  ) AS item(value)
                              ), ''
                          )
                      ), 'B'
                  )
                || pg_catalog.setweight(
                      pg_catalog.to_tsvector(
                          'simple'::regconfig, coalesce(c.content, '')
                      ), 'C'
                  )
            WHERE c.document_id = NEW.id;
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        f"""
        CREATE TRIGGER {DOCUMENT_TRIGGER}
        AFTER UPDATE OF title ON rag_v2.policy_documents
        FOR EACH ROW EXECUTE FUNCTION {DOCUMENT_FTS_FUNCTION}()
        """
    )

    op.execute(
        f"""
        CREATE OR REPLACE FUNCTION {FTS_RPC}(
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
                SELECT pg_catalog.plainto_tsquery(
                    'simple'::regconfig, coalesce(query_text, '')
                ) AS terms
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
            WHERE query.terms <> pg_catalog.to_tsquery('simple'::regconfig, '')
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
    op.execute(f"REVOKE ALL ON FUNCTION {FTS_RPC}(text, text, integer) FROM PUBLIC")
    op.execute(
        f"""
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT EXECUTE ON FUNCTION {FTS_RPC}(text, text, integer) TO service_role;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {FTS_RPC}(text, text, integer) FROM PUBLIC")
    op.execute(f"DROP FUNCTION IF EXISTS {FTS_RPC}(text, text, integer)")
    op.execute(f"DROP TRIGGER IF EXISTS {DOCUMENT_TRIGGER} ON rag_v2.policy_documents")
    op.execute(f"DROP TRIGGER IF EXISTS {CHUNK_TRIGGER} ON rag_v2.policy_chunks")
    op.execute(f"DROP FUNCTION IF EXISTS {DOCUMENT_FTS_FUNCTION}()")
    op.execute(f"DROP FUNCTION IF EXISTS {FTS_FUNCTION}()")
    op.execute(f"DROP INDEX IF EXISTS rag_v2.{FTS_INDEX}")
    op.execute("ALTER TABLE rag_v2.policy_chunks DROP COLUMN IF EXISTS search_document")
