"""Offline tests for Stage 13C1 candidate-generation alternatives."""

from __future__ import annotations

from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.supabase_fts_retriever import (  # noqa: E402
    build_or_tsquery,
    normalize_fts_tokens,
)
from scripts.run_stage13c1_candidate_generation import (  # noqa: E402
    TARGET_GOLD_ID,
    _coverage,
    _gold_ranks,
    build_candidate_union,
)


def test_or_query_is_fixed_token_or_without_stemming_or_accent_removal() -> None:
    query = "Đất, đất; tài sản gắn liền với đất?"
    assert normalize_fts_tokens(query) == ["đất", "tài", "sản", "gắn", "liền", "với"]
    assert build_or_tsquery(query) == "đất | tài | sản | gắn | liền | với"


def test_empty_or_query_is_rejected() -> None:
    with pytest.raises(ValueError, match="lexical tokens"):
        build_or_tsquery("!!!")


def test_duplicate_tokens_are_removed_stably() -> None:
    assert normalize_fts_tokens("tín dụng tín DỤNG") == ["tín", "dụng"]


def test_candidate_coverage_supports_multigold_and_union() -> None:
    ids = ["other", TARGET_GOLD_ID, "second-gold"]
    assert _coverage(ids, [TARGET_GOLD_ID, "second-gold"], "union")["hit"] == 1
    assert _coverage(ids[:2], [TARGET_GOLD_ID, "second-gold"], "2")["recall"] == 0.5


def test_candidate_union_preserves_all_vector_ids_and_deduplicates() -> None:
    result = build_candidate_union(["v1", "v2"], ["v2", "l1", "l1"])
    assert result == ["v1", "v2", "l1"]
    assert set(["v1", "v2"]).issubset(result)


def test_absent_rank_is_explicit_depth_marker() -> None:
    assert _gold_ranks(["other"], [TARGET_GOLD_ID], ">20") == {TARGET_GOLD_ID: ">20"}
