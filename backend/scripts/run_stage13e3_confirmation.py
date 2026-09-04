"""Stage 13E3: confirmation benchmark for vector top-10 versus top-20.

The benchmark intentionally makes one query-embedding call and one canonical
``match_policy_chunks`` call per query.  Top-10 is the exact prefix of that
single top-20 result, so candidate generation is held constant between arms.
Only the frozen candidate depth supplied to the already-approved llama.cpp
Qwen3 reranker differs.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Iterable

BACKEND_ROOT = Path(__file__).resolve().parents[1]
ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.eval.gold_v2 import CanonicalGoldValidator, FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter  # noqa: E402
from app.eval.llama_v2_reranker import LlamaV2RerankerAdapter  # noqa: E402
from app.eval.metrics import (  # noqa: E402
    binary_ndcg_at_k,
    hit_at_k,
    mrr_at_k,
    percentile,
    recall_at_k,
)
from app.services.supabase_v2_retriever import (  # noqa: E402
    CanonicalV2Retriever,
    normalize_specialist_scope,
)
from scripts.run_stage13b0_candidate_recall import (  # noqa: E402
    read_remote_state,
    validate_result_contract,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-expanded.jsonl"
PILOT_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
CORPUS_MANIFEST_PATH = ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
EMBEDDING_ARTIFACT_PATH = ROOT / "dataset/embeddings/v2/embeddings.parquet"
EMBEDDING_MANIFEST_PATH = ROOT / "dataset/embeddings/v2/embedding-manifest.json"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
CANDIDATE_PATH = RESULTS_DIR / "vector-top20-v2-expanded-candidates.jsonl"
TOP10_SUMMARY_PATH = RESULTS_DIR / "reranker-top10-v2-expanded-summary.json"
TOP10_RUN1_PATH = RESULTS_DIR / "reranker-top10-v2-expanded-run-1-traces.jsonl"
TOP10_RUN2_PATH = RESULTS_DIR / "reranker-top10-v2-expanded-run-2-traces.jsonl"
TOP20_SUMMARY_PATH = RESULTS_DIR / "reranker-top20-v2-expanded-summary.json"
TOP20_RUN1_PATH = RESULTS_DIR / "reranker-top20-v2-expanded-run-1-traces.jsonl"
TOP20_RUN2_PATH = RESULTS_DIR / "reranker-top20-v2-expanded-run-2-traces.jsonl"
SUMMARY_PATH = RESULTS_DIR / "reranker-depth-confirmation-v2-expanded-summary.json"
DOC_PATH = ROOT / "docs/STAGE-13E3-RERANKER-DEPTH-CONFIRMATION.md"

EXPECTED_GOLD_SHA256 = "1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69"
EXPECTED_PILOT_SHA256 = "c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a"
EXPECTED_CORPUS_MANIFEST_SHA256 = "b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a"
EXPECTED_EMBEDDING_ARTIFACT_SHA256 = "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c"
EXPECTED_EMBEDDING_MANIFEST_SHA256 = "cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863"
EXPECTED_QUERY_COUNT = 100
EXPECTED_CHUNK_COUNT = 1610
EXPECTED_VECTOR_CANDIDATES = 20
SUPPORTED_SCOPES = (
    "credit",
    "risk_management",
    "legal_compliance",
    "customer_relationship",
    "collateral_appraisal",
)
K_VALUES = (1, 3, 5)

RERANKER_MODEL_PATH = Path(r"D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf")
RERANKER_MODEL_SHA256 = "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
RERANKER_MODEL_BYTES = 639153184
RERANKER_BUILD = "0.2.0-dev (build 10603, commit c060ca974)"
RERANKER_ENDPOINT = "http://127.0.0.1:8082"
RERANKER_DEVICE = "Vulkan1 / NVIDIA GeForce RTX 2050"
RERANKER_CONTEXT = 4096
RERANKER_PARALLEL = 1
RERANKER_POOLING = "rank"
RERANKER_DOCUMENT_TEMPLATE = "Title: {title}\nSection: {heading_path}\nText:\n{content}"


class Stage13E3Error(RuntimeError):
    """Raised when a frozen confirmation contract is violated."""


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return float(statistics.fmean(values)) if values else 0.0


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _status(value: object) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _gold_ids(record: dict[str, Any]) -> list[str]:
    return list(record["expected_canonical_chunk_ids"])


def _gold_ranks(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, int | None]:
    rank_by_id = {chunk_id: rank for rank, chunk_id in enumerate(retrieved_ids, 1)}
    return {chunk_id: rank_by_id.get(chunk_id) for chunk_id in gold_ids}


def _first_rank(ranks: dict[str, int | None], absent: str) -> int | str:
    present = [rank for rank in ranks.values() if rank is not None]
    return min(present) if present else absent


def metric_values(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, float | int]:
    gold_set = set(gold_ids)
    return {
        f"{metric}@{k}": value
        for k in K_VALUES
        for metric, value in (
            ("hit", hit_at_k(retrieved_ids, gold_set, k)),
            ("recall", recall_at_k(retrieved_ids, gold_set, k)),
            ("mrr", mrr_at_k(retrieved_ids, gold_set, k)),
            ("ndcg", binary_ndcg_at_k(retrieved_ids, gold_set, k)),
        )
    }


def aggregate_metrics(traces: list[dict[str, Any]], field: str) -> dict[str, float]:
    return {
        key: _mean(float(trace[field][key]) for trace in traces)
        for key in (
            f"{metric}@{k}"
            for metric in ("hit", "recall", "mrr", "ndcg")
            for k in K_VALUES
        )
    }


def validate_preflight(corpus: FrozenCorpusV2) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if sha256_file(GOLD_PATH) != EXPECTED_GOLD_SHA256:
        raise Stage13E3Error("expanded gold SHA-256 does not match the frozen identity")
    if sha256_file(PILOT_PATH) != EXPECTED_PILOT_SHA256:
        raise Stage13E3Error("Stage 12A pilot SHA-256 changed")
    expected_files = {
        CORPUS_MANIFEST_PATH: EXPECTED_CORPUS_MANIFEST_SHA256,
        EMBEDDING_ARTIFACT_PATH: EXPECTED_EMBEDDING_ARTIFACT_SHA256,
        EMBEDDING_MANIFEST_PATH: EXPECTED_EMBEDDING_MANIFEST_SHA256,
    }
    for path, expected in expected_files.items():
        if sha256_file(path) != expected:
            raise Stage13E3Error(f"frozen identity changed: {path}")
    if not RERANKER_MODEL_PATH.is_file():
        raise Stage13E3Error(f"local reranker model is missing: {RERANKER_MODEL_PATH}")
    if RERANKER_MODEL_PATH.stat().st_size != RERANKER_MODEL_BYTES:
        raise Stage13E3Error("local reranker model byte size changed")
    if sha256_file(RERANKER_MODEL_PATH) != RERANKER_MODEL_SHA256:
        raise Stage13E3Error("local reranker model SHA-256 changed")

    records = CanonicalGoldValidator(corpus).parse_file(GOLD_PATH)
    if len(records) != EXPECTED_QUERY_COUNT:
        raise Stage13E3Error(f"expected 100 gold records, got {len(records)}")
    if any(_status(record["status"]) != "REVIEWED" for record in records):
        raise Stage13E3Error("expanded gold is not entirely REVIEWED")
    ids = [record["evaluation_id"] for record in records]
    if len(set(ids)) != EXPECTED_QUERY_COUNT:
        raise Stage13E3Error("expanded gold contains duplicate evaluation IDs")
    scopes = [normalize_specialist_scope(record["specialist_scope"]) for record in records]
    if set(scopes) != set(SUPPORTED_SCOPES):
        raise Stage13E3Error(f"unsupported/missing specialist scopes: {sorted(set(scopes))}")
    if any(record["specialist_scope"] == "BankingOperations" for record in records):
        raise Stage13E3Error("BankingOperations is not a supported retrieval scope")
    all_gold = {chunk_id for record in records for chunk_id in _gold_ids(record)}
    if not all_gold.issubset(corpus.by_id):
        raise Stage13E3Error("expanded gold contains a non-V2 canonical ID")
    stage004 = next(record for record in records if record["evaluation_id"] == "stage12a-004")
    expected_004 = {
        "a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c",
        "90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78",
    }
    if set(_gold_ids(stage004)) != expected_004 or len(_gold_ids(stage004)) != 2:
        raise Stage13E3Error("stage12a-004 no longer has its two approved gold IDs")
    if len(corpus.rows) != EXPECTED_CHUNK_COUNT or len(corpus.by_id) != EXPECTED_CHUNK_COUNT:
        raise Stage13E3Error("local frozen Corpus V2 is not 1610 unique chunks")

    remote = read_remote_state(__import__("app.config", fromlist=["get_settings"]).get_settings())
    expected_remote = {
        "documents": 10,
        "chunks": 1610,
        "distinct_ids": 1610,
        "vectors": 1610,
        "shared": 1573,
        "scoped": 37,
        "scope_rows": 125,
        "dimension_failures": 0,
        "null_search_documents": 0,
    }
    for key, value in expected_remote.items():
        if remote.get(key) != value:
            raise Stage13E3Error(f"remote canonical state mismatch for {key}: {remote.get(key)}")
    if remote.get("hnsw_ef_search") != "40":
        raise Stage13E3Error(f"hnsw.ef_search changed: {remote.get('hnsw_ef_search')}")
    if remote.get("corpus_name") != "policy-corpus-v2" or remote.get("corpus_manifest_sha256") != EXPECTED_CORPUS_MANIFEST_SHA256:
        raise Stage13E3Error("remote corpus identity mismatch")
    if remote.get("embedding_model") != "Qwen3-Embedding-0.6B" or remote.get("embedding_dimension") != 1024:
        raise Stage13E3Error("remote embedding profile mismatch")
    return records, remote


def _candidate_result_payload(result: Any, rank: int, corpus: FrozenCorpusV2) -> dict[str, Any]:
    row = corpus.by_id[result.canonical_chunk_id]
    source = corpus.sources[row["source_id"]]
    return {
        "canonical_chunk_id": result.canonical_chunk_id,
        "rank": rank,
        "similarity": float(result.similarity),
        "document_source_id": result.document_source_id,
        "document_version_id": result.document_version_id,
        "document_title": result.document_title,
        "heading_path": result.heading_path,
        "locator": result.locator,
        "namespace": result.namespace,
        "visibility": result.visibility,
        "source_type": "synthetic_internal_policy" if source["synthetic"] else "real_regulation",
    }


def collect_candidates(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    adapter = LlamaV2QueryEmbeddingAdapter()
    retriever = CanonicalV2Retriever(embedding_adapter=adapter)
    traces: list[dict[str, Any]] = []
    for record in records:
        evaluation_id = record["evaluation_id"]
        scope = normalize_specialist_scope(record["specialist_scope"])
        embedding_started = time.perf_counter()
        vector = adapter.embed_query(record["query"])
        embedding_ms = (time.perf_counter() - embedding_started) * 1000
        if len(vector) != 1024 or not all(math.isfinite(value) for value in vector):
            raise Stage13E3Error(f"invalid query vector for {evaluation_id}")
        norm = math.sqrt(sum(value * value for value in vector))
        if not math.isfinite(norm) or norm == 0 or not math.isclose(norm, 1.0, abs_tol=1e-4, rel_tol=0.0):
            raise Stage13E3Error(f"query vector norm invalid for {evaluation_id}: {norm}")
        vector_hash = hashlib.sha256(
            json.dumps(vector, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        retrieval_started = time.perf_counter()
        results = retriever.retrieve_with_query_vector(vector, scope, k=EXPECTED_VECTOR_CANDIDATES)
        retrieval_ms = (time.perf_counter() - retrieval_started) * 1000
        if len(results) != EXPECTED_VECTOR_CANDIDATES:
            raise Stage13E3Error(f"{evaluation_id} returned {len(results)} candidates, expected 20")
        ids = [result.canonical_chunk_id for result in results]
        if len(set(ids)) != EXPECTED_VECTOR_CANDIDATES or any(chunk_id not in corpus.by_id for chunk_id in ids):
            raise Stage13E3Error(f"{evaluation_id} has invalid/duplicate V2 candidates")
        for result in results:
            validate_result_contract(result, corpus, scope)
        gold_ids = _gold_ids(record)
        ranks = _gold_ranks(ids, gold_ids)
        traces.append(
            {
                "evaluation_id": evaluation_id,
                "question": record["query"],
                "specialist_scope": scope,
                "gold_canonical_chunk_ids": gold_ids,
                "gold_set_size": len(gold_ids),
                "query_embedding": {"dimension": len(vector), "norm": norm, "sha256": vector_hash},
                "candidate_depth": EXPECTED_VECTOR_CANDIDATES,
                "candidate_source": "canonical one-vector -> public.match_policy_chunks",
                "vector_candidate_canonical_chunk_ids": ids,
                "vector_candidate_similarity_scores": [float(result.similarity) for result in results],
                "vector_candidate_results": [
                    _candidate_result_payload(result, rank, corpus)
                    for rank, result in enumerate(results, 1)
                ],
                "vector_gold_ranks": {chunk_id: rank if rank is not None else ">20" for chunk_id, rank in ranks.items()},
                "vector_first_relevant_rank": _first_rank(ranks, ">20"),
                "vector_candidate_metrics": metric_values(ids, gold_ids),
                "candidate_coverage_at_5": {
                    "hit": hit_at_k(ids, set(gold_ids), 5),
                    "recall": recall_at_k(ids, set(gold_ids), 5),
                },
                "candidate_coverage_at_10": {
                    "hit": hit_at_k(ids, set(gold_ids), 10),
                    "recall": recall_at_k(ids, set(gold_ids), 10),
                },
                "candidate_coverage_at_20": {
                    "hit": hit_at_k(ids, set(gold_ids), 20),
                    "recall": recall_at_k(ids, set(gold_ids), 20),
                },
                "timing_ms": {"embedding": embedding_ms, "vector_retrieval": retrieval_ms},
                "scope_contract_satisfied": True,
                "rpc": "public.match_policy_chunks",
                "v2_only": True,
                "legacy_tables_used": False,
                "fts_used": False,
                "hybrid_used": False,
            }
        )
    if len(traces) != EXPECTED_QUERY_COUNT or sum(len(t["vector_candidate_canonical_chunk_ids"]) for t in traces) != 2000:
        raise Stage13E3Error("candidate trace count/workload failed")
    coverage = {
        f"hit@{k}": _mean(hit_at_k(t["vector_candidate_canonical_chunk_ids"], set(t["gold_canonical_chunk_ids"]), k) for t in traces)
        for k in (5, 10, 20)
    }
    coverage.update({
        f"recall@{k}": _mean(recall_at_k(t["vector_candidate_canonical_chunk_ids"], set(t["gold_canonical_chunk_ids"]), k) for t in traces)
        for k in (5, 10, 20)
    })
    rank_groups = Counter(
        "1-10" if isinstance(t["vector_first_relevant_rank"], int) and t["vector_first_relevant_rank"] <= 10
        else "11-20" if isinstance(t["vector_first_relevant_rank"], int)
        else ">20"
        for t in traces
    )
    candidate_summary = {
        "coverage": coverage,
        "gold_rank_groups": dict(rank_groups),
        "gold_absent_top10_present_top20": sum(
            isinstance(t["vector_first_relevant_rank"], int) and t["vector_first_relevant_rank"] > 10
            for t in traces
        ),
        "gold_absent_top20": rank_groups[">20"],
        "query_count": len(traces),
        "candidate_rows": 2000,
        "embedding_latency_ms": {
            "p50": percentile([t["timing_ms"]["embedding"] for t in traces], 50),
            "p95": percentile([t["timing_ms"]["embedding"] for t in traces], 95),
        },
        "vector_retrieval_latency_ms": {
            "p50": percentile([t["timing_ms"]["vector_retrieval"] for t in traces], 50),
            "p95": percentile([t["timing_ms"]["vector_retrieval"] for t in traces], 95),
        },
    }
    _write_jsonl(CANDIDATE_PATH, traces)
    return traces, candidate_summary


def load_frozen_candidates(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Load and validate the candidate freeze without calling embedding/RPC."""

    if not CANDIDATE_PATH.is_file():
        raise Stage13E3Error(f"frozen candidate artifact is missing: {CANDIDATE_PATH}")
    traces = _read_jsonl(CANDIDATE_PATH)
    expected_ids = [record["evaluation_id"] for record in records]
    if len(traces) != EXPECTED_QUERY_COUNT or [trace.get("evaluation_id") for trace in traces] != expected_ids:
        raise Stage13E3Error("frozen candidate artifact does not match gold order/count")
    for record, trace in zip(records, traces):
        if trace.get("candidate_depth") != EXPECTED_VECTOR_CANDIDATES:
            raise Stage13E3Error(f"{record['evaluation_id']} candidate depth is not 20")
        candidate_ids = trace.get("vector_candidate_canonical_chunk_ids")
        if not isinstance(candidate_ids, list) or len(candidate_ids) != EXPECTED_VECTOR_CANDIDATES or len(set(candidate_ids)) != EXPECTED_VECTOR_CANDIDATES:
            raise Stage13E3Error(f"{record['evaluation_id']} frozen candidates are not exactly 20 unique IDs")
        if any(chunk_id not in corpus.by_id for chunk_id in candidate_ids):
            raise Stage13E3Error(f"{record['evaluation_id']} frozen candidates contain a non-V2 ID")
        if trace.get("specialist_scope") != normalize_specialist_scope(record["specialist_scope"]):
            raise Stage13E3Error(f"{record['evaluation_id']} frozen candidate scope changed")
        if trace.get("gold_canonical_chunk_ids") != _gold_ids(record):
            raise Stage13E3Error(f"{record['evaluation_id']} frozen candidate gold changed")
        if trace.get("rpc") != "public.match_policy_chunks" or trace.get("fts_used") or trace.get("hybrid_used"):
            raise Stage13E3Error(f"{record['evaluation_id']} frozen candidate provenance is not canonical vector-only")
    coverage = {
        f"hit@{k}": _mean(hit_at_k(t["vector_candidate_canonical_chunk_ids"], set(t["gold_canonical_chunk_ids"]), k) for t in traces)
        for k in (5, 10, 20)
    }
    coverage.update({
        f"recall@{k}": _mean(recall_at_k(t["vector_candidate_canonical_chunk_ids"], set(t["gold_canonical_chunk_ids"]), k) for t in traces)
        for k in (5, 10, 20)
    })
    rank_groups = Counter(
        "1-10" if isinstance(t["vector_first_relevant_rank"], int) and t["vector_first_relevant_rank"] <= 10
        else "11-20" if isinstance(t["vector_first_relevant_rank"], int)
        else ">20"
        for t in traces
    )
    return traces, {
        "coverage": coverage,
        "gold_rank_groups": dict(rank_groups),
        "gold_absent_top10_present_top20": sum(
            isinstance(t["vector_first_relevant_rank"], int) and t["vector_first_relevant_rank"] > 10
            for t in traces
        ),
        "gold_absent_top20": rank_groups[">20"],
        "query_count": len(traces),
        "candidate_rows": EXPECTED_QUERY_COUNT * EXPECTED_VECTOR_CANDIDATES,
        "embedding_latency_ms": {
            "p50": percentile([t["timing_ms"]["embedding"] for t in traces], 50),
            "p95": percentile([t["timing_ms"]["embedding"] for t in traces], 95),
        },
        "vector_retrieval_latency_ms": {
            "p50": percentile([t["timing_ms"]["vector_retrieval"] for t in traces], 50),
            "p95": percentile([t["timing_ms"]["vector_retrieval"] for t in traces], 95),
        },
    }


def _format_document(corpus: FrozenCorpusV2, chunk_id: str) -> str:
    row = corpus.by_id[chunk_id]
    source = corpus.sources[row["source_id"]]
    return LlamaV2RerankerAdapter.format_document(
        title=source["title"],
        heading_path=list(row.get("heading_path", [])),
        content=row["content"],
    )


def _rerank_trace(record: dict[str, Any], candidate: dict[str, Any], corpus: FrozenCorpusV2, adapter: LlamaV2RerankerAdapter, depth: int, run_number: int) -> dict[str, Any]:
    all_ids = list(candidate["vector_candidate_canonical_chunk_ids"])
    ids = all_ids[:depth]
    if len(ids) != depth or len(set(ids)) != depth or not set(ids).issubset(set(all_ids)):
        raise Stage13E3Error(f"{record['evaluation_id']} has invalid frozen {depth}-candidate prefix")
    documents = [_format_document(corpus, chunk_id) for chunk_id in ids]
    started = time.perf_counter()
    native_scores = adapter.rerank(record["query"], documents)
    reranker_ms = (time.perf_counter() - started) * 1000
    if len(native_scores) != depth or {score.index for score in native_scores} != set(range(depth)):
        raise Stage13E3Error(f"reranker did not return the exact {depth}-index set for {record['evaluation_id']}")
    score_by_id = {ids[score.index]: float(score.relevance_score) for score in native_scores}
    if any(not math.isfinite(value) for value in score_by_id.values()):
        raise Stage13E3Error(f"non-finite reranker score for {record['evaluation_id']}")
    reranked_ids = sorted(ids, key=lambda chunk_id: (-score_by_id[chunk_id], chunk_id))
    if set(reranked_ids) != set(ids) or len(reranked_ids) != depth:
        raise Stage13E3Error(f"reranker changed candidate identity set for {record['evaluation_id']}")
    gold_ids = _gold_ids(record)
    vector_ranks = _gold_ranks(all_ids, gold_ids)
    reranked_ranks = _gold_ranks(reranked_ids, gold_ids)
    vector_first = _first_rank(vector_ranks, ">20")
    reranked_first = _first_rank(reranked_ranks, f">{depth}")
    rank_status = (
        "IMPROVED" if isinstance(vector_first, int) and isinstance(reranked_first, int) and reranked_first < vector_first
        else "WORSENED" if isinstance(vector_first, int) and isinstance(reranked_first, int) and reranked_first > vector_first
        else "UNCHANGED" if isinstance(vector_first, int) and isinstance(reranked_first, int)
        else "UNRECOVERABLE-CANDIDATE"
    )
    return {
        "run": run_number,
        "evaluation_id": record["evaluation_id"],
        "question": record["query"],
        "specialist_scope": normalize_specialist_scope(record["specialist_scope"]),
        "gold_canonical_chunk_ids": gold_ids,
        "candidate_depth": depth,
        "candidate_source": "same frozen canonical vector top20; exact prefix" if depth == 10 else "same frozen canonical vector top20",
        "vector_top20_canonical_chunk_ids": all_ids,
        "vector_top20_similarity_scores": list(candidate["vector_candidate_similarity_scores"]),
        "vector_candidate_canonical_chunk_ids": ids,
        "vector_candidate_similarity_scores": list(candidate["vector_candidate_similarity_scores"][:depth]),
        "vector_first_relevant_rank": vector_first,
        "vector_gold_ranks": {chunk_id: rank if rank is not None else ">20" for chunk_id, rank in vector_ranks.items()},
        "reranker_scores_by_candidate": [
            {
                "input_index": index,
                "canonical_chunk_id": chunk_id,
                "vector_rank": index + 1,
                "vector_similarity": float(candidate["vector_candidate_similarity_scores"][index]),
                "relevance_score": score_by_id[chunk_id],
            }
            for index, chunk_id in enumerate(ids)
        ],
        "reranked_canonical_chunk_ids": reranked_ids,
        "reranked_relevance_scores": [score_by_id[chunk_id] for chunk_id in reranked_ids],
        "reranked_gold_ranks": {chunk_id: rank if rank is not None else f">{depth}" for chunk_id, rank in reranked_ranks.items()},
        "reranked_first_relevant_rank": reranked_first,
        "rank_status_vs_vector_top20": rank_status,
        "reranked_metrics": metric_values(reranked_ids, gold_ids),
        "timing_ms": {"reranker": reranker_ms, "total_reranking": reranker_ms},
        "pair_count": depth,
        "scope_contract_satisfied": True,
        "rpc": "public.match_policy_chunks",
        "retrieval_source": "supabase_rpc",
        "reranker_endpoint": f"{RERANKER_ENDPOINT}/v1/rerank",
        "reranker_used": True,
        "vector_score_blended": False,
        "v2_only": True,
        "legacy_tables_used": False,
        "fts_used": False,
        "hybrid_used": False,
    }


def _run_order(records: list[dict[str, Any]], candidate_by_id: dict[str, dict[str, Any]], corpus: FrozenCorpusV2, adapter: LlamaV2RerankerAdapter, order: tuple[int, int], run_number: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_depth: dict[int, list[dict[str, Any]]] = {10: [], 20: []}
    record_by_id = {record["evaluation_id"]: record for record in records}
    for depth in order:
        for record in records:
            by_depth[depth].append(_rerank_trace(record, candidate_by_id[record["evaluation_id"]], corpus, adapter, depth, run_number))
    return by_depth[10], by_depth[20]


def _compare_repeats(run1: list[dict[str, Any]], run2: list[dict[str, Any]], depth: int) -> dict[str, Any]:
    if [trace["evaluation_id"] for trace in run1] != [trace["evaluation_id"] for trace in run2]:
        raise Stage13E3Error(f"top-{depth} repeat query order changed")
    top5_equal = 0
    gold_equal = 0
    drifts: list[float] = []
    for first, second in zip(run1, run2):
        if first["reranked_canonical_chunk_ids"] != second["reranked_canonical_chunk_ids"]:
            raise Stage13E3Error(f"top-{depth} reranked order changed for {first['evaluation_id']}")
        if first["reranked_canonical_chunk_ids"][:5] == second["reranked_canonical_chunk_ids"][:5]:
            top5_equal += 1
        if first["reranked_gold_ranks"] != second["reranked_gold_ranks"]:
            raise Stage13E3Error(f"top-{depth} reranked gold ranks changed for {first['evaluation_id']}")
        gold_equal += 1
        second_scores = {item["canonical_chunk_id"]: float(item["relevance_score"]) for item in second["reranker_scores_by_candidate"]}
        drifts.append(max(abs(float(item["relevance_score"]) - second_scores[item["canonical_chunk_id"]]) for item in first["reranker_scores_by_candidate"]))
    metrics_equal = aggregate_metrics(run1, "reranked_metrics") == aggregate_metrics(run2, "reranked_metrics")
    if not metrics_equal:
        raise Stage13E3Error(f"top-{depth} aggregate metrics changed between repeats")
    return {
        "metrics_equal": metrics_equal,
        "ordered_top5_agreement": top5_equal / len(run1),
        "gold_rank_agreement": gold_equal / len(run1),
        "max_score_drift": max(drifts) if drifts else 0.0,
    }


def _breakdown(traces: list[dict[str, Any]], field: str, key_field: str = "specialist_scope") -> dict[str, Any]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        groups[str(trace[key_field])].append(trace)
    return {
        key: {"query_count": len(group), **{metric: value for metric, value in aggregate_metrics(group, field).items() if metric in {"hit@1", "hit@3", "hit@5", "recall@5", "mrr@5", "ndcg@5"}}}
        for key, group in sorted(groups.items())
    }


def _provenance_breakdown(traces: list[dict[str, Any]], records: list[dict[str, Any]], field: str) -> dict[str, Any]:
    provenance = {record["evaluation_id"]: "synthetic" if record["is_synthetic"] else "real_authoritative" for record in records}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trace in traces:
        groups[provenance[trace["evaluation_id"]]].append(trace)
    return {
        key: {"query_count": len(group), **{metric: value for metric, value in aggregate_metrics(group, field).items() if metric in {"hit@5", "recall@5", "mrr@5", "ndcg@5"}}}
        for key, group in sorted(groups.items())
    }


def _build_doc(summary: dict[str, Any]) -> None:
    t10 = summary["arms"]["top10"]
    t20 = summary["arms"]["top20"]
    lines = [
        "# Stage 13E3 — 100-Query Top10 vs Top20 Reranker Confirmation",
        "",
        "Status: **CONFIRMATION BENCHMARK / PILOT / EXPLORATORY / DESCRIPTIVE ONLY**.",
        "",
        "One canonical query vector and one canonical top-20 RPC result were collected per question. Top-10 is the exact prefix of that same top-20 list. The only arm variable is reranker candidate depth.",
        "",
        "## Frozen identity",
        "",
        f"- Gold: `{summary['identity']['gold_path']}`, 100 REVIEWED, SHA-256 `{summary['identity']['gold_sha256']}`.",
        f"- Corpus: `{summary['identity']['corpus']}`, 1610 chunks; manifest SHA-256 `{summary['identity']['corpus_manifest_sha256']}`.",
        f"- Embedding: `{summary['identity']['embedding_model']}`, 1024D, llama.cpp/Vulkan; artifact SHA-256 `{summary['identity']['embedding_artifact_sha256']}`; manifest SHA-256 `{summary['identity']['embedding_manifest_sha256']}`.",
        f"- Reranker: `{summary['reranker']['model']}` Q8_0 GGUF; SHA-256 `{summary['reranker']['sha256']}`; `{summary['reranker']['build']}`; `{summary['reranker']['device']}`.",
        "",
        "## Results",
        "",
        "| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in (("Top10 + reranker", t10["metrics"]), ("Top20 + reranker", t20["metrics"])):
        lines.append("| " + label + " | " + " | ".join(f"{metrics[f'{metric}@{k}']:.4f}" for metric in ("hit", "recall", "mrr", "ndcg") for k in K_VALUES) + " |")
    lines.extend([
        "",
        "## Candidate coverage",
        "",
        f"- Vector candidate coverage Hit@5/10/20: `{summary['candidate_coverage']['hit@5']:.4f}` / `{summary['candidate_coverage']['hit@10']:.4f}` / `{summary['candidate_coverage']['hit@20']:.4f}`.",
        f"- Vector candidate coverage Recall@5/10/20: `{summary['candidate_coverage']['recall@5']:.4f}` / `{summary['candidate_coverage']['recall@10']:.4f}` / `{summary['candidate_coverage']['recall@20']:.4f}`.",
        f"- First relevant vector rank groups: 1–10 `{summary['candidate_rank_groups'].get('1-10', 0)}`, 11–20 `{summary['candidate_rank_groups'].get('11-20', 0)}`, >20 `{summary['candidate_rank_groups'].get('>20', 0)} `.",
        "",
        "## Latency and workload",
        "",
        f"- Top10 reranker p50/p95: `{summary['latency']['top10']['p50_ms']:.3f}` / `{summary['latency']['top10']['p95_ms']:.3f}` ms; 1000 pairs/run.",
        f"- Top20 reranker p50/p95: `{summary['latency']['top20']['p50_ms']:.3f}` / `{summary['latency']['top20']['p95_ms']:.3f}` ms; 2000 pairs/run.",
        f"- Top10 minus Top20 p50: `{summary['latency']['p50_reduction_ms']:.3f}` ms ({summary['latency']['p50_reduction_percent']:.2f}%).",
        "",
        "## Repeatability and constraints",
        "",
        f"- Top10 repeat: metrics equal `{summary['repeatability']['top10']['metrics_equal']}`, ordered top-5 agreement `{summary['repeatability']['top10']['ordered_top5_agreement']:.4f}`, max score drift `{summary['repeatability']['top10']['max_score_drift']:.9f}`.",
        f"- Top20 repeat: metrics equal `{summary['repeatability']['top20']['metrics_equal']}`, ordered top-5 agreement `{summary['repeatability']['top20']['ordered_top5_agreement']:.4f}`, max score drift `{summary['repeatability']['top20']['max_score_drift']:.9f}`.",
        f"- Decision: **{summary['classification']}**.",
        "- No FTS, hybrid/RRF, query rewrite, generation model, model download, corpus mutation, embedding regeneration, gold mutation, local deletion, or Git mutation was performed.",
    ])
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(mode: str = "benchmark") -> int:
    corpus = FrozenCorpusV2()
    records, remote = validate_preflight(corpus)
    if mode == "collect-candidates":
        candidate_traces, candidate_summary = collect_candidates(records, corpus)
        print(json.dumps({"candidate_artifact": str(CANDIDATE_PATH), "query_count": len(candidate_traces), "rows": sum(len(trace["vector_candidate_canonical_chunk_ids"]) for trace in candidate_traces), "coverage": candidate_summary["coverage"]}, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if mode != "benchmark":
        raise Stage13E3Error("mode must be benchmark or collect-candidates")
    candidate_traces, candidate_summary = load_frozen_candidates(records, corpus)
    candidate_by_id = {trace["evaluation_id"]: trace for trace in candidate_traces}
    adapter = LlamaV2RerankerAdapter(base_url=RERANKER_ENDPOINT)

    # Unscored warm-up only; no gold or candidate data is sent.
    adapter.rerank(
        "Hệ thống xếp hạng tín dụng nội bộ phải được rà soát bao lâu một lần?",
        [
            "Hệ thống xếp hạng tín dụng nội bộ phải được xem xét, đánh giá ít nhất mỗi năm một lần.",
            "Tổ chức tín dụng không được cho vay để mua vàng miếng.",
        ],
    )

    run10_1, run20_1 = _run_order(records, candidate_by_id, corpus, adapter, (10, 20), 1)
    run10_2, run20_2 = _run_order(records, candidate_by_id, corpus, adapter, (20, 10), 2)
    repeat10 = _compare_repeats(run10_1, run10_2, 10)
    repeat20 = _compare_repeats(run20_1, run20_2, 20)
    _write_jsonl(TOP10_RUN1_PATH, run10_1)
    _write_jsonl(TOP10_RUN2_PATH, run10_2)
    _write_jsonl(TOP20_RUN1_PATH, run20_1)
    _write_jsonl(TOP20_RUN2_PATH, run20_2)

    metrics10 = aggregate_metrics(run10_1, "reranked_metrics")
    metrics20 = aggregate_metrics(run20_1, "reranked_metrics")
    delta = {key: metrics10[key] - metrics20[key] for key in metrics10}
    top5_disagreements = [
        first["evaluation_id"]
        for first, second in zip(run10_1, run20_1)
        if first["reranked_canonical_chunk_ids"][:5] != second["reranked_canonical_chunk_ids"][:5]
    ]
    top20_additional_successes = [
        first["evaluation_id"]
        for first, second in zip(run10_1, run20_1)
        if hit_at_k(first["reranked_canonical_chunk_ids"], set(first["gold_canonical_chunk_ids"]), 5) == 0
        and hit_at_k(second["reranked_canonical_chunk_ids"], set(second["gold_canonical_chunk_ids"]), 5) == 1
    ]
    top10_improved: list[str] = []
    top20_improved: list[str] = []
    same: list[str] = []
    for first, second in zip(run10_1, run20_1):
        r10, r20 = first["reranked_first_relevant_rank"], second["reranked_first_relevant_rank"]
        if isinstance(r10, int) and isinstance(r20, int) and r10 < r20:
            top10_improved.append(first["evaluation_id"])
        elif isinstance(r20, int) and (not isinstance(r10, int) or r20 < r10):
            top20_improved.append(first["evaluation_id"])
        else:
            same.append(first["evaluation_id"])
    cases_11_20 = [
        {
            "evaluation_id": trace["evaluation_id"],
            "specialist_scope": trace["specialist_scope"],
            "vector_first_gold_rank": trace["vector_first_relevant_rank"],
            "top10_reranked_first_gold_rank": next(item["reranked_first_relevant_rank"] for item in run10_1 if item["evaluation_id"] == trace["evaluation_id"]),
            "top20_reranked_first_gold_rank": next(item["reranked_first_relevant_rank"] for item in run20_1 if item["evaluation_id"] == trace["evaluation_id"]),
        }
        for trace in candidate_traces
        if isinstance(trace["vector_first_relevant_rank"], int) and 11 <= trace["vector_first_relevant_rank"] <= 20
    ]
    top20_failures = [trace["evaluation_id"] for trace in candidate_traces if trace["vector_first_relevant_rank"] == ">20"]
    top10_latency = [float(trace["timing_ms"]["reranker"]) for trace in run10_1]
    top20_latency = [float(trace["timing_ms"]["reranker"]) for trace in run20_1]
    p50_10, p95_10 = percentile(top10_latency, 50), percentile(top10_latency, 95)
    p50_20, p95_20 = percentile(top20_latency, 50), percentile(top20_latency, 95)
    classification = (
        "A — TOP10 CONFIRMED"
        if metrics10["hit@5"] >= metrics20["hit@5"] - 0.01
        and metrics10["recall@5"] >= metrics20["recall@5"] - 0.01
        and metrics10["mrr@5"] >= metrics20["mrr@5"] - 0.01
        and metrics10["ndcg@5"] >= metrics20["ndcg@5"] - 0.01
        and len([x for x in top5_disagreements if x in top20_additional_successes]) <= 1
        and all(
            _breakdown(run10_1, "reranked_metrics").get(scope, {}).get("hit@5", 0.0)
            >= _breakdown(run20_1, "reranked_metrics").get(scope, {}).get("hit@5", 0.0) - 0.05
            for scope in SUPPORTED_SCOPES
        )
        and p50_10 <= p50_20 * 0.70
        else "B — TOP20 JUSTIFIED"
        if metrics20["hit@5"] - metrics10["hit@5"] >= 0.02 or len(top20_additional_successes) >= 2
        else "C — MIXED / INCONCLUSIVE"
    )
    summary = {
        "stage": "13E3 — 100-Query Top10 vs Top20 Reranker Confirmation Benchmark",
        "status": "CONFIRMATION / PILOT / EXPLORATORY / DESCRIPTIVE ONLY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "gold_path": "dataset/evaluation/retrieval-v2-gold-expanded.jsonl",
            "gold_sha256": EXPECTED_GOLD_SHA256,
            "gold_record_count": EXPECTED_QUERY_COUNT,
            "gold_status": "REVIEWED",
            "corpus": "policy-corpus-v2",
            "corpus_version": "V2",
            "corpus_documents": 10,
            "corpus_chunks": EXPECTED_CHUNK_COUNT,
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_model": "Qwen3-Embedding-0.6B",
            "embedding_dimension": 1024,
            "embedding_artifact_sha256": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
            "embedding_manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
            "hnsw_ef_search": remote["hnsw_ef_search"],
        },
        "query_embedding": {
            "backend": "llama.cpp",
            "endpoint": "http://127.0.0.1:8081/v1/embeddings",
            "instruction": LlamaV2QueryEmbeddingAdapter.QUERY_INSTRUCTION,
            "format": "Instruct: {instruction}\nQuery: {query}",
            "one_embedding_per_query": True,
        },
        "retrieval": {
            "backend": "Supabase rag_v2",
            "rpc": "public.match_policy_chunks",
            "distance": "cosine",
            "candidate_depth": 20,
            "one_rpc_per_query": True,
            "top10_definition": "same ordered top20 result prefix [0:10]",
            "scope_semantics": "SHARED or explicitly authorized SCOPED",
            "legacy_tables_used": False,
            "fts_used": False,
            "hybrid_used": False,
        },
        "candidate_coverage": candidate_summary["coverage"],
        "candidate_rank_groups": candidate_summary["gold_rank_groups"],
        "gold_absent_top10_present_top20": candidate_summary["gold_absent_top10_present_top20"],
        "gold_absent_top20": candidate_summary["gold_absent_top20"],
        "candidate_trace_count": len(candidate_traces),
        "candidate_rows": 2000,
        "reranker": {
            "model": "Qwen3-Reranker-0.6B",
            "path": str(RERANKER_MODEL_PATH),
            "bytes": RERANKER_MODEL_BYTES,
            "sha256": RERANKER_MODEL_SHA256,
            "quantization": "Q8_0 GGUF",
            "build": RERANKER_BUILD,
            "runtime": "llama.cpp",
            "device": RERANKER_DEVICE,
            "endpoint": f"{RERANKER_ENDPOINT}/v1/rerank",
            "context": RERANKER_CONTEXT,
            "parallel": RERANKER_PARALLEL,
            "pooling": RERANKER_POOLING,
            "document_template": RERANKER_DOCUMENT_TEMPLATE,
            "query": "exact human-reviewed Vietnamese question",
            "score_blended": False,
            "tie_ordering": "relevance_score DESC, canonical_chunk_id ASC",
            "warmup": True,
        },
        "arms": {
            "top10": {"candidate_depth": 10, "pair_workload_per_run": 1000, "metrics": metrics10, "by_scope": _breakdown(run10_1, "reranked_metrics"), "by_provenance": _provenance_breakdown(run10_1, records, "reranked_metrics")},
            "top20": {"candidate_depth": 20, "pair_workload_per_run": 2000, "metrics": metrics20, "by_scope": _breakdown(run20_1, "reranked_metrics"), "by_provenance": _provenance_breakdown(run20_1, records, "reranked_metrics")},
        },
        "delta_top10_minus_top20": delta,
        "query_level": {
            "top10_improved": top10_improved,
            "same": same,
            "top20_improved": top20_improved,
            "top5_disagreements": top5_disagreements,
            "additional_top20_successes": top20_additional_successes,
            "gold_vector_rank_11_20": cases_11_20,
            "top20_candidate_failures": top20_failures,
        },
        "latency": {
            "query_embedding_p50_ms": candidate_summary["embedding_latency_ms"]["p50"],
            "query_embedding_p95_ms": candidate_summary["embedding_latency_ms"]["p95"],
            "vector_retrieval_p50_ms": candidate_summary["vector_retrieval_latency_ms"]["p50"],
            "vector_retrieval_p95_ms": candidate_summary["vector_retrieval_latency_ms"]["p95"],
            "top10": {"p50_ms": p50_10, "p95_ms": p95_10, "mean_ms": _mean(top10_latency)},
            "top20": {"p50_ms": p50_20, "p95_ms": p95_20, "mean_ms": _mean(top20_latency)},
            "p50_reduction_ms": p50_20 - p50_10,
            "p50_reduction_percent": (p50_20 - p50_10) / p50_20 * 100 if p50_20 else 0.0,
            "p95_reduction_ms": p95_20 - p95_10,
            "p95_reduction_percent": (p95_20 - p95_10) / p95_20 * 100 if p95_20 else 0.0,
            "experimental_shared_candidate_collection": True,
            "production_top10_rpc_latency_not_measured": True,
        },
        "repeatability": {"top10": repeat10, "top20": repeat20, "execution_order": {"run1": ["top10", "top20"], "run2": ["top20", "top10"]}},
        "constraints": {
            "no_fts": True,
            "no_hybrid": True,
            "no_rrf": True,
            "no_top50": True,
            "no_query_rewrite": True,
            "no_generation": True,
            "no_sentence_transformer": True,
            "no_gold_mutation": True,
            "no_corpus_mutation": True,
            "no_embedding_regeneration": True,
            "no_hnsw_mutation": True,
            "no_model_download": True,
            "no_local_deletion": True,
        },
        "classification": classification,
        "interpretation": "CONFIRMATION BENCHMARK ON FROZEN 100-QUERY HUMAN-REVIEWED GOLD; PILOT / EXPLORATORY / DESCRIPTIVE ONLY",
        "artifacts": {
            "top10_summary": str(TOP10_SUMMARY_PATH.relative_to(ROOT)),
            "top10_run1": str(TOP10_RUN1_PATH.relative_to(ROOT)),
            "top10_run2": str(TOP10_RUN2_PATH.relative_to(ROOT)),
            "top20_summary": str(TOP20_SUMMARY_PATH.relative_to(ROOT)),
            "top20_run1": str(TOP20_RUN1_PATH.relative_to(ROOT)),
            "top20_run2": str(TOP20_RUN2_PATH.relative_to(ROOT)),
            "combined_summary": str(SUMMARY_PATH.relative_to(ROOT)),
            "candidate_artifact": str(CANDIDATE_PATH.relative_to(ROOT)),
            "documentation": str(DOC_PATH.relative_to(ROOT)),
        },
    }
    top10_summary = {"stage": summary["stage"], "identity": summary["identity"], "arm": "top10", "metrics": metrics10, "latency": summary["latency"]["top10"], "repeatability": repeat10, "trace_count": 100, "pair_count": 1000}
    top20_summary = {"stage": summary["stage"], "identity": summary["identity"], "arm": "top20", "metrics": metrics20, "latency": summary["latency"]["top20"], "repeatability": repeat20, "trace_count": 100, "pair_count": 2000}
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    TOP10_SUMMARY_PATH.write_text(json.dumps(top10_summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    TOP20_SUMMARY_PATH.write_text(json.dumps(top20_summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    _build_doc(summary)
    print(json.dumps({"summary": str(SUMMARY_PATH), "top10": metrics10, "top20": metrics20, "classification": classification}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "benchmark"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Stage 13E3 failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1)
