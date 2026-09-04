"""Consistency checks for the documentation-only BANK-RAG V1 closure."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2

ROOT = Path(__file__).resolve().parents[2]
SUMMARY_PATH = ROOT / "dataset/evaluation/results/bank-rag-v1-baseline-summary.json"
GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
CORPUS_MANIFEST_PATH = ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
EMBEDDING_MANIFEST_PATH = ROOT / "dataset/embeddings/v2/embedding-manifest.json"
EMBEDDING_ARTIFACT_PATH = ROOT / "dataset/embeddings/v2/embeddings.parquet"
RERANKER_PATH = Path(r"D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf")
GENERATOR_PATH = Path(r"D:\llm-models\Qwen_Qwen3.5-4B-Q4_K_S.gguf")

GOLD_SHA256 = "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
CORPUS_MANIFEST_SHA256 = "b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a"
EMBEDDING_ARTIFACT_SHA256 = "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c"
EMBEDDING_MANIFEST_SHA256 = "cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863"
RERANKER_SHA256 = "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
GENERATOR_SHA256 = "3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def test_v1_summary_has_frozen_status_and_metric_totals() -> None:
    summary = json.loads(SUMMARY_PATH.read_text(encoding="utf-8"))
    assert summary["version"] == "v1"
    assert summary["status"] == "BASELINE_COMPLETE"
    assert summary["gold"]["records"] == 100
    assert summary["retrieval"]["hit_at_5"] == 0.97
    assert summary["retrieval"]["recall_at_5"] == 0.97
    assert summary["human_review"]["clean_answers"] == 72
    assert sum(summary["human_review"]["correctness"].values()) == 100
    assert sum(summary["human_review"]["groundedness"].values()) == 100
    assert sum(summary["human_review"]["citation"].values()) == 100
    assert sum(summary["human_review"]["abstention"].values()) == 100
    assert sum(summary["human_review"]["failure_source"].values()) == 100
    assert summary["human_review"]["authoritative"] is True
    assert summary["human_review"]["semantic_judge"] == "human"


def test_frozen_gold_and_model_identities_match_closure() -> None:
    assert _sha256(GOLD_PATH) == GOLD_SHA256
    assert _sha256(CORPUS_MANIFEST_PATH) == CORPUS_MANIFEST_SHA256
    assert _sha256(EMBEDDING_ARTIFACT_PATH) == EMBEDDING_ARTIFACT_SHA256
    assert _sha256(EMBEDDING_MANIFEST_PATH) == EMBEDDING_MANIFEST_SHA256
    assert _sha256(RERANKER_PATH) == RERANKER_SHA256
    assert _sha256(GENERATOR_PATH) == GENERATOR_SHA256


def test_frozen_gold_is_100_reviewed_and_corpus_is_1610_chunks() -> None:
    corpus = FrozenCorpusV2()
    records = CanonicalGoldValidator(corpus).parse_file(GOLD_PATH)
    assert len(records) == 100
    assert all(record["status"] == "REVIEWED" for record in records)
    assert len(corpus.rows) == len(corpus.by_id) == 1610
    assert all(record["specialist_scope"] != "BankingOperations" for record in records)


def test_readme_and_closure_doc_state_baseline_completion() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    closure = (ROOT / "docs/BANK-RAG-V1-BASELINE.md").read_text(encoding="utf-8")
    assert "BANK-RAG V1 BASELINE COMPLETE" in readme
    assert "BASELINE COMPLETE" in closure
    assert "97% answer accuracy" not in closure
    assert "not answer\naccuracy" in closure
    assert "72/100" in closure
    assert "V1.1 / POST-V1 OPTIMIZATION" in closure
