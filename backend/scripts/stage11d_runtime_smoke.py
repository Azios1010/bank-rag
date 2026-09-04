"""Run non-benchmark live checks for the frozen Corpus V2 retrieval runtime.

This script writes no output files and never substitutes another embedding
backend.  If llama.cpp is unavailable, it reports the required blocked state
and exits successfully so the non-live Stage 11D checks can still be used.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings
from app.eval.llama_v2_query_embedding import (
    LlamaEmbeddingResponseError,
    LlamaV2QueryEmbeddingAdapter,
)
from app.services.supabase_v2_retriever import (
    CanonicalV2Retriever,
    SupabaseV2RetrievalError,
)


CASES = (
    ("credit_regulation", "credit", "Doanh nghiệp cần đáp ứng điều kiện gì để được cấp tín dụng?"),
    ("risk_regulation", "risk_management", "Ngân hàng phải kiểm soát giới hạn rủi ro tín dụng như thế nào?"),
    ("legal_regulation", "legal_compliance", "Những yêu cầu pháp lý nào cần kiểm tra trước khi cấp tín dụng?"),
    ("credit_synthetic", "credit", "Chính sách nội bộ quy định ngưỡng phê duyệt tín dụng doanh nghiệp ra sao?"),
    ("customer_relationship", "customer_relationship", "Hồ sơ và thông tin nào cần thu thập khi tiếp nhận khách hàng doanh nghiệp?"),
    ("collateral_shared_regulation", "collateral_appraisal", "Quy định pháp luật nào áp dụng cho tài sản bảo đảm và định giá?"),
)


def main() -> int:
    settings = get_settings()
    adapter = LlamaV2QueryEmbeddingAdapter(settings.llama_embedding_base_url)
    probe = CASES[0][2]
    try:
        first = adapter.embed_query(probe)
        second = adapter.embed_query(probe)
    except LlamaEmbeddingResponseError:
        print("LIVE_QUERY_SMOKE: BLOCKED BY LOCAL INFERENCE")
        return 0

    max_abs_diff = max(abs(left - right) for left, right in zip(first, second, strict=True))
    norm = math.sqrt(math.fsum(value * value for value in first))
    print(
        json.dumps(
            {
                "live_query_smoke": "PASS",
                "endpoint": adapter.endpoint,
                "dimension": len(first),
                "finite": all(math.isfinite(value) for value in first),
                "non_zero": any(value != 0.0 for value in first),
                "norm": norm,
                "repeat_max_abs_diff": max_abs_diff,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if max_abs_diff > 1e-7:
        print("LIVE_QUERY_SMOKE: FAIL material query-vector nondeterminism")
        return 1

    retriever = CanonicalV2Retriever(settings, embedding_adapter=adapter)
    for case_name, scope, query in CASES:
        try:
            results = retriever.retrieve(query, scope, k=5)
        except SupabaseV2RetrievalError as exc:
            print(f"END_TO_END_SMOKE: FAIL {case_name}: {exc}")
            return 1
        print(
            json.dumps(
                {
                    "case": case_name,
                    "scope": scope,
                    "top_canonical_ids": [item.canonical_chunk_id for item in results],
                    "top_source_types": [item.source_type for item in results],
                    "top_visibility": [item.visibility for item in results],
                    "scope_contract_satisfied": all(
                        item.visibility in {"SHARED", "SCOPED"} for item in results
                    ),
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
    print("END_TO_END_SMOKE: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
