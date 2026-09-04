"""Compare frozen vector and deterministic OR-FTS candidate generation.

Stage 13C1 is a candidate-availability diagnostic.  Vector top-50 is an
offline exact oracle over the frozen parquet vectors; it is not a production
retrieval request.  The lexical arm uses a mechanically generated OR tsquery
through the additive backend-only RPC over the existing PostgreSQL FTS index.
No reranker, score fusion, or gold mutation is performed.
"""

from __future__ import annotations

from datetime import datetime, timezone
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

from sqlalchemy import create_engine, text  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter  # noqa: E402
from app.services.supabase_fts_retriever import (  # noqa: E402
    CanonicalV2OrLexicalRetriever,
    build_or_tsquery,
)
from app.services.supabase_v2_retriever import (  # noqa: E402
    CanonicalV2Retriever,
    normalize_specialist_scope,
)
from scripts.run_stage12b_vector_v2_baseline import (  # noqa: E402
    EXPECTED_CORPUS_MANIFEST_SHA256,
    EXPECTED_EMBEDDING_ARTIFACT_SHA256,
    EXPECTED_EMBEDDING_MANIFEST_SHA256,
    EXPECTED_GOLD_SHA256,
    sha256_file,
    validate_gold_identity,
)
from scripts.run_stage13c0_exact_candidate_audit import (  # noqa: E402
    _StaticQueryAdapter,
    exact_ranked,
    load_frozen_vectors,
)
from scripts.run_stage13b0_candidate_recall import (  # noqa: E402
    read_remote_state,
    validate_result_contract,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
PARQUET_PATH = ROOT / "dataset/embeddings/v2/embeddings.parquet"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
SUMMARY_PATH = RESULTS_DIR / "candidate-generation-v2-pilot-summary.json"
LEXICAL_TRACE_PATH = RESULTS_DIR / "lexical-or-v2-pilot-traces.jsonl"
UNION_TRACE_PATH = RESULTS_DIR / "vector20-lexical10-union-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-13C1-CANDIDATE-GENERATION.md"

VECTOR20_DEPTH = 20
VECTOR50_DEPTH = 50
LEXICAL10_DEPTH = 10
EXPECTED_QUERY_COUNT = 25
TARGET_ID = "stage12a-024"
TARGET_GOLD_ID = "e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9"


class CandidateGenerationAuditError(RuntimeError):
    """Raised when a candidate-generation invariant fails."""


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def _percentile(values: Iterable[float], percentile: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    position = (len(values) - 1) * percentile / 100
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    return float(values[lower] + (values[upper] - values[lower]) * (position - lower))


def _gold_ranks(
    candidate_ids: list[str], gold_ids: list[str], absent_label: str
) -> dict[str, int | str]:
    by_id = {chunk_id: rank for rank, chunk_id in enumerate(candidate_ids, 1)}
    return {chunk_id: by_id.get(chunk_id, absent_label) for chunk_id in gold_ids}


def _coverage(candidate_ids: list[str], gold_ids: list[str], depth_label: str) -> dict[str, float | int]:
    gold_set = set(gold_ids)
    relevant = sum(chunk_id in gold_set for chunk_id in candidate_ids)
    return {
        "hit": int(relevant > 0),
        "recall": relevant / len(gold_set) if gold_set else 0.0,
        "candidate_count": len(candidate_ids),
        "depth": depth_label,
    }


def build_candidate_union(vector_ids: list[str], lexical_ids: list[str]) -> list[str]:
    """Preserve vector order and append only new lexical candidate IDs."""

    result: list[str] = []
    seen: set[str] = set()
    for chunk_id in vector_ids + lexical_ids:
        if chunk_id not in seen:
            seen.add(chunk_id)
            result.append(chunk_id)
    return result


def _source_type(corpus: FrozenCorpusV2, chunk_id: str) -> str:
    source = corpus.sources[corpus.by_id[chunk_id]["source_id"]]
    return "synthetic_internal_policy" if source["synthetic"] else "real_regulation"


def _scope_slug(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).casefold()


def _citation(result: Any, rank: int, corpus: FrozenCorpusV2) -> dict[str, Any]:
    chunk_id = result.canonical_chunk_id
    row = corpus.by_id[chunk_id]
    source = corpus.sources[row["source_id"]]
    return {
        "rank": rank,
        "canonical_chunk_id": chunk_id,
        "score": result.lexical_score if hasattr(result, "lexical_score") else result.similarity,
        "score_type": "lexical" if hasattr(result, "lexical_score") else "vector_similarity",
        "source_id": row["source_id"],
        "version_id": row["version_id"],
        "title": source["title"],
        "article": row.get("article"),
        "heading_path": row.get("heading_path", []),
        "locator": result.locator,
        "visibility": result.visibility,
        "source_type": "synthetic_internal_policy" if source["synthetic"] else "real_regulation",
    }


def _validate_lexical_result(result: Any, corpus: FrozenCorpusV2, scope: str) -> None:
    chunk_id = result.canonical_chunk_id
    if chunk_id not in corpus.by_id:
        raise CandidateGenerationAuditError(f"OR-FTS returned non-V2 ID: {chunk_id}")
    if not math.isfinite(result.lexical_score) or result.lexical_score < 0:
        raise CandidateGenerationAuditError(f"OR-FTS returned invalid score for {chunk_id}")
    row = corpus.by_id[chunk_id]
    source = corpus.sources[row["source_id"]]
    expected_visibility = "SCOPED" if source["synthetic"] else "SHARED"
    for field, expected in {
        "document_source_id": row["source_id"],
        "document_version_id": row["version_id"],
        "document_title": source["title"],
        "heading_path": row.get("heading_path", []),
        "content": row["content"],
        "visibility": expected_visibility,
        "namespace": source["namespace"],
    }.items():
        if getattr(result, field) != expected:
            raise CandidateGenerationAuditError(
                f"OR-FTS identity mismatch for {chunk_id}: {field}"
            )
    if result.locator.get("article") != row.get("article"):
        raise CandidateGenerationAuditError(f"OR-FTS locator mismatch for {chunk_id}")
    if source["synthetic"]:
        allowed = {_scope_slug(value) for value in source.get("agent_scopes", [])}
        if scope not in allowed:
            raise CandidateGenerationAuditError(f"OR-FTS leaked {chunk_id} to {scope}")


def _read_fts_or_security(settings: Any) -> dict[str, Any]:
    engine = create_engine(settings.admin_database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                      to_regprocedure('public.match_policy_chunks_fts_or(text,text,integer)') IS NOT NULL AS exists,
                      has_function_privilege('anon', 'public.match_policy_chunks_fts_or(text,text,integer)', 'EXECUTE') AS anon_execute,
                      has_function_privilege('authenticated', 'public.match_policy_chunks_fts_or(text,text,integer)', 'EXECUTE') AS authenticated_execute,
                      has_function_privilege('service_role', 'public.match_policy_chunks_fts_or(text,text,integer)', 'EXECUTE') AS service_execute
                    """
                )
            ).one()
            result = dict(row._mapping)
            if not result["exists"] or result["anon_execute"] or result["authenticated_execute"] or not result["service_execute"]:
                raise CandidateGenerationAuditError(f"OR-FTS RPC security contract failed: {result}")
            return result
    finally:
        engine.dispose()


def validate_frozen_inputs() -> tuple[FrozenCorpusV2, list[dict[str, Any]], dict[str, list[float]]]:
    corpus = FrozenCorpusV2()
    records = validate_gold_identity(corpus)
    expected = {
        GOLD_PATH: EXPECTED_GOLD_SHA256,
        ROOT / "dataset/manifests/policy-corpus-v2-manifest.json": EXPECTED_CORPUS_MANIFEST_SHA256,
        PARQUET_PATH: EXPECTED_EMBEDDING_ARTIFACT_SHA256,
        ROOT / "dataset/embeddings/v2/embedding-manifest.json": EXPECTED_EMBEDDING_MANIFEST_SHA256,
    }
    for path, expected_hash in expected.items():
        if sha256_file(path) != expected_hash:
            raise CandidateGenerationAuditError(f"frozen identity changed: {path}")
    if len(records) != EXPECTED_QUERY_COUNT or {record["status"] for record in records} != {"REVIEWED"}:
        raise CandidateGenerationAuditError("gold must contain exactly 25 REVIEWED records")
    if len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise CandidateGenerationAuditError("Corpus V2 must contain 1610 unique IDs")
    vectors = load_frozen_vectors(corpus)
    return corpus, records, vectors


def _build_doc(summary: dict[str, Any]) -> str:
    comparison = summary["comparison"]
    target = summary["stage12a_024"]
    lines = [
        "# Stage 13C1 — Candidate Generation Alternatives Audit",
        "",
        "Status: completed exploratory candidate-availability diagnostic. No gold, corpus, document embedding, reranker, or canonical vector runtime setting was changed.",
        "",
        "## Frozen identity",
        "",
        f"- Gold SHA-256: `{summary['identity']['gold_sha256']}`",
        f"- Corpus: `policy-corpus-v2`, 1,610 unique chunks",
        f"- Corpus manifest SHA-256: `{summary['identity']['corpus_manifest_sha256']}`",
        f"- Embedding artifact SHA-256: `{summary['identity']['embedding_artifact_sha256']}`",
        f"- Embedding manifest SHA-256: `{summary['identity']['embedding_manifest_sha256']}`",
        "",
        "## Fixed configurations",
        "",
        "- Vector top-20: unchanged canonical llama.cpp → `public.match_policy_chunks` path.",
        "- Vector top-50: exact offline cosine oracle over frozen parquet vectors; no HNSW top-50 request.",
        "- OR-FTS top-10: PostgreSQL `simple` config, canonical title/heading/content index, deterministic NFC/casefold tokenization, OR tsquery, `ts_rank_cd`, canonical ID tie-break.",
        "- Union: vector top-20 IDs followed by lexical top-10 IDs not already present; no score fusion and no reranking.",
        "",
        "## Candidate coverage",
        "",
        "| Candidate generator (coverage point) | Hit | Recall | Mean candidate count |",
        "|---|---:|---:|---:|",
    ]
    display_labels = {
        "vector_top20": "Vector top20 (@20)",
        "vector_top50_exact_diagnostic": "Vector top50 exact diagnostic (@50)",
        "lexical_or_top10": "Lexical OR top10 (@10)",
        "vector20_plus_lexical10_union": "Vector20 + Lexical10 union (full)",
    }
    for label, values in comparison.items():
        lines.append(
            f"| {display_labels[label]} | {values['hit']:.4f} | {values['recall']:.4f} | {values['mean_candidate_count']:.2f} |"
        )
    lines += [
        "",
        "## Lexical coverage details",
        "",
        f"- Queries returning at least 10 OR-FTS candidates: `{summary['lexical']['queries_with_at_least_10']}/25`",
        f"- OR-FTS Hit@5 / Hit@10: `{summary['lexical']['hit_at_5']:.4f}` / `{summary['lexical']['hit_at_10']:.4f}`",
        f"- OR-FTS Recall@5 / Recall@10: `{summary['lexical']['recall_at_5']:.4f}` / `{summary['lexical']['recall_at_10']:.4f}`",
        "",
        "## Stage12a-024",
        "",
        f"- Exact vector rank: `{target['exact_vector_rank']}`",
        f"- Vector top-20: `{target['vector20_present']}`",
        f"- Exact vector top-50: `{target['vector50_present']}`",
        f"- OR-FTS top-10 rank: `{target['lexical_rank']}`",
        f"- Vector20 + OR-FTS10 union: `{target['union_present']}`",
        f"- OR-FTS top-10 IDs/articles: `{json.dumps(target['lexical_top10'], ensure_ascii=False)}`",
        "",
        "## Scope and safety",
        "",
        "- SHARED regulation remains eligible for every supported specialist scope.",
        "- SCOPED synthetic chunks are returned only for explicit authorized scopes; BankingOperations is unsupported.",
        "- Every vector top-20 ID is preserved in its union; union size is never greater than 30.",
        f"- OR-FTS RPC security: anon/authenticated denied, service role allowed — `{summary['fts_or_security']}`.",
        f"- Real scoped probe: `{summary['real_scope_isolation_probe']}`.",
        "",
        "## Latency",
        "",
        f"- Vector top-20 RPC retrieval p50/p95: `{summary['latency_ms']['vector_top20_p50']:.3f}` / `{summary['latency_ms']['vector_top20_p95']:.3f}` ms.",
        f"- OR-FTS top-10 p50/p95: `{summary['latency_ms']['lexical_top10_p50']:.3f}` / `{summary['latency_ms']['lexical_top10_p95']:.3f}` ms.",
        f"- Union construction p50/p95: `{summary['latency_ms']['union_p50']:.3f}` / `{summary['latency_ms']['union_p95']:.3f}` ms.",
        "",
        "## Decision",
        "",
        f"**{summary['classification']}** — {summary['decision_reason']}",
        "",
        "This remains a pilot/exploratory candidate-coverage result. No arm is adopted canonically here and no reranker was invoked.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    corpus, records, vectors = validate_frozen_inputs()
    settings = get_settings()
    canonical_remote_state = read_remote_state(settings)
    fts_or_security = _read_fts_or_security(settings)
    adapter = LlamaV2QueryEmbeddingAdapter(base_url=settings.llama_embedding_base_url)
    lexical_retriever = CanonicalV2OrLexicalRetriever(settings=settings)

    lexical_traces: list[dict[str, Any]] = []
    union_traces: list[dict[str, Any]] = []
    vector20_latencies: list[float] = []
    lexical_latencies: list[float] = []
    union_latencies: list[float] = []
    exact_vector50_hit: list[int] = []
    exact_vector50_recall: list[float] = []
    exact_vector20_hit: list[int] = []
    exact_vector20_recall: list[float] = []
    lexical_hit5: list[int] = []
    lexical_hit10: list[int] = []
    lexical_recall5: list[float] = []
    lexical_recall10: list[float] = []
    vector20_hit20: list[int] = []
    vector20_recall20: list[float] = []
    union_hit: list[int] = []
    union_recall: list[float] = []
    target_details: dict[str, Any] | None = None

    for record in records:
        evaluation_id = record["evaluation_id"]
        scope = normalize_specialist_scope(record["specialist_scope"])
        gold_ids = list(record["expected_canonical_chunk_ids"])

        query_vector = adapter.embed_query(record["query"])
        vector_retriever = CanonicalV2Retriever(
            settings=settings,
            embedding_adapter=_StaticQueryAdapter(query_vector),
        )
        vector_started = time.perf_counter()
        vector_results, vector_timing = vector_retriever.retrieve_with_timing(
            record["query"], scope, k=VECTOR20_DEPTH
        )
        vector_elapsed_ms = (time.perf_counter() - vector_started) * 1000
        if len(vector_results) != VECTOR20_DEPTH:
            raise CandidateGenerationAuditError(
                f"{evaluation_id} vector RPC returned {len(vector_results)} rows, expected 20"
            )
        for result in vector_results:
            validate_result_contract(result, corpus, scope)
        vector20_ids = [result.canonical_chunk_id for result in vector_results]
        if len(set(vector20_ids)) != VECTOR20_DEPTH:
            raise CandidateGenerationAuditError(f"{evaluation_id} vector IDs are not unique")
        vector20_latencies.append(vector_timing.retrieval_ms)
        vector20_cov = _coverage(vector20_ids, gold_ids, "20")
        vector20_hit20.append(int(vector20_cov["hit"]))
        vector20_recall20.append(float(vector20_cov["recall"]))

        exact_ranked_results = exact_ranked(corpus, vectors, query_vector, scope)
        exact50 = exact_ranked_results[:VECTOR50_DEPTH]
        exact50_ids = [item["canonical_chunk_id"] for item in exact50]
        exact20_cov = _coverage(exact50_ids[:VECTOR20_DEPTH], gold_ids, "20")
        exact50_cov = _coverage(exact50_ids, gold_ids, "50")
        exact_vector20_hit.append(int(exact20_cov["hit"]))
        exact_vector20_recall.append(float(exact20_cov["recall"]))
        exact_vector50_hit.append(int(exact50_cov["hit"]))
        exact_vector50_recall.append(float(exact50_cov["recall"]))

        lexical_started = time.perf_counter()
        lexical_results, lexical_timing = lexical_retriever.retrieve_with_timing(
            record["query"], scope, k=LEXICAL10_DEPTH
        )
        lexical_elapsed_ms = (time.perf_counter() - lexical_started) * 1000
        lexical_ids = [result.canonical_chunk_id for result in lexical_results]
        if len(set(lexical_ids)) != len(lexical_ids):
            raise CandidateGenerationAuditError(f"{evaluation_id} lexical IDs are not unique")
        for result in lexical_results:
            _validate_lexical_result(result, corpus, scope)
        lexical_latencies.append(lexical_timing.retrieval_ms)
        lexical_cov5 = _coverage(lexical_ids[:5], gold_ids, "5")
        lexical_cov10 = _coverage(lexical_ids[:10], gold_ids, "10")
        lexical_hit5.append(int(lexical_cov5["hit"]))
        lexical_hit10.append(int(lexical_cov10["hit"]))
        lexical_recall5.append(float(lexical_cov5["recall"]))
        lexical_recall10.append(float(lexical_cov10["recall"]))

        union_started = time.perf_counter()
        union_ids = build_candidate_union(vector20_ids, lexical_ids)
        union_elapsed_ms = (time.perf_counter() - union_started) * 1000
        union_latencies.append(union_elapsed_ms)
        if not set(vector20_ids).issubset(union_ids):
            raise CandidateGenerationAuditError(f"{evaluation_id} lost vector20 candidates in union")
        if len(union_ids) > VECTOR20_DEPTH + LEXICAL10_DEPTH:
            raise CandidateGenerationAuditError(f"{evaluation_id} union exceeds 30 candidates")
        union_cov = _coverage(union_ids, gold_ids, "union")
        union_hit.append(int(union_cov["hit"]))
        union_recall.append(float(union_cov["recall"]))

        vector_ranks = _gold_ranks(vector20_ids, gold_ids, ">20")
        exact_ranks = _gold_ranks(exact50_ids, gold_ids, ">50")
        lexical_ranks = _gold_ranks(lexical_ids, gold_ids, ">10")
        union_ranks = _gold_ranks(union_ids, gold_ids, ">union")
        vector_trace = {
            "evaluation_id": evaluation_id,
            "query": record["query"],
            "specialist_scope": scope,
            "gold_canonical_chunk_ids": gold_ids,
            "vector20_ids": vector20_ids,
            "vector20_results": [_citation(result, rank, corpus) for rank, result in enumerate(vector_results, 1)],
            "exact_vector50_ids": exact50_ids,
            "exact_vector50_scores": [item["similarity"] for item in exact50],
            "exact_vector50_gold_ranks": exact_ranks,
            "vector20_gold_ranks": vector_ranks,
            "vector20_coverage": vector20_cov,
            "exact_vector50_coverage": exact50_cov,
            "latency_ms": {"vector_rpc": vector_timing.retrieval_ms, "vector_total": vector_elapsed_ms},
            "candidate_source": "canonical_vector_rpc_plus_offline_exact_oracle",
            "hnsw_top50_requested": False,
            "reranker_used": False,
            "fts_used": False,
        }
        lexical_trace = {
            "evaluation_id": evaluation_id,
            "query": record["query"],
            "specialist_scope": scope,
            "gold_canonical_chunk_ids": gold_ids,
            "query_tokens": build_or_tsquery(record["query"]),
            "lexical_top10_ids": lexical_ids,
            "lexical_results": [_citation(result, rank, corpus) for rank, result in enumerate(lexical_results, 1)],
            "gold_ranks": lexical_ranks,
            "coverage_at_5": lexical_cov5,
            "coverage_at_10": lexical_cov10,
            "latency_ms": {"fts_rpc": lexical_timing.retrieval_ms, "fts_total": lexical_elapsed_ms},
            "rpc": "public.match_policy_chunks_fts_or",
            "fts_config": "simple",
            "ranking": "ts_rank_cd DESC, canonical_chunk_id ASC",
            "candidate_depth": LEXICAL10_DEPTH,
            "reranker_used": False,
            "scope_contract_satisfied": True,
            "v2_only": True,
        }
        union_trace = {
            "evaluation_id": evaluation_id,
            "query": record["query"],
            "specialist_scope": scope,
            "gold_canonical_chunk_ids": gold_ids,
            "vector20_ids": vector20_ids,
            "lexical10_ids": lexical_ids,
            "union_ids": union_ids,
            "union_size": len(union_ids),
            "gold_ranks_in_union": union_ranks,
            "union_coverage": union_cov,
            "vector20_preserved": set(vector20_ids).issubset(union_ids),
            "score_fusion": False,
            "reranker_used": False,
            "latency_ms": {"union_construction": union_elapsed_ms},
        }
        lexical_traces.append(lexical_trace)
        union_traces.append(union_trace)

        if evaluation_id == TARGET_ID:
            target_id = gold_ids[0]
            lexical_rank = lexical_ranks[target_id]
            target_details = {
                "evaluation_id": evaluation_id,
                "gold_canonical_chunk_id": target_id,
                "exact_vector_rank": exact_ranks[target_id],
                "vector20_present": target_id in vector20_ids,
                "vector50_present": target_id in exact50_ids,
                "lexical_rank": lexical_rank,
                "union_present": target_id in union_ids,
                "lexical_top10": [
                    {"rank": rank, "canonical_chunk_id": result.canonical_chunk_id, "article": result.locator.get("article")}
                    for rank, result in enumerate(lexical_results, 1)
                ],
            }

    if len(lexical_traces) != EXPECTED_QUERY_COUNT or len(union_traces) != EXPECTED_QUERY_COUNT:
        raise CandidateGenerationAuditError("candidate traces must contain exactly 25 records")
    if target_details is None:
        raise CandidateGenerationAuditError("stage12a-024 trace missing")
    if target_details["exact_vector_rank"] != 49:
        raise CandidateGenerationAuditError(
            f"stage12a-024 exact vector rank changed: {target_details['exact_vector_rank']}"
        )

    comparison = {
        "vector_top20": {
            "hit": _mean(vector20_hit20),
            "recall": _mean(vector20_recall20),
            "hit_at_20": _mean(vector20_hit20),
            "recall_at_20": _mean(vector20_recall20),
            "mean_candidate_count": float(VECTOR20_DEPTH),
        },
        "vector_top50_exact_diagnostic": {
            "hit": _mean(exact_vector50_hit),
            "recall": _mean(exact_vector50_recall),
            "hit_at_20": _mean(exact_vector20_hit),
            "recall_at_20": _mean(exact_vector20_recall),
            "hit_at_50": _mean(exact_vector50_hit),
            "recall_at_50": _mean(exact_vector50_recall),
            "mean_candidate_count": float(VECTOR50_DEPTH),
        },
        "lexical_or_top10": {
            "hit": _mean(lexical_hit10),
            "recall": _mean(lexical_recall10),
            "hit_at_10": _mean(lexical_hit10),
            "recall_at_10": _mean(lexical_recall10),
            "mean_candidate_count": _mean(trace["coverage_at_10"]["candidate_count"] for trace in lexical_traces),
        },
        "vector20_plus_lexical10_union": {
            "hit": _mean(union_hit),
            "recall": _mean(union_recall),
            "hit_at_union": _mean(union_hit),
            "recall_at_union": _mean(union_recall),
            "mean_candidate_count": _mean(trace["union_size"] for trace in union_traces),
            "min_candidate_count": min(trace["union_size"] for trace in union_traces),
            "max_candidate_count": max(trace["union_size"] for trace in union_traces),
        },
    }
    if comparison["vector_top20"]["hit"] != 0.96 or comparison["vector_top20"]["recall"] != 0.96:
        raise CandidateGenerationAuditError("frozen vector top20 coverage did not reproduce 0.96")
    if not all(trace["vector20_preserved"] for trace in union_traces):
        raise CandidateGenerationAuditError("union lost a vector top20 candidate")

    lexical_nonempty = sum(bool(trace["lexical_top10_ids"]) for trace in lexical_traces)
    queries_at_least_10 = sum(len(trace["lexical_top10_ids"]) >= LEXICAL10_DEPTH for trace in lexical_traces)
    if lexical_nonempty == 0:
        raise CandidateGenerationAuditError("corrected OR-FTS returned zero candidates for every query")

    if target_details["union_present"] and comparison["vector_top20"]["hit"] == 0.96:
        classification = "A — LEXICAL UNION PROMISING"
        reason = "The Vector20 + OR-FTS10 union supplies the known missing gold while preserving every vector20 candidate."
    elif target_details["vector50_present"]:
        classification = "B — VECTOR DEPTH ONLY"
        reason = "The exact vector depth diagnostic supplies the missing gold, while the fixed OR-FTS10 arm does not."
    else:
        classification = "C — NEITHER USEFUL"
        reason = "Neither fixed alternative supplies the missing gold under the stated diagnostic contract."

    # Real-data scope smoke: choose a canonical synthetic chunk whose source
    # declares Credit but not CollateralAppraisal, then query its own frozen
    # text through the same deterministic OR-FTS RPC.  This checks routing,
    # not relevance labels, and does not enter any candidate metric.
    scoped_probe_row = next(
        row
        for row in corpus.rows
        if corpus.sources[row["source_id"]]["synthetic"]
        and "Credit" in corpus.sources[row["source_id"]].get("agent_scopes", [])
        and "CollateralAppraisal"
        not in corpus.sources[row["source_id"]].get("agent_scopes", [])
    )
    scoped_probe_id = scoped_probe_row["canonical_chunk_id"]
    scoped_probe_query = scoped_probe_row["content"]
    credit_probe = lexical_retriever.retrieve(scoped_probe_query, "credit", k=10)
    collateral_probe = lexical_retriever.retrieve(
        scoped_probe_query, "collateral_appraisal", k=10
    )
    credit_probe_ids = [item.canonical_chunk_id for item in credit_probe]
    collateral_probe_ids = [item.canonical_chunk_id for item in collateral_probe]
    if scoped_probe_id not in credit_probe_ids or scoped_probe_id in collateral_probe_ids:
        raise CandidateGenerationAuditError(
            "real OR-FTS scoped leakage probe failed"
        )

    summary = {
        "stage": "13C1",
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "classification": classification,
        "decision_reason": reason,
        "identity": {
            "gold_path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"),
            "gold_sha256": sha256_file(GOLD_PATH),
            "corpus_name": "policy-corpus-v2",
            "corpus_version": "V2",
            "corpus_chunk_count": len(corpus.rows),
            "corpus_unique_id_count": len(corpus.by_id),
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_model": "Qwen3-Embedding-0.6B",
            "embedding_dimension": 1024,
            "embedding_artifact_sha256": sha256_file(ROOT / "dataset/embeddings/v2/embeddings.parquet"),
            "embedding_manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
        },
        "configuration": {
            "vector_top20": {"source": "public.match_policy_chunks", "depth": VECTOR20_DEPTH},
            "vector_top50": {"source": "offline_exact_cosine_oracle", "depth": VECTOR50_DEPTH, "hnsw_requested": False},
            "lexical_or_top10": {
                "source": "public.match_policy_chunks_fts_or",
                "depth": LEXICAL10_DEPTH,
                "text_config": "simple",
                "indexed_fields": ["title", "heading_path", "content"],
                "query": "deterministic NFC + casefold tokens joined by |",
                "ranking": "ts_rank_cd DESC, canonical_chunk_id ASC",
            },
            "union": {"vector_depth": VECTOR20_DEPTH, "lexical_depth": LEXICAL10_DEPTH, "score_fusion": False, "reranker": False},
        },
        "comparison": comparison,
        "lexical": {
            "queries_with_any_results": lexical_nonempty,
            "queries_with_at_least_10": queries_at_least_10,
            "hit_at_5": _mean(lexical_hit5),
            "hit_at_10": _mean(lexical_hit10),
            "recall_at_5": _mean(lexical_recall5),
            "recall_at_10": _mean(lexical_recall10),
        },
        "stage12a_024": target_details,
        "latency_ms": {
            "vector_top20_p50": _percentile(vector20_latencies, 50),
            "vector_top20_p95": _percentile(vector20_latencies, 95),
            "lexical_top10_p50": _percentile(lexical_latencies, 50),
            "lexical_top10_p95": _percentile(lexical_latencies, 95),
            "union_p50": _percentile(union_latencies, 50),
            "union_p95": _percentile(union_latencies, 95),
        },
        "remote_canonical_state": canonical_remote_state,
        "fts_or_security": fts_or_security,
        "real_scope_isolation_probe": {
            "probe_chunk_id": scoped_probe_id,
            "authorized_scope": "credit",
            "authorized_present": True,
            "unauthorized_scope": "collateral_appraisal",
            "unauthorized_present": False,
        },
        "guardrails": {
            "gold_modified": False,
            "corpus_modified": False,
            "embeddings_modified": False,
            "reranker_used": False,
            "hnsw_top50_requested": False,
            "hnsw_settings_modified": False,
            "plainto_tsquery_full_question_used": False,
            "query_expansion": False,
            "query_rewrite": False,
            "score_fusion": False,
            "v2_only": True,
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    LEXICAL_TRACE_PATH.write_text(
        "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in lexical_traces),
        encoding="utf-8",
    )
    UNION_TRACE_PATH.write_text(
        "".join(json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n" for item in union_traces),
        encoding="utf-8",
    )
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.write_text(_build_doc(summary), encoding="utf-8")
    print(json.dumps({
        "summary": str(SUMMARY_PATH),
        "lexical_traces": str(LEXICAL_TRACE_PATH),
        "union_traces": str(UNION_TRACE_PATH),
        "classification": classification,
        "comparison": comparison,
        "lexical": summary["lexical"],
        "stage12a_024": target_details,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
