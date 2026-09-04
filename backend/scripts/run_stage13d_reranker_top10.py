"""Stage 13D: fixed top-10 versus frozen top-20 reranker ablation.

The ``freeze-candidates`` phase is the only phase that calls the live canonical
embedding -> Supabase vector path.  The ``benchmark`` phase reads that frozen
top-10 candidate set and calls only the already-approved dedicated llama.cpp
reranker twice.  It never calls FTS, hybrid retrieval, a legacy table, or an
alternate embedding backend.
"""

from __future__ import annotations

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

from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_reranker import (  # noqa: E402
    LlamaV2RerankerAdapter,
)
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
    result_payload,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
TOP20_TRACE_PATH = ROOT / "dataset/evaluation/results/reranker-qwen3-0.6b-q8-v2-pilot-run-1-traces.jsonl"
TOP20_SUMMARY_PATH = ROOT / "dataset/evaluation/results/reranker-qwen3-0.6b-q8-v2-pilot-summary.json"
TOP20_CANDIDATE_TRACE_PATH = ROOT / "dataset/evaluation/results/vector-v2-top20-candidate-traces.jsonl"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
CANDIDATE_FREEZE_PATH = RESULTS_DIR / "reranker-top10-v2-frozen-candidates.json"
SUMMARY_PATH = RESULTS_DIR / "reranker-top10-v2-pilot-summary.json"
RUN1_TRACE_PATH = RESULTS_DIR / "reranker-top10-v2-pilot-run-1-traces.jsonl"
RUN2_TRACE_PATH = RESULTS_DIR / "reranker-top10-v2-pilot-run-2-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-13D-RERANKER-CANDIDATE-DEPTH.md"

CANDIDATE_DEPTH = 10
TOP20_DEPTH = 20
K_VALUES = (1, 3, 5)
EXPECTED_HIT_AT_10 = 0.96
EXPECTED_RECALL_AT_10 = 0.96
EXPECTED_MISS_RANKS = {
    "stage12a-007": 10,
    "stage12a-008": 8,
    "stage12a-013": 7,
    "stage12a-024": ">10",
}

RERANKER_MODEL_PATH = Path(r"D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf")
RERANKER_MODEL_SHA256 = "22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48"
RERANKER_MODEL_BYTES = 639153184
RERANKER_BUILD = "0.2.0-dev (build 10603, commit c060ca974)"
RERANKER_ENDPOINT = "http://127.0.0.1:8082/v1/rerank"
RERANKER_DEVICE = "Vulkan1"
RERANKER_CONTEXT = 4096
RERANKER_PARALLEL = 1
RERANKER_POOLING = "rank"
RERANKER_BATCH = 4096
RERANKER_UBATCH = 4096
RERANKER_DOCUMENT_TEMPLATE = "Title: {title}\nSection: {heading_path}\nText:\n{content}"
RERANKER_LAUNCH_COMMAND = (
    r"llama-server.exe -m D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf "
    "-dev Vulkan1 -ngl 99 -c 4096 -np 1 -b 4096 -ub 4096 "
    "--embedding --rerank --pooling rank --host 127.0.0.1 --port 8082"
)

TOP20_METRICS = {
    "hit@1": 0.84,
    "hit@3": 0.96,
    "hit@5": 0.96,
    "recall@1": 0.82,
    "recall@3": 0.96,
    "recall@5": 0.96,
    "mrr@1": 0.84,
    "mrr@3": 0.90,
    "mrr@5": 0.90,
    "ndcg@1": 0.84,
    "ndcg@3": 0.9125004019945024,
    "ndcg@5": 0.9125004019945024,
}


class Stage13DError(RuntimeError):
    """Raised when the top-10 ablation contract is violated."""


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return float(statistics.fmean(values)) if values else 0.0


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _gold_ranks(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, int | None]:
    rank_by_id = {chunk_id: rank for rank, chunk_id in enumerate(retrieved_ids, 1)}
    return {chunk_id: rank_by_id.get(chunk_id) for chunk_id in gold_ids}


def _coverage(retrieved_ids: list[str], gold_ids: list[str], k: int) -> dict[str, float | int]:
    gold_set = set(gold_ids)
    return {
        "hit": hit_at_k(retrieved_ids, gold_set, k),
        "recall": recall_at_k(retrieved_ids, gold_set, k),
    }


def score_results(retrieved_ids: list[str], gold_ids: list[str]) -> dict[str, float | int]:
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


def validate_frozen_identity(corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    records = validate_gold_identity(corpus)
    expected_files = {
        ROOT / "dataset/manifests/policy-corpus-v2-manifest.json": EXPECTED_CORPUS_MANIFEST_SHA256,
        ROOT / "dataset/embeddings/v2/embeddings.parquet": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
        ROOT / "dataset/embeddings/v2/embedding-manifest.json": EXPECTED_EMBEDDING_MANIFEST_SHA256,
    }
    for path, expected in expected_files.items():
        if sha256_file(path) != expected:
            raise Stage13DError(f"frozen identity changed: {path}")
    if _sha256(RERANKER_MODEL_PATH) != RERANKER_MODEL_SHA256:
        raise Stage13DError("local reranker GGUF SHA-256 changed")
    if RERANKER_MODEL_PATH.stat().st_size != RERANKER_MODEL_BYTES:
        raise Stage13DError("local reranker GGUF byte size changed")
    if len(records) != EXPECTED_QUERY_COUNT or len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise Stage13DError("frozen query/corpus count is not 25/1610")
    if len(_read_jsonl(TOP20_TRACE_PATH)) != EXPECTED_QUERY_COUNT:
        raise Stage13DError("frozen Stage 13B reranker trace is not complete")
    summary = json.loads(TOP20_SUMMARY_PATH.read_text(encoding="utf-8"))
    actual_metrics = summary.get("reranked_metrics")
    if not isinstance(actual_metrics, dict) or any(
        not math.isclose(float(actual_metrics[key]), value, rel_tol=0.0, abs_tol=1e-12)
        for key, value in TOP20_METRICS.items()
    ):
        raise Stage13DError("frozen Stage 13B top-20 metrics changed")
    return records


def _load_top20_candidates() -> dict[str, dict[str, Any]]:
    if not TOP20_CANDIDATE_TRACE_PATH.exists():
        raise Stage13DError(f"frozen Stage 13B0 candidate trace missing: {TOP20_CANDIDATE_TRACE_PATH}")
    traces = _read_jsonl(TOP20_CANDIDATE_TRACE_PATH)
    if len(traces) != EXPECTED_QUERY_COUNT or len({item.get("evaluation_id") for item in traces}) != EXPECTED_QUERY_COUNT:
        raise Stage13DError("frozen top-20 candidate trace does not contain 25 unique queries")
    by_id: dict[str, dict[str, Any]] = {}
    for item in traces:
        ids = item.get("candidate_canonical_chunk_ids")
        if item.get("candidate_depth") != TOP20_DEPTH or not isinstance(ids, list) or len(ids) != TOP20_DEPTH:
            raise Stage13DError(f"invalid frozen top-20 candidate trace: {item.get('evaluation_id')}")
        by_id[item["evaluation_id"]] = item
    return by_id


def freeze_live_candidates(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> dict[str, Any]:
    """Call only the live canonical Vector10 path and freeze its result."""

    expected_top20 = _load_top20_candidates()
    retriever = CanonicalV2Retriever()
    traces: list[dict[str, Any]] = []
    for record in records:
        evaluation_id = record["evaluation_id"]
        scope = normalize_specialist_scope(record["specialist_scope"])
        started = time.perf_counter()
        results, timing = retriever.retrieve_with_timing(record["query"], scope, k=CANDIDATE_DEPTH)
        total_ms = (time.perf_counter() - started) * 1000
        if len(results) != CANDIDATE_DEPTH:
            raise Stage13DError(f"{evaluation_id} returned {len(results)} candidates, expected 10")
        ids = [result.canonical_chunk_id for result in results]
        if len(set(ids)) != CANDIDATE_DEPTH or any(chunk_id not in corpus.by_id for chunk_id in ids):
            raise Stage13DError(f"{evaluation_id} contains invalid/duplicate V2 candidate IDs")
        if ids != list(expected_top20[evaluation_id]["candidate_canonical_chunk_ids"][:CANDIDATE_DEPTH]):
            raise Stage13DError(f"live top-10 ordering differs from frozen top-20 prefix for {evaluation_id}")
        gold_ids = list(record["expected_canonical_chunk_ids"])
        raw_ranks = _gold_ranks(ids, gold_ids)
        ranks = {chunk_id: rank if rank is not None else ">10" for chunk_id, rank in raw_ranks.items()}
        if evaluation_id in EXPECTED_MISS_RANKS:
            expected = EXPECTED_MISS_RANKS[evaluation_id]
            actual = ranks[gold_ids[0]]
            if actual != expected:
                raise Stage13DError(f"frozen top-10 rank changed for {evaluation_id}: {actual} != {expected}")
        traces.append(
            {
                "evaluation_id": evaluation_id,
                "query": record["query"],
                "specialist_scope": scope,
                "gold_canonical_chunk_ids": gold_ids,
                "gold_set_size": len(gold_ids),
                "candidate_depth": CANDIDATE_DEPTH,
                "candidate_source": "canonical live llama.cpp embedding -> CanonicalV2Retriever -> public.match_policy_chunks",
                "candidate_canonical_chunk_ids": ids,
                "candidate_similarity_scores": [float(result.similarity) for result in results],
                "candidate_results": [result_payload(result, rank, corpus) for rank, result in enumerate(results, 1)],
                "gold_ranks": ranks,
                "coverage_at_10": _coverage(ids, gold_ids, 10),
                "timing_ms": {
                    "embedding": timing.embedding_ms,
                    "vector_retrieval": timing.retrieval_ms,
                    "total": total_ms,
                },
                "scope_contract_satisfied": True,
                "rpc": "public.match_policy_chunks",
                "retrieval_source": "supabase_rpc",
                "query_embedding_backend": "llama.cpp",
                "v2_only": True,
                "legacy_tables_used": False,
                "fts_used": False,
                "hybrid_used": False,
                "reranker_used": False,
            }
        )

    hit10 = _mean(float(item["coverage_at_10"]["hit"]) for item in traces)
    recall10 = _mean(float(item["coverage_at_10"]["recall"]) for item in traces)
    if not math.isclose(hit10, EXPECTED_HIT_AT_10, rel_tol=0.0, abs_tol=1e-12) or not math.isclose(recall10, EXPECTED_RECALL_AT_10, rel_tol=0.0, abs_tol=1e-12):
        raise Stage13DError(f"top-10 candidate coverage changed: Hit@10={hit10}, Recall@10={recall10}")
    freeze = {
        "stage": "13D — frozen Vector top-10 candidate set",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "gold_path": "dataset/evaluation/retrieval-v2-gold-pilot.jsonl",
            "gold_sha256": EXPECTED_GOLD_SHA256,
            "corpus": "policy-corpus-v2",
            "corpus_chunks": 1610,
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_model": "Qwen3-Embedding-0.6B",
            "embedding_dimension": 1024,
            "embedding_artifact_sha256": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
            "embedding_manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
        },
        "candidate_contract": {
            "source": "canonical live llama.cpp embedding -> CanonicalV2Retriever -> public.match_policy_chunks",
            "rpc": "public.match_policy_chunks",
            "depth": CANDIDATE_DEPTH,
            "query_count": len(traces),
            "ordered_prefix_of_frozen_top20": True,
            "fts_used": False,
            "hybrid_used": False,
            "reranker_used": False,
        },
        "coverage": {"hit@10": hit10, "recall@10": recall10},
        "traces": traces,
    }
    CANDIDATE_FREEZE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATE_FREEZE_PATH.write_text(json.dumps(freeze, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    return freeze


def _format_document(corpus: FrozenCorpusV2, chunk_id: str) -> str:
    row = corpus.by_id[chunk_id]
    source = corpus.sources[row["source_id"]]
    return LlamaV2RerankerAdapter.format_document(
        title=source["title"], heading_path=list(row.get("heading_path", [])), content=row["content"]
    )


def _rank_status(old: int | str, new: int | str) -> str:
    if isinstance(old, str):
        return "UNRECOVERABLE-CANDIDATE"
    if isinstance(new, str):
        return "WORSENED"
    if new < old:
        return "IMPROVED"
    if new > old:
        return "WORSENED"
    return "UNCHANGED"


def _load_candidate_freeze() -> dict[str, Any]:
    if not CANDIDATE_FREEZE_PATH.exists():
        raise Stage13DError(f"top-10 candidate freeze missing: {CANDIDATE_FREEZE_PATH}")
    freeze = json.loads(CANDIDATE_FREEZE_PATH.read_text(encoding="utf-8"))
    traces = freeze.get("traces")
    if freeze.get("candidate_contract", {}).get("depth") != CANDIDATE_DEPTH or not isinstance(traces, list) or len(traces) != EXPECTED_QUERY_COUNT:
        raise Stage13DError("top-10 candidate freeze contract failed")
    if freeze.get("identity", {}).get("gold_sha256") != EXPECTED_GOLD_SHA256:
        raise Stage13DError("top-10 candidate freeze gold SHA changed")
    seen: set[str] = set()
    for item in traces:
        evaluation_id = item.get("evaluation_id")
        ids = item.get("candidate_canonical_chunk_ids")
        if not isinstance(evaluation_id, str) or evaluation_id in seen:
            raise Stage13DError("top-10 candidate freeze has duplicate/invalid query IDs")
        seen.add(evaluation_id)
        if not isinstance(ids, list) or len(ids) != CANDIDATE_DEPTH or len(set(ids)) != CANDIDATE_DEPTH:
            raise Stage13DError(f"{evaluation_id} does not have exactly 10 unique candidates")
    return freeze


def _rerank_one(record: dict[str, Any], candidate: dict[str, Any], corpus: FrozenCorpusV2, adapter: LlamaV2RerankerAdapter, run_number: int) -> dict[str, Any]:
    ids = list(candidate["candidate_canonical_chunk_ids"])
    if len(ids) != CANDIDATE_DEPTH or len(set(ids)) != CANDIDATE_DEPTH:
        raise Stage13DError(f"{record['evaluation_id']} does not have exactly 10 candidates")
    if any(chunk_id not in corpus.by_id for chunk_id in ids):
        raise Stage13DError(f"{record['evaluation_id']} contains a non-V2 candidate")
    documents = [_format_document(corpus, chunk_id) for chunk_id in ids]
    started = time.perf_counter()
    native_scores = adapter.rerank(record["query"], documents)
    elapsed = (time.perf_counter() - started) * 1000
    if len(native_scores) != CANDIDATE_DEPTH or {item.index for item in native_scores} != set(range(CANDIDATE_DEPTH)):
        raise Stage13DError(f"reranker did not return the exact 10-index set for {record['evaluation_id']}")
    score_by_id = {ids[item.index]: float(item.relevance_score) for item in native_scores}
    if any(not math.isfinite(value) for value in score_by_id.values()):
        raise Stage13DError(f"non-finite reranker score for {record['evaluation_id']}")
    reranked_ids = sorted(ids, key=lambda chunk_id: (-score_by_id[chunk_id], chunk_id))
    if set(reranked_ids) != set(ids) or len(reranked_ids) != CANDIDATE_DEPTH:
        raise Stage13DError(f"reranker changed candidate identity set for {record['evaluation_id']}")
    gold_ids = list(record["expected_canonical_chunk_ids"])
    vector_ranks = _gold_ranks(ids, gold_ids)
    reranked_ranks = _gold_ranks(reranked_ids, gold_ids)
    vector_present = [rank for rank in vector_ranks.values() if rank is not None]
    reranked_present = [rank for rank in reranked_ranks.values() if rank is not None]
    vector_first: int | str = min(vector_present) if vector_present else ">10"
    reranked_first: int | str = min(reranked_present) if reranked_present else ">10"
    return {
        "run": run_number,
        "evaluation_id": record["evaluation_id"],
        "query": record["query"],
        "specialist_scope": normalize_specialist_scope(record["specialist_scope"]),
        "gold_canonical_chunk_ids": gold_ids,
        "gold_set_size": len(gold_ids),
        "candidate_depth": CANDIDATE_DEPTH,
        "candidate_source": "frozen canonical vector top-10 candidate set",
        "vector_candidate_canonical_chunk_ids": ids,
        "vector_candidate_similarity_scores": list(candidate["candidate_similarity_scores"]),
        "vector_candidate_results": list(candidate["candidate_results"]),
        "vector_gold_ranks": {chunk_id: rank if rank is not None else ">10" for chunk_id, rank in vector_ranks.items()},
        "reranker_scores_by_candidate": [
            {
                "input_index": index,
                "canonical_chunk_id": chunk_id,
                "vector_rank": index + 1,
                "vector_similarity": float(candidate["candidate_similarity_scores"][index]),
                "relevance_score": score_by_id[chunk_id],
            }
            for index, chunk_id in enumerate(ids)
        ],
        "reranked_canonical_chunk_ids": reranked_ids,
        "reranked_relevance_scores": [score_by_id[chunk_id] for chunk_id in reranked_ids],
        "reranked_gold_ranks": {chunk_id: rank if rank is not None else ">10" for chunk_id, rank in reranked_ranks.items()},
        "vector_first_relevant_rank": vector_first,
        "reranked_first_relevant_rank": reranked_first,
        "rank_status_vs_vector_top10": _rank_status(vector_first, reranked_first),
        "vector_metrics": score_results(ids, gold_ids),
        "reranked_metrics": score_results(reranked_ids, gold_ids),
        "timing_ms": {"reranker": elapsed, "total_reranking": elapsed},
        "pair_count": CANDIDATE_DEPTH,
        "scope_contract_satisfied": True,
        "rpc": "public.match_policy_chunks",
        "retrieval_source": "supabase_rpc",
        "reranker_endpoint": RERANKER_ENDPOINT,
        "reranker_used": True,
        "vector_score_blended": False,
        "v2_only": True,
        "legacy_tables_used": False,
        "fts_used": False,
        "hybrid_used": False,
    }


def _aggregate(traces: list[dict[str, Any]], field: str) -> dict[str, float]:
    return {
        f"{metric}@{k}": _mean(float(trace[field][f"{metric}@{k}"]) for trace in traces)
        for metric in ("hit", "recall", "mrr", "ndcg")
        for k in K_VALUES
    }


def _repeatability(run1: list[dict[str, Any]], run2: list[dict[str, Any]]) -> dict[str, Any]:
    if [item["evaluation_id"] for item in run1] != [item["evaluation_id"] for item in run2]:
        raise Stage13DError("top-10 reranker runs changed query ordering")
    per_query: list[dict[str, Any]] = []
    drifts: list[float] = []
    for first, second in zip(run1, run2):
        if first["reranked_canonical_chunk_ids"] != second["reranked_canonical_chunk_ids"]:
            raise Stage13DError(f"top-10 reranked ordering is not repeatable for {first['evaluation_id']}")
        if first["reranked_gold_ranks"] != second["reranked_gold_ranks"]:
            raise Stage13DError(f"top-10 gold ranks are not repeatable for {first['evaluation_id']}")
        second_scores = {item["canonical_chunk_id"]: float(item["relevance_score"]) for item in second["reranker_scores_by_candidate"]}
        drift = max(abs(float(item["relevance_score"]) - second_scores[item["canonical_chunk_id"]]) for item in first["reranker_scores_by_candidate"])
        drifts.append(drift)
        per_query.append(
            {
                "evaluation_id": first["evaluation_id"],
                "ordered_top5_equal": True,
                "ordered_top10_equal": True,
                "gold_rank_equal": True,
                "max_score_drift": drift,
            }
        )
    metrics_equal = _aggregate(run1, "reranked_metrics") == _aggregate(run2, "reranked_metrics")
    return {
        "metrics_equal": metrics_equal,
        "ordered_top5_agreement": 1.0,
        "ordered_top10_agreement": 1.0,
        "gold_rank_agreement": 1.0,
        "max_score_drift": max(drifts) if drifts else 0.0,
        "per_query": per_query,
    }


def _load_top20_reranked() -> dict[str, dict[str, Any]]:
    traces = _read_jsonl(TOP20_TRACE_PATH)
    if len(traces) != EXPECTED_QUERY_COUNT:
        raise Stage13DError("Stage 13B top-20 trace is not 25 records")
    by_id = {item["evaluation_id"]: item for item in traces}
    if len(by_id) != EXPECTED_QUERY_COUNT:
        raise Stage13DError("Stage 13B top-20 trace has duplicate IDs")
    for item in traces:
        if item.get("candidate_depth") != TOP20_DEPTH or len(item.get("reranked_canonical_chunk_ids", [])) != TOP20_DEPTH:
            raise Stage13DError(f"invalid frozen Stage 13B trace for {item.get('evaluation_id')}")
    return by_id


def _compare_depths(run1: list[dict[str, Any]], top20: dict[str, dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    deltas: list[dict[str, Any]] = []
    regressions = {"top1": [], "top3": [], "top5": []}
    for trace in run1:
        old = top20[trace["evaluation_id"]]["reranked_first_relevant_rank"]
        new = trace["reranked_first_relevant_rank"]
        if isinstance(old, str) or isinstance(new, str):
            classification = "UNRECOVERABLE-CANDIDATE"
            delta = None
        elif new < old:
            classification = "IMPROVED"
            delta = new - old
        elif new > old:
            classification = "WORSENED"
            delta = new - old
        else:
            classification = "UNCHANGED"
            delta = 0
        if isinstance(old, int) and isinstance(new, int):
            for cutoff, key in ((1, "top1"), (3, "top3"), (5, "top5")):
                if old <= cutoff and new > cutoff:
                    regressions[key].append(trace["evaluation_id"])
        deltas.append(
            {
                "evaluation_id": trace["evaluation_id"],
                "top20_first_gold_rank": old,
                "top10_first_gold_rank": new,
                "delta_top10_minus_top20": delta,
                "classification": classification,
                "top20_all_gold_ranks": top20[trace["evaluation_id"]]["reranked_gold_ranks"],
                "top10_all_gold_ranks": trace["reranked_gold_ranks"],
            }
        )
    return deltas, regressions


def run_semantic_smokes(adapter: LlamaV2RerankerAdapter) -> list[dict[str, Any]]:
    cases = [
        {
            "name": "lending prohibited-purpose contrast",
            "query": "Khoản vay có được sử dụng để mua vàng miếng không?",
            "relevant": "Theo quy định về hoạt động cho vay, tổ chức tín dụng không được cho vay đối với nhu cầu vốn để mua vàng miếng.",
            "irrelevant": "Hệ thống xếp hạng tín dụng nội bộ phải được xem xét, đánh giá ít nhất mỗi năm một lần.",
        },
        {
            "name": "internal-rating review-period contrast",
            "query": "Hệ thống xếp hạng tín dụng nội bộ phải được rà soát bao lâu một lần?",
            "relevant": "Hệ thống xếp hạng tín dụng nội bộ phải được xem xét, đánh giá ít nhất mỗi năm một lần.",
            "irrelevant": "Tổ chức tín dụng không được cho vay để mua vàng miếng.",
        },
    ]
    output: list[dict[str, Any]] = []
    for case in cases:
        scores = adapter.rerank(case["query"], [case["relevant"], case["irrelevant"]])
        by_index = {item.index: item.relevance_score for item in scores}
        if by_index[0] <= by_index[1]:
            raise Stage13DError(f"dedicated reranker semantic smoke failed: {case['name']}")
        output.append(
            {
                "name": case["name"],
                "relevant_score": float(by_index[0]),
                "irrelevant_score": float(by_index[1]),
                "passed": True,
            }
        )
    return output


def _write_jsonl(path: Path, traces: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in traces:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _build_document(summary: dict[str, Any]) -> None:
    top10 = summary["top10_reranked_metrics"]
    top20 = summary["top20_reranked_metrics"]
    lines = [
        "# Stage 13D — Reranker Candidate-Depth Ablation: Top10 vs Top20",
        "",
        "Status: **PILOT / EXPLORATORY / DESCRIPTIVE ONLY**.",
        "",
        "This experiment changes only the number of frozen canonical vector candidates sent to the already-local Qwen3 reranker. No corpus, gold, embedding, vector RPC, scope rule, or reranker configuration was changed.",
        "",
        "## Frozen contract",
        "",
        f"- Gold SHA-256: `{summary['identity']['gold_sha256']}`; 25 REVIEWED records.",
        f"- Corpus: `{summary['identity']['corpus']}`, 1610 chunks; manifest SHA-256 `{summary['identity']['corpus_manifest_sha256']}`.",
        f"- Query embedding: Qwen3-Embedding-0.6B, 1024D, llama.cpp/Vulkan; artifact SHA-256 `{summary['identity']['embedding_artifact_sha256']}`.",
        f"- Reranker: `{summary['model']['path']}`; SHA-256 `{summary['model']['sha256']}`; `{summary['model']['llama_cpp_build']}`.",
        f"- Runtime: `{summary['model']['device']}`, context `{summary['model']['context']}`, `np={summary['model']['parallel']}`, pooling `{summary['model']['pooling']}`, endpoint `{summary['model']['endpoint']}`.",
        f"- Document format: `{RERANKER_DOCUMENT_TEMPLATE}`; original human question; no IDs, ranks, scores, gold labels, rationale, or evaluation metadata.",
        "- Reranker-only ordering: relevance score descending, then `canonical_chunk_id` ascending; vector scores are not blended.",
        "",
        "## Results",
        "",
        "| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label, metrics in (("Vector top-20 + reranker (frozen)", top20), ("Vector top-10 + reranker", top10)):
        lines.append("| " + label + " | " + " | ".join(f"{metrics[f'{name}@{k}']:.4f}" for name in ("hit", "recall", "mrr", "ndcg") for k in K_VALUES) + " |")
    lines.extend(
        [
            "",
            "## Candidate workload and latency",
            "",
            f"- Top-10: 25 × 10 = 250 query-document pairs; reranker p50/p95 `{summary['latency']['top10_reranker_p50_ms']:.3f}` / `{summary['latency']['top10_reranker_p95_ms']:.3f}` ms.",
            f"- Top-20 frozen reference: 25 × 20 = 500 query-document pairs; reranker p50/p95 `{summary['latency']['top20_reranker_p50_ms']:.3f}` / `{summary['latency']['top20_reranker_p95_ms']:.3f}` ms.",
            f"- Reduction: p50 `{summary['latency']['reduction_p50_ms']:.3f}` ms ({summary['latency']['reduction_p50_percent']:.2f}%), p95 `{summary['latency']['reduction_p95_ms']:.3f}` ms ({summary['latency']['reduction_p95_percent']:.2f}%).",
            "",
            "## Recovery and regressions",
            "",
        ]
    )
    for item in summary["recoverable_misses"]:
        lines.append(f"- `{item['evaluation_id']}`: top-10 reranked rank `{item['top10_reranked_rank']}`, frozen top-20 reranked rank `{item['top20_reranked_rank']}`, **{item['status']}**.")
    lines.append("- `stage12a-024`: candidate-generation failure in both arms; exact vector rank 49 and absent from top-10/top-20 candidates.")
    lines.extend(
        [
            "",
            f"- Top-1 regressions: `{len(summary['regressions']['top1'])}`; top-3: `{len(summary['regressions']['top3'])}`; top-5: `{len(summary['regressions']['top5'])}`.",
            "",
            "## Repeatability",
            "",
            f"- Metrics equal: `{summary['repeatability']['metrics_equal']}`; ordered top-5 agreement `{summary['repeatability']['ordered_top5_agreement']:.4f}`; gold-rank agreement `{summary['repeatability']['gold_rank_agreement']:.4f}`; max score drift `{summary['repeatability']['max_score_drift']:.9f}`.",
            "",
            "No gold, corpus, document embedding, hnsw setting, reranker model, or local canonical file was changed. No top-50 reranking, FTS, hybrid retrieval, metric tuning, model download, commit, or push was performed.",
        ]
    )
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def run_benchmark(records: list[dict[str, Any]], corpus: FrozenCorpusV2) -> dict[str, Any]:
    freeze = _load_candidate_freeze()
    freeze_by_id = {item["evaluation_id"]: item for item in freeze["traces"]}
    if set(freeze_by_id) != {item["evaluation_id"] for item in records}:
        raise Stage13DError("candidate freeze IDs do not match frozen gold IDs")
    adapter = LlamaV2RerankerAdapter(base_url=RERANKER_ENDPOINT.removesuffix("/v1/rerank"))
    smoke_tests = run_semantic_smokes(adapter)
    runs: list[list[dict[str, Any]]] = []
    for run_number in (1, 2):
        current: list[dict[str, Any]] = []
        for record in records:
            current.append(_rerank_one(record, freeze_by_id[record["evaluation_id"]], corpus, adapter, run_number))
        if len(current) != EXPECTED_QUERY_COUNT or sum(item["pair_count"] for item in current) != 250:
            raise Stage13DError("top-10 reranker workload/trace count failed")
        runs.append(current)
    run1, run2 = runs
    repetition = _repeatability(run1, run2)
    if not repetition["metrics_equal"]:
        raise Stage13DError("top-10 reranker aggregate metrics differ between runs")
    top20 = _load_top20_reranked()
    rank_deltas, regressions = _compare_depths(run1, top20)
    top10_metrics = _aggregate(run1, "reranked_metrics")
    top10_vector_candidate_metrics = _aggregate(run1, "vector_metrics")
    deltas = {key: top10_metrics[key] - TOP20_METRICS[key] for key in TOP20_METRICS}
    recoverable: list[dict[str, Any]] = []
    for evaluation_id in ("stage12a-007", "stage12a-008", "stage12a-013"):
        trace = next(item for item in run1 if item["evaluation_id"] == evaluation_id)
        top20_rank = top20[evaluation_id]["reranked_first_relevant_rank"]
        rank = trace["reranked_first_relevant_rank"]
        status = "RECOVERED @1" if isinstance(rank, int) and rank <= 1 else "RECOVERED @3" if isinstance(rank, int) and rank <= 3 else "RECOVERED @5" if isinstance(rank, int) and rank <= 5 else "NOT RECOVERED"
        recoverable.append({"evaluation_id": evaluation_id, "top10_vector_rank": trace["vector_first_relevant_rank"], "top10_reranked_rank": rank, "top20_reranked_rank": top20_rank, "status": status})
    top10_latencies = [float(item["timing_ms"]["reranker"]) for item in run1]
    top20_p50 = 2634.266
    top20_p95 = 3081.723
    top10_p50 = percentile(top10_latencies, 50)
    top10_p95 = percentile(top10_latencies, 95)
    reduction_p50 = top20_p50 - top10_p50
    reduction_p95 = top20_p95 - top10_p95
    no_metric_degradation = all(top10_metrics[key] + 1e-12 >= TOP20_METRICS[key] for key in TOP20_METRICS)
    no_boundary_regressions = not any(regressions.values())
    if no_metric_degradation and no_boundary_regressions and reduction_p50 > 0 and reduction_p95 > 0:
        classification = "A — TOP10 DOMINATES"
    elif reduction_p50 > 0 and reduction_p95 > 0 and max(abs(value) for value in deltas.values()) <= 0.02:
        classification = "B — TOP10 ACCEPTABLE TRADEOFF"
    else:
        classification = "C — TOP20 JUSTIFIED"
    summary = {
        "stage": "13D — Reranker Candidate-Depth Ablation: Top10 vs Top20",
        "status": "PILOT / EXPLORATORY / DESCRIPTIVE ONLY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "gold_path": "dataset/evaluation/retrieval-v2-gold-pilot.jsonl",
            "gold_sha256": EXPECTED_GOLD_SHA256,
            "gold_record_count": EXPECTED_QUERY_COUNT,
            "corpus": "policy-corpus-v2",
            "corpus_version": "V2",
            "corpus_chunks": 1610,
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_model": "Qwen3-Embedding-0.6B",
            "embedding_dimension": 1024,
            "embedding_artifact_sha256": EXPECTED_EMBEDDING_ARTIFACT_SHA256,
            "embedding_manifest_sha256": EXPECTED_EMBEDDING_MANIFEST_SHA256,
        },
        "model": {
            "path": str(RERANKER_MODEL_PATH),
            "bytes": RERANKER_MODEL_BYTES,
            "sha256": RERANKER_MODEL_SHA256,
            "model": "Qwen3-Reranker-0.6B",
            "revision": "qwen3-reranker-0.6b-q8_0.gguf",
            "quantization": "Q8_0 GGUF",
            "llama_cpp_build": RERANKER_BUILD,
            "runtime": "llama.cpp",
            "device": RERANKER_DEVICE,
            "context": RERANKER_CONTEXT,
            "parallel": RERANKER_PARALLEL,
            "pooling": RERANKER_POOLING,
            "endpoint": RERANKER_ENDPOINT,
            "launch_command": RERANKER_LAUNCH_COMMAND,
            "batch": RERANKER_BATCH,
            "ubatch": RERANKER_UBATCH,
            "peak_vram": None,
            "already_present": True,
            "downloaded": False,
        },
        "candidate_contract": {
            "top10_source": "frozen canonical live vector top-10 from public.match_policy_chunks",
            "top10_depth": CANDIDATE_DEPTH,
            "top20_reference_source": "frozen Stage 13B top-20 reranker result",
            "top20_depth": TOP20_DEPTH,
            "candidate_hit@10": EXPECTED_HIT_AT_10,
            "candidate_recall@10": EXPECTED_RECALL_AT_10,
            "pair_workload_top10": 250,
            "pair_workload_top20": 500,
            "vector_score_blended": False,
            "no_candidate_injection_or_loss": True,
        },
        "reranker_contract": {
            "document_template": RERANKER_DOCUMENT_TEMPLATE,
            "query": "exact human-reviewed Vietnamese question",
            "instruction_prepended": False,
            "sort": "relevance_score DESC, canonical_chunk_id ASC",
            "score_blended": False,
            "input_batching": "one /v1/rerank request containing 10 documents per query",
        },
        "smoke_tests": smoke_tests,
        "top10_vector_candidate_metrics": top10_vector_candidate_metrics,
        "top20_reranked_metrics": TOP20_METRICS,
        "top10_reranked_metrics": top10_metrics,
        "delta_top10_reranked_minus_top20_reranked": deltas,
        "recoverable_misses": recoverable,
        "stage12a_024": {
            "top10_status": "CANDIDATE-GENERATION FAILURE",
            "top20_status": "CANDIDATE-GENERATION FAILURE",
            "exact_vector_rank": 49,
            "gold_absent_from_top10": True,
            "gold_absent_from_top20": True,
        },
        "rank_deltas_top10_vs_top20": rank_deltas,
        "regressions": regressions,
        "latency": {
            "top10_reranker_p50_ms": top10_p50,
            "top10_reranker_p95_ms": top10_p95,
            "top20_reranker_p50_ms": top20_p50,
            "top20_reranker_p95_ms": top20_p95,
            "reduction_p50_ms": reduction_p50,
            "reduction_p95_ms": reduction_p95,
            "reduction_p50_percent": reduction_p50 / top20_p50 * 100,
            "reduction_p95_percent": reduction_p95 / top20_p95 * 100,
            "requests_per_run": EXPECTED_QUERY_COUNT,
            "query_document_pairs_top10": 250,
            "query_document_pairs_top20": 500,
        },
        "repeatability": repetition,
        "classification": classification,
        "interpretation": "PILOT / EXPLORATORY / DESCRIPTIVE ONLY",
        "constraints": {
            "candidate_depth_only_variable": True,
            "gold_modified": False,
            "corpus_modified": False,
            "document_embeddings_regenerated": False,
            "hnsw_settings_modified": False,
            "fts_used": False,
            "hybrid_used": False,
            "sentence_transformer_used": False,
            "model_downloaded": False,
            "local_files_deleted": False,
        },
        "trace_count": len(run1),
    }
    _write_jsonl(RUN1_TRACE_PATH, run1)
    _write_jsonl(RUN2_TRACE_PATH, run2)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    _build_document(summary)
    return summary


def main(mode: str) -> int:
    corpus = FrozenCorpusV2()
    records = validate_frozen_identity(corpus)
    if mode == "freeze-candidates":
        freeze = freeze_live_candidates(records, corpus)
        print(json.dumps({"candidate_freeze": str(CANDIDATE_FREEZE_PATH), "query_count": len(freeze["traces"]), "coverage": freeze["coverage"]}, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if mode == "benchmark":
        summary = run_benchmark(records, corpus)
        print(json.dumps({"summary": str(SUMMARY_PATH), "metrics": summary["top10_reranked_metrics"], "classification": summary["classification"]}, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    raise Stage13DError("mode must be freeze-candidates or benchmark")


if __name__ == "__main__":
    try:
        raise SystemExit(main(sys.argv[1] if len(sys.argv) > 1 else "benchmark"))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Stage 13D failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1)
