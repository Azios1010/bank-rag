"""Read-only verification of the frozen Supabase Corpus V2 runtime state."""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import sys

from sqlalchemy import select, text
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db.supabase_models import (
    ChunkScopeAccess,
    CorpusVersion,
    EmbeddingProfile,
    PolicyChunk,
    V2PolicyDocument,
)
from app.services.supabase_corpus_import import (
    load_frozen_bundle,
    validate_database,
    verify_local_snapshot,
)
from app.services.supabase_storage import SupabaseStorageClient


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    settings = get_settings()
    bundle = load_frozen_bundle(ROOT)
    verify_local_snapshot(bundle)

    from sqlalchemy import create_engine

    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        storage = SupabaseStorageClient(settings)
        bucket_results = storage.verify_private_buckets()
        storage_verified = []
        for obj in bundle.objects:
            actual = storage.read_object(obj.bucket, obj.path)
            if actual is None or len(actual) != obj.byte_size or _sha256(actual) != obj.sha256:
                raise RuntimeError(f"Storage identity mismatch at {obj.bucket}/{obj.path}")
            storage_verified.append(f"{obj.bucket}/{obj.path}")

        with Session(engine) as session:
            profile = session.get(EmbeddingProfile, bundle.embedding_profile_id)
            corpus = session.get(CorpusVersion, bundle.corpus_version_id)
            if profile is None or corpus is None:
                raise RuntimeError("canonical embedding profile or corpus version is missing")
            database = validate_database(session, bundle, profile, corpus)

            if profile.model_id != "Qwen3-Embedding-0.6B" or profile.dimension != 1024:
                raise RuntimeError("embedding profile identity mismatch")
            if profile.similarity != "cosine" or not profile.is_unit_normalized:
                raise RuntimeError("embedding profile normalization/similarity mismatch")
            if corpus.manifest_sha256 != _sha256(
                (ROOT / "dataset/manifests/policy-corpus-v2-manifest.json").read_bytes()
            ):
                raise RuntimeError("corpus manifest identity mismatch")
            if corpus.metadata_.get("embedding_artifact_sha256") != next(
                obj.sha256 for obj in bundle.objects if obj.kind == "embedding_parquet"
            ):
                raise RuntimeError("corpus embedding artifact binding mismatch")

            profile_report = {
                "model_id": profile.model_id,
                "dimension": profile.dimension,
                "similarity": profile.similarity,
                "unit_normalized": profile.is_unit_normalized,
            }
            corpus_report = {
                "id": str(corpus.id),
                "name": corpus.corpus_name,
                "version": corpus.version,
                "manifest_sha256": corpus.manifest_sha256,
            }

            documents = session.scalars(select(V2PolicyDocument)).all()
            for document in documents:
                if not document.storage_bucket or not document.storage_path:
                    raise RuntimeError(f"document has no Storage reference: {document.source_id}")
                actual = storage.read_object(document.storage_bucket, document.storage_path)
                if actual is None or _sha256(actual) != document.sha256:
                    raise RuntimeError(f"document Storage reference is dangling: {document.source_id}")

            shared_ids = session.scalars(
                select(PolicyChunk.canonical_chunk_id)
                .where(PolicyChunk.visibility == "SHARED")
                .order_by(PolicyChunk.canonical_chunk_id)
            ).all()
            scoped_ids = session.scalars(
                select(PolicyChunk.canonical_chunk_id)
                .where(PolicyChunk.visibility == "SCOPED")
                .order_by(PolicyChunk.canonical_chunk_id)
            ).all()
            scope_counts = dict(
                sorted(
                    Counter(
                        session.scalars(select(ChunkScopeAccess.scope)).all()
                    ).items()
                )
            )

            repeat_sql = text(
                """
                SELECT canonical_chunk_id
                FROM public.match_policy_chunks(
                    (SELECT embedding FROM rag_v2.policy_chunks
                     WHERE is_synthetic = false
                     ORDER BY canonical_chunk_id LIMIT 1),
                    :scope, :match_count
                )
                """
            )
            first_order = session.execute(
                repeat_sql, {"scope": "collateral_appraisal", "match_count": 5}
            ).scalars().all()
            second_order = session.execute(
                repeat_sql, {"scope": "collateral_appraisal", "match_count": 5}
            ).scalars().all()
            if first_order != second_order:
                raise RuntimeError("RPC result ordering is not deterministic")

            scope_sql = text(
                """
                SELECT canonical_chunk_id
                FROM public.match_policy_chunks(
                    (SELECT embedding FROM rag_v2.policy_chunks
                     WHERE is_synthetic = true
                     ORDER BY canonical_chunk_id LIMIT 1),
                    :scope, 100
                )
                """
            )
            credit_results = session.execute(scope_sql, {"scope": "credit"}).scalars().all()
            collateral_results = session.execute(
                scope_sql, {"scope": "collateral_appraisal"}
            ).scalars().all()
            synthetic_probe = scoped_ids[0]
            if synthetic_probe not in credit_results or synthetic_probe in collateral_results:
                raise RuntimeError("real scoped-policy leakage test failed")

            regulation_probe = shared_ids[0]
            shared_results = session.execute(
                text(
                    """
                    SELECT canonical_chunk_id
                    FROM public.match_policy_chunks(
                        (SELECT embedding FROM rag_v2.policy_chunks
                         WHERE canonical_chunk_id = :chunk_id),
                        'collateral_appraisal', 1
                    )
                    """
                ),
                {"chunk_id": regulation_probe},
            ).scalars().all()
            if not shared_results or shared_results[0] != regulation_probe:
                raise RuntimeError("SHARED regulation was not available to collateral_appraisal")

            function_order = session.scalar(
                text(
                    """
                    SELECT pg_get_functiondef(p.oid)
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proname = 'match_policy_chunks'
                      AND p.pronargs = 3
                    LIMIT 1
                    """
                )
            )
            if (
                not isinstance(function_order, str)
                or "ORDER BY c.embedding" not in function_order
                or "c.canonical_chunk_id" not in function_order
            ):
                raise RuntimeError("RPC deterministic tie ordering definition is missing")

            rls = session.execute(
                text(
                    """
                    SELECT c.relname, c.relrowsecurity
                    FROM pg_class c
                    JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = 'rag_v2'
                      AND c.relname IN ('corpus_versions', 'embedding_profiles',
                        'policy_documents', 'policy_chunks', 'chunk_scope_access')
                    ORDER BY c.relname
                    """
                )
            ).all()
            if not rls or not all(value for _, value in rls):
                raise RuntimeError("RLS is not enabled on every rag_v2 table")

            rpc_security = session.execute(
                text(
                    """
                    SELECT p.prosecdef, p.proconfig,
                        has_function_privilege(
                            'anon',
                            'public.match_policy_chunks(extensions.vector,text,integer)',
                            'EXECUTE'
                        ) AS anon_execute,
                        has_function_privilege(
                            'authenticated',
                            'public.match_policy_chunks(extensions.vector,text,integer)',
                            'EXECUTE'
                        ) AS authenticated_execute
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public'
                      AND p.proname = 'match_policy_chunks'
                      AND p.pronargs = 3
                    LIMIT 1
                    """
                )
            ).one()
            if (
                rpc_security[0]
                or "search_path=pg_catalog, rag_v2" not in (rpc_security[1] or [])
                or rpc_security[2]
                or rpc_security[3]
            ):
                raise RuntimeError("RPC security or client privileges drifted")

            session.rollback()
            anon_write_denied = False
            session.execute(text("SET LOCAL ROLE anon"))
            try:
                session.execute(
                    text(
                        """
                        INSERT INTO rag_v2.corpus_versions
                            (id, corpus_name, version, metadata)
                        VALUES ('00000000-0000-0000-0000-000000000011',
                            'stage11d-security-probe', 'probe', '{}'::jsonb)
                        """
                    )
                )
            except Exception:  # noqa: BLE001
                anon_write_denied = True
            finally:
                session.rollback()
            if not anon_write_denied:
                raise RuntimeError("anon mutation was not denied")

        print(
            json.dumps(
                {
                    "database": database,
                    "profile": profile_report,
                    "corpus": corpus_report,
                    "scope_counts": scope_counts,
                    "rpc_repeat_ordering": "PASS",
                    "scoped_leakage": "PASS",
                    "shared_collateral_access": "PASS",
                    "rls": "PASS",
                    "rpc_security": "PASS",
                    "anon_writes": "DENIED",
                    "private_buckets": [item.name for item in bucket_results],
                    "storage_objects_verified": len(storage_verified),
                    "document_storage_references": len(documents),
                    "vector_finite_nonzero_check": (
                        database["dimension_failures"] == 0
                        and database["zero_vectors"] == 0
                        and database["nonfinite_vectors"] == 0
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
                indent=2,
            )
        )
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Stage 11D remote verification failed ({type(exc).__name__})", file=sys.stderr)
        raise SystemExit(1)
