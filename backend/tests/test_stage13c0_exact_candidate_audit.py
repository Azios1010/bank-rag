"""Offline contract tests for the Stage 13C0 exact-cosine diagnostic."""

from __future__ import annotations

import math
from pathlib import Path
import sys

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from scripts.run_stage13c0_exact_candidate_audit import (  # noqa: E402
    EXPECTED_EMBEDDING_ARTIFACT_SHA256,
    PARQUET_PATH,
    TARGET_SCOPE,
    _gold_rank,
    _scope_slug,
    eligible_ids,
    exact_cosine,
    exact_ranked,
    load_frozen_vectors,
    sha256_file,
    validate_frozen_inputs,
)


def test_exact_cosine_is_deterministic_and_normalized_vectors_use_dot_product() -> None:
    left = [1.0, 0.0, 0.0]
    right = [1.0, 0.0, 0.0]
    assert exact_cosine(left, right) == 1.0
    assert exact_cosine([0.0, 1.0], [1.0, 0.0]) == 0.0


def test_exact_cosine_rejects_zero_vector() -> None:
    with pytest.raises(Exception, match="zero vector"):
        exact_cosine([0.0, 0.0], [1.0, 0.0])


def test_frozen_parquet_identity_and_vectors() -> None:
    corpus, records, vectors = validate_frozen_inputs()
    assert len(records) == 25
    assert len(corpus.by_id) == 1610
    assert len(vectors) == 1610
    assert sha256_file(PARQUET_PATH) == EXPECTED_EMBEDDING_ARTIFACT_SHA256
    assert all(len(vector) == 1024 for vector in vectors.values())
    assert all(math.isclose(math.sqrt(math.fsum(x * x for x in vector)), 1.0, abs_tol=1e-4) for vector in vectors.values())


def test_collateral_scope_excludes_all_unauthorized_synthetic_chunks() -> None:
    corpus = FrozenCorpusV2()
    eligible = set(eligible_ids(corpus, TARGET_SCOPE))
    synthetic_ids = {
        row["canonical_chunk_id"]
        for row in corpus.rows
        if corpus.sources[row["source_id"]]["synthetic"]
    }
    assert len(eligible) == 1573
    assert not eligible & synthetic_ids


def test_scope_slug_preserves_canonical_specialist_names() -> None:
    assert _scope_slug("CollateralAppraisal") == "collateral_appraisal"
    assert _scope_slug("BankingOperations") == "banking_operations"


def test_exact_rank_uses_canonical_id_tie_break() -> None:
    corpus = FrozenCorpusV2()
    rows = corpus.rows[:2]
    vectors = {row["canonical_chunk_id"]: [1.0] for row in rows}
    # This helper is tested with a minimal fake corpus-like object so the
    # ranking contract is isolated from the 1024D production artifact.
    class Sources:
        synthetic = False
        title = "test"
        agent_scopes: list[str] = []

        def __getitem__(self, key: str):
            return getattr(self, key)

        def get(self, key: str, default=None):
            return getattr(self, key, default)

    class Corpus:
        pass

    fake_corpus = Corpus()
    fake_corpus.by_id = {row["canonical_chunk_id"]: row for row in rows}
    fake_corpus.rows = rows
    fake_corpus.sources = {row["source_id"]: Sources() for row in rows}

    ranked = exact_ranked(fake_corpus, vectors, [1.0], "credit")
    assert [item["canonical_chunk_id"] for item in ranked] == sorted(fake_corpus.by_id)


def test_gold_rank_represents_absent_ids_as_gt20() -> None:
    assert _gold_rank([], ["missing-id"]) == {"missing-id": ">20"}
