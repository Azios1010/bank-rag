"""Measure the fixed PostgreSQL FTS + vector + RRF Corpus V2 pilot.

The vector arm is the frozen Stage 12B reference.  The lexical arm uses the
original reviewed question text and the additive ``simple`` PostgreSQL FTS
RPC.  The hybrid arm fuses fixed-depth candidate ranks with RRF only; it does
not mix raw vector and lexical scores or apply any learned/reranking stage.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter  # noqa: E402
from app.services.hybrid_v2_retriever import (  # noqa: E402
    CanonicalV2HybridResult,
    CanonicalV2HybridRetriever,
)
from app.services.supabase_fts_retriever import (  # noqa: E402
    CanonicalV2LexicalResult,
    CanonicalV2LexicalRetriever,
)
from app.services.supabase_v2_retriever import (  # noqa: E402
    CanonicalV2RetrievalResult,
    CanonicalV2Retriever,
    normalize_specialist_scope,
)
from scripts.run_stage12b_vector_v2_baseline import (  # noqa: E402
    EXPECTED_GOLD_SHA256,
    EXPECTED_CORPUS_MANIFEST_SHA256,
    EXPECTED_EMBEDDING_ARTIFACT_SHA256,
    EXPECTED_EMBEDDING_MANIFEST_SHA256,
    K_VALUES,
    MAX_K,
    aggregate_metrics as vector_aggregate_metrics,
    breakdown as vector_breakdown,
    percentile,
    score_results,
    sha256_file,
    validate_gold_identity,
    miss_analysis as vector_miss_analysis,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
VECTOR_SUMMARY_PATH = RESULTS_DIR / "vector-v2-pilot-summary.json"
VECTOR_TRACE_PATH = RESULTS_DIR / "vector-v2-pilot-run-1-traces.jsonl"
LEXICAL_SUMMARY_PATH = RESULTS_DIR / "lexical-v2-pilot-summary.json"
LEXICAL_TRACE_PATH = RESULTS_DIR / "lexical-v2-pilot-traces.jsonl"
LEXICAL_RUN1_TRACE_PATH = RESULTS_DIR / "lexical-v2-pilot-run-1-traces.jsonl"
LEXICAL_RUN2_TRACE_PATH = RESULTS_DIR / "lexical-v2-pilot-run-2-traces.jsonl"
HYBRID_SUMMARY_PATH = RESULTS_DIR / "hybrid-rrf-v2-pilot-summary.json"
HYBRID_TRACE_PATH = RESULTS_DIR / "hybrid-rrf-v2-pilot-traces.jsonl"
HYBRID_RUN1_TRACE_PATH = RESULTS_DIR / "hybrid-rrf-v2-pilot-run-1-traces.jsonl"
HYBRID_RUN2_TRACE_PATH = RESULTS_DIR / "hybrid-rrf-v2-pilot-run-2-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-13A-HYBRID-RRF.md"

EXPECTED_QUERY_COUNT = 25
SUPPORTED_SCOPES = (
    "credit",
    "risk_management",
    "legal_compliance",
    "customer_relationship",
    "collateral_appraisal",
)
FTS_CONFIG = "simple"
FTS_FIELDS = ("title", "heading_path", "content")
VECTOR_CANDIDATE_DEPTH = 20
LEXICAL_CANDIDATE_DEPTH = 20
RRF_K = 60


class Stage13AHybridError(RuntimeError):
    """Raised when the frozen hybrid pilot contract cannot be satisfied."""


def _without_sha(value: str) -> str:
    return value.removeprefix("sha256:")


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def _source_type(source: dict[str, Any]) -> str:
    return "synthetic_internal_policy" if source["synthetic"] else "real_regulation"


def _source_group(record: dict[str, Any]) -> str:
    return "synthetic_scoped" if record["is_synthetic"] else "real_shared"


def _record_by_id(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {record["evaluation_id"]: record for record in records}


def _validate_common_result(
    result: object,
    corpus: FrozenCorpusV2,
    requested_scope: str,
    score_field: str,
) -> None:
    chunk_id = getattr(result, "canonical_chunk_id", None)
    if not isinstance(chunk_id, str) or chunk_id not in corpus.by_id:
        raise Stage13AHybridError(f"result contains a non-V2 canonical ID: {chunk_id}")
    score = getattr(result, score_field, None)
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(float(score)):
        raise Stage13AHybridError(f"{score_field} is not finite for {chunk_id}")
    if score_field == "lexical_score" and float(score) < 0:
        raise Stage13AHybridError(f"lexical score is negative for {chunk_id}")

    row = corpus.by_id[chunk_id]
    source = corpus.sources[row["source_id"]]
    expected_visibility = "SCOPED" if source["synthetic"] else "SHARED"
    expected_fields = {
        "document_source_id": row["source_id"],
        "document_version_id": row["version_id"],
        "document_title": source["title"],
        "namespace": source["namespace"],
        "visibility": expected_visibility,
        "heading_path": row.get("heading_path", []),
        "content": row["content"],
    }
    for field, expected in expected_fields.items():
        if getattr(result, field, None) != expected:
            raise Stage13AHybridError(f"result identity mismatch at {field} for {chunk_id}")
    locator = getattr(result, "locator", None)
    if not isinstance(locator, dict) or locator.get("article") != row.get("article"):
        raise Stage13AHybridError(f"result locator mismatch for {chunk_id}")
    metadata = getattr(result, "metadata", None)
    if not isinstance(metadata, dict):
        raise Stage13AHybridError(f"result metadata is invalid for {chunk_id}")
    if source["synthetic"]:
        allowed = {
            _scope_slug(scope_name) for scope_name in source.get("agent_scopes", [])
        }
        if requested_scope not in allowed:
            raise Stage13AHybridError(
                f"SCOPED result {chunk_id} leaked to {requested_scope}"
            )


def _scope_slug(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def _citation_payload(result: object, rank: int, corpus: FrozenCorpusV2) -> dict[str, Any]:
    chunk_id = result.canonical_chunk_id
    source = corpus.sources[corpus.by_id[chunk_id]["source_id"]]
    payload = {
        "canonical_chunk_id": chunk_id,
        "rank": rank,
        "content": result.content,
        "document_source_id": result.document_source_id,
        "document_version_id": result.document_version_id,
        "document_title": result.document_title,
        "heading_path": result.heading_path,
        "locator": result.locator,
        "namespace": result.namespace,
        "visibility": result.visibility,
        "source_type": _source_type(source),
        "metadata": result.metadata,
    }
    if isinstance(result, CanonicalV2RetrievalResult):
        payload["similarity"] = result.similarity
    elif isinstance(result, CanonicalV2LexicalResult):
        payload["lexical_score"] = result.lexical_score
    elif isinstance(result, CanonicalV2HybridResult):
        payload.update(
            {
                "rrf_score": result.rrf_score,
                "vector_rank": result.vector_rank,
                "lexical_rank": result.lexical_rank,
                "vector_similarity": result.vector_similarity,
                "lexical_score": result.lexical_score,
            }
        )
    else:  # pragma: no cover - only canonical result classes are passed
        raise Stage13AHybridError(f"unsupported result type: {type(result).__name__}")
    return payload


def _gold_ranks(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, int | None]:
    by_id = {chunk_id: rank for rank, chunk_id in enumerate(retrieved_ids, start=1)}
    return {chunk_id: by_id.get(chunk_id) for chunk_id in gold_ids}


def _first_relevant(gold_ranks: dict[str, int | None]) -> int | None:
    ranks = [rank for rank in gold_ranks.values() if rank is not None]
    return min(ranks) if ranks else None


def run_lexical_once(
    records: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
    retriever: CanonicalV2LexicalRetriever,
    run_number: int,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for record in records:
        scope = normalize_specialist_scope(record["specialist_scope"])
        started = time.perf_counter()
        candidates, timing = retriever.retrieve_with_timing(
            record["query"], scope, k=LEXICAL_CANDIDATE_DEPTH
        )
        total_ms = (time.perf_counter() - started) * 1000
        for result in candidates:
            _validate_common_result(result, corpus, scope, "lexical_score")
        top_results = candidates[:MAX_K]
        retrieved_ids = [result.canonical_chunk_id for result in top_results]
        gold_ids = list(record["expected_canonical_chunk_ids"])
        ranks = _gold_ranks(retrieved_ids, gold_ids)
        source = corpus.sources[corpus.by_id[gold_ids[0]]["source_id"]]
        traces.append(
            {
                "run": run_number,
                "evaluation_id": record["evaluation_id"],
                "query": record["query"],
                "specialist_scope": scope,
                "gold_canonical_chunk_ids": gold_ids,
                "gold_visibility": record["visibility"],
                "gold_source_type": _source_type(source),
                "candidate_depth": LEXICAL_CANDIDATE_DEPTH,
                "candidate_canonical_chunk_ids": [
                    result.canonical_chunk_id for result in candidates
                ],
                "candidate_results": [
                    _citation_payload(result, rank, corpus)
                    for rank, result in enumerate(candidates, start=1)
                ],
                "retrieved_results": [
                    _citation_payload(result, rank, corpus)
                    for rank, result in enumerate(top_results, start=1)
                ],
                "retrieved_canonical_chunk_ids": retrieved_ids,
                "gold_ranks": ranks,
                "first_relevant_rank": _first_relevant(ranks),
                "metrics": score_results(retrieved_ids, gold_ids),
                "latency_ms": {"fts": timing.retrieval_ms, "total": total_ms},
                "scope_contract_satisfied": True,
                "retrieval_source": "supabase_fts_rpc",
                "rpc": "public.match_policy_chunks_fts",
                "legacy_tables_used": False,
                "query_embedding_backend": None,
                "v2_only": True,
                "gold_set_size": len(set(gold_ids)),
            }
        )
    return traces


def run_hybrid_once(
    records: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
    retriever: CanonicalV2HybridRetriever,
    run_number: int,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for record in records:
        scope = normalize_specialist_scope(record["specialist_scope"])
        results, vector_candidates, lexical_candidates, timing = (
            retriever.retrieve_with_candidates_with_timing(
                record["query"], scope, k=MAX_K
            )
        )
        if len(results) != MAX_K:
            raise Stage13AHybridError(
                f"{record['evaluation_id']} returned {len(results)} hybrid results, expected {MAX_K}"
            )
        for result in vector_candidates:
            _validate_common_result(result, corpus, scope, "similarity")
        for result in lexical_candidates:
            _validate_common_result(result, corpus, scope, "lexical_score")
        for result in results:
            if not math.isfinite(result.rrf_score) or result.rrf_score <= 0:
                raise Stage13AHybridError("hybrid result has an invalid RRF score")
            _validate_common_result(result, corpus, scope, "rrf_score")
        retrieved_ids = [result.canonical_chunk_id for result in results]
        gold_ids = list(record["expected_canonical_chunk_ids"])
        ranks = _gold_ranks(retrieved_ids, gold_ids)
        source = corpus.sources[corpus.by_id[gold_ids[0]]["source_id"]]
        total_ms = timing.total_ms
        traces.append(
            {
                "run": run_number,
                "evaluation_id": record["evaluation_id"],
                "query": record["query"],
                "specialist_scope": scope,
                "gold_canonical_chunk_ids": gold_ids,
                "gold_visibility": record["visibility"],
                "gold_source_type": _source_type(source),
                "vector_candidate_depth": VECTOR_CANDIDATE_DEPTH,
                "lexical_candidate_depth": LEXICAL_CANDIDATE_DEPTH,
                "vector_candidate_canonical_chunk_ids": [
                    result.canonical_chunk_id for result in vector_candidates
                ],
                "lexical_candidate_canonical_chunk_ids": [
                    result.canonical_chunk_id for result in lexical_candidates
                ],
                "vector_candidate_results": [
                    _citation_payload(result, rank, corpus)
                    for rank, result in enumerate(vector_candidates, start=1)
                ],
                "lexical_candidate_results": [
                    _citation_payload(result, rank, corpus)
                    for rank, result in enumerate(lexical_candidates, start=1)
                ],
                "retrieved_results": [
                    _citation_payload(result, rank, corpus)
                    for rank, result in enumerate(results, start=1)
                ],
                "retrieved_canonical_chunk_ids": retrieved_ids,
                "gold_ranks": ranks,
                "first_relevant_rank": _first_relevant(ranks),
                "metrics": score_results(retrieved_ids, gold_ids),
                "latency_ms": {
                    "embedding": timing.vector_embedding_ms,
                    "vector": timing.vector_retrieval_ms,
                    "fts": timing.lexical_ms,
                    "fusion": timing.fusion_ms,
                    "total": total_ms,
                },
                "scope_contract_satisfied": True,
                "retrieval_source": "supabase_vector_rpc_plus_fts_rpc_rrf",
                "vector_rpc": "public.match_policy_chunks",
                "lexical_rpc": "public.match_policy_chunks_fts",
                "legacy_tables_used": False,
                "query_embedding_backend": "llama.cpp",
                "v2_only": True,
                "rrf_k": RRF_K,
                "rrf_formula": "1/(60+vector_rank) + 1/(60+lexical_rank)",
                "gold_set_size": len(set(gold_ids)),
            }
        )
    return traces


def aggregate_metrics(traces: list[dict[str, Any]]) -> dict[str, float]:
    return {
        name: _mean(float(trace["metrics"][name]) for trace in traces)
        for name in (
            f"{metric}@{k}"
            for metric in ("hit", "recall", "mrr", "ndcg")
            for k in K_VALUES
        )
    }


def latency_summary(traces: list[dict[str, Any]], phases: tuple[str, ...]) -> dict[str, dict[str, float]]:
    return {
        phase: {
            "p50_ms": percentile([float(trace["latency_ms"][phase]) for trace in traces], 50),
            "p95_ms": percentile([float(trace["latency_ms"][phase]) for trace in traces], 95),
        }
        for phase in phases
    }


def repeatability(
    run1: list[dict[str, Any]], run2: list[dict[str, Any]], score_field: str
) -> dict[str, Any]:
    if [item["evaluation_id"] for item in run1] != [item["evaluation_id"] for item in run2]:
        raise Stage13AHybridError("repeat runs do not contain the same query IDs")
    pairs: list[dict[str, Any]] = []
    for first, second in zip(run1, run2):
        first_ids = first["retrieved_canonical_chunk_ids"]
        second_ids = second["retrieved_canonical_chunk_ids"]
        first_scores = [item[score_field] for item in first["retrieved_results"]]
        second_scores = [item[score_field] for item in second["retrieved_results"]]
        rank_differences = {
            chunk_id: {
                "run_1": first_ids.index(chunk_id) + 1 if chunk_id in first_ids else None,
                "run_2": second_ids.index(chunk_id) + 1 if chunk_id in second_ids else None,
            }
            for chunk_id in sorted(set(first_ids) | set(second_ids))
            if (first_ids.index(chunk_id) + 1 if chunk_id in first_ids else None)
            != (second_ids.index(chunk_id) + 1 if chunk_id in second_ids else None)
        }
        if not first_ids and not second_ids:
            top5_set_overlap = 1.0
        else:
            top5_set_overlap = len(set(first_ids) & set(second_ids)) / MAX_K
        pairs.append(
            {
                "evaluation_id": first["evaluation_id"],
                "ordered_top5_equal": first_ids == second_ids,
                "top1_equal": first_ids[:1] == second_ids[:1],
                "top5_set_overlap": top5_set_overlap,
                "rank_differences": rank_differences,
                "max_score_drift": max(
                    (abs(float(left) - float(right)) for left, right in zip(first_scores, second_scores)),
                    default=0.0,
                ),
            }
        )
    metrics1 = aggregate_metrics(run1)
    metrics2 = aggregate_metrics(run2)
    return {
        "metrics_equal": metrics1 == metrics2,
        "ordered_top5_agreement": _mean(item["ordered_top5_equal"] for item in pairs),
        "top1_agreement": _mean(item["top1_equal"] for item in pairs),
        "top5_set_agreement": _mean(item["top5_set_overlap"] == 1.0 for item in pairs),
        "top5_set_overlap": {
            "min": min(item["top5_set_overlap"] for item in pairs),
            "mean": _mean(item["top5_set_overlap"] for item in pairs),
            "max": max(item["top5_set_overlap"] for item in pairs),
        },
        "queries_with_rank_differences": [
            item["evaluation_id"] for item in pairs if item["rank_differences"]
        ],
        "rank_difference_count": sum(bool(item["rank_differences"]) for item in pairs),
        "max_score_drift": max((item["max_score_drift"] for item in pairs), default=0.0),
        "mean_max_score_drift": _mean(item["max_score_drift"] for item in pairs),
        "per_query": pairs,
    }


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _frozen_vector_reference(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> dict[str, Any]:
    if not VECTOR_SUMMARY_PATH.is_file() or not VECTOR_TRACE_PATH.is_file():
        raise Stage13AHybridError("frozen Stage 12B vector artifacts are missing")
    summary = json.loads(VECTOR_SUMMARY_PATH.read_text(encoding="utf-8"))
    if summary.get("gold", {}).get("sha256") != EXPECTED_GOLD_SHA256:
        raise Stage13AHybridError("Stage 12B summary is not bound to the frozen gold SHA")
    traces = _load_jsonl(VECTOR_TRACE_PATH)
    if len(traces) != EXPECTED_QUERY_COUNT:
        raise Stage13AHybridError("Stage 12B vector reference does not contain 25 traces")
    if [item["evaluation_id"] for item in traces] != [item["evaluation_id"] for item in records]:
        raise Stage13AHybridError("Stage 12B vector reference IDs differ from frozen gold")
    all_ids = set(corpus.by_id)
    for trace in traces:
        if not set(trace["retrieved_canonical_chunk_ids"]).issubset(all_ids):
            raise Stage13AHybridError("Stage 12B reference contains a non-V2 result")
    return {"summary": summary, "traces": traces}


def verify_remote_state(settings: Any, corpus: FrozenCorpusV2) -> dict[str, Any]:
    """Read-only remote canonical and additive FTS verification."""

    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            counts = connection.execute(
                text(
                    """
                    SELECT
                        (SELECT count(*) FROM rag_v2.policy_documents) AS documents,
                        (SELECT count(*) FROM rag_v2.policy_chunks) AS chunks,
                        (SELECT count(DISTINCT canonical_chunk_id) FROM rag_v2.policy_chunks) AS distinct_ids,
                        (SELECT count(*) FROM rag_v2.policy_chunks WHERE embedding IS NOT NULL) AS vectors,
                        (SELECT count(*) FROM rag_v2.policy_chunks WHERE visibility = 'SHARED') AS shared,
                        (SELECT count(*) FROM rag_v2.policy_chunks WHERE visibility = 'SCOPED') AS scoped,
                        (SELECT count(*) FROM rag_v2.chunk_scope_access) AS scope_rows,
                        (SELECT count(*) FROM rag_v2.chunk_scope_access WHERE scope = 'BankingOperations') AS banking_scope_rows,
                        (SELECT count(*) FROM rag_v2.policy_chunks c LEFT JOIN rag_v2.policy_documents d ON d.id = c.document_id WHERE d.id IS NULL) AS orphan_chunks,
                        (SELECT count(*) FROM rag_v2.chunk_scope_access a LEFT JOIN rag_v2.policy_chunks c ON c.id = a.policy_chunk_id WHERE c.id IS NULL) AS orphan_scope_rows,
                        (SELECT count(*) - count(DISTINCT canonical_chunk_id) FROM rag_v2.policy_chunks) AS duplicate_ids,
                        (SELECT count(*) FROM rag_v2.policy_chunks WHERE embedding IS NULL OR vector_dims(embedding) <> 1024) AS vector_failures
                    """
                )
            ).mappings().one()
            scope_counts = dict(
                connection.execute(
                    text(
                        "SELECT scope, count(*) AS count FROM rag_v2.chunk_scope_access GROUP BY scope ORDER BY scope"
                    )
                ).all()
            )
            scope_counts = {
                scope: int(scope_counts.get(scope, 0)) for scope in SUPPORTED_SCOPES
            }
            identity = connection.execute(
                text(
                    """
                    SELECT
                        p.model_id, p.dimension, p.similarity, p.is_unit_normalized,
                        p.metadata AS profile_metadata,
                        c.corpus_name, c.version, c.manifest_sha256,
                        c.metadata AS corpus_metadata
                    FROM rag_v2.embedding_profiles p
                    CROSS JOIN rag_v2.corpus_versions c
                    """
                )
            ).mappings().all()
            if len(identity) != 1:
                raise Stage13AHybridError("remote canonical identity rows are not exactly one profile/version")
            row = identity[0]
            if (
                counts["documents"] != 10
                or counts["chunks"] != 1610
                or counts["distinct_ids"] != 1610
                or counts["vectors"] != 1610
                or counts["shared"] != 1573
                or counts["scoped"] != 37
                or counts["scope_rows"] != 125
                or counts["banking_scope_rows"] != 0
                or counts["orphan_chunks"] != 0
                or counts["orphan_scope_rows"] != 0
                or counts["duplicate_ids"] != 0
                or counts["vector_failures"] != 0
            ):
                raise Stage13AHybridError(f"remote canonical counts failed: {dict(counts)}")
            if scope_counts != {
                "collateral_appraisal": 0,
                "credit": 37,
                "customer_relationship": 14,
                "legal_compliance": 37,
                "risk_management": 37,
            }:
                raise Stage13AHybridError(f"remote scope distribution failed: {scope_counts}")
            if (
                row["model_id"] != "Qwen3-Embedding-0.6B"
                or row["dimension"] != 1024
                or row["similarity"] != "cosine"
                or not row["is_unit_normalized"]
                or row["corpus_name"] != "policy-corpus-v2"
                or row["manifest_sha256"] != EXPECTED_CORPUS_MANIFEST_SHA256
            ):
                raise Stage13AHybridError("remote corpus or embedding profile identity failed")
            profile_metadata = row["profile_metadata"]
            corpus_metadata = row["corpus_metadata"]
            if (
                profile_metadata.get("profile_identity", {}).get("embedding_artifact_sha256")
                != EXPECTED_EMBEDDING_ARTIFACT_SHA256
                or profile_metadata.get("profile_identity", {}).get("embedding_manifest_artifact_sha256")
                != EXPECTED_EMBEDDING_MANIFEST_SHA256
                or corpus_metadata.get("embedding_artifact_sha256")
                != EXPECTED_EMBEDDING_ARTIFACT_SHA256
                or corpus_metadata.get("embedding_manifest_artifact_sha256")
                != EXPECTED_EMBEDDING_MANIFEST_SHA256
                or corpus_metadata.get("chunk_counts", {}).get("total") != 1610
            ):
                raise Stage13AHybridError("remote artifact identity binding failed")

            fts_index = connection.execute(
                text(
                    """
                    SELECT indexname, indexdef
                    FROM pg_indexes
                    WHERE schemaname = 'rag_v2'
                      AND indexname = 'ix_rag_v2_policy_chunks_search_document_gin'
                    """
                )
            ).mappings().all()
            indexed_rows = connection.scalar(
                text(
                    "SELECT count(*) FROM rag_v2.policy_chunks WHERE search_document IS NOT NULL"
                )
            )
            fts_security = connection.execute(
                text(
                    """
                    SELECT p.prosecdef, p.proconfig,
                        has_function_privilege('anon', 'public.match_policy_chunks_fts(text,text,integer)', 'EXECUTE') AS anon_execute,
                        has_function_privilege('authenticated', 'public.match_policy_chunks_fts(text,text,integer)', 'EXECUTE') AS authenticated_execute,
                        has_function_privilege('service_role', 'public.match_policy_chunks_fts(text,text,integer)', 'EXECUTE') AS service_execute
                    FROM pg_proc p
                    JOIN pg_namespace n ON n.oid = p.pronamespace
                    WHERE n.nspname = 'public' AND p.proname = 'match_policy_chunks_fts' AND p.pronargs = 3
                    """
                )
            ).mappings().all()
            if len(fts_index) != 1 or indexed_rows != 1610 or len(fts_security) != 1:
                raise Stage13AHybridError("additive FTS index or RPC is not fully provisioned")
            security = fts_security[0]
            if security["prosecdef"] or security["anon_execute"] or security["authenticated_execute"] or not security["service_execute"]:
                raise Stage13AHybridError("FTS RPC privilege contract is unsafe")
            return {
                "documents": int(counts["documents"]),
                "chunks": int(counts["chunks"]),
                "distinct_canonical_ids": int(counts["distinct_ids"]),
                "vectors": int(counts["vectors"]),
                "shared": int(counts["shared"]),
                "scoped": int(counts["scoped"]),
                "scope_rows": int(counts["scope_rows"]),
                "scope_counts": scope_counts,
                "orphan_chunks": int(counts["orphan_chunks"]),
                "orphan_scope_rows": int(counts["orphan_scope_rows"]),
                "duplicate_ids": int(counts["duplicate_ids"]),
                "vector_failures": int(counts["vector_failures"]),
                "embedding_profile": {
                    "model_id": row["model_id"],
                    "dimension": row["dimension"],
                    "similarity": row["similarity"],
                    "unit_normalized": row["is_unit_normalized"],
                    "artifact_sha256": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
                    "manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
                },
                "corpus_version": {
                    "name": row["corpus_name"],
                    "version": row["version"],
                    "manifest_sha256": row["manifest_sha256"],
                    "artifact_sha256": corpus_metadata.get("embedding_artifact_sha256"),
                    "embedding_manifest_sha256": corpus_metadata.get("embedding_manifest_artifact_sha256"),
                },
                "fts": {
                    "index": fts_index[0]["indexname"],
                    "indexed_rows": int(indexed_rows),
                    "rpc": "public.match_policy_chunks_fts",
                    "security_invoker": not bool(security["prosecdef"]),
                    "anon_execute": bool(security["anon_execute"]),
                    "authenticated_execute": bool(security["authenticated_execute"]),
                    "service_role_execute": bool(security["service_execute"]),
                },
            }
    finally:
        engine.dispose()


def verify_fts_scope_semantics(settings: Any, corpus: FrozenCorpusV2) -> dict[str, Any]:
    """Run read-only real-data FTS visibility probes, not evaluation labeling."""

    synthetic_probe = next(
        row
        for row in corpus.rows
        if corpus.sources[row["source_id"]]["synthetic"]
        and "credit" in {
            _scope_slug(scope) for scope in corpus.sources[row["source_id"]].get("agent_scopes", [])
        }
    )
    shared_probe = next(
        row
        for row in corpus.rows
        if not corpus.sources[row["source_id"]]["synthetic"]
    )
    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            statement = text(
                """
                SELECT EXISTS(
                    SELECT 1 FROM public.match_policy_chunks_fts(
                        :query_text, :scope, 100
                    ) WHERE canonical_chunk_id = :chunk_id
                )
                """
            )
            synthetic_query = synthetic_probe["content"]
            credit_visible = connection.scalar(
                statement,
                {
                    "query_text": synthetic_query,
                    "scope": "credit",
                    "chunk_id": synthetic_probe["canonical_chunk_id"],
                },
            )
            collateral_visible = connection.scalar(
                statement,
                {
                    "query_text": synthetic_query,
                    "scope": "collateral_appraisal",
                    "chunk_id": synthetic_probe["canonical_chunk_id"],
                },
            )
            shared_query = " ".join(shared_probe["content"].split()[:5])
            shared_collateral_visible = connection.scalar(
                statement,
                {
                    "query_text": shared_query,
                    "scope": "collateral_appraisal",
                    "chunk_id": shared_probe["canonical_chunk_id"],
                },
            )
            if not credit_visible or collateral_visible or not shared_collateral_visible:
                raise Stage13AHybridError("real-data FTS scope isolation probe failed")
            return {
                "synthetic_probe_id": synthetic_probe["canonical_chunk_id"],
                "synthetic_credit_visible": bool(credit_visible),
                "synthetic_collateral_appraisal_visible": bool(collateral_visible),
                "shared_collateral_appraisal_visible": bool(shared_collateral_visible),
                "banking_operations_scope_persisted": False,
            }
    finally:
        engine.dispose()


def _summary_arm(
    traces: list[dict[str, Any]],
    phases: tuple[str, ...],
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "query_count": len(traces),
        "metrics": aggregate_metrics(traces),
        "latency": latency_summary(traces, phases),
        "by_scope": vector_breakdown(records, traces, "scope"),
        "by_source_type": vector_breakdown(records, traces, "source_type"),
        "empty_candidate_queries": sum(
            not (
                trace.get("candidate_canonical_chunk_ids", [])
                or trace.get("vector_candidate_canonical_chunk_ids", [])
                or trace.get("lexical_candidate_canonical_chunk_ids", [])
            )
            for trace in traces
        ),
    }


def _baseline_arm(reference: dict[str, Any], records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = reference["summary"]
    traces = reference["traces"]
    return {
        "query_count": len(traces),
        "metrics": summary["run_1"]["metrics"],
        "latency": summary["run_1"]["latency"],
        "by_scope": summary["run_1"]["by_scope"],
        "by_source_type": summary["run_1"]["by_source_type"],
        "artifact": str(VECTOR_SUMMARY_PATH.relative_to(ROOT)),
    }


def _miss_recovery(
    records: list[dict[str, Any]],
    vector_traces: list[dict[str, Any]],
    lexical_traces: list[dict[str, Any]],
    hybrid_traces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {
        "vector": {item["evaluation_id"]: item for item in vector_traces},
        "lexical": {item["evaluation_id"]: item for item in lexical_traces},
        "hybrid": {item["evaluation_id"]: item for item in hybrid_traces},
    }
    target_ids = {"stage12a-007", "stage12a-008", "stage12a-013", "stage12a-024"}
    output: list[dict[str, Any]] = []
    for record in records:
        if record["evaluation_id"] not in target_ids:
            continue
        evaluation_id = record["evaluation_id"]
        output.append(
            {
                "evaluation_id": evaluation_id,
                "gold_canonical_chunk_ids": list(record["expected_canonical_chunk_ids"]),
                "vector_gold_ranks": by_id["vector"][evaluation_id]["gold_ranks"],
                "lexical_gold_ranks": by_id["lexical"][evaluation_id]["gold_ranks"],
                "hybrid_gold_ranks": by_id["hybrid"][evaluation_id]["gold_ranks"],
                "vector_hit_at_5": bool(by_id["vector"][evaluation_id]["metrics"]["hit@5"]),
                "lexical_hit_at_5": bool(by_id["lexical"][evaluation_id]["metrics"]["hit@5"]),
                "hybrid_hit_at_5": bool(by_id["hybrid"][evaluation_id]["metrics"]["hit@5"]),
                "lexical_recovered": bool(by_id["lexical"][evaluation_id]["metrics"]["hit@5"]),
                "hybrid_recovered": bool(by_id["hybrid"][evaluation_id]["metrics"]["hit@5"]),
            }
        )
    return output


def _regressions(
    records: list[dict[str, Any]],
    vector_traces: list[dict[str, Any]],
    hybrid_traces: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    vector = {item["evaluation_id"]: item for item in vector_traces}
    hybrid = {item["evaluation_id"]: item for item in hybrid_traces}
    output: list[dict[str, Any]] = []
    for record in records:
        evaluation_id = record["evaluation_id"]
        vector_trace = vector[evaluation_id]
        hybrid_trace = hybrid[evaluation_id]
        vector_rank = vector_trace["first_relevant_rank"]
        hybrid_rank = hybrid_trace["first_relevant_rank"]
        if vector_rank is None:
            continue
        if hybrid_rank is not None and hybrid_rank <= vector_rank:
            continue
        vector_ids = set(vector_trace.get("vector_candidate_canonical_chunk_ids") or vector_trace["retrieved_canonical_chunk_ids"])
        lexical_only_displacers = [
            chunk_id
            for chunk_id in hybrid_trace["retrieved_canonical_chunk_ids"]
            if chunk_id not in vector_ids
        ]
        output.append(
            {
                "evaluation_id": evaluation_id,
                "vector_first_relevant_rank": vector_rank,
                "hybrid_first_relevant_rank": hybrid_rank,
                "vector_top1_hit": bool(vector_trace["metrics"]["hit@1"]),
                "hybrid_top1_hit": bool(hybrid_trace["metrics"]["hit@1"]),
                "top1_regressed": bool(vector_trace["metrics"]["hit@1"] and not hybrid_trace["metrics"]["hit@1"]),
                "lexical_only_hybrid_results": lexical_only_displacers,
                "note": "Descriptive ranking comparison; no gold or result correction was applied.",
            }
        )
    return output


def _gold_rank_gt_one_analysis(
    vector_traces: list[dict[str, Any]], hybrid_traces: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    vector = {item["evaluation_id"]: item for item in vector_traces}
    hybrid = {item["evaluation_id"]: item for item in hybrid_traces}
    wanted = {"stage12a-003", "stage12a-004", "stage12a-010", "stage12a-012", "stage12a-018"}
    output: list[dict[str, Any]] = []
    for evaluation_id in sorted(wanted):
        old_ranks = vector[evaluation_id]["gold_ranks"]
        new_ranks = hybrid[evaluation_id]["gold_ranks"]
        old_rank_values = [rank if rank is not None else MAX_K + 1 for rank in old_ranks.values()]
        new_rank_values = [new_ranks.get(chunk_id) if new_ranks.get(chunk_id) is not None else MAX_K + 1 for chunk_id in old_ranks]
        if any(new < old for new, old in zip(new_rank_values, old_rank_values)) and not any(new > old for new, old in zip(new_rank_values, old_rank_values)):
            comparison = "IMPROVED"
        elif any(new > old for new, old in zip(new_rank_values, old_rank_values)):
            comparison = "WORSENED"
        else:
            comparison = "UNCHANGED"
        output.append(
            {
                "evaluation_id": evaluation_id,
                "vector_gold_ranks": old_ranks,
                "hybrid_gold_ranks": new_ranks,
                "vector_first_relevant_rank": vector[evaluation_id]["first_relevant_rank"],
                "hybrid_first_relevant_rank": hybrid[evaluation_id]["first_relevant_rank"],
                "comparison": comparison,
            }
        )
    return output


def _delta(hybrid: dict[str, float], vector: dict[str, float]) -> dict[str, float]:
    return {name: float(hybrid[name]) - float(vector[name]) for name in vector}


def _validate_output(
    records: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
    traces: list[dict[str, Any]],
    *,
    require_nonempty: bool,
) -> None:
    if len(traces) != EXPECTED_QUERY_COUNT:
        raise Stage13AHybridError("evaluation output does not contain exactly 25 traces")
    expected_ids = [item["evaluation_id"] for item in records]
    if [item["evaluation_id"] for item in traces] != expected_ids:
        raise Stage13AHybridError("evaluation trace IDs do not match frozen gold order")
    all_ids = set(corpus.by_id)
    for trace in traces:
        retrieved = trace["retrieved_canonical_chunk_ids"]
        if require_nonempty and len(retrieved) != MAX_K:
            raise Stage13AHybridError(f"{trace['evaluation_id']} has fewer than five results")
        candidate_ids = set(trace.get("candidate_canonical_chunk_ids", []))
        candidate_ids.update(trace.get("vector_candidate_canonical_chunk_ids", []))
        candidate_ids.update(trace.get("lexical_candidate_canonical_chunk_ids", []))
        if not candidate_ids.issubset(all_ids) or not set(retrieved).issubset(all_ids):
            raise Stage13AHybridError("evaluation output contains a non-V2 result ID")
        if len(retrieved) != len(set(retrieved)):
            raise Stage13AHybridError("evaluation output contains duplicate result IDs")
        if any(not 0.0 <= float(value) <= 1.0 for value in trace["metrics"].values()):
            raise Stage13AHybridError("evaluation output contains a metric outside [0,1]")
        if any(float(value) < 0.0 for value in trace["latency_ms"].values()):
            raise Stage13AHybridError("evaluation output contains a negative latency")
    multi = next(item for item in records if item["evaluation_id"] == "stage12a-004")
    expected_multi = [
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    ]
    if multi["expected_canonical_chunk_ids"] != expected_multi:
        raise Stage13AHybridError("stage12a-004 multi-gold set changed")


def _write_jsonl(path: Path, traces: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")


def _metric_row(metrics: dict[str, Any], metric: str) -> str:
    return " / ".join(f"{float(metrics[f'{metric}@{k}']):.4f}" for k in K_VALUES)


def write_document(summary: dict[str, Any]) -> None:
    vector = summary["arms"]["vector_only"]["metrics"]
    lexical = summary["arms"]["lexical_only"]["run_1"]["metrics"]
    hybrid = summary["arms"]["hybrid_rrf"]["run_1"]["metrics"]
    metric_names = [
        f"{metric}@{k}"
        for metric in ("hit", "recall", "mrr", "ndcg")
        for k in K_VALUES
    ]
    lines = [
        "# Stage 13A - FTS + Vector + RRF",
        "",
        "Status: PILOT / EXPLORATORY / DESCRIPTIVE.",
        "",
        "## Frozen identity and configuration",
        "",
        f"- Gold: `{summary['gold']['path']}`; SHA-256 `{summary['gold']['sha256']}`; 25 REVIEWED records.",
        f"- Corpus: `{summary['corpus']['name']}` {summary['corpus']['version']}; 1610 chunks; manifest SHA-256 `{summary['corpus']['manifest_sha256']}`.",
        f"- Embedding: `{summary['embedding']['model']}`, GGUF F16, 1024D, llama.cpp/Vulkan; artifact SHA-256 `{summary['embedding']['artifact_sha256']}`.",
        f"- FTS: PostgreSQL `{FTS_CONFIG}` configuration over `{', '.join(FTS_FIELDS)}`; original human query text; GIN-backed derived tsvector.",
        f"- Candidate depths: vector `{VECTOR_CANDIDATE_DEPTH}`, lexical `{LEXICAL_CANDIDATE_DEPTH}`; RRF constant `{RRF_K}`.",
        "- RRF formula: `1/(60 + vector_rank) + 1/(60 + lexical_rank)`; final ordering is RRF score descending, then canonical_chunk_id ascending.",
        "- Calls are sequential. No lexical score, vector similarity, gold metadata, query rewrite, expansion, reranker, or benchmark tuning was used.",
        "",
        "## Three-arm metrics",
        "",
        "| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        "| Vector-only (frozen) | " + " | ".join(f"{float(vector[name]):.4f}" for name in metric_names) + " |",
        "| Lexical-only | " + " | ".join(f"{float(lexical[name]):.4f}" for name in metric_names) + " |",
        "| Hybrid RRF | " + " | ".join(f"{float(hybrid[name]):.4f}" for name in metric_names) + " |",
        "",
        "Metric column order is Hit, Recall, MRR, nDCG, each at K=1,3,5. Existing R02 definitions were used.",
        f"Lexical-only returned no candidates for {summary['arms']['lexical_only']['run_1']['empty_candidate_queries']} of 25 full natural-language questions under direct `plainto_tsquery` semantics; this is a measured arm outcome, not a runtime failure.",
        "",
        "## Hybrid delta versus frozen vector",
        "",
        "| Metric | @1 | @3 | @5 |",
        "| --- | ---: | ---: | ---: |",
    ]
    for metric in ("hit", "recall", "mrr", "ndcg"):
        delta = summary["delta_hybrid_vs_vector"]
        lines.append(
            f"| {metric} | {delta[f'{metric}@1']:+.4f} | {delta[f'{metric}@3']:+.4f} | {delta[f'{metric}@5']:+.4f} |"
        )
    lines.extend(["", "## Latency", ""])
    lines.append("Latency is local llama.cpp plus remote Supabase staging and is exploratory, not an SLA.")
    for label, arm_key in (("Lexical-only", "lexical_only"), ("Hybrid RRF", "hybrid_rrf")):
        arm = summary["arms"][arm_key]["run_1"]
        lines.append("")
        lines.append(f"### {label}")
        lines.append("")
        for phase, values in arm["latency"].items():
            lines.append(f"- {phase}: p50 `{values['p50_ms']:.3f} ms`; p95 `{values['p95_ms']:.3f} ms`")
    lines.extend(["", "## Frozen vector misses @5", ""])
    for item in summary["miss_recovery"]:
        lines.append(
            f"- `{item['evaluation_id']}`: vector ranks `{item['vector_gold_ranks']}`; lexical ranks `{item['lexical_gold_ranks']}`; hybrid ranks `{item['hybrid_gold_ranks']}`; lexical `{('RECOVERED' if item['lexical_recovered'] else 'NOT RECOVERED')}`; hybrid `{('RECOVERED' if item['hybrid_recovered'] else 'NOT RECOVERED')}`."
        )
    lines.append("")
    for item in summary["misses_at_5"]["vector_only"]:
        lines.append(
            f"- Frozen vector miss category `{item['evaluation_id']}`: `{item['category']}`."
        )
    lines.extend(["", "## Regression and rank analysis", ""])
    if summary["regressions"]:
        for item in summary["regressions"]:
            lines.append(
                f"- `{item['evaluation_id']}`: vector first relevant rank `{item['vector_first_relevant_rank']}`, hybrid `{item['hybrid_first_relevant_rank']}`; top-1 regressed `{item['top1_regressed']}`; lexical-only hybrid results `{item['lexical_only_hybrid_results']}`."
            )
    else:
        lines.append("- No query had a worse first relevant rank in hybrid than in the frozen vector reference.")
    lines.append("")
    for item in summary["gold_rank_greater_than_one_analysis"]:
        lines.append(
            f"- Gold-rank analysis `{item['evaluation_id']}`: vector ranks `{item['vector_gold_ranks']}` -> hybrid ranks `{item['hybrid_gold_ranks']}`: **{item['comparison']}**."
        )
    lines.extend(["", "## Scope and source breakdown", "", "Scope and source subsets are descriptive small-N views.", ""])
    lines.append("| Scope | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: |")
    for scope, values in summary["arms"]["hybrid_rrf"]["run_1"]["by_scope"].items():
        lines.append(f"| {scope} | {values['query_count']} | {values['hit@1']:.4f} | {values['hit@3']:.4f} | {values['hit@5']:.4f} | {values['recall@5']:.4f} | {values['mrr@5']:.4f} |")
    lines.append("")
    lines.append("| Source class | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 | nDCG@5 |")
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |")
    for group, values in summary["arms"]["hybrid_rrf"]["run_1"]["by_source_type"].items():
        lines.append(f"| {group} | {values['query_count']} | {values['hit@1']:.4f} | {values['hit@3']:.4f} | {values['hit@5']:.4f} | {values['recall@5']:.4f} | {values['mrr@5']:.4f} | {values['ndcg@5']:.4f} |")
    lines.extend(["", "## Repeatability", ""])
    for label, key in (("Lexical-only", "lexical_only"), ("Hybrid RRF", "hybrid_rrf")):
        repeat = summary["repeatability"][key]
        lines.append(f"- {label}: metrics equal `{repeat['metrics_equal']}`; ordered top-5 agreement `{repeat['ordered_top5_agreement']:.4f}`; top-1 agreement `{repeat['top1_agreement']:.4f}`; top-5 set agreement `{repeat['top5_set_agreement']:.4f}`; rank-difference queries `{repeat['queries_with_rank_differences']}`; max score drift `{repeat['max_score_drift']:.8f}`.")
    lines.extend([
        "",
        "## Safety and scope contract",
        "",
        "- FTS is additive and uses only canonical title, heading path, and content.",
        "- Both RPCs preserve SHARED/SCOPED visibility; BankingOperations is unsupported.",
        "- Returned IDs are validated against the frozen 1610-ID Corpus V2 set.",
        "- Stage 12B artifacts were not overwritten; no corpus, vector, gold, Supabase canonical data, or local canonical files were changed.",
        "- No benchmark beyond this pilot, no gold mutation, no document embedding regeneration, and no model download occurred.",
        "",
        "## Artifacts",
        "",
        f"- Summary: `{HYBRID_SUMMARY_PATH.relative_to(ROOT).as_posix()}`",
        f"- Hybrid run 1: `{HYBRID_RUN1_TRACE_PATH.relative_to(ROOT).as_posix()}`",
        f"- Hybrid run 2: `{HYBRID_RUN2_TRACE_PATH.relative_to(ROOT).as_posix()}`",
        f"- Lexical summary: `{LEXICAL_SUMMARY_PATH.relative_to(ROOT).as_posix()}`",
        f"- Lexical run 1: `{LEXICAL_RUN1_TRACE_PATH.relative_to(ROOT).as_posix()}`",
        f"- Lexical run 2: `{LEXICAL_RUN2_TRACE_PATH.relative_to(ROOT).as_posix()}`",
    ])
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def _classify(summary: dict[str, Any]) -> str:
    vector = summary["arms"]["vector_only"]["metrics"]
    hybrid = summary["arms"]["hybrid_rrf"]["run_1"]["metrics"]
    delta_values = [float(hybrid[key]) - float(vector[key]) for key in vector]
    improved = any(value > 0 for value in delta_values)
    reduced = any(value < 0 for value in delta_values)
    regressions = summary["regressions"]
    if improved and not reduced and not regressions:
        return "A"
    if improved and (reduced or regressions):
        return "B"
    if reduced and not improved:
        return "D"
    return "C"


def main() -> int:
    corpus = FrozenCorpusV2()
    records = validate_gold_identity(corpus)
    if sha256_file(GOLD_PATH) != EXPECTED_GOLD_SHA256:
        raise Stage13AHybridError("frozen gold SHA-256 mismatch")
    reference = _frozen_vector_reference(records, corpus)
    settings = get_settings()
    remote_state = verify_remote_state(settings, corpus)
    fts_scope_smoke = verify_fts_scope_semantics(settings, corpus)

    adapter = LlamaV2QueryEmbeddingAdapter(settings.llama_embedding_base_url)
    expected_template = (
        "Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages "
        "that directly support the answer.\nQuery: {query}"
    )
    if adapter.format_query("{query}") != expected_template:
        raise Stage13AHybridError("canonical query template does not match the frozen contract")
    vector_retriever = CanonicalV2Retriever(settings, embedding_adapter=adapter)
    lexical_retriever = CanonicalV2LexicalRetriever(settings)
    hybrid_retriever = CanonicalV2HybridRetriever(
        settings,
        vector_retriever=vector_retriever,
        lexical_retriever=lexical_retriever,
    )

    # Explicit live end-to-end preflight.  The measured arms below remain the
    # only benchmark runs and use fixed K/depth parameters.
    probe_record = records[0]
    probe_scope = normalize_specialist_scope(probe_record["specialist_scope"])
    probe, probe_vectors, probe_lexical, _ = hybrid_retriever.retrieve_with_candidates_with_timing(
        probe_record["query"], probe_scope, k=MAX_K
    )
    if len(probe) != MAX_K:
        raise Stage13AHybridError("live hybrid preflight did not return five results")
    for result in probe_vectors:
        _validate_common_result(result, corpus, probe_scope, "similarity")
    for result in probe_lexical:
        _validate_common_result(result, corpus, probe_scope, "lexical_score")
    for result in probe:
        _validate_common_result(result, corpus, probe_scope, "rrf_score")

    lexical_run1 = run_lexical_once(records, corpus, lexical_retriever, run_number=1)
    hybrid_run1 = run_hybrid_once(records, corpus, hybrid_retriever, run_number=1)
    lexical_run2 = run_lexical_once(records, corpus, lexical_retriever, run_number=2)
    hybrid_run2 = run_hybrid_once(records, corpus, hybrid_retriever, run_number=2)
    _validate_output(records, corpus, lexical_run1, require_nonempty=False)
    _validate_output(records, corpus, lexical_run2, require_nonempty=False)
    _validate_output(records, corpus, hybrid_run1, require_nonempty=True)
    _validate_output(records, corpus, hybrid_run2, require_nonempty=True)

    lexical_arm1 = _summary_arm(lexical_run1, ("fts", "total"), records)
    lexical_arm2 = _summary_arm(lexical_run2, ("fts", "total"), records)
    hybrid_arm1 = _summary_arm(hybrid_run1, ("embedding", "vector", "fts", "fusion", "total"), records)
    hybrid_arm2 = _summary_arm(hybrid_run2, ("embedding", "vector", "fts", "fusion", "total"), records)
    vector_arm = _baseline_arm(reference, records)
    summary: dict[str, Any] = {
        "stage": "13A - Measured Hybrid Retrieval: PostgreSQL FTS + Vector + RRF",
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
            "remote_state": remote_state,
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
        "runtime": {
            "query_embedding_backend": "llama.cpp",
            "endpoint": adapter.endpoint,
            "query_instruction": adapter.QUERY_INSTRUCTION,
            "query_format": expected_template,
            "retrieval": "Supabase public.match_policy_chunks plus public.match_policy_chunks_fts",
            "distance": "cosine for vector branch",
            "sequential_calls": True,
            "sentence_transformer_used": False,
            "fallback_backend_used": False,
            "legacy_tables_used": False,
        },
        "configuration": {
            "fts_config": FTS_CONFIG,
            "fts_indexed_fields": list(FTS_FIELDS),
            "fts_query": "original human query text",
            "vector_candidate_depth": VECTOR_CANDIDATE_DEPTH,
            "lexical_candidate_depth": LEXICAL_CANDIDATE_DEPTH,
            "rrf_k": RRF_K,
            "rrf_formula": "1/(60+vector_rank) + 1/(60+lexical_rank)",
            "final_ordering": "rrf_score DESC, canonical_chunk_id ASC",
            "k_values": list(K_VALUES),
            "top_k": MAX_K,
            "raw_score_mixing": False,
            "query_rewrite": False,
            "query_expansion": False,
            "reranker": False,
        },
        "fts_scope_smoke": fts_scope_smoke,
        "arms": {
            "vector_only": vector_arm,
            "lexical_only": {"run_1": lexical_arm1, "run_2": lexical_arm2},
            "hybrid_rrf": {"run_1": hybrid_arm1, "run_2": hybrid_arm2},
        },
        "delta_hybrid_vs_vector": _delta(hybrid_arm1["metrics"], vector_arm["metrics"]),
        "miss_recovery": _miss_recovery(records, reference["traces"], lexical_run1, hybrid_run1),
        "misses_at_5": {
            "vector_only": vector_miss_analysis(records, reference["traces"], corpus),
            "lexical_only": vector_miss_analysis(records, lexical_run1, corpus),
            "hybrid_rrf": vector_miss_analysis(records, hybrid_run1, corpus),
        },
        "regressions": _regressions(records, reference["traces"], hybrid_run1),
        "gold_rank_greater_than_one_analysis": _gold_rank_gt_one_analysis(
            reference["traces"], hybrid_run1
        ),
        "repeatability": {
            "lexical_only": repeatability(lexical_run1, lexical_run2, "lexical_score"),
            "hybrid_rrf": repeatability(hybrid_run1, hybrid_run2, "rrf_score"),
        },
        "constraints": {
            "frozen_vector_baseline_overwritten": False,
            "gold_modified": False,
            "supabase_corpus_mutated": False,
            "document_embeddings_regenerated": False,
            "model_downloaded": False,
            "local_files_deleted": False,
            "benchmark_metrics_only": True,
        },
    }
    summary["classification"] = _classify(summary)

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    _write_jsonl(LEXICAL_RUN1_TRACE_PATH, lexical_run1)
    _write_jsonl(LEXICAL_RUN2_TRACE_PATH, lexical_run2)
    _write_jsonl(LEXICAL_TRACE_PATH, lexical_run1)
    _write_jsonl(HYBRID_RUN1_TRACE_PATH, hybrid_run1)
    _write_jsonl(HYBRID_RUN2_TRACE_PATH, hybrid_run2)
    _write_jsonl(HYBRID_TRACE_PATH, hybrid_run1)
    LEXICAL_SUMMARY_PATH.write_text(
        json.dumps(
            {
                "stage": "13A - Lexical-only FTS arm",
                "status": summary["status"],
                "identity": {"gold_sha256": summary["gold"]["sha256"], "corpus": summary["corpus"], "embedding": summary["embedding"]},
                "configuration": summary["configuration"],
                "run_1": lexical_arm1,
                "run_2": lexical_arm2,
                "repeatability": summary["repeatability"]["lexical_only"],
                "constraints": summary["constraints"],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    HYBRID_SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_document(summary)

    for path, expected in (
        (LEXICAL_TRACE_PATH, 25),
        (LEXICAL_RUN1_TRACE_PATH, 25),
        (LEXICAL_RUN2_TRACE_PATH, 25),
        (HYBRID_TRACE_PATH, 25),
        (HYBRID_RUN1_TRACE_PATH, 25),
        (HYBRID_RUN2_TRACE_PATH, 25),
    ):
        actual = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
        if actual != expected:
            raise Stage13AHybridError(f"trace count mismatch at {path}: {actual} != {expected}")

    print(
        json.dumps(
            {
                "status": "PASS",
                "classification": summary["classification"],
                "lexical_metrics": lexical_arm1["metrics"],
                "hybrid_metrics": hybrid_arm1["metrics"],
                "hybrid_delta": summary["delta_hybrid_vs_vector"],
                "lexical_repeatability": {
                    "metrics_equal": summary["repeatability"]["lexical_only"]["metrics_equal"],
                    "ordered_top5_agreement": summary["repeatability"]["lexical_only"]["ordered_top5_agreement"],
                },
                "hybrid_repeatability": {
                    "metrics_equal": summary["repeatability"]["hybrid_rrf"]["metrics_equal"],
                    "ordered_top5_agreement": summary["repeatability"]["hybrid_rrf"]["ordered_top5_agreement"],
                },
                "artifacts": {
                    "summary": str(HYBRID_SUMMARY_PATH.relative_to(ROOT)),
                    "traces": str(HYBRID_TRACE_PATH.relative_to(ROOT)),
                    "documentation": str(DOC_PATH.relative_to(ROOT)),
                },
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
    except Stage13AHybridError as exc:
        print(f"STAGE13A FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
