"""Audit frozen Corpus V2 vector candidate coverage for Stage 13B0.

This is a feasibility audit, not a benchmark or a reranker implementation.
Each reviewed question is embedded once through the canonical llama.cpp
adapter and sent to the existing vector RPC with ``match_count=50``.  The
script never calls the additive FTS RPC, hybrid code, legacy tables, or a
reranker, and it never mutates Supabase state.
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

from sqlalchemy import create_engine, text

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter  # noqa: E402
from app.eval.metrics import hit_at_k, percentile, recall_at_k  # noqa: E402
from app.services.supabase_v2_retriever import (  # noqa: E402
    CanonicalV2RetrievalResult,
    CanonicalV2Retriever,
    normalize_specialist_scope,
)
from scripts.run_stage12b_vector_v2_baseline import (  # noqa: E402
    EXPECTED_CORPUS_MANIFEST_SHA256,
    EXPECTED_EMBEDDING_ARTIFACT_SHA256,
    EXPECTED_EMBEDDING_MANIFEST_SHA256,
    EXPECTED_GOLD_SHA256,
    EXPECTED_QUERY_COUNT,
    sha256_file,
    validate_gold_identity,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
SUMMARY_PATH = RESULTS_DIR / "vector-v2-candidate-recall-summary.json"
TRACE_PATH = RESULTS_DIR / "vector-v2-candidate-recall-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-13B0-CANDIDATE-RECALL.md"

CANDIDATE_DEPTH = 50
COVERAGE_K = (5, 10, 20, 50)
FROZEN_BASELINE_HIT_AT_5 = 0.84
FROZEN_MISS_IDS = (
    "stage12a-007",
    "stage12a-008",
    "stage12a-013",
    "stage12a-024",
)


class Stage13B0CandidateRecallError(RuntimeError):
    """Raised when the frozen candidate audit contract is not satisfied."""


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def _without_sha(value: str) -> str:
    return value.removeprefix("sha256:")


def _source_type(source: dict[str, Any]) -> str:
    return "synthetic_internal_policy" if source["synthetic"] else "real_regulation"


def _scope_slug(value: str) -> str:
    chars: list[str] = []
    for index, char in enumerate(value):
        if char.isupper() and index:
            chars.append("_")
        chars.append(char.lower())
    return "".join(chars)


def validate_identity(corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    """Re-assert all local identity bindings before any live vector call."""

    records = validate_gold_identity(corpus)
    expected_files = {
        ROOT / "dataset/manifests/policy-corpus-v2-manifest.json": EXPECTED_CORPUS_MANIFEST_SHA256,
        ROOT / "dataset/embeddings/v2/embeddings.parquet": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
        ROOT / "dataset/embeddings/v2/embedding-manifest.json": EXPECTED_EMBEDDING_MANIFEST_SHA256,
    }
    for path, expected in expected_files.items():
        actual = sha256_file(path)
        if actual != expected:
            raise Stage13B0CandidateRecallError(
                f"frozen identity mismatch for {path}: {actual} != {expected}"
            )
    if sha256_file(GOLD_PATH) != EXPECTED_GOLD_SHA256:
        raise Stage13B0CandidateRecallError("released gold SHA-256 changed")
    if len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise Stage13B0CandidateRecallError("local Corpus V2 is not 1610 unique chunks")
    identity = corpus.embedding_identity
    expected_embedding = {
        "model": "Qwen3-Embedding-0.6B",
        "dimension": 1024,
        "runtime": "llama.cpp",
        "backend": "Vulkan",
    }
    if any(identity[key] != value for key, value in expected_embedding.items()):
        raise Stage13B0CandidateRecallError(
            f"local embedding identity mismatch: {identity}"
        )
    return records


def read_remote_state(settings: Any) -> dict[str, Any]:
    """Read canonical counts/identity and additive index state without writes."""

    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            counts = conn.execute(
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
                      (SELECT count(*) FROM rag_v2.policy_chunks WHERE vector_dims(embedding) <> 1024) AS dimension_failures,
                      (SELECT count(*) FROM rag_v2.policy_chunks WHERE search_document IS NULL) AS null_search_documents
                    """
                )
            ).one()._mapping
            values = {key: int(value) for key, value in counts.items()}
            if values != {
                "documents": 10,
                "chunks": 1610,
                "distinct_ids": 1610,
                "vectors": 1610,
                "shared": 1573,
                "scoped": 37,
                "scope_rows": 125,
                "dimension_failures": 0,
                "null_search_documents": 0,
            }:
                raise Stage13B0CandidateRecallError(
                    f"remote canonical counts drifted: {values}"
                )
            corpus_row = conn.execute(
                text(
                    """
                    SELECT corpus_name, version, manifest_sha256, metadata
                    FROM rag_v2.corpus_versions
                    """
                )
            ).one()
            profile_row = conn.execute(
                text(
                    """
                    SELECT model_id, dimension, similarity, is_unit_normalized, metadata
                    FROM rag_v2.embedding_profiles
                    """
                )
            ).one()
            if (
                corpus_row.corpus_name != "policy-corpus-v2"
                or corpus_row.manifest_sha256 != EXPECTED_CORPUS_MANIFEST_SHA256
                or profile_row.model_id != "Qwen3-Embedding-0.6B"
                or profile_row.dimension != 1024
                or profile_row.similarity != "cosine"
                or not profile_row.is_unit_normalized
            ):
                raise Stage13B0CandidateRecallError(
                    "remote corpus/profile identity does not match the frozen contract"
                )
            indexes = [
                row.indexname
                for row in conn.execute(
                    text(
                        """
                        SELECT indexname
                        FROM pg_indexes
                        WHERE schemaname = 'rag_v2'
                          AND tablename = 'policy_chunks'
                        ORDER BY indexname
                        """
                    )
                )
            ]
            migration_head = conn.scalar(text("SELECT version_num FROM alembic_version"))
            hnsw_ef_search = conn.scalar(text("SHOW hnsw.ef_search"))
            enable_indexscan = conn.scalar(text("SHOW enable_indexscan"))
            return {
                **values,
                "corpus_name": corpus_row.corpus_name,
                "corpus_version": corpus_row.version,
                "corpus_manifest_sha256": corpus_row.manifest_sha256,
                "embedding_model": profile_row.model_id,
                "embedding_dimension": profile_row.dimension,
                "embedding_similarity": profile_row.similarity,
                "embedding_unit_normalized": profile_row.is_unit_normalized,
                "migration_head": migration_head,
                "hnsw_ef_search": hnsw_ef_search,
                "enable_indexscan": enable_indexscan,
                "policy_chunk_indexes": indexes,
                "vector_rpc_used": "public.match_policy_chunks",
                "fts_rpc_used": False,
            }
    finally:
        engine.dispose()


def validate_result_contract(
    result: CanonicalV2RetrievalResult,
    corpus: FrozenCorpusV2,
    requested_scope: str,
) -> None:
    """Validate one returned row against frozen V2 identity and routing."""

    if result.canonical_chunk_id not in corpus.by_id:
        raise Stage13B0CandidateRecallError(
            f"retriever returned a non-V2 ID: {result.canonical_chunk_id}"
        )
    if not math.isfinite(result.similarity):
        raise Stage13B0CandidateRecallError("retriever returned non-finite similarity")
    row = corpus.by_id[result.canonical_chunk_id]
    source = corpus.sources[row["source_id"]]
    expected_visibility = "SCOPED" if source["synthetic"] else "SHARED"
    expected = {
        "document_source_id": row["source_id"],
        "document_version_id": row["version_id"],
        "document_title": source["title"],
        "namespace": source["namespace"],
        "visibility": expected_visibility,
        "heading_path": row.get("heading_path", []),
        "content": row["content"],
    }
    for field, expected_value in expected.items():
        if getattr(result, field) != expected_value:
            raise Stage13B0CandidateRecallError(
                f"result identity mismatch for {result.canonical_chunk_id}: {field}"
            )
    if result.locator.get("article") != row.get("article"):
        raise Stage13B0CandidateRecallError(
            f"result locator mismatch for {result.canonical_chunk_id}"
        )
    if not isinstance(result.metadata, dict):
        raise Stage13B0CandidateRecallError("result metadata is malformed")
    if source["synthetic"]:
        allowed_scopes = {
            _scope_slug(scope_name) for scope_name in source.get("agent_scopes", [])
        }
        if requested_scope not in allowed_scopes:
            raise Stage13B0CandidateRecallError(
                f"SCOPED result leaked to {requested_scope}: {result.canonical_chunk_id}"
            )


def gold_ranks(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, int | None]:
    rank_by_id = {chunk_id: rank for rank, chunk_id in enumerate(retrieved_ids, 1)}
    return {chunk_id: rank_by_id.get(chunk_id) for chunk_id in gold_ids}


def coverage_for_ids(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, float | int]:
    gold_set = set(gold_ids)
    return {
        **{
            f"hit@{k}": hit_at_k(retrieved_ids, gold_set, k)
            for k in COVERAGE_K
        },
        **{
            f"recall@{k}": recall_at_k(retrieved_ids, gold_set, k)
            for k in COVERAGE_K
        },
    }


def result_payload(
    result: CanonicalV2RetrievalResult,
    rank: int,
    corpus: FrozenCorpusV2,
) -> dict[str, Any]:
    source = corpus.sources[corpus.by_id[result.canonical_chunk_id]["source_id"]]
    return {
        "canonical_chunk_id": result.canonical_chunk_id,
        "rank": rank,
        "similarity": result.similarity,
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


def run_once(
    records: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
    retriever: CanonicalV2Retriever,
) -> list[dict[str, Any]]:
    """Run the fixed top-50 vector candidate audit sequentially."""

    traces: list[dict[str, Any]] = []
    for record in records:
        scope = normalize_specialist_scope(record["specialist_scope"])
        started = time.perf_counter()
        results, timing = retriever.retrieve_with_timing(
            record["query"], scope, k=CANDIDATE_DEPTH
        )
        total_ms = (time.perf_counter() - started) * 1000
        if len(results) != CANDIDATE_DEPTH:
            raise Stage13B0CandidateRecallError(
                f"{record['evaluation_id']} returned {len(results)} candidates, expected 50"
            )
        seen: set[str] = set()
        for result in results:
            validate_result_contract(result, corpus, scope)
            if result.canonical_chunk_id in seen:
                raise Stage13B0CandidateRecallError(
                    f"duplicate candidate ID for {record['evaluation_id']}"
                )
            seen.add(result.canonical_chunk_id)
        ids = [result.canonical_chunk_id for result in results]
        gold_ids = list(record["expected_canonical_chunk_ids"])
        ranks = gold_ranks(ids, gold_ids)
        present = [rank for rank in ranks.values() if rank is not None]
        traces.append(
            {
                "evaluation_id": record["evaluation_id"],
                "query": record["query"],
                "specialist_scope": scope,
                "gold_canonical_chunk_ids": gold_ids,
                "gold_set_size": len(gold_ids),
                "gold_visibility": record["visibility"],
                "gold_source_type": (
                    "synthetic_internal_policy"
                    if record["is_synthetic"]
                    else "real_regulation"
                ),
                "candidate_depth": CANDIDATE_DEPTH,
                "candidate_canonical_chunk_ids": ids,
                "candidate_similarity_scores": [result.similarity for result in results],
                "candidate_results": [
                    result_payload(result, rank, corpus)
                    for rank, result in enumerate(results, 1)
                ],
                "gold_ranks": ranks,
                "first_relevant_rank": min(present) if present else None,
                "coverage": coverage_for_ids(ids, gold_ids),
                "latency_ms": {
                    "embedding": timing.embedding_ms,
                    "retrieval": timing.retrieval_ms,
                    "total": total_ms,
                },
                "scope_contract_satisfied": True,
                "retrieval_source": "supabase_rpc",
                "rpc": "public.match_policy_chunks",
                "legacy_tables_used": False,
                "fts_used": False,
                "hybrid_used": False,
                "reranker_used": False,
                "query_embedding_backend": "llama.cpp",
                "v2_only": True,
            }
        )
    return traces


def aggregate_coverage(traces: list[dict[str, Any]]) -> dict[str, float]:
    return {
        f"{metric}@{k}": _mean(
            float(trace["coverage"][f"{metric}@{k}"]) for trace in traces
        )
        for metric in ("hit", "recall")
        for k in COVERAGE_K
    }


def latency_summary(traces: list[dict[str, Any]]) -> dict[str, float]:
    return {
        f"{phase}_p50_ms": percentile(
            [float(trace["latency_ms"][phase]) for trace in traces], 50
        )
        for phase in ("embedding", "retrieval", "total")
    } | {
        f"{phase}_p95_ms": percentile(
            [float(trace["latency_ms"][phase]) for trace in traces], 95
        )
        for phase in ("embedding", "retrieval", "total")
    }


def classify_rank(rank: int | None) -> str:
    if rank is None or rank > 50:
        return "D — NOT PRACTICALLY RERANKABLE FROM VECTOR CANDIDATES"
    if rank <= 10:
        return "A — HIGHLY RERANKABLE"
    if rank <= 20:
        return "B — RERANKABLE"
    return "C — POSSIBLY RERANKABLE BUT EXPENSIVE"


def miss_inspection(
    records: list[dict[str, Any]],
    traces: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
) -> list[dict[str, Any]]:
    records_by_id = {record["evaluation_id"]: record for record in records}
    traces_by_id = {trace["evaluation_id"]: trace for trace in traces}
    details: list[dict[str, Any]] = []
    for evaluation_id in FROZEN_MISS_IDS:
        record = records_by_id[evaluation_id]
        trace = traces_by_id[evaluation_id]
        ranks = trace["gold_ranks"]
        present = [rank for rank in ranks.values() if rank is not None]
        first_rank = min(present) if present else None
        gold_sources = {
            corpus.by_id[chunk_id]["source_id"]
            for chunk_id in record["expected_canonical_chunk_ids"]
        }
        top1 = trace["candidate_results"][0]
        same_document = [
            item
            for item in trace["candidate_results"]
            if item["document_source_id"] in gold_sources
        ]
        details.append(
            {
                "evaluation_id": evaluation_id,
                "scope": trace["specialist_scope"],
                "gold_canonical_chunk_ids": record["expected_canonical_chunk_ids"],
                "gold_ranks": ranks,
                "first_gold_rank": first_rank if first_rank is not None else ">50",
                "classification": classify_rank(first_rank),
                "failure_type": (
                    "ranking failure" if first_rank is not None and first_rank <= 20
                    else "candidate-generation failure"
                ),
                "top1": {
                    "canonical_chunk_id": top1["canonical_chunk_id"],
                    "document_source_id": top1["document_source_id"],
                    "document_title": top1["document_title"],
                    "article": top1["locator"].get("article"),
                    "visibility": top1["visibility"],
                },
                "same_document_candidates": [
                    {
                        "canonical_chunk_id": item["canonical_chunk_id"],
                        "rank": item["rank"],
                        "article": item["locator"].get("article"),
                    }
                    for item in same_document
                ],
                "same_document_candidate_count": len(same_document),
                "note": "Candidate trace inspection only; approved gold was not changed.",
            }
        )
    return details


def write_jsonl(path: Path, traces: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")


def write_document(summary: dict[str, Any], misses: list[dict[str, Any]]) -> None:
    coverage = summary["coverage"]
    lines = [
        "# Stage 13B0 — Candidate Recall Audit",
        "",
        "Status: **PILOT / FEASIBILITY DIAGNOSTIC ONLY**. This audit measures",
        "whether the frozen vector candidate pool contains the approved gold.",
        "It does not implement or load a reranker and is not a quality benchmark.",
        "",
        "## Frozen contract",
        "",
        f"- Gold: `{summary['gold']['path']}`; SHA-256 `{summary['gold']['sha256']}`",
        f"- Corpus: `{summary['corpus']['name']}` / {summary['corpus']['chunk_count']} chunks; manifest SHA-256 `{summary['corpus']['manifest_sha256']}`",
        f"- Embedding: `{summary['embedding']['model']}`, {summary['embedding']['dimension']}D, `{summary['embedding']['runtime']}/{summary['embedding']['backend']}`",
        f"- Vector runtime: `CanonicalV2Retriever -> public.match_policy_chunks`; candidate depth `{CANDIDATE_DEPTH}`",
        "- No FTS, hybrid/RRF, query rewrite, reranker, legacy table, or embedding regeneration was used.",
        "",
        "## Candidate coverage",
        "",
        "These are candidate-pool coverage measurements at the requested depths; deep-K values do not replace the frozen Stage 12B metrics.",
        "",
        "| Metric | @5 | @10 | @20 | @50 |",
        "| --- | ---: | ---: | ---: | ---: |",
        f"| Hit | {coverage['hit@5']:.4f} | {coverage['hit@10']:.4f} | {coverage['hit@20']:.4f} | {coverage['hit@50']:.4f} |",
        f"| Recall | {coverage['recall@5']:.4f} | {coverage['recall@10']:.4f} | {coverage['recall@20']:.4f} | {coverage['recall@50']:.4f} |",
        "",
        "## Frozen @5 misses",
        "",
    ]
    for item in misses:
        lines.append(
            f"- `{item['evaluation_id']}` — first gold rank `{item['first_gold_rank']}`; **{item['classification']}**; **{item['failure_type']}**. Top-1 `{item['top1']['canonical_chunk_id']}` from `{item['top1']['document_source_id']}`, article `{item['top1']['article']}`. Same-document candidates in top 50: `{item['same_document_candidate_count']}`."
        )
    upper = summary["reranker_upper_bound"]
    lines.extend(
        [
            "",
            "## Reranker feasibility gate",
            "",
            f"- Frozen Stage 12B Hit@5: `{upper['frozen_hit@5']:.4f}`.",
            f"- Candidate Hit@20: `{upper['candidate_hit@20']:.4f}`; this is the approximate single-gold perfect-reranker Hit@5 ceiling.",
            f"- Frozen @5 misses with at least one gold in top 20: `{upper['maximum_recoverable_frozen_misses']}` of `{len(FROZEN_MISS_IDS)}`.",
            f"- Candidate Recall@20: `{upper['candidate_recall@20']:.4f}`; for stage12a-004's two gold IDs, this is the maximum fraction of approved evidence available to a reranker.",
            f"- Gate decision: **{summary['decision']['reranker']}**; feasibility **{summary['decision']['feasibility']}**.",
            "- This ceiling is theoretical and does not claim an actual reranker will achieve it.",
            "",
            "## Successful queries with gold available by top 20",
            "",
        ]
    )
    for item in summary["successful_queries_with_gold_in_top20"]:
        lines.append(
            f"- `{item['evaluation_id']}` — first gold rank `{item['first_gold_rank']}`; gold present in candidate pool by rank 20.")
    lines.extend(
        [
            "",
            "## Latency (descriptive)",
            "",
            "The top-50 depth is different from Stage 12B top-5 retrieval; these timings are not a production comparison.",
            "",
            "| Phase | p50 ms | p95 ms |",
            "| --- | ---: | ---: |",
            f"| Embedding | {summary['latency']['embedding_p50_ms']:.3f} | {summary['latency']['embedding_p95_ms']:.3f} |",
            f"| Retrieval | {summary['latency']['retrieval_p50_ms']:.3f} | {summary['latency']['retrieval_p95_ms']:.3f} |",
            f"| Total | {summary['latency']['total_p50_ms']:.3f} | {summary['latency']['total_p95_ms']:.3f} |",
            "",
            "## Constraints",
            "",
            "- Gold, Corpus V2, Supabase canonical rows, document vectors, and local frozen inputs were not modified.",
            "- No benchmark metrics, FTS, hybrid retrieval, query tuning, reranker, model download, or local deletion occurred.",
            "",
            f"Artifacts: `{TRACE_PATH.relative_to(ROOT).as_posix()}` and `{SUMMARY_PATH.relative_to(ROOT).as_posix()}`.",
            "",
        ]
    )
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    corpus = FrozenCorpusV2()
    records = validate_identity(corpus)
    if len(records) != EXPECTED_QUERY_COUNT:
        raise Stage13B0CandidateRecallError("expected exactly 25 frozen gold records")
    settings = get_settings()
    remote_state = read_remote_state(settings)
    adapter = LlamaV2QueryEmbeddingAdapter(settings.llama_embedding_base_url)
    expected_template = (
        "Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages "
        "that directly support the answer.\nQuery: {query}"
    )
    if adapter.format_query("{query}") != expected_template:
        raise Stage13B0CandidateRecallError("canonical query template drifted")
    retriever = CanonicalV2Retriever(settings, embedding_adapter=adapter)

    # Required live preflight is separate from the 25-query audit.
    preflight_scope = normalize_specialist_scope(records[0]["specialist_scope"])
    preflight_results, _ = retriever.retrieve_with_timing(
        records[0]["query"], preflight_scope, k=CANDIDATE_DEPTH
    )
    if len(preflight_results) != CANDIDATE_DEPTH:
        raise Stage13B0CandidateRecallError(
            "canonical public.match_policy_chunks requested k=50 but returned "
            f"{len(preflight_results)} rows; the unchanged runtime cannot provide "
            "an honest top-50 audit under its current approximate-index settings "
            f"(hnsw.ef_search={remote_state['hnsw_ef_search']}, "
            f"enable_indexscan={remote_state['enable_indexscan']})"
        )
    for result in preflight_results:
        validate_result_contract(result, corpus, preflight_scope)

    traces = run_once(records, corpus, retriever)
    if len(traces) != EXPECTED_QUERY_COUNT:
        raise Stage13B0CandidateRecallError("candidate trace count is not 25")
    coverage = aggregate_coverage(traces)
    misses = miss_inspection(records, traces, corpus)
    traces_by_id = {trace["evaluation_id"]: trace for trace in traces}
    successful = []
    for trace in traces:
        present = [rank for rank in trace["gold_ranks"].values() if rank is not None and rank <= 20]
        if trace["coverage"]["hit@5"] == 1 and present:
            successful.append(
                {
                    "evaluation_id": trace["evaluation_id"],
                    "first_gold_rank": min(present),
                }
            )
    recoverable_misses = sum(
        1
        for item in misses
        if isinstance(item["first_gold_rank"], int) and item["first_gold_rank"] <= 20
    )
    candidate_hit20 = coverage["hit@20"]
    if candidate_hit20 <= FROZEN_BASELINE_HIT_AT_5:
        decision = {
            "reranker": "NOT JUSTIFIED",
            "feasibility": "NOT JUSTIFIED",
            "reason": "candidate Hit@20 does not exceed frozen Hit@5",
        }
    elif recoverable_misses <= 1:
        decision = {
            "reranker": "FEASIBLE",
            "feasibility": "LIMITED",
            "reason": "only one or fewer frozen @5 misses is available by top 20",
        }
    else:
        decision = {
            "reranker": "FEASIBLE",
            "feasibility": "MODERATE",
            "reason": "multiple frozen @5 misses are available by top 20",
        }

    summary = {
        "stage": "13B0 — Candidate Recall Audit",
        "status": "PILOT / FEASIBILITY DIAGNOSTIC ONLY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "gold": {
            "path": GOLD_PATH.relative_to(ROOT).as_posix(),
            "sha256": sha256_file(GOLD_PATH),
            "record_count": len(records),
            "statuses": ["REVIEWED"],
        },
        "corpus": {
            **corpus.corpus_identity,
            "name": corpus.corpus_identity["corpus_name"],
            "manifest_sha256": _without_sha(corpus.corpus_identity["corpus_manifest_sha256"]),
            "remote_state": remote_state,
        },
        "embedding": {
            "model": corpus.embedding_identity["model"],
            "dimension": corpus.embedding_identity["dimension"],
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
            "fallback_backend": None,
            "sentence_transformer_used": False,
        },
        "retrieval": {
            "backend": "Supabase",
            "rpc": "public.match_policy_chunks",
            "distance": "cosine",
            "tie_ordering": "cosine distance ASC, canonical_chunk_id ASC",
            "candidate_depth": CANDIDATE_DEPTH,
            "coverage_k": list(COVERAGE_K),
            "supported_scopes": [
                "customer_relationship",
                "credit",
                "risk_management",
                "legal_compliance",
                "collateral_appraisal",
            ],
            "legacy_tables_used": False,
            "fts_used": False,
            "hybrid_used": False,
            "reranker_used": False,
            "query_rewrite_used": False,
            "v2_only": True,
        },
        "coverage": coverage,
        "reranker_upper_bound": {
            "frozen_hit@5": FROZEN_BASELINE_HIT_AT_5,
            "candidate_hit@20": coverage["hit@20"],
            "maximum_recoverable_frozen_misses": recoverable_misses,
            "candidate_recall@20": coverage["recall@20"],
            "multi_gold_stage12a_004_gold_ids": traces_by_id["stage12a-004"]["gold_canonical_chunk_ids"],
            "interpretation": "candidate Hit@20 is an approximate perfect-reranker ceiling for single-gold Hit@5; candidate Recall@20 bounds multi-gold recovery",
        },
        "frozen_miss_inspection": misses,
        "successful_queries_with_gold_in_top20": successful,
        "latency": latency_summary(traces),
        "trace_count": len(traces),
        "constraints": {
            "gold_modified": False,
            "corpus_modified": False,
            "supabase_corpus_mutated": False,
            "document_embeddings_regenerated": False,
            "fts_used": False,
            "hybrid_used": False,
            "reranker_used": False,
            "model_downloaded": False,
            "local_files_deleted": False,
        },
        "decision": decision,
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(TRACE_PATH, traces)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_document(summary, misses)

    # Output-level assertions deliberately occur after writing so the files
    # themselves are checked as part of the gate.
    written_traces = [
        json.loads(line)
        for line in TRACE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(written_traces) != EXPECTED_QUERY_COUNT:
        raise Stage13B0CandidateRecallError("written trace count is not 25")
    if len({trace["evaluation_id"] for trace in written_traces}) != EXPECTED_QUERY_COUNT:
        raise Stage13B0CandidateRecallError("written trace IDs are not unique")
    all_ids = set(corpus.by_id)
    if any(
        not set(trace["candidate_canonical_chunk_ids"]).issubset(all_ids)
        for trace in written_traces
    ):
        raise Stage13B0CandidateRecallError("written trace contains a non-V2 ID")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(
            f"ERROR: Stage 13B0 candidate recall audit failed ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        raise SystemExit(1)
