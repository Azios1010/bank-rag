"""Run the frozen Stage 13B0-R1 top-20 candidate recall audit.

This script measures candidate coverage for the intended top-20 reranker pool
using the unchanged llama.cpp -> Supabase vector RPC path.  It deliberately
does not call FTS, hybrid retrieval, a reranker, or any alternate query plan.
"""

from __future__ import annotations

from datetime import datetime, timezone
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

from app.eval.metrics import hit_at_k, percentile, recall_at_k  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_query_embedding import LlamaV2QueryEmbeddingAdapter  # noqa: E402
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
from scripts.run_stage13b0_candidate_recall import (  # noqa: E402
    read_remote_state,
    result_payload,
    validate_result_contract,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
SUMMARY_PATH = RESULTS_DIR / "vector-v2-top20-candidate-summary.json"
TRACE_PATH = RESULTS_DIR / "vector-v2-top20-candidate-traces.jsonl"
RUN2_TRACE_PATH = RESULTS_DIR / "vector-v2-top20-candidate-run-2-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-13B0-TOP20-CANDIDATE-RECALL.md"

CANDIDATE_DEPTH = 20
COVERAGE_K = (5, 10, 20)
FROZEN_BASELINE_HIT_AT_5 = 0.84
FROZEN_MISS_IDS = (
    "stage12a-007",
    "stage12a-008",
    "stage12a-013",
    "stage12a-024",
)


class Stage13B0R1Error(RuntimeError):
    """Raised when the frozen top-20 audit contract is violated."""


def _mean(values: list[float] | Any) -> float:
    values = list(values)
    return statistics.fmean(values) if values else 0.0


def _without_sha(value: str) -> str:
    return value.removeprefix("sha256:")


def _source_type(source: dict[str, Any]) -> str:
    return "synthetic_internal_policy" if source["synthetic"] else "real_regulation"


def validate_identity(corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    records = validate_gold_identity(corpus)
    expected_files = {
        ROOT / "dataset/manifests/policy-corpus-v2-manifest.json": EXPECTED_CORPUS_MANIFEST_SHA256,
        ROOT / "dataset/embeddings/v2/embeddings.parquet": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
        ROOT / "dataset/embeddings/v2/embedding-manifest.json": EXPECTED_EMBEDDING_MANIFEST_SHA256,
    }
    for path, expected in expected_files.items():
        if sha256_file(path) != expected:
            raise Stage13B0R1Error(f"frozen identity changed: {path}")
    if sha256_file(GOLD_PATH) != EXPECTED_GOLD_SHA256:
        raise Stage13B0R1Error("released gold SHA-256 changed")
    if len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise Stage13B0R1Error("Corpus V2 is not exactly 1610 unique chunks")
    identity = corpus.embedding_identity
    if {
        identity["model"],
        identity["dimension"],
        identity["runtime"],
        identity["backend"],
    } != {"Qwen3-Embedding-0.6B", 1024, "llama.cpp", "Vulkan"}:
        raise Stage13B0R1Error("frozen embedding identity changed")
    return records


def coverage_for_ids(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, float | int]:
    gold_set = set(gold_ids)
    return {
        **{f"hit@{k}": hit_at_k(retrieved_ids, gold_set, k) for k in COVERAGE_K},
        **{f"recall@{k}": recall_at_k(retrieved_ids, gold_set, k) for k in COVERAGE_K},
    }


def gold_ranks(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, int | None]:
    rank_by_id = {chunk_id: rank for rank, chunk_id in enumerate(retrieved_ids, 1)}
    return {chunk_id: rank_by_id.get(chunk_id) for chunk_id in gold_ids}


def _trace_run(
    records: list[dict[str, Any]],
    corpus: FrozenCorpusV2,
    retriever: CanonicalV2Retriever,
    run_number: int,
) -> list[dict[str, Any]]:
    traces: list[dict[str, Any]] = []
    for record in records:
        scope = normalize_specialist_scope(record["specialist_scope"])
        started = time.perf_counter()
        results, timing = retriever.retrieve_with_timing(
            record["query"], scope, k=CANDIDATE_DEPTH
        )
        total_ms = (time.perf_counter() - started) * 1000
        if len(results) != CANDIDATE_DEPTH:
            raise Stage13B0R1Error(
                f"{record['evaluation_id']} returned {len(results)} rows, expected 20"
            )
        seen: set[str] = set()
        for result in results:
            if result.canonical_chunk_id in seen:
                raise Stage13B0R1Error(f"duplicate ID in {record['evaluation_id']}")
            seen.add(result.canonical_chunk_id)
            validate_result_contract(result, corpus, scope)
        retrieved_ids = [result.canonical_chunk_id for result in results]
        gold_ids = list(record["expected_canonical_chunk_ids"])
        raw_ranks = gold_ranks(retrieved_ids, gold_ids)
        present = [rank for rank in raw_ranks.values() if rank is not None]
        ranks = {
            chunk_id: rank if rank is not None else ">20"
            for chunk_id, rank in raw_ranks.items()
        }
        traces.append(
            {
                "run": run_number,
                "evaluation_id": record["evaluation_id"],
                "query": record["query"],
                "specialist_scope": scope,
                "gold_canonical_chunk_ids": gold_ids,
                "gold_set_size": len(gold_ids),
                "gold_visibility": record["visibility"],
                "gold_source_type": (
                    "synthetic_internal_policy" if record["is_synthetic"] else "real_regulation"
                ),
                "candidate_depth": CANDIDATE_DEPTH,
                "candidate_canonical_chunk_ids": retrieved_ids,
                "candidate_similarity_scores": [result.similarity for result in results],
                "candidate_results": [
                    result_payload(result, rank, corpus)
                    for rank, result in enumerate(results, 1)
                ],
                "gold_ranks": ranks,
                "first_relevant_rank": min(present) if present else ">20",
                "coverage": coverage_for_ids(retrieved_ids, gold_ids),
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
    summary: dict[str, float] = {}
    for phase in ("embedding", "retrieval", "total"):
        values = [float(trace["latency_ms"][phase]) for trace in traces]
        summary[f"{phase}_p50_ms"] = percentile(values, 50)
        summary[f"{phase}_p95_ms"] = percentile(values, 95)
    return summary


def _classify(rank: int | None) -> str:
    if rank is None or rank > 20:
        return "D — NOT RECOVERABLE BY A TOP-20 RERANKER"
    if rank <= 10:
        return "A — HIGHLY RERANKABLE"
    return "B — RERANKABLE"


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
        present = [rank for rank in ranks.values() if isinstance(rank, int)]
        first_rank = min(present) if present else None
        source_ids = {
            corpus.by_id[chunk_id]["source_id"]
            for chunk_id in record["expected_canonical_chunk_ids"]
        }
        top1 = trace["candidate_results"][0]
        nearby = [
            {
                "canonical_chunk_id": item["canonical_chunk_id"],
                "rank": item["rank"],
                "article": item["locator"].get("article"),
            }
            for item in trace["candidate_results"]
            if item["document_source_id"] in source_ids
        ]
        details.append(
            {
                "evaluation_id": evaluation_id,
                "scope": trace["specialist_scope"],
                "gold_canonical_chunk_ids": record["expected_canonical_chunk_ids"],
                "gold_ranks": ranks,
                "first_gold_rank": first_rank if first_rank is not None else ">20",
                "failure_type": "ranking failure" if first_rank is not None else "candidate-generation failure",
                "rerankability": _classify(first_rank),
                "top1": {
                    "canonical_chunk_id": top1["canonical_chunk_id"],
                    "document_source_id": top1["document_source_id"],
                    "document_title": top1["document_title"],
                    "article": top1["locator"].get("article"),
                    "visibility": top1["visibility"],
                },
                "same_document_nearby_provisions": nearby,
                "same_document_candidate_count": len(nearby),
                "note": "Candidate trace inspection only; approved gold was not changed.",
            }
        )
    return details


def repeatability(run1: list[dict[str, Any]], run2: list[dict[str, Any]]) -> dict[str, Any]:
    if [item["evaluation_id"] for item in run1] != [item["evaluation_id"] for item in run2]:
        raise Stage13B0R1Error("repeat runs have different query IDs")
    per_query: list[dict[str, Any]] = []
    for first, second in zip(run1, run2):
        ids1 = first["candidate_canonical_chunk_ids"]
        ids2 = second["candidate_canonical_chunk_ids"]
        score_drift = max(
            abs(float(left) - float(right))
            for left, right in zip(first["candidate_similarity_scores"], second["candidate_similarity_scores"])
        )
        rank_equal = first["gold_ranks"] == second["gold_ranks"]
        per_query.append(
            {
                "evaluation_id": first["evaluation_id"],
                "ordered_top20_equal": ids1 == ids2,
                "ordered_top10_equal": ids1[:10] == ids2[:10],
                "ordered_top5_equal": ids1[:5] == ids2[:5],
                "gold_ranks_equal": rank_equal,
                "max_score_drift": score_drift,
            }
        )
    return {
        "ordered_top20_agreement": _mean(item["ordered_top20_equal"] for item in per_query),
        "ordered_top10_agreement": _mean(item["ordered_top10_equal"] for item in per_query),
        "ordered_top5_agreement": _mean(item["ordered_top5_equal"] for item in per_query),
        "exact_gold_rank_agreement": _mean(item["gold_ranks_equal"] for item in per_query),
        "queries_with_rank_differences": [
            item["evaluation_id"] for item in per_query if not item["ordered_top20_equal"]
        ],
        "max_score_drift": max(item["max_score_drift"] for item in per_query),
        "metrics_equal": aggregate_coverage(run1) == aggregate_coverage(run2),
        "per_query": per_query,
    }


def write_jsonl(path: Path, traces: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")


def write_document(summary: dict[str, Any], misses: list[dict[str, Any]]) -> None:
    coverage = summary["run_1"]["coverage"]
    lines = [
        "# Stage 13B0-R1 — Frozen Top-20 Candidate Recall Audit",
        "",
        "Status: **FEASIBILITY DIAGNOSTIC ONLY**. The unchanged vector path was",
        "audited at the intended top-20 reranker candidate depth. No reranker was",
        "loaded or implemented, and no quality benchmark was run.",
        "",
        "## Runtime",
        "",
        f"- Canonical path: `llama.cpp -> CanonicalV2Retriever -> public.match_policy_chunks`",
        f"- Candidate depth: `{CANDIDATE_DEPTH}`; coverage K: `5, 10, 20`",
        f"- HNSW `ef_search`: `{summary['remote_state']['hnsw_ef_search']}`; no planner/index setting was changed.",
        "- No FTS, hybrid, sequential scan, session-local ANN tuning, query rewrite, or reranker was used.",
        "",
        "## Frozen identity",
        "",
        f"- Gold SHA-256: `{summary['gold']['sha256']}`",
        f"- Corpus: `{summary['corpus']['name']}` / `{summary['corpus']['chunk_count']}` chunks; manifest SHA-256 `{summary['corpus']['manifest_sha256']}`",
        f"- Embedding: `{summary['embedding']['model']}`, `{summary['embedding']['dimension']}D`, `{summary['embedding']['runtime']}/{summary['embedding']['backend']}`",
        "",
        "## Candidate coverage",
        "",
        "| Metric | @5 | @10 | @20 |",
        "| --- | ---: | ---: | ---: |",
        f"| Hit | {coverage['hit@5']:.4f} | {coverage['hit@10']:.4f} | {coverage['hit@20']:.4f} |",
        f"| Recall | {coverage['recall@5']:.4f} | {coverage['recall@10']:.4f} | {coverage['recall@20']:.4f} |",
        "",
        "## Frozen @5 misses",
        "",
    ]
    for item in misses:
        lines.append(
            f"- `{item['evaluation_id']}` — gold rank `{item['first_gold_rank']}`; **{item['failure_type']}**; **{item['rerankability']}**. Top-1 `{item['top1']['canonical_chunk_id']}`, source `{item['top1']['document_source_id']}`, article `{item['top1']['article']}`. Same-document candidates: `{item['same_document_candidate_count']}`."
        )
    upper = summary["perfect_top20_reranker_ceiling"]
    lines.extend(
        [
            "",
            "## Perfect top-20 reranker ceiling",
            "",
            f"- Frozen Stage 12B Hit@5: `{upper['frozen_hit@5']:.4f}`.",
            f"- Candidate Hit@20: `{upper['candidate_hit@20']:.4f}`.",
            f"- Maximum additional frozen @5 misses available to a perfect top-20 reranker: `{upper['maximum_additional_recoverable_queries']}`.",
            f"- Candidate Recall@20: `{upper['candidate_recall@20']:.4f}`; this bounds recovery of all approved IDs, including both gold IDs for stage12a-004.",
            f"- Decision: **{summary['decision']}**.",
            "- The ceiling is theoretical and does not predict actual reranker performance.",
            "",
            "## Repeatability",
            "",
            f"- Ordered top-20 agreement: `{summary['repeatability']['ordered_top20_agreement']:.4f}`",
            f"- Ordered top-10 agreement: `{summary['repeatability']['ordered_top10_agreement']:.4f}`",
            f"- Ordered top-5 agreement: `{summary['repeatability']['ordered_top5_agreement']:.4f}`",
            f"- Exact gold-rank agreement: `{summary['repeatability']['exact_gold_rank_agreement']:.4f}`",
            f"- Metrics equal: `{summary['repeatability']['metrics_equal']}`",
            f"- Rank differences: `{summary['repeatability']['queries_with_rank_differences']}`",
            "",
            "## Latency (descriptive)",
            "",
            "| Phase | p50 ms | p95 ms |",
            "| --- | ---: | ---: |",
            f"| Embedding | {summary['run_1']['latency']['embedding_p50_ms']:.3f} | {summary['run_1']['latency']['embedding_p95_ms']:.3f} |",
            f"| Retrieval | {summary['run_1']['latency']['retrieval_p50_ms']:.3f} | {summary['run_1']['latency']['retrieval_p95_ms']:.3f} |",
            f"| Total | {summary['run_1']['latency']['total_p50_ms']:.3f} | {summary['run_1']['latency']['total_p95_ms']:.3f} |",
            "",
            "## HNSW note",
            "",
            "The unchanged remote `hnsw.ef_search=40` setting prevents reliable top-50 retrieval, but does not block this top-20 experiment. It was not modified.",
            "",
            "No gold, corpus, embeddings, Supabase canonical rows, or local frozen files were modified.",
            "",
        ]
    )
    DOC_PATH.write_text("\n".join(lines), encoding="utf-8", newline="\n")


def main() -> int:
    corpus = FrozenCorpusV2()
    records = validate_identity(corpus)
    if len(records) != EXPECTED_QUERY_COUNT:
        raise Stage13B0R1Error("expected 25 reviewed gold records")
    settings = get_settings()
    remote_state = read_remote_state(settings)
    adapter = LlamaV2QueryEmbeddingAdapter(settings.llama_embedding_base_url)
    expected_template = (
        "Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages "
        "that directly support the answer.\nQuery: {query}"
    )
    if adapter.format_query("{query}") != expected_template:
        raise Stage13B0R1Error("canonical query formatter drifted")
    retriever = CanonicalV2Retriever(settings, embedding_adapter=adapter)

    # Live preflight proves that the unchanged canonical top-20 path returns
    # a complete candidate pool before the two audit passes begin.
    preflight, _ = retriever.retrieve_with_timing(
        records[0]["query"], normalize_specialist_scope(records[0]["specialist_scope"]), k=20
    )
    if len(preflight) != CANDIDATE_DEPTH:
        raise Stage13B0R1Error("canonical top-20 preflight returned fewer than 20 rows")
    for result in preflight:
        validate_result_contract(result, corpus, records[0]["specialist_scope"])

    run1 = _trace_run(records, corpus, retriever, 1)
    run2 = _trace_run(records, corpus, retriever, 2)
    if len(run1) != 25 or len(run2) != 25:
        raise Stage13B0R1Error("each audit run must contain 25 traces")
    if aggregate_coverage(run1)["hit@5"] != FROZEN_BASELINE_HIT_AT_5:
        raise Stage13B0R1Error(
            f"top-5 candidate Hit changed from frozen baseline: {aggregate_coverage(run1)['hit@5']}"
        )
    misses = miss_inspection(records, run1, corpus)
    recoverable = sum(
        1
        for item in misses
        if isinstance(item["first_gold_rank"], int) and item["first_gold_rank"] <= 20
    )
    candidate_hit20 = aggregate_coverage(run1)["hit@20"]
    if recoverable >= 3:
        decision = "HIGH"
    elif recoverable == 2:
        decision = "MODERATE"
    elif recoverable == 1:
        decision = "LIMITED"
    else:
        decision = "NOT JUSTIFIED"

    summary = {
        "stage": "13B0-R1 — Frozen Top-20 Candidate Recall Audit",
        "status": "PILOT / FEASIBILITY DIAGNOSTIC ONLY",
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
            "manifest_sha256": _without_sha(corpus.corpus_identity["corpus_manifest_sha256"]),
            "corpus_jsonl_sha256": _without_sha(corpus.corpus_identity["corpus_jsonl_sha256"]),
            "corpus_v2_hash": _without_sha(corpus.corpus_identity["corpus_v2_hash"]),
            "manifest_hash": _without_sha(corpus.corpus_identity["manifest_hash"]),
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
            "sentence_transformer_used": False,
            "fallback_backend": None,
        },
        "retrieval": {
            "backend": "Supabase",
            "rpc": "public.match_policy_chunks",
            "distance": "cosine",
            "tie_ordering": "cosine distance ASC, canonical_chunk_id ASC",
            "candidate_depth": CANDIDATE_DEPTH,
            "coverage_k": list(COVERAGE_K),
            "scope_routing": "SHARED or explicitly authorized SCOPED",
            "legacy_tables_used": False,
            "fts_used": False,
            "hybrid_used": False,
            "reranker_used": False,
            "session_ann_tuning": False,
            "v2_only": True,
        },
        "remote_state": remote_state,
        "run_1": {
            "query_count": len(run1),
            "coverage": aggregate_coverage(run1),
            "latency": latency_summary(run1),
            "frozen_miss_inspection": misses,
        },
        "run_2": {
            "query_count": len(run2),
            "coverage": aggregate_coverage(run2),
            "latency": latency_summary(run2),
        },
        "perfect_top20_reranker_ceiling": {
            "frozen_hit@5": FROZEN_BASELINE_HIT_AT_5,
            "candidate_hit@20": candidate_hit20,
            "maximum_additional_recoverable_queries": recoverable,
            "candidate_recall@20": aggregate_coverage(run1)["recall@20"],
            "stage12a_004_gold_ids": next(
                item["gold_canonical_chunk_ids"]
                for item in run1
                if item["evaluation_id"] == "stage12a-004"
            ),
        },
        "repeatability": repeatability(run1, run2),
        "decision": decision,
        "constraints": {
            "hnsw_ef_search_modified": False,
            "planner_settings_modified": False,
            "indexscan_settings_modified": False,
            "top50_scored": False,
            "gold_modified": False,
            "corpus_modified": False,
            "supabase_corpus_mutated": False,
            "document_embeddings_regenerated": False,
            "model_downloaded": False,
            "local_files_deleted": False,
        },
        "trace_count": len(run1),
    }
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(TRACE_PATH, run1)
    write_jsonl(RUN2_TRACE_PATH, run2)
    SUMMARY_PATH.write_text(
        json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    write_document(summary, misses)

    for path in (TRACE_PATH, RUN2_TRACE_PATH):
        parsed = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if len(parsed) != 25:
            raise Stage13B0R1Error(f"trace count mismatch at {path}")
    trace_ids = [json.loads(line)["evaluation_id"] for line in TRACE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(set(trace_ids)) != 25 or trace_ids != [item["evaluation_id"] for item in records]:
        raise Stage13B0R1Error("trace IDs do not match frozen gold order")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Stage 13B0-R1 failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1)
