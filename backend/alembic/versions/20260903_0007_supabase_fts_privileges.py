"""Restrict the canonical FTS RPC to the backend service role.

Supabase can apply direct default ACL grants for API roles when a function is
created.  Revoking only PUBLIC therefore does not guarantee backend-only
execution; this additive migration removes those direct grants explicitly.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260903_0007"
down_revision: str | None = "20260903_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


FUNCTION = "public.match_policy_chunks_fts(text, text, integer)"


def upgrade() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC, anon, authenticated")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
                GRANT EXECUTE ON FUNCTION public.match_policy_chunks_fts(text, text, integer)
                    TO service_role;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {FUNCTION} FROM PUBLIC, anon, authenticated")
