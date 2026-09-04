"""Run the frozen Stage 12B Corpus V2 vector-only pilot baseline.

This runner deliberately uses only the canonical V2 runtime:

    reviewed gold -> LlamaV2QueryEmbeddingAdapter -> CanonicalV2Retriever
    -> Supabase public.match_policy_chunks

It does not import the historical R01 runner, legacy retrieval models, or an
alternate embedding implementation.  The two sequential runs are retained so
that ranking repeatability can be checked without changing the frozen gold or
retrieval parameters.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys
import time
from typing import Any, Iterable


BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import (  # noqa: E402
    LlamaV2QueryEmbeddingAdapter,
)
from app.eval.metrics import (  # noqa: E402
    binary_ndcg_at_k,
    hit_at_k,
    mrr_at_k,
    percentile,
    recall_at_k,
)
from app.services.supabase_v2_retriever import (  # noqa: E402
    CanonicalV2RetrievalResult,
    CanonicalV2Retriever,
    normalize_specialist_scope,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
SUMMARY_PATH = RESULTS_DIR / "vector-v2-pilot-summary.json"
TRACE_PATH = RESULTS_DIR / "vector-v2-pilot-traces.jsonl"
RUN1_TRACE_PATH = RESULTS_DIR / "vector-v2-pilot-run-1-traces.jsonl"
RUN2_TRACE_PATH = RESULTS_DIR / "vector-v2-pilot-run-2-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-12B-VECTOR-BASELINE.md"

EXPECTED_GOLD_SHA256 = (
    "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
)
EXPECTED_CORPUS_MANIFEST_SHA256 = (
    "b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a"
)
EXPECTED_EMBEDDING_ARTIFACT_SHA256 = (
    "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c"
)
EXPECTED_EMBEDDING_MANIFEST_SHA256 = (
    "cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863"
)
K_VALUES = (1, 3, 5)
MAX_K = 5
EXPECTED_QUERY_COUNT = 25
METRIC_NAMES = tuple(
    f"{metric}@{k}"
    for metric in ("hit", "recall", "mrr", "ndcg")
    for k in K_VALUES
)
SUPPORTED_SCOPE_NAMES = (
    "credit",
    "risk_management",
    "legal_compliance",
    "customer_relationship",
    "collateral_appraisal",
)


class Stage12BBaselineError(RuntimeError):
    """Raised when the frozen baseline contract cannot be satisfied."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _without_sha(value: str) -> str:
    return value.removeprefix("sha256:")


def _scope_slug(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).casefold()


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def score_results(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, float | int]:
    """Apply the existing R02 metric definitions to one ranked result list."""

    gold_set = set(gold_ids)
    scores: dict[str, float | int] = {}
    for k in K_VALUES:
        scores[f"hit@{k}"] = hit_at_k(retrieved_ids, gold_set, k)
        scores[f"recall@{k}"] = recall_at_k(retrieved_ids, gold_set, k)
        scores[f"mrr@{k}"] = mrr_at_k(retrieved_ids, gold_set, k)
        scores[f"ndcg@{k}"] = binary_ndcg_at_k(retrieved_ids, gold_set, k)
    return scores


def validate_gold_identity(corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    """Validate the released gold and all frozen local identity bindings."""

    if not GOLD_PATH.exists():
        raise Stage12BBaselineError(f"released gold is missing: {GOLD_PATH}")
    actual_gold_sha = sha256_file(GOLD_PATH)
    if actual_gold_sha != EXPECTED_GOLD_SHA256:
        raise Stage12BBaselineError(
            f"released gold SHA-256 mismatch: {actual_gold_sha} != {EXPECTED_GOLD_SHA256}"
        )

    records = CanonicalGoldValidator(corpus).parse_file(GOLD_PATH)
    if len(records) != EXPECTED_QUERY_COUNT:
        raise Stage12BBaselineError(
            f"released gold contains {len(records)} records, expected {EXPECTED_QUERY_COUNT}"
        )
    if any(record["status"] != "REVIEWED" for record in records):
        raise Stage12BBaselineError("released gold contains a non-REVIEWED record")
    if len({record["evaluation_id"] for record in records}) != EXPECTED_QUERY_COUNT:
        raise Stage12BBaselineError("released gold contains duplicate query IDs")
    if len({record["query"] for record in records}) != EXPECTED_QUERY_COUNT:
        raise Stage12BBaselineError("released gold contains duplicate questions")
    for record in records:
        try:
            normalize_specialist_scope(record["specialist_scope"])
        except ValueError as exc:
            raise Stage12BBaselineError(str(exc)) from exc
        for chunk_id in record["expected_canonical_chunk_ids"]:
            if chunk_id not in corpus.by_id:
                raise Stage12BBaselineError(
                    f"gold ID is not in frozen Corpus V2: {chunk_id}"
                )

    multi_gold = next(
        record for record in records if record["evaluation_id"] == "stage12a-004"
    )
    expected_multi_gold = [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]
    if multi_gold["expected_canonical_chunk_ids"] != expected_multi_gold:
        raise Stage12BBaselineError(
            "stage12a-004 no longer contains its approved two-chunk gold set"
        )

    corpus_manifest_path = ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
    embedding_artifact_path = ROOT / "dataset/embeddings/v2/embeddings.parquet"
    embedding_manifest_path = ROOT / "dataset/embeddings/v2/embedding-manifest.json"
    if sha256_file(corpus_manifest_path) != EXPECTED_CORPUS_MANIFEST_SHA256:
        raise Stage12BBaselineError("Corpus V2 manifest SHA-256 changed")
    if sha256_file(embedding_artifact_path) != EXPECTED_EMBEDDING_ARTIFACT_SHA256:
        raise Stage12BBaselineError("frozen embedding artifact SHA-256 changed")
    if sha256_file(embedding_manifest_path) != EXPECTED_EMBEDDING_MANIFEST_SHA256:
        raise Stage12BBaselineError("frozen embedding manifest SHA-256 changed")

    if len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise Stage12BBaselineError("local frozen Corpus V2 is not exactly 1610 unique chunks")
    shared_count = sum(
        not corpus.sources[row["source_id"]]["synthetic"] for row in corpus.rows
    )
    scoped_count = sum(
        corpus.sources[row["source_id"]]["synthetic"] for row in corpus.rows
    )
    if (shared_count, scoped_count) != (1573, 37):
        raise Stage12BBaselineError(
            f"local Corpus V2 visibility counts are {shared_count}/{scoped_count}, expected 1573/37"
        )
    identity = corpus.embedding_identity
    if (
        identity["model"] != "Qwen3-Embedding-0.6B"
        or identity["dimension"] != 1024
        or identity["runtime"] != "llama.cpp"
        or identity["backend"] != "Vulkan"
        or _without_sha(identity["embedding_artifact_sha256"])
        != EXPECTED_EMBEDDING_ARTIFACT_SHA256
        or _without_sha(identity["embedding_manifest_sha256"])
        != EXPECTED_EMBEDDING_MANIFEST_SHA256
    ):
        raise Stage12BBaselineError("local frozen embedding identity does not match Stage 10")
    return records


def validate_result_contract(
    result: CanonicalV2RetrievalResult,
    corpus: FrozenCorpusV2,
    requested_scope: str,
) -> None:
    """Prove a returned citation belongs to frozen V2 and its scope contract."""

    if result.canonical_chunk_id not in corpus.by_id:
        raise Stage12BBaselineError(
            f"retriever returned a non-V2 canonical ID: {result.canonical_chunk_id}"
        )
    if not math.isfinite(result.similarity):
        raise Stage12BBaselineError("retriever returned a non-finite similarity")
    row = corpus.by_id[result.canonical_chunk_id]
    source = corpus.sources[row["source_id"]]
    expected_visibility = "SCOPED" if source["synthetic"] else "SHARED"
    expected_namespace = source["namespace"]
    if result.document_source_id != row["source_id"]:
        raise Stage12BBaselineError("retriever returned a mismatched source identity")
    if result.document_version_id != row["version_id"]:
        raise Stage12BBaselineError("retriever returned a mismatched version identity")
    if result.document_title != source["title"]:
        raise Stage12BBaselineError("retriever returned a mismatched document title")
    if result.namespace != expected_namespace:
        raise Stage12BBaselineError("retriever returned a mismatched namespace")
    if result.visibility != expected_visibility:
        raise Stage12BBaselineError("retriever returned an invalid V2 visibility")
    if result.heading_path != row.get("heading_path", []):
        raise Stage12BBaselineError("retriever returned a mismatched heading path")
    if result.locator.get("article") != row.get("article"):
        raise Stage12BBaselineError("retriever returned a mismatched article locator")
    if result.content != row["content"]:
        raise Stage12BBaselineError("retriever returned content not matching frozen V2")
    if source["synthetic"]:
        allowed_scopes = {_scope_slug(name) for name in source.get("agent_scopes", [])}
        if requested_scope not in allowed_scopes:
            raise Stage12BBaselineError(
                f"SCOPED result {result.canonical_chunk_id} leaked to {requested_scope}"
            )


def result_payload(
    result: CanonicalV2RetrievalResult,
    rank: int,
    corpus: FrozenCorpusV2,
) -> dict[str, Any]:
    source = corpus.sources[result.document_source_id]
    return {
        "canonical_chunk_id": result.canonical_chunk_id,
        "rank": rank,
        "similarity": result.similarity,
        "content": result.content,
        "document_source_id": result.document_source_id,
        "document_version_id": result.document_version_id,
        "document_title": result.document_title,
        "heading_path": result.heading_path,
        "locator": result.locator,
        "namespace": result.namespace,
        "visibility": result.visibility,
        "source_type": "synthetic_internal_policy" if source["synthetic"] else "real_regulation",
        "metadata": result.metadata,
    }


def run_once(
    records: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
    retriever: CanonicalV2Retriever,
    run_number: int,
) -> list[dict[str, Any]]:
    """Execute one strictly sequential 25-query run."""

    traces: list[dict[str, Any]] = []
    for record in records:
        requested_scope = normalize_specialist_scope(record["specialist_scope"])
        started = time.perf_counter()
        results, timing = retriever.retrieve_with_timing(
            record["query"], requested_scope, k=MAX_K
        )
        total_elapsed_ms = (time.perf_counter() - started) * 1000
        if len(results) != MAX_K:
            raise Stage12BBaselineError(
                f"{record['evaluation_id']} returned {len(results)} results, expected {MAX_K}"
            )
        seen_ids: set[str] = set()
        for result in results:
            if result.canonical_chunk_id in seen_ids:
                raise Stage12BBaselineError("duplicate canonical ID in one top-5 result")
            seen_ids.add(result.canonical_chunk_id)
            validate_result_contract(result, corpus, requested_scope)

        retrieved_ids = [result.canonical_chunk_id for result in results]
        gold_ids = list(record["expected_canonical_chunk_ids"])
        gold_set = set(gold_ids)
        rank_by_id = {chunk_id: rank for rank, chunk_id in enumerate(retrieved_ids, start=1)}
        gold_ranks = {
            chunk_id: rank_by_id.get(chunk_id) for chunk_id in gold_ids
        }
        present_ranks = [rank for rank in gold_ranks.values() if rank is not None]
        source = corpus.sources[corpus.by_id[gold_ids[0]]["source_id"]]
        trace = {
            "run": run_number,
            "evaluation_id": record["evaluation_id"],
            "query": record["query"],
            "specialist_scope": requested_scope,
            "gold_canonical_chunk_ids": gold_ids,
            "gold_visibility": record["visibility"],
            "gold_source_type": "synthetic_internal_policy" if source["synthetic"] else "real_regulation",
            "retrieved_results": [
                result_payload(result, rank, corpus)
                for rank, result in enumerate(results, start=1)
            ],
            "retrieved_canonical_chunk_ids": retrieved_ids,
            "gold_ranks": gold_ranks,
            "first_relevant_rank": min(present_ranks) if present_ranks else None,
            "metrics": score_results(retrieved_ids, gold_ids),
            "latency_ms": {
                "embedding": timing.embedding_ms,
                "retrieval": timing.retrieval_ms,
                "total": total_elapsed_ms,
            },
            "scope_contract_satisfied": True,
            "retrieval_source": "supabase_rpc",
            "legacy_tables_used": False,
            "query_embedding_backend": "llama.cpp",
            "v2_only": True,
            "gold_set_size": len(gold_set),
        }
        traces.append(trace)
    return traces


def aggregate_metrics(traces: list[dict[str, Any]]) -> dict[str, float]:
    return {
        name: _mean(float(trace["metrics"][name]) for trace in traces)
        for name in METRIC_NAMES
    }


def latency_summary(traces: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
    return {
        phase: {
            "p50_ms": percentile(
                [float(trace["latency_ms"][phase]) for trace in traces], 50
            ),
            "p95_ms": percentile(
                [float(trace["latency_ms"][phase]) for trace in traces], 95
            ),
        }
        for phase in ("embedding", "retrieval", "total")
    }


def breakdown(
    records: list[dict[str, Any]], traces: list[dict[str, Any]], field: str
) -> dict[str, dict[str, Any]]:
    records_by_id = {record["evaluation_id"]: record for record in records}
    groups: dict[str, list[dict[str, Any]]] = {}
    for trace in traces:
        record = records_by_id[trace["evaluation_id"]]
        if field == "scope":
            key = record["specialist_scope"]
        elif field == "source_type":
            key = "synthetic_scoped" if record["is_synthetic"] else "real_shared"
        else:
            raise ValueError(f"unsupported breakdown field: {field}")
        groups.setdefault(key, []).append(trace)

    result: dict[str, dict[str, Any]] = {}
    for key in sorted(groups):
        subset = groups[key]
        result[key] = {
            "query_count": len(subset),
            "hit@1": _mean(trace["metrics"]["hit@1"] for trace in subset),
            "hit@3": _mean(trace["metrics"]["hit@3"] for trace in subset),
            "hit@5": _mean(trace["metrics"]["hit@5"] for trace in subset),
            "recall@5": _mean(trace["metrics"]["recall@5"] for trace in subset),
            "mrr@5": _mean(trace["metrics"]["mrr@5"] for trace in subset),
            "ndcg@5": _mean(trace["metrics"]["ndcg@5"] for trace in subset),
        }
    return result


def classify_miss(record: dict[str, Any], trace: dict[str, Any], corpus: FrozenCorpusV2) -> str:
    """Assign a descriptive, post-run diagnostic category without changing gold."""

    if record["is_synthetic"]:
        if all(item["source_type"] == "real_regulation" for item in trace["retrieved_results"]):
            return "synthetic-vs-regulation competition"
        return "embedding semantic weakness"
    gold_source_ids = {
        corpus.by_id[chunk_id]["source_id"]
        for chunk_id in record["expected_canonical_chunk_ids"]
    }
    if any(
        item["document_source_id"] in gold_source_ids
        for item in trace["retrieved_results"]
    ):
        return "same document, wrong article"
    if len(record["expected_canonical_chunk_ids"]) > 1:
        return "multi-gold / distributed evidence"
    if record["visibility"] == "SCOPED":
        return "scope/routing issue"
    return "embedding semantic weakness"


def miss_analysis(
    records: list[dict[str, Any]], traces: list[dict[str, Any]], corpus: FrozenCorpusV2
) -> list[dict[str, Any]]:
    records_by_id = {record["evaluation_id"]: record for record in records}
    misses: list[dict[str, Any]] = []
    for trace in traces:
        if trace["metrics"]["hit@5"] != 0:
            continue
        record = records_by_id[trace["evaluation_id"]]
        misses.append(
            {
                "evaluation_id": trace["evaluation_id"],
                "category": classify_miss(record, trace, corpus),
                "scope": trace["specialist_scope"],
                "gold_canonical_chunk_ids": trace["gold_canonical_chunk_ids"],
                "retrieved_top5": trace["retrieved_canonical_chunk_ids"],
                "note": "Descriptive trace inspection only; approved gold was not changed.",
            }
        )
    return misses


def repeatability(run1: list[dict[str, Any]], run2: list[dict[str, Any]]) -> dict[str, Any]:
    if [trace["evaluation_id"] for trace in run1] != [trace["evaluation_id"] for trace in run2]:
        raise Stage12BBaselineError("repeat runs do not contain the same query IDs")
    pair_data: list[dict[str, Any]] = []
    for first, second in zip(run1, run2):
        first_ids = first["retrieved_canonical_chunk_ids"]
        second_ids = second["retrieved_canonical_chunk_ids"]
        first_scores = [item["similarity"] for item in first["retrieved_results"]]
        second_scores = [item["similarity"] for item in second["retrieved_results"]]
        rank_differences = {
            chunk_id: {
                "run_1": first_ids.index(chunk_id) + 1 if chunk_id in first_ids else None,
                "run_2": second_ids.index(chunk_id) + 1 if chunk_id in second_ids else None,
            }
            for chunk_id in sorted(set(first_ids) | set(second_ids))
            if (first_ids.index(chunk_id) + 1 if chunk_id in first_ids else None)
            != (second_ids.index(chunk_id) + 1 if chunk_id in second_ids else None)
        }
        pair_data.append(
            {
                "evaluation_id": first["evaluation_id"],
                "ordered_top5_equal": first_ids == second_ids,
                "top1_equal": first_ids[0] == second_ids[0],
                "top5_set_overlap": len(set(first_ids) & set(second_ids)) / MAX_K,
                "rank_differences": rank_differences,
                "max_score_drift": max(
                    abs(float(left) - float(right))
                    for left, right in zip(first_scores, second_scores)
                ),
            }
        )

    differing = [item for item in pair_data if not item["ordered_top5_equal"]]
    score_drifts = [item["max_score_drift"] for item in pair_data]
    run1_metrics = aggregate_metrics(run1)
    run2_metrics = aggregate_metrics(run2)
    return {
        "metrics_equal": run1_metrics == run2_metrics,
        "ordered_top5_agreement": _mean(item["ordered_top5_equal"] for item in pair_data),
        "top1_agreement": _mean(item["top1_equal"] for item in pair_data),
        "top5_set_agreement": _mean(
            item["top5_set_overlap"] == 1.0 for item in pair_data
        ),
        "top5_set_overlap": {
            "min": min(item["top5_set_overlap"] for item in pair_data),
            "mean": _mean(item["top5_set_overlap"] for item in pair_data),
            "max": max(item["top5_set_overlap"] for item in pair_data),
        },
        "queries_with_rank_differences": [item["evaluation_id"] for item in differing],
        "rank_difference_count": len(differing),
        "max_score_drift": max(score_drifts),
        "mean_max_score_drift": _mean(score_drifts),
        "per_query": pair_data,
    }


def server_details(corpus: FrozenCorpusV2) -> dict[str, Any]:
    manifest = corpus.embedding_manifest
    runtime = manifest.get("runtime", {})
    return {
        "llama_cpp_build": "0.2.0-dev (build 10603, commit c060ca974; Clang 20.1.8, Windows x86_64)",
        "backend": runtime.get("acceleration", "Vulkan"),
        "gpu": runtime.get("gpu", manifest.get("gpu")),
        "model_path_basename": "Qwen3-Embedding-0.6B-f16.gguf",
        "pooling": "last",
        "context_size": manifest.get("context_length", 3072),
        "parallel_slots": 1,
        "batch": None,
        "ubatch": None,
        "threads": None,
        "threads_batch": None,
        "requests": "sequential",
        "np": 1,
    }


def _format_metric_row(values: dict[str, Any], names: tuple[str, ...]) -> str:
    return " | ".join(f"{float(values[name]):.4f}" for name in names)


def write_document(summary: dict[str, Any], misses: list[dict[str, Any]]) -> None:
    metrics = summary["run_1"]["metrics"]
    lines = [
        "# Stage 12B — Canonical Vector-Only Baseline",
        "",
        "Status: **PILOT / EXPLORATORY / DESCRIPTIVE**. This document records the",
        "first frozen vector-only measurement and is not a production SLA or a",
        "statistically conclusive comparison.",
        "",
        "## Frozen contract",
        "",
        f"- Gold: `{summary['gold']['path']}` ({summary['gold']['record_count']} REVIEWED records)",
        f"- Gold SHA-256: `{summary['gold']['sha256']}`",
        f"- Corpus: `{summary['corpus']['name']}` / {summary['corpus']['chunk_count']} chunks",
        f"- Corpus manifest SHA-256: `{summary['corpus']['manifest_sha256']}`",
        f"- Embedding: `{summary['embedding']['model']}`, GGUF F16, 1024D, `{summary['embedding']['runtime']}/{summary['embedding']['backend']}`",
        f"- Embedding artifact SHA-256: `{summary['embedding']['artifact_sha256']}`",
        f"- Embedding manifest SHA-256: `{summary['embedding']['manifest_sha256']}`",
        f"- Query instruction: `{summary['query']['instruction']}`",
        "- Query template: `Instruct: {instruction}\\nQuery: {query}`",
        "- Retriever: `CanonicalV2Retriever -> Supabase public.match_policy_chunks`",
        "- Distance/order: cosine distance ascending, then `canonical_chunk_id` ascending",
        "- K: `1, 3, 5`; no lexical, hybrid, RRF, reranking, expansion, or answer generation",
        "",
        "## Run 1 metrics",
        "",
        "| Metric | @1 | @3 | @5 |",
        "| --- | ---: | ---: | ---: |",
        f"| Hit | {metrics['hit@1']:.4f} | {metrics['hit@3']:.4f} | {metrics['hit@5']:.4f} |",
        f"| Recall | {metrics['recall@1']:.4f} | {metrics['recall@3']:.4f} | {metrics['recall@5']:.4f} |",
        f"| MRR | {metrics['mrr@1']:.4f} | {metrics['mrr@3']:.4f} | {metrics['mrr@5']:.4f} |",
        f"| nDCG | {metrics['ndcg@1']:.4f} | {metrics['ndcg@3']:.4f} | {metrics['ndcg@5']:.4f} |",
        "",
        "## Latency (exploratory)",
        "",
        "| Phase | p50 ms | p95 ms |",
        "| --- | ---: | ---: |",
    ]
    for phase in ("embedding", "retrieval", "total"):
        phase_summary = summary["run_1"]["latency"][phase]
        lines.append(
            f"| {phase} | {phase_summary['p50_ms']:.3f} | {phase_summary['p95_ms']:.3f} |"
        )

    lines.extend(["", "## Scope breakdown", "", "| Scope | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 |", "| --- | ---: | ---: | ---: | ---: | ---: | ---: |"])
    for scope, values in summary["run_1"]["by_scope"].items():
        lines.append(
            f"| {scope} | {values['query_count']} | {values['hit@1']:.4f} | {values['hit@3']:.4f} | {values['hit@5']:.4f} | {values['recall@5']:.4f} | {values['mrr@5']:.4f} |"
        )

    lines.extend([
        "",
        "## Real versus synthetic",
        "",
        "| Set | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 | nDCG@5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ])
    for label, values in summary["run_1"]["by_source_type"].items():
        lines.append(
            f"| {label} | {values['query_count']} | {values['hit@1']:.4f} | {values['hit@3']:.4f} | {values['hit@5']:.4f} | {values['recall@5']:.4f} | {values['mrr@5']:.4f} | {values['ndcg@5']:.4f} |"
        )

    lines.extend(["", "## Miss analysis", ""])
    if not misses:
        lines.append("No Hit@5 misses in Run 1.")
    else:
        for miss in misses:
            lines.append(
                f"- `{miss['evaluation_id']}` — **{miss['category']}**; gold `{', '.join(miss['gold_canonical_chunk_ids'])}`; retrieved `{', '.join(miss['retrieved_top5'])}`."
            )
        lines.append("")
        lines.append("Categories are descriptive trace inspection only; no gold or retrieval result was corrected.")

    repeat = summary["repeatability"]
    lines.extend([
        "",
        "## Repeatability",
        "",
        f"- Run 1 and Run 2 aggregate metrics equal: `{repeat['metrics_equal']}`",
        f"- Ordered top-5 agreement: `{repeat['ordered_top5_agreement']:.4f}`",
        f"- Top-1 agreement: `{repeat['top1_agreement']:.4f}`",
        f"- Exact top-5 set agreement: `{repeat['top5_set_agreement']:.4f}`",
        f"- Queries with rank differences: `{repeat['queries_with_rank_differences']}`",
        f"- Maximum corresponding-rank score drift: `{repeat['max_score_drift']:.9f}`",
        "",
        "## Artifacts",
        "",
        f"- Summary: `{SUMMARY_PATH.relative_to(ROOT).as_posix()}`",
        f"- Run 1 traces: `{RUN1_TRACE_PATH.relative_to(ROOT).as_posix()}`",
        f"- Run 2 traces: `{RUN2_TRACE_PATH.relative_to(ROOT).as_posix()}`",
        f"- Primary traces (Run 1): `{TRACE_PATH.relative_to(ROOT).as_posix()}`",
        "",
        "No gold, Corpus V2, Supabase data, document vectors, or local canonical files were modified. No benchmark optimization was performed.",
        "",
    ])
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def write_jsonl(path: Path, traces: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    corpus = FrozenCorpusV2()
    records = validate_gold_identity(corpus)
    settings = get_settings()
    adapter = LlamaV2QueryEmbeddingAdapter(settings.llama_embedding_base_url)
    expected_template = (
        "Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages "
        "that directly support the answer.\nQuery: {query}"
    )
    if adapter.format_query("{query}") != expected_template:
        raise Stage12BBaselineError("canonical query template does not match the frozen contract")

    # The adapter and retriever are instantiated once. Each run and each query
    # is sequential; no concurrent embedding or RPC requests are made.
    retriever = CanonicalV2Retriever(settings, embedding_adapter=adapter)
    run1 = run_once(records, corpus, retriever, run_number=1)
    run2 = run_once(records, corpus, retriever, run_number=2)
    if len(run1) != EXPECTED_QUERY_COUNT or len(run2) != EXPECTED_QUERY_COUNT:
        raise Stage12BBaselineError("a benchmark run did not produce exactly 25 traces")

    misses = miss_analysis(records, run1, corpus)
    summary = {
        "stage": "12B — Canonical Vector-Only Baseline",
        "status": "PILOT / EXPLORATORY / DESCRIPTIVE",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold": {
            "path": GOLD_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(GOLD_PATH),
            "record_count": len(records),
            "statuses": ["REVIEWED"],
        },
        "corpus": {
            "name": corpus.corpus_identity["corpus_name"],
            "version": corpus.corpus_identity["version"],
            "chunk_count": corpus.corpus_identity["chunk_count"],
            "shared": 1573,
            "scoped": 37,
            "manifest_sha256": _without_sha(corpus.corpus_identity["corpus_manifest_sha256"]),
            "corpus_jsonl_sha256": _without_sha(corpus.corpus_identity["corpus_jsonl_sha256"]),
            "corpus_v2_hash": _without_sha(corpus.corpus_identity["corpus_v2_hash"]),
            "manifest_hash": _without_sha(corpus.corpus_identity["manifest_hash"]),
            "remote_state": {
                "policy_documents": 10,
                "policy_chunks": 1610,
                "distinct_canonical_chunk_id": 1610,
                "vectors": 1610,
                "scope_rows": 125,
                "remote_verification": "PASS",
            },
        },
        "embedding": {
            "model": corpus.embedding_identity["model"],
            "format": corpus.embedding_identity["format"],
            "dimension": corpus.embedding_identity["dimension"],
            "dtype": corpus.embedding_identity["dtype"],
            "runtime": corpus.embedding_identity["runtime"],
            "backend": corpus.embedding_identity["backend"],
            "pooling": corpus.embedding_identity["pooling"],
            "normalization": corpus.embedding_identity["normalization"],
            "artifact_sha256": _without_sha(corpus.embedding_identity["embedding_artifact_sha256"]),
            "manifest_sha256": _without_sha(corpus.embedding_identity["embedding_manifest_sha256"]),
        },
        "query": {
            "backend": "llama.cpp",
            "endpoint": adapter.endpoint,
            "instruction": adapter.QUERY_INSTRUCTION,
            "format": expected_template,
            "utf8": True,
            "fallback_backend": None,
            "sentence_transformer_used": False,
        },
        "retrieval": {
            "backend": "Supabase",
            "rpc": "public.match_policy_chunks",
            "distance": "cosine",
            "tie_ordering": "cosine distance ASC, canonical_chunk_id ASC",
            "k_values": list(K_VALUES),
            "supported_scopes": list(SUPPORTED_SCOPE_NAMES),
            "legacy_tables_used": False,
            "lexical_search_used": False,
            "hybrid_search_used": False,
            "reranker_used": False,
            "query_expansion_used": False,
            "v2_only": True,
        },
        "server": server_details(corpus),
        "run_1": {
            "query_count": len(run1),
            "metrics": aggregate_metrics(run1),
            "latency": latency_summary(run1),
            "by_scope": breakdown(records, run1, "scope"),
            "by_source_type": breakdown(records, run1, "source_type"),
            "miss_analysis": misses,
            "gold_rank_greater_than_one": [
                trace["evaluation_id"]
                for trace in run1
                if any(rank is not None and rank > 1 for rank in trace["gold_ranks"].values())
            ],
        },
        "run_2": {
            "query_count": len(run2),
            "metrics": aggregate_metrics(run2),
            "latency": latency_summary(run2),
            "by_scope": breakdown(records, run2, "scope"),
            "by_source_type": breakdown(records, run2, "source_type"),
        },
        "repeatability": repeatability(run1, run2),
        "constraints": {
            "document_embeddings_regenerated": False,
            "gold_modified": False,
            "supabase_corpus_mutated": False,
            "benchmark_quality_metrics_only": True,
            "model_downloaded": False,
            "local_files_deleted": False,
        },
    }

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(RUN1_TRACE_PATH, run1)
    write_jsonl(RUN2_TRACE_PATH, run2)
    write_jsonl(TRACE_PATH, run1)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_document(summary, misses)

    for trace_path, expected_count in (
        (TRACE_PATH, 25),
        (RUN1_TRACE_PATH, 25),
        (RUN2_TRACE_PATH, 25),
    ):
        trace_count = sum(1 for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip())
        if trace_count != expected_count:
            raise Stage12BBaselineError(f"trace count mismatch at {trace_path}: {trace_count}")
    all_ids = set(corpus.by_id)
    for trace in run1 + run2:
        if not set(trace["retrieved_canonical_chunk_ids"]).issubset(all_ids):
            raise Stage12BBaselineError("output trace contains an ID outside frozen Corpus V2")
        if any(
            not 0.0 <= float(value) <= 1.0
            for value in trace["metrics"].values()
        ):
            raise Stage12BBaselineError("output trace contains a metric outside [0,1]")
        if any(float(value) < 0.0 for value in trace["latency_ms"].values()):
            raise Stage12BBaselineError("output trace contains a negative latency")

    print(
        json.dumps(
            {
                "status": "PASS",
                "summary": str(SUMMARY_PATH.relative_to(ROOT)),
                "traces": str(TRACE_PATH.relative_to(ROOT)),
                "query_count": len(run1),
                "run1_metrics": summary["run_1"]["metrics"],
                "run2_metrics": summary["run_2"]["metrics"],
                "repeatability": {
                    "metrics_equal": summary["repeatability"]["metrics_equal"],
                    "ordered_top5_agreement": summary["repeatability"]["ordered_top5_agreement"],
                    "top1_agreement": summary["repeatability"]["top1_agreement"],
                    "rank_difference_count": summary["repeatability"]["rank_difference_count"],
                    "max_score_drift": summary["repeatability"]["max_score_drift"],
                },
                "miss_count": len(misses),
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: Stage 12B vector baseline failed ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
