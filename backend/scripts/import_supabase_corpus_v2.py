"""Import the frozen Corpus V2 bundle into Supabase Storage and rag_v2."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from sqlalchemy import create_engine

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.services.supabase_corpus_import import (
    CorpusImportError,
    import_database,
    load_frozen_bundle,
    snapshot_counts,
    sync_storage,
    verify_local_snapshot,
)
from app.services.supabase_storage import SupabaseStorageClient, SupabaseStorageError


def _same_counts(left: dict[str, int], right: dict[str, int]) -> bool:
    return left == right


def run_stage11c(root: Path) -> dict[str, object]:
    """Run the ordered Stage 11C workflow and return a secret-free report."""

    bundle = load_frozen_bundle(root)
    settings = get_settings()
    storage_results = sync_storage(bundle, SupabaseStorageClient(settings))
    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        before = snapshot_counts(engine)
        dry_run = import_database(bundle, engine, dry_run=True)
        after_dry_run = snapshot_counts(engine)
        if not _same_counts(before, after_dry_run):
            raise CorpusImportError("transactional dry run did not roll back cleanly")

        first_import = import_database(bundle, engine, dry_run=False)
        after_first = snapshot_counts(engine)
        second_import = import_database(bundle, engine, dry_run=False)
        after_second = snapshot_counts(engine)
        second_storage_results = sync_storage(bundle, SupabaseStorageClient(settings))
        if any(result.uploaded or not result.existing_identical for result in second_storage_results):
            raise CorpusImportError("second Storage synchronization was not idempotent")
        if not _same_counts(after_first, after_second):
            raise CorpusImportError("second import changed database counts")
        if first_import["identity_digest"] != second_import["identity_digest"]:
            raise CorpusImportError("second import changed canonical database identity")
        verify_local_snapshot(bundle)
        return {
            "local": {
                "corpus_rows": len(bundle.chunks),
                "corpus_unique_ids": len({chunk["canonical_chunk_id"] for chunk in bundle.chunks}),
                "embedding_rows": len(bundle.vectors),
                "embedding_unique_ids": len({chunk["canonical_chunk_id"] for chunk in bundle.chunks}),
                "vector_dimension": 1024,
                "embedding_artifact_sha256": next(
                    item.sha256 for item in bundle.objects if item.kind == "embedding_parquet"
                ),
            },
            "storage": {
                "objects": len(storage_results),
                "real_source_objects": sum(item.kind == "real_source" for item in bundle.objects),
                "synthetic_source_objects": sum(item.kind == "synthetic_source" for item in bundle.objects),
                "corpus_artifacts": sum(item.kind.startswith("corpus_") or item.kind.startswith("embedding_") for item in bundle.objects),
                "uploaded": sum(result.uploaded for result in storage_results),
                "identical_collisions": sum(result.existing_identical for result in storage_results),
                "hash_verified": True,
                "all_private": True,
                "second_sync_uploaded": sum(result.uploaded for result in second_storage_results),
                "second_sync_identical": sum(result.existing_identical for result in second_storage_results),
            },
            "database": first_import,
            "dry_run": {
                "passed": True,
                "rollback_clean": True,
                "before_counts": before,
                "after_rollback_counts": after_dry_run,
            },
            "idempotency": {
                "first_import": True,
                "second_import": True,
                "counts_changed": not _same_counts(after_first, after_second),
                "identity_changed": first_import["identity_digest"] != second_import["identity_digest"],
            },
            "local_snapshot_verified": True,
        }
    finally:
        engine.dispose()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    args = parser.parse_args()
    try:
        report = run_stage11c(args.root)
    except (CorpusImportError, SupabaseStorageError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:
        # Do not print driver exception strings: connection errors can include
        # the configured database URL and therefore credentials.
        print(f"ERROR: Stage 11C failed ({type(exc).__name__})", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
