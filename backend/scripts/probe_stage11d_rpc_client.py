"""Probe the canonical Supabase RPC client without creating a query vector.

The vector is read from an existing canonical row solely to exercise the
application REST/RPC path when local llama.cpp is unavailable.  This is not a
retrieval-quality measurement and never writes data.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.db.supabase_models import PolicyChunk
from app.services.supabase_v2_retriever import CanonicalV2Retriever


class _StaticCanonicalAdapter:
    def __init__(self, vector: list[float]) -> None:
        self._vector = vector

    def embed_query(self, query: str) -> list[float]:
        return self._vector


def main() -> int:
    settings = get_settings()
    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            row = session.execute(
                select(PolicyChunk.canonical_chunk_id, PolicyChunk.embedding)
                .where(PolicyChunk.is_synthetic.is_(True))
                .order_by(PolicyChunk.canonical_chunk_id)
                .limit(1)
            ).one()
            target_id = row[0]
            vector = list(row[1])

        retriever = CanonicalV2Retriever(
            settings,
            embedding_adapter=_StaticCanonicalAdapter(vector),
        )
        credit = retriever.retrieve("static RPC probe", "credit", k=100)
        collateral = retriever.retrieve("static RPC probe", "collateral_appraisal", k=100)
        report = {
            "rpc_client": "PASS",
            "synthetic_probe": target_id,
            "credit_results": len(credit),
            "collateral_results": len(collateral),
            "credit_contains_probe": any(item.canonical_chunk_id == target_id for item in credit),
            "collateral_contains_probe": any(
                item.canonical_chunk_id == target_id for item in collateral
            ),
            "credit_result_source": credit[0].source_type if credit else None,
            "collateral_result_source": collateral[0].source_type if collateral else None,
        }
        if not report["credit_contains_probe"] or report["collateral_contains_probe"]:
            raise RuntimeError("application RPC client scope isolation failed")
        print(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Stage 11D RPC client probe failed ({type(exc).__name__})", file=sys.stderr)
        raise SystemExit(1)
