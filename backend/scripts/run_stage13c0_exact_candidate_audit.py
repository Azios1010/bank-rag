"""Audit the exact vector rank behind the Stage 13C0 candidate miss.

This is an offline diagnostic, not a replacement retriever.  It obtains query
vectors from the canonical llama.cpp adapter, computes an exact cosine oracle
over the frozen parquet vectors, and compares that oracle with the unchanged
Supabase HNSW RPC.  It never changes the corpus, index settings, or gold.
"""

from __future__ import annotations

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

import pyarrow.parquet as pq  # noqa: E402

from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import (  # noqa: E402
    LlamaV2QueryEmbeddingAdapter,
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
from scripts.run_stage13b0_candidate_recall import (  # noqa: E402
    read_remote_state,
    validate_result_contract,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
PARQUET_PATH = ROOT / "dataset/embeddings/v2/embeddings.parquet"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
SUMMARY_PATH = RESULTS_DIR / "exact-candidate-audit-v2.json"
DOC_PATH = ROOT / "docs/STAGE-13C0-EXACT-CANDIDATE-AUDIT.md"

TARGET_ID = "stage12a-024"
OPTIONAL_MISS_IDS = ("stage12a-007", "stage12a-008", "stage12a-013")
TARGET_SCOPE = "collateral_appraisal"
CANONICAL_RPC = "public.match_policy_chunks"
QUERY_INSTRUCTION = LlamaV2QueryEmbeddingAdapter.QUERY_INSTRUCTION
VECTOR_DIMENSION = LlamaV2QueryEmbeddingAdapter.DIMENSION
HNSW_CANDIDATE_DEPTH = 20
NORM_TOLERANCE = 1e-4


class ExactCandidateAuditError(RuntimeError):
    """Raised when the diagnostic contract cannot be established."""


def _scope_slug(value: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", value).casefold()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _compact(value: str) -> str:
    return " ".join(value.split())


def _excerpt(value: str, limit: int = 420) -> str:
    compact = _compact(value)
    if len(compact) <= limit:
        return compact
    return compact[:limit].rsplit(" ", 1)[0] + "…"


def _validate_vector(vector: Iterable[object], label: str) -> list[float]:
    values = list(vector)
    if len(values) != VECTOR_DIMENSION:
        raise ExactCandidateAuditError(
            f"{label} has {len(values)} dimensions, expected {VECTOR_DIMENSION}"
        )
    if any(isinstance(value, bool) or not isinstance(value, (int, float)) for value in values):
        raise ExactCandidateAuditError(f"{label} contains a non-numeric value")
    result = [float(value) for value in values]
    if not all(math.isfinite(value) for value in result):
        raise ExactCandidateAuditError(f"{label} contains a non-finite value")
    norm = math.sqrt(math.fsum(value * value for value in result))
    if not math.isfinite(norm) or norm == 0.0:
        raise ExactCandidateAuditError(f"{label} is zero or non-finite")
    if not math.isclose(norm, 1.0, rel_tol=0.0, abs_tol=NORM_TOLERANCE):
        raise ExactCandidateAuditError(f"{label} is not unit-normalized: {norm}")
    return result


def load_frozen_vectors(corpus: FrozenCorpusV2) -> dict[str, list[float]]:
    """Load and validate exactly the frozen Stage 10 parquet vectors."""

    if sha256_file(PARQUET_PATH) != EXPECTED_EMBEDDING_ARTIFACT_SHA256:
        raise ExactCandidateAuditError("embedding parquet SHA-256 changed")
    table = pq.read_table(
        PARQUET_PATH,
        columns=["chunk_id", "embedding", "embedding_dimension", "normalized", "embedding_model"],
    )
    if table.num_rows != 1610:
        raise ExactCandidateAuditError(f"embedding parquet has {table.num_rows} rows, expected 1610")
    dimensions = set(table.column("embedding_dimension").to_pylist())
    if dimensions != {VECTOR_DIMENSION}:
        raise ExactCandidateAuditError(f"unexpected parquet dimensions: {dimensions}")
    if set(table.column("normalized").to_pylist()) != {True}:
        raise ExactCandidateAuditError("parquet vectors are not marked normalized")
    if set(table.column("embedding_model").to_pylist()) != {"Qwen3-Embedding-0.6B"}:
        raise ExactCandidateAuditError("parquet embedding model identity changed")

    ids = table.column("chunk_id").to_pylist()
    if any(not isinstance(chunk_id, str) or not chunk_id for chunk_id in ids):
        raise ExactCandidateAuditError("parquet contains an invalid chunk_id")
    if len(set(ids)) != len(ids):
        raise ExactCandidateAuditError("parquet contains duplicate chunk_id values")
    if set(ids) != set(corpus.by_id):
        raise ExactCandidateAuditError("parquet canonical ID set differs from frozen corpus")

    vectors = table.column("embedding").to_pylist()
    result: dict[str, list[float]] = {}
    for chunk_id, vector in zip(ids, vectors, strict=True):
        result[chunk_id] = _validate_vector(vector, f"embedding {chunk_id}")
    if len(result) != 1610:
        raise ExactCandidateAuditError("validated parquet vector count is not 1610")
    return result


def validate_frozen_inputs() -> tuple[FrozenCorpusV2, list[dict[str, Any]], dict[str, list[float]]]:
    corpus = FrozenCorpusV2()
    records = validate_gold_identity(corpus)
    if len(records) != 25 or {record["status"] for record in records} != {"REVIEWED"}:
        raise ExactCandidateAuditError("released gold is not exactly 25 REVIEWED records")
    expected_files = {
        ROOT / "dataset/manifests/policy-corpus-v2-manifest.json": EXPECTED_CORPUS_MANIFEST_SHA256,
        ROOT / "dataset/embeddings/v2/embedding-manifest.json": EXPECTED_EMBEDDING_MANIFEST_SHA256,
        GOLD_PATH: EXPECTED_GOLD_SHA256,
    }
    for path, expected in expected_files.items():
        if sha256_file(path) != expected:
            raise ExactCandidateAuditError(f"frozen identity changed: {path}")
    if len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise ExactCandidateAuditError("frozen corpus is not exactly 1610 unique chunks")
    target = next(record for record in records if record["evaluation_id"] == TARGET_ID)
    if target["specialist_scope"] != TARGET_SCOPE:
        raise ExactCandidateAuditError("stage12a-024 scope changed")
    if target["expected_canonical_chunk_ids"] != [
        "e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9"
    ]:
        raise ExactCandidateAuditError("stage12a-024 approved gold ID changed")
    vectors = load_frozen_vectors(corpus)
    return corpus, records, vectors


def eligible_ids(corpus: FrozenCorpusV2, requested_scope: str) -> list[str]:
    """Build the canonical SHARED/SCOPED eligibility set without ranking."""

    scope = normalize_specialist_scope(requested_scope)
    eligible: list[str] = []
    for row in corpus.rows:
        source = corpus.sources[row["source_id"]]
        if not source["synthetic"]:
            eligible.append(row["canonical_chunk_id"])
            continue
        allowed = {_scope_slug(value) for value in source.get("agent_scopes", [])}
        if scope in allowed:
            eligible.append(row["canonical_chunk_id"])
    return eligible


def exact_cosine(left: Iterable[float], right: Iterable[float]) -> float:
    """Compute cosine with stable summation for the offline oracle."""

    left_values = list(left)
    right_values = list(right)
    if len(left_values) != len(right_values):
        raise ExactCandidateAuditError("cosine vectors have different dimensions")
    left_norm = math.sqrt(math.fsum(value * value for value in left_values))
    right_norm = math.sqrt(math.fsum(value * value for value in right_values))
    if left_norm == 0.0 or right_norm == 0.0:
        raise ExactCandidateAuditError("cosine cannot use a zero vector")
    return math.fsum(a * b for a, b in zip(left_values, right_values, strict=True)) / (
        left_norm * right_norm
    )


def exact_ranked(
    corpus: FrozenCorpusV2,
    vectors: dict[str, list[float]],
    query_vector: list[float],
    requested_scope: str,
) -> list[dict[str, Any]]:
    ranked: list[dict[str, Any]] = []
    for chunk_id in eligible_ids(corpus, requested_scope):
        row = corpus.by_id[chunk_id]
        source = corpus.sources[row["source_id"]]
        score = exact_cosine(query_vector, vectors[chunk_id])
        ranked.append(
            {
                "canonical_chunk_id": chunk_id,
                "similarity": score,
                "source_id": row["source_id"],
                "version_id": row["version_id"],
                "title": source["title"],
                "article": row.get("article"),
                "heading_path": row.get("heading_path", []),
                "locator": {
                    "article": row.get("article"),
                    "clause": row.get("clause"),
                    "point": row.get("point"),
                    "page_start": row.get("page_start"),
                    "page_end": row.get("page_end"),
                },
                "visibility": "SCOPED" if source["synthetic"] else "SHARED",
                "source_type": (
                    "synthetic_internal_policy" if source["synthetic"] else "real_regulation"
                ),
                "content_excerpt": _excerpt(row["content"]),
            }
        )
    ranked.sort(key=lambda item: (-item["similarity"], item["canonical_chunk_id"]))
    for rank, item in enumerate(ranked, 1):
        item["rank"] = rank
    return ranked


class _StaticQueryAdapter:
    """Feed the captured canonical vector into the unchanged RPC client."""

    def __init__(self, vector: list[float]) -> None:
        self.vector = list(vector)

    def embed_query(self, query: str) -> list[float]:
        if not isinstance(query, str) or not query.strip():
            raise ValueError("query must be a non-empty string")
        return list(self.vector)


def _result_summary(result: Any, rank: int, corpus: FrozenCorpusV2) -> dict[str, Any]:
    row = corpus.by_id[result.canonical_chunk_id]
    source = corpus.sources[row["source_id"]]
    return {
        "rank": rank,
        "canonical_chunk_id": result.canonical_chunk_id,
        "similarity": result.similarity,
        "source_id": result.document_source_id,
        "version_id": result.document_version_id,
        "title": result.document_title,
        "article": row.get("article"),
        "heading_path": result.heading_path,
        "locator": result.locator,
        "visibility": result.visibility,
        "source_type": "synthetic_internal_policy" if source["synthetic"] else "real_regulation",
        "content_excerpt": _excerpt(row["content"]),
    }


def _gold_rank(ranked: list[dict[str, Any]], gold_ids: list[str]) -> dict[str, int | str]:
    ranks = {item["canonical_chunk_id"]: item["rank"] for item in ranked}
    return {chunk_id: ranks.get(chunk_id, ">20") for chunk_id in gold_ids}


def _top_items(ranked: list[dict[str, Any]], count: int) -> list[dict[str, Any]]:
    return [
        {
            key: item[key]
            for key in (
                "rank",
                "canonical_chunk_id",
                "similarity",
                "source_id",
                "version_id",
                "title",
                "article",
                "heading_path",
                "locator",
                "visibility",
                "source_type",
                "content_excerpt",
            )
        }
        for item in ranked[:count]
    ]


def _target_analysis(
    corpus: FrozenCorpusV2,
    target: dict[str, Any],
    query_vector: list[float],
    vectors: dict[str, list[float]],
    hnsw_results: list[Any],
    hnsw_timing: Any,
) -> dict[str, Any]:
    requested_scope = normalize_specialist_scope(target["specialist_scope"])
    exact = exact_ranked(corpus, vectors, query_vector, requested_scope)
    gold_ids = list(target["expected_canonical_chunk_ids"])
    exact_ranks = _gold_rank(exact, gold_ids)
    exact_rank_values = [rank for rank in exact_ranks.values() if isinstance(rank, int)]
    exact_gold_rank = min(exact_rank_values) if exact_rank_values else ">20"
    exact_by_id = {item["canonical_chunk_id"]: item for item in exact}
    gold_id = gold_ids[0]
    if gold_id not in exact_by_id:
        raise ExactCandidateAuditError("approved 024 gold ID is absent from exact eligible set")

    validate_results: list[dict[str, Any]] = []
    hnsw_ids: list[str] = []
    for rank, result in enumerate(hnsw_results, 1):
        validate_result_contract(result, corpus, requested_scope)
        hnsw_ids.append(result.canonical_chunk_id)
        validate_results.append(_result_summary(result, rank, corpus))
    if len(hnsw_results) != HNSW_CANDIDATE_DEPTH:
        raise ExactCandidateAuditError(
            f"canonical RPC returned {len(hnsw_results)} rows, expected {HNSW_CANDIDATE_DEPTH}"
        )
    if len(set(hnsw_ids)) != len(hnsw_ids):
        raise ExactCandidateAuditError("canonical RPC returned duplicate IDs")

    exact_top20 = exact[:HNSW_CANDIDATE_DEPTH]
    exact_ids = [item["canonical_chunk_id"] for item in exact_top20]
    exact_set = set(exact_ids)
    hnsw_set = set(hnsw_ids)
    exact_gold_score = exact_by_id[gold_id]["similarity"]
    rank10_score = exact[9]["similarity"]
    rank20_score = exact[19]["similarity"]
    margin = exact_gold_score - rank20_score
    if isinstance(exact_gold_rank, int) and exact_gold_rank <= 20 and gold_id not in hnsw_set:
        classification = "ANN_FAILURE"
    elif isinstance(exact_gold_rank, int) and exact_gold_rank > 20:
        classification = "EMBEDDING_CANDIDATE_FAILURE"
    else:
        classification = "ANN_FAILURE"

    return {
        "evaluation_id": target["evaluation_id"],
        "question": target["query"],
        "scope": requested_scope,
        "gold_canonical_chunk_ids": gold_ids,
        "gold_source": target["document"],
        "eligible_chunk_count": len(eligible_ids(corpus, requested_scope)),
        "exact_gold_ranks": exact_ranks,
        "gold_exact_rank": exact_gold_rank,
        "gold_exact_cosine": exact_gold_score,
        "rank10_cosine": rank10_score,
        "rank20_cosine": rank20_score,
        "gold_minus_rank20_cosine": margin,
        "exact_top1": _top_items(exact, 1),
        "exact_top5": _top_items(exact, 5),
        "exact_top10": _top_items(exact, 10),
        "exact_top20": _top_items(exact, 20),
        "exact_top50_diagnostic_only": _top_items(exact, 50),
        "hnsw_gold_rank": _gold_rank(validate_results, gold_ids),
        "hnsw_top20": validate_results,
        "top20_set_overlap_count": len(exact_set & hnsw_set),
        "top20_set_overlap_fraction": len(exact_set & hnsw_set) / HNSW_CANDIDATE_DEPTH,
        "top20_same_position_count": sum(
            left == right for left, right in zip(exact_ids, hnsw_ids, strict=True)
        ),
        "exact_top20_missing_from_hnsw": [chunk_id for chunk_id in exact_ids if chunk_id not in hnsw_set],
        "hnsw_top20_not_in_exact_top20": [chunk_id for chunk_id in hnsw_ids if chunk_id not in exact_set],
        "classification": classification,
        "hnsw_latency_ms": {
            "embedding": hnsw_timing.embedding_ms,
            "retrieval": hnsw_timing.retrieval_ms,
        },
    }


def _miss_exact_rank(
    corpus: FrozenCorpusV2,
    record: dict[str, Any],
    query_vector: list[float],
    vectors: dict[str, list[float]],
) -> dict[str, Any]:
    ranked = exact_ranked(corpus, vectors, query_vector, record["specialist_scope"])
    gold_ids = list(record["expected_canonical_chunk_ids"])
    ranks = _gold_rank(ranked, gold_ids)
    return {
        "evaluation_id": record["evaluation_id"],
        "scope": normalize_specialist_scope(record["specialist_scope"]),
        "gold_canonical_chunk_ids": gold_ids,
        "exact_gold_ranks": ranks,
        "first_exact_gold_rank": min(
            (rank for rank in ranks.values() if isinstance(rank, int)), default=">20"
        ),
    }


def _markdown(summary: dict[str, Any]) -> str:
    target = summary["target_analysis"]
    gold_item = next(
        item
        for item in target["exact_top50_diagnostic_only"]
        if item["canonical_chunk_id"] == target["gold_canonical_chunk_ids"][0]
    )
    exact_gold = target["gold_exact_cosine"]
    rank20 = target["rank20_cosine"]
    margin = target["gold_minus_rank20_cosine"]
    lines = [
        "# Stage 13C0 — Exact Candidate-Generation Failure Audit",
        "",
        "Status: completed read-only diagnostic. No HNSW setting, corpus, embedding, gold, or production retriever was changed.",
        "",
        "## Frozen identity",
        "",
        f"- Gold: `{summary['identity']['gold_sha256']}`",
        f"- Embedding parquet: `{summary['identity']['embedding_artifact_sha256']}`",
        f"- Corpus: `policy-corpus-v2`, 1,610 unique canonical chunks",
        f"- Embedding: `Qwen3-Embedding-0.6B`, 1,024D, unit-normalized",
        "",
        "## Query under audit",
        "",
        f"- Evaluation ID: `{target['evaluation_id']}`",
        f"- Scope: `{target['scope']}`",
        f"- Question: {target['question']}",
        f"- Approved gold: `{target['gold_canonical_chunk_ids'][0]}`",
        f"- Eligible canonical chunks: **{target['eligible_chunk_count']}** (SHARED plus explicitly authorized SCOPED)",
        "",
        "## Exact cosine oracle",
        "",
        f"- Gold exact rank: **{target['gold_exact_rank']}**",
        f"- Gold cosine: `{exact_gold:.9f}`",
        f"- Rank-10 cosine: `{target['rank10_cosine']:.9f}`",
        f"- Rank-20 cosine: `{rank20:.9f}`",
        f"- Gold minus rank-20: `{margin:.9f}`",
        f"- Top-1 exact candidate: `{target['exact_top1'][0]['canonical_chunk_id']}` — Article {target['exact_top1'][0]['article']} ({target['exact_top1'][0]['title']})",
        "",
        "### Exact top five",
        "",
        "| Rank | Canonical ID | Cosine | Article | Source |",
        "|---:|---|---:|---|---|",
    ]
    for item in target["exact_top5"]:
        lines.append(
            f"| {item['rank']} | `{item['canonical_chunk_id']}` | {item['similarity']:.9f} | {item['article'] or '—'} | {item['title']} |"
        )
    lines += [
        "",
        "## Unchanged canonical HNSW comparison",
        "",
        f"- Observed `hnsw.ef_search`: `{summary['remote_state'].get('hnsw_ef_search')}` (read-only; unchanged)",
        f"- Requested and returned rows: `{HNSW_CANDIDATE_DEPTH}`",
        f"- Gold HNSW rank: `{target['hnsw_gold_rank'][target['gold_canonical_chunk_ids'][0]]}`",
        f"- Exact/HNSW top-20 set overlap: `{target['top20_set_overlap_count']}/20` ({target['top20_set_overlap_fraction']:.2%})",
        f"- Same-position count: `{target['top20_same_position_count']}/20`",
        f"- Exact top-20 IDs missing from HNSW: `{len(target['exact_top20_missing_from_hnsw'])}`",
        "",
        "## Root-cause classification",
        "",
        f"**{target['classification']}**",
        "",
        "The approved gold is not in the HNSW top-20. The exact oracle rank and score determine whether that is semantic under-ranking or ANN omission; no index setting was changed to obtain this comparison.",
        "",
        "## Content inspection",
        "",
        "### Approved gold",
        "",
        f"- `{target['gold_canonical_chunk_ids'][0]}` — {target['gold_source']['title']}, Article {gold_item['article']}; the approved passage lists online, paper/direct/postal, and email filing methods and qualifies electronic/email methods for land-related assets under specialized law.",
        f"- Excerpt: {gold_item['content_excerpt']}",
        "",
        "### Exact top-ranked wrong candidates",
        "",
    ]
    for item in target["exact_top5"]:
        if item["canonical_chunk_id"] == target["gold_canonical_chunk_ids"][0]:
            continue
        lines.append(
            f"- Rank {item['rank']}, `{item['canonical_chunk_id']}`, Article {item['article']}: {item['content_excerpt']}"
        )
    lines += [
        "",
        "The top wrong passages are from the same security-registration document and share filing/registration terminology, but concern different procedures or articles. This is consistent with semantic under-ranking at article/chunk granularity rather than a scope leak.",
        "",
        "## Other frozen @5 misses — exact descriptive ranks",
        "",
    ]
    for item in summary["other_misses_exact"]:
        lines.append(f"- `{item['evaluation_id']}`: exact first gold rank `{item['first_exact_gold_rank']}`")
    lines += [
        "",
        "## Method guardrails",
        "",
        "- Query vectors came from the canonical llama.cpp adapter with the frozen instruction/template.",
        "- Exact ranking used frozen parquet vectors, cosine, and canonical ID ascending as the tie-break.",
        "- HNSW comparison used the unchanged `public.match_policy_chunks` RPC at `match_count=20`.",
        "- No FTS, hybrid retrieval, reranker, query rewrite, model download, or benchmark metric was used.",
        "- `exact_top50_diagnostic_only` is an offline oracle view; no HNSW top-50 request was made.",
        "",
        "## Decision",
        "",
        f"**{target['classification']}** — "
        + (
            "the approved gold is semantically below the exact top-20 candidate cutoff; investigate candidate-generation alternatives before changing the retained reranker."
            if target["classification"] == "EMBEDDING_CANDIDATE_FAILURE"
            else "the approved gold is within the exact top-20 but omitted by HNSW; run a separately authorized HNSW configuration experiment."
        ),
        "",
        "OpenCode review status is recorded separately; no verdict is inferred from unavailable reviewer infrastructure.",
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    corpus, records, vectors = validate_frozen_inputs()
    settings = get_settings()
    remote_state = read_remote_state(settings)
    target = next(record for record in records if record["evaluation_id"] == TARGET_ID)
    adapter = LlamaV2QueryEmbeddingAdapter(base_url=settings.llama_embedding_base_url)

    query_started = time.perf_counter()
    target_vector = adapter.embed_query(target["query"])
    target_embedding_ms = (time.perf_counter() - query_started) * 1000
    target_vector = _validate_vector(target_vector, "stage12a-024 query vector")

    static_retriever = CanonicalV2Retriever(
        settings=settings,
        embedding_adapter=_StaticQueryAdapter(target_vector),
    )
    hnsw_started = time.perf_counter()
    hnsw_results, hnsw_timing = static_retriever.retrieve_with_timing(
        target["query"], TARGET_SCOPE, k=HNSW_CANDIDATE_DEPTH
    )
    hnsw_total_ms = (time.perf_counter() - hnsw_started) * 1000
    target_analysis = _target_analysis(
        corpus, target, target_vector, vectors, hnsw_results, hnsw_timing
    )
    target_analysis["query_embedding_latency_ms"] = target_embedding_ms
    target_analysis["hnsw_total_latency_ms"] = hnsw_total_ms

    other_misses: list[dict[str, Any]] = []
    for evaluation_id in OPTIONAL_MISS_IDS:
        record = next(item for item in records if item["evaluation_id"] == evaluation_id)
        vector = _validate_vector(adapter.embed_query(record["query"]), f"{evaluation_id} query vector")
        other_misses.append(_miss_exact_rank(corpus, record, vector, vectors))

    summary = {
        "stage": "13C0",
        "status": "completed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "diagnostic_only": True,
        "identity": {
            "gold_path": str(GOLD_PATH.relative_to(ROOT)).replace("\\", "/"),
            "gold_sha256": _sha256(GOLD_PATH),
            "corpus_name": "policy-corpus-v2",
            "corpus_version": "V2",
            "corpus_chunk_count": len(corpus.rows),
            "corpus_unique_id_count": len(corpus.by_id),
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_model": "Qwen3-Embedding-0.6B",
            "embedding_dimension": VECTOR_DIMENSION,
            "embedding_artifact_path": str(PARQUET_PATH.relative_to(ROOT)).replace("\\", "/"),
            "embedding_artifact_sha256": _sha256(PARQUET_PATH),
            "embedding_manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
        },
        "query_runtime": {
            "backend": "llama.cpp",
            "endpoint": adapter.endpoint,
            "instruction": QUERY_INSTRUCTION,
            "format": "Instruct: {instruction}\\nQuery: {query}",
            "vector_dimension": VECTOR_DIMENSION,
            "norm_tolerance": NORM_TOLERANCE,
        },
        "scope_rule": "visibility=SHARED OR explicit requested-scope authorization",
        "target_analysis": target_analysis,
        "other_misses_exact": other_misses,
        "remote_state": {
            key: value
            for key, value in remote_state.items()
            if key
            in {
                "documents",
                "chunks",
                "distinct_ids",
                "vectors",
                "shared",
                "scoped",
                "scope_rows",
                "corpus_name",
                "corpus_version",
                "corpus_manifest_sha256",
                "embedding_model",
                "embedding_dimension",
                "hnsw_ef_search",
                "enable_indexscan",
                "migration_head",
                "policy_chunk_indexes",
                "vector_rpc_used",
            }
        },
        "guardrails": {
            "rpc": CANONICAL_RPC,
            "rpc_match_count": HNSW_CANDIDATE_DEPTH,
            "exact_top50_is_offline_only": True,
            "hnsw_top50_requested": False,
            "hnsw_settings_modified": False,
            "fts_used": False,
            "hybrid_used": False,
            "reranker_used": False,
            "sentence_transformer_used": False,
            "gold_modified": False,
            "corpus_modified": False,
            "embeddings_modified": False,
        },
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text(_markdown(summary), encoding="utf-8")
    print(json.dumps({
        "summary": str(SUMMARY_PATH),
        "documentation": str(DOC_PATH),
        "classification": target_analysis["classification"],
        "eligible_chunks": target_analysis["eligible_chunk_count"],
        "exact_gold_rank": target_analysis["gold_exact_rank"],
        "hnsw_gold_rank": target_analysis["hnsw_gold_rank"],
        "top20_overlap": target_analysis["top20_set_overlap_count"],
        "other_misses": other_misses,
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
