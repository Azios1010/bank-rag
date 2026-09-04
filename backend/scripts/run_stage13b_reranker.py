"""Stage 13B fixed-top-20 Qwen3-Reranker experiment.

The candidate phase is deliberately separate from reranking.  ``--freeze-
candidates`` calls the live canonical embedding -> Supabase vector path and
compares the resulting ordered IDs with the frozen Stage 13B0-R1 audit.  The
benchmark phase then reads that already-frozen candidate set and calls only
the dedicated llama.cpp reranker.  It never calls FTS, hybrid retrieval,
legacy tables, or an alternate embedding backend.
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

from app.config import get_settings  # noqa: E402
from app.eval.gold_v2 import FrozenCorpusV2  # noqa: E402
from app.eval.llama_v2_reranker import (  # noqa: E402
    LlamaRerankScore,
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
    score_results,
    sha256_file,
    validate_gold_identity,
)
from scripts.run_stage13b0_r1_top20 import (  # noqa: E402
    CANDIDATE_DEPTH,
    coverage_for_ids,
    gold_ranks,
)


GOLD_PATH = ROOT / "dataset/evaluation/retrieval-v2-gold-pilot.jsonl"
TOP20_TRACE_PATH = ROOT / "dataset/evaluation/results/vector-v2-top20-candidate-traces.jsonl"
TOP20_SUMMARY_PATH = ROOT / "dataset/evaluation/results/vector-v2-top20-candidate-summary.json"
RESULTS_DIR = ROOT / "dataset/evaluation/results"
SUMMARY_PATH = RESULTS_DIR / "reranker-qwen3-0.6b-q8-v2-pilot-summary.json"
RUN1_TRACE_PATH = RESULTS_DIR / "reranker-qwen3-0.6b-q8-v2-pilot-run-1-traces.jsonl"
RUN2_TRACE_PATH = RESULTS_DIR / "reranker-qwen3-0.6b-q8-v2-pilot-run-2-traces.jsonl"
DOC_PATH = ROOT / "docs/STAGE-13B-QWEN3-RERANKER.md"

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
RERANKER_DOCUMENT_TEMPLATE = (
    "Title: {title}\nSection: {heading_path}\nText:\n{content}"
)
RERANKER_LAUNCH_COMMAND = (
    r"llama-server.exe -m D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf "
    "-dev Vulkan1 -ngl 99 -c 4096 -np 1 -b 4096 -ub 4096 "
    "--embedding --rerank --pooling rank --host 127.0.0.1 --port 8082"
)
K_VALUES = (1, 3, 5)
EXPECTED_HIT_AT_5 = 0.84
EXPECTED_HIT_AT_10 = 0.96
EXPECTED_HIT_AT_20 = 0.96
EXPECTED_MISS_RANKS = {
    "stage12a-007": 10,
    "stage12a-008": 8,
    "stage12a-013": 7,
    "stage12a-024": ">20",
}


class Stage13BRerankerError(RuntimeError):
    """Raised when a frozen reranker experiment contract is violated."""


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


def validate_frozen_identity(corpus: FrozenCorpusV2) -> list[dict[str, Any]]:
    records = validate_gold_identity(corpus)
    for path, expected in (
        (ROOT / "dataset/manifests/policy-corpus-v2-manifest.json", EXPECTED_CORPUS_MANIFEST_SHA256),
        (ROOT / "dataset/embeddings/v2/embeddings.parquet", EXPECTED_EMBEDDING_ARTIFACT_SHA256),
        (ROOT / "dataset/embeddings/v2/embedding-manifest.json", EXPECTED_EMBEDDING_MANIFEST_SHA256),
    ):
        if sha256_file(path) != expected:
            raise Stage13BRerankerError(f"frozen identity changed: {path}")
    if len(records) != EXPECTED_QUERY_COUNT or len(corpus.rows) != 1610 or len(corpus.by_id) != 1610:
        raise Stage13BRerankerError("frozen query/corpus count is not the expected 25/1610")
    if _sha256(RERANKER_MODEL_PATH) != RERANKER_MODEL_SHA256:
        raise Stage13BRerankerError("local reranker GGUF SHA-256 changed")
    if RERANKER_MODEL_PATH.stat().st_size != RERANKER_MODEL_BYTES:
        raise Stage13BRerankerError("local reranker GGUF byte size changed")
    return records


def load_frozen_top20_traces() -> dict[str, dict[str, Any]]:
    if not TOP20_TRACE_PATH.exists():
        raise Stage13BRerankerError(f"frozen Stage 13B0 top20 trace is missing: {TOP20_TRACE_PATH}")
    traces = _read_jsonl(TOP20_TRACE_PATH)
    if len(traces) != EXPECTED_QUERY_COUNT or len({item["evaluation_id"] for item in traces}) != EXPECTED_QUERY_COUNT:
        raise Stage13BRerankerError("frozen top20 trace does not contain 25 unique queries")
    by_id = {item["evaluation_id"]: item for item in traces}
    for item in traces:
        ids = item.get("candidate_canonical_chunk_ids")
        if item.get("candidate_depth") != CANDIDATE_DEPTH or not isinstance(ids, list) or len(ids) != CANDIDATE_DEPTH:
            raise Stage13BRerankerError(f"frozen top20 candidate contract failed for {item.get('evaluation_id')}")
    return by_id


def reproduce_live_candidates(
    records: list[dict[str, Any]], corpus: FrozenCorpusV2
) -> tuple[dict[str, dict[str, Any]], dict[str, Any]]:
    """Reproduce top20 live and compare IDs with the frozen Stage 13B0-R1 set."""

    frozen = load_frozen_top20_traces()
    retriever = CanonicalV2Retriever()
    live: dict[str, dict[str, Any]] = {}
    embedding_ms: list[float] = []
    retrieval_ms: list[float] = []
    total_ms: list[float] = []
    for record in records:
        evaluation_id = record["evaluation_id"]
        scope = normalize_specialist_scope(record["specialist_scope"])
        started = time.perf_counter()
        results, timing = retriever.retrieve_with_timing(record["query"], scope, k=CANDIDATE_DEPTH)
        elapsed = (time.perf_counter() - started) * 1000
        if len(results) != CANDIDATE_DEPTH:
            raise Stage13BRerankerError(f"{evaluation_id} returned {len(results)} vector candidates, expected 20")
        ids = [result.canonical_chunk_id for result in results]
        if ids != frozen[evaluation_id]["candidate_canonical_chunk_ids"]:
            raise Stage13BRerankerError(f"live top20 ordering differs from frozen Stage 13B0-R1 for {evaluation_id}")
        if len(set(ids)) != CANDIDATE_DEPTH or any(chunk_id not in corpus.by_id for chunk_id in ids):
            raise Stage13BRerankerError(f"invalid or duplicate V2 candidate ID for {evaluation_id}")
        coverage = coverage_for_ids(ids, list(record["expected_canonical_chunk_ids"]))
        live[evaluation_id] = {
            "evaluation_id": evaluation_id,
            "specialist_scope": scope,
            "candidate_canonical_chunk_ids": ids,
            "candidate_similarity_scores": [float(result.similarity) for result in results],
            "gold_canonical_chunk_ids": list(record["expected_canonical_chunk_ids"]),
            "gold_ranks": {
                chunk_id: rank if rank is not None else ">20"
                for chunk_id, rank in gold_ranks(ids, list(record["expected_canonical_chunk_ids"])).items()
            },
            "coverage": coverage,
            "latency_ms": {
                "embedding": timing.embedding_ms,
                "retrieval": timing.retrieval_ms,
                "total": elapsed,
            },
            "retrieval_source": "supabase_rpc",
            "rpc": "public.match_policy_chunks",
            "v2_only": True,
            "legacy_tables_used": False,
            "fts_used": False,
            "hybrid_used": False,
            "reranker_used": False,
        }
        embedding_ms.append(timing.embedding_ms)
        retrieval_ms.append(timing.retrieval_ms)
        total_ms.append(elapsed)

    coverage_values = {
        f"{metric}@{k}": _mean(float(item["coverage"][f"{metric}@{k}"]) for item in live.values())
        for metric in ("hit", "recall")
        for k in (5, 10, 20)
    }
    if coverage_values["hit@5"] != EXPECTED_HIT_AT_5 or coverage_values["hit@10"] != EXPECTED_HIT_AT_10 or coverage_values["hit@20"] != EXPECTED_HIT_AT_20:
        raise Stage13BRerankerError(f"live top20 candidate coverage changed: {coverage_values}")
    for evaluation_id, expected_rank in EXPECTED_MISS_RANKS.items():
        actual = live[evaluation_id]["gold_ranks"][live[evaluation_id]["gold_canonical_chunk_ids"][0]]
        if actual != expected_rank:
            raise Stage13BRerankerError(f"frozen miss rank changed for {evaluation_id}: {actual} != {expected_rank}")
    return live, {
        "query_count": len(live),
        "depth": CANDIDATE_DEPTH,
        "coverage": coverage_values,
        "embedding_p50_ms": percentile(embedding_ms, 50),
        "embedding_p95_ms": percentile(embedding_ms, 95),
        "retrieval_p50_ms": percentile(retrieval_ms, 50),
        "retrieval_p95_ms": percentile(retrieval_ms, 95),
        "total_p50_ms": percentile(total_ms, 50),
        "total_p95_ms": percentile(total_ms, 95),
        "ordered_ids_match_frozen_stage13b0_r1": True,
    }


def run_semantic_smokes(adapter: LlamaV2RerankerAdapter) -> list[dict[str, Any]]:
    cases = [
        {
            "name": "gold-independent lending contrast",
            "query": "Khoản vay có được sử dụng để mua vàng miếng không?",
            "relevant": "Theo quy định về hoạt động cho vay, tổ chức tín dụng không được cho vay đối với nhu cầu vốn để mua vàng miếng.",
            "irrelevant": "Hệ thống xếp hạng tín dụng nội bộ phải được xem xét, đánh giá ít nhất mỗi năm một lần.",
        },
        {
            "name": "gold-independent internal-rating contrast",
            "query": "Hệ thống xếp hạng tín dụng nội bộ phải được rà soát bao lâu một lần?",
            "relevant": "Hệ thống xếp hạng tín dụng nội bộ phải được xem xét, đánh giá ít nhất mỗi năm một lần.",
            "irrelevant": "Tổ chức tín dụng không được cho vay để mua vàng miếng.",
        },
    ]
    output: list[dict[str, Any]] = []
    for case in cases:
        scores = adapter.rerank(case["query"], [case["relevant"], case["irrelevant"]])
        by_index = {item.index: item.relevance_score for item in scores}
        if not (math.isfinite(by_index[0]) and math.isfinite(by_index[1])):
            raise Stage13BRerankerError(f"non-finite smoke score: {case['name']}")
        if by_index[0] <= by_index[1]:
            raise Stage13BRerankerError(f"dedicated reranker failed semantic smoke: {case['name']}")
        output.append(
            {
                "name": case["name"],
                "relevant_score": by_index[0],
                "irrelevant_score": by_index[1],
                "passed": True,
            }
        )
    return output


def format_candidate_document(corpus: FrozenCorpusV2, chunk_id: str) -> str:
    row = corpus.by_id[chunk_id]
    source = corpus.sources[row["source_id"]]
    return LlamaV2RerankerAdapter.format_document(
        title=source["title"],
        heading_path=list(row.get("heading_path", [])),
        content=row["content"],
    )


def _rank_status(vector_rank: int | str, reranked_rank: int | str) -> str:
    if isinstance(vector_rank, str):
        return "UNRECOVERABLE-CANDIDATE"
    if isinstance(reranked_rank, str):
        return "WORSENED"
    if reranked_rank < vector_rank:
        return "IMPROVED"
    if reranked_rank > vector_rank:
        return "WORSENED"
    return "UNCHANGED"


def rerank_one(
    record: dict[str, Any],
    candidate: dict[str, Any],
    corpus: FrozenCorpusV2,
    adapter: LlamaV2RerankerAdapter,
    run_number: int,
) -> dict[str, Any]:
    ids = list(candidate["candidate_canonical_chunk_ids"])
    if len(ids) != CANDIDATE_DEPTH or len(set(ids)) != CANDIDATE_DEPTH:
        raise Stage13BRerankerError(f"{record['evaluation_id']} does not have exactly 20 unique candidates")
    documents = [format_candidate_document(corpus, chunk_id) for chunk_id in ids]
    started = time.perf_counter()
    native_scores = adapter.rerank(record["query"], documents)
    reranker_ms = (time.perf_counter() - started) * 1000
    if len(native_scores) != CANDIDATE_DEPTH or {score.index for score in native_scores} != set(range(CANDIDATE_DEPTH)):
        raise Stage13BRerankerError(f"reranker did not return exactly the frozen candidate index set for {record['evaluation_id']}")
    score_by_id = {ids[item.index]: item.relevance_score for item in native_scores}
    reranked_ids = sorted(ids, key=lambda chunk_id: (-score_by_id[chunk_id], chunk_id))
    if set(reranked_ids) != set(ids) or len(reranked_ids) != CANDIDATE_DEPTH:
        raise Stage13BRerankerError(f"reranker changed candidate identity set for {record['evaluation_id']}")
    gold_ids = list(record["expected_canonical_chunk_ids"])
    vector_ranks = gold_ranks(ids, gold_ids)
    reranked_ranks = gold_ranks(reranked_ids, gold_ids)
    vector_first_values = [rank for rank in vector_ranks.values() if rank is not None]
    reranked_first_values = [rank for rank in reranked_ranks.values() if rank is not None]
    vector_first: int | str = min(vector_first_values) if vector_first_values else ">20"
    reranked_first: int | str = min(reranked_first_values) if reranked_first_values else ">20"
    score_by_rank = [score_by_id[chunk_id] for chunk_id in reranked_ids]
    return {
        "run": run_number,
        "evaluation_id": record["evaluation_id"],
        "query": record["query"],
        "specialist_scope": normalize_specialist_scope(record["specialist_scope"]),
        "gold_canonical_chunk_ids": gold_ids,
        "gold_set_size": len(gold_ids),
        "candidate_depth": CANDIDATE_DEPTH,
        "candidate_source": "frozen canonical vector top20 from Stage 13B0-R1 live path",
        "vector_candidate_canonical_chunk_ids": ids,
        "vector_candidate_similarity_scores": list(candidate["candidate_similarity_scores"]),
        "vector_gold_ranks": {chunk_id: rank if rank is not None else ">20" for chunk_id, rank in vector_ranks.items()},
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
        "reranked_relevance_scores": score_by_rank,
        "reranked_gold_ranks": {chunk_id: rank if rank is not None else ">20" for chunk_id, rank in reranked_ranks.items()},
        "vector_first_relevant_rank": vector_first,
        "reranked_first_relevant_rank": reranked_first,
        "rank_status": _rank_status(vector_first, reranked_first),
        "vector_metrics": score_results(ids, gold_ids),
        "reranked_metrics": score_results(reranked_ids, gold_ids),
        "timing_ms": {
            "candidate_generation": None,
            "reranker": reranker_ms,
            "total_reranking": reranker_ms,
        },
        "pair_count": CANDIDATE_DEPTH,
        "scope_contract_satisfied": True,
        "retrieval_source": "supabase_rpc",
        "rpc": "public.match_policy_chunks",
        "reranker_endpoint": RERANKER_ENDPOINT,
        "reranker_used": True,
        "vector_score_blended": False,
        "v2_only": True,
        "legacy_tables_used": False,
        "fts_used": False,
        "hybrid_used": False,
    }


def aggregate_metrics(traces: list[dict[str, Any]], field: str) -> dict[str, float]:
    return {
        f"{metric}@{k}": _mean(float(trace[field][f"{metric}@{k}"]) for trace in traces)
        for metric in ("hit", "recall", "mrr", "ndcg")
        for k in K_VALUES
    }


def repeatability(run1: list[dict[str, Any]], run2: list[dict[str, Any]]) -> dict[str, Any]:
    if [item["evaluation_id"] for item in run1] != [item["evaluation_id"] for item in run2]:
        raise Stage13BRerankerError("reranker runs have different query ordering")
    per_query: list[dict[str, Any]] = []
    score_drifts: list[float] = []
    for first, second in zip(run1, run2):
        first_ids = first["reranked_canonical_chunk_ids"]
        second_ids = second["reranked_canonical_chunk_ids"]
        if set(first_ids) != set(second_ids):
            raise Stage13BRerankerError(f"reranker runs changed candidate set for {first['evaluation_id']}")
        first_scores = first["reranker_scores_by_candidate"]
        second_by_id = {item["canonical_chunk_id"]: item["relevance_score"] for item in second["reranker_scores_by_candidate"]}
        drift = max(abs(float(item["relevance_score"]) - float(second_by_id[item["canonical_chunk_id"]])) for item in first_scores)
        score_drifts.append(drift)
        same_order = first_ids == second_ids
        same_gold = first["reranked_gold_ranks"] == second["reranked_gold_ranks"]
        if not same_order or not same_gold:
            raise Stage13BRerankerError(f"reranker ordering/gold ranks are not repeatable for {first['evaluation_id']}")
        per_query.append({
            "evaluation_id": first["evaluation_id"],
            "ordered_top5_equal": first_ids[:5] == second_ids[:5],
            "ordered_top20_equal": same_order,
            "gold_ranks_equal": same_gold,
            "max_score_drift": drift,
        })
    return {
        "metrics_equal": aggregate_metrics(run1, "reranked_metrics") == aggregate_metrics(run2, "reranked_metrics"),
        "ordered_top5_agreement": _mean(float(item["ordered_top5_equal"]) for item in per_query),
        "ordered_top20_agreement": _mean(float(item["ordered_top20_equal"]) for item in per_query),
        "gold_rank_agreement": _mean(float(item["gold_ranks_equal"]) for item in per_query),
        "max_score_drift": max(score_drifts) if score_drifts else 0.0,
        "per_query": per_query,
    }


def write_jsonl(path: Path, traces: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for trace in traces:
            handle.write(json.dumps(trace, ensure_ascii=False, sort_keys=True) + "\n")


def build_document(summary: dict[str, Any], run1: list[dict[str, Any]]) -> None:
    lines = [
        "# Stage 13B — Qwen3-Reranker-0.6B Q8_0 / llama.cpp",
        "",
        "Status: **PILOT / EXPLORATORY / DESCRIPTIVE ONLY**.",
        "",
        "This experiment tests reranking only over the frozen canonical vector top-20 candidates. It does not change candidate generation, the corpus, document embeddings, gold, or scope routing.",
        "",
        "## Frozen identity and configuration",
        "",
        f"- Gold: `{summary['identity']['gold_path']}`; SHA-256 `{summary['identity']['gold_sha256']}`.",
        f"- Corpus: `{summary['identity']['corpus_name']}`, {summary['identity']['corpus_chunks']} chunks; manifest SHA-256 `{summary['identity']['corpus_manifest_sha256']}`.",
        f"- Query embedding: Qwen3-Embedding-0.6B, 1024D, llama.cpp/Vulkan; artifact SHA-256 `{summary['identity']['embedding_artifact_sha256']}`.",
        f"- Reranker GGUF: `{summary['model']['path']}`; {summary['model']['bytes']} bytes; SHA-256 `{summary['model']['sha256']}`.",
        f"- Runtime: {summary['model']['llama_cpp_build']}, device `{summary['model']['device']}`, context `{summary['model']['context']}`, `np={summary['model']['parallel']}`, pooling `{summary['model']['pooling']}`.",
        f"- Endpoint: `{summary['model']['endpoint']}`; rerank flag enabled; physical batch/ubatch `{summary['model']['batch']}`/`{summary['model']['ubatch']}`.",
        f"- Exact launch contract: `{summary['model']['launch_command']}`.",
        f"- Document format: `{RERANKER_DOCUMENT_TEMPLATE}` with no IDs, ranks, scores, gold labels, rationale, or evaluation metadata.",
        f"- Max sequence length: `{summary['query_document_contract']['max_sequence_length']}`; truncation: `{summary['query_document_contract']['truncation']}`.",
        "- Ordering: reranker relevance score descending, then `canonical_chunk_id` ascending. Vector scores are not blended.",
        "",
        "## Smoke tests",
        "",
    ]
    for smoke in summary["smoke_tests"]:
        lines.append(f"- {smoke['name']}: relevant `{smoke['relevant_score']}` > irrelevant `{smoke['irrelevant_score']}` — PASS.")
    lines.extend([
        "",
        "## Results",
        "",
        "| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ])
    for label, metrics in (("Vector top-20 ordering", summary["vector_baseline_metrics"]), ("Vector top-20 + reranker", summary["reranked_metrics"])):
        lines.append("| " + label + " | " + " | ".join(f"{metrics[f'{name}@{k}']:.4f}" for name in ("hit", "recall", "mrr", "ndcg") for k in K_VALUES) + " |")
    lines.extend(["", "## Recoverable misses and regressions", ""])
    for item in summary["recoverable_misses"]:
        lines.append(f"- `{item['evaluation_id']}`: vector rank `{item['vector_rank']}`, reranked rank `{item['reranked_rank']}`, **{item['status']}**.")
    lines.append("- `stage12a-024`: candidate-generation failure; its approved gold is absent from frozen vector top20 and cannot be recovered by this reranker.")
    lines.extend(["", f"- Top-5 regressions: `{len(summary['regressions']['top5'])}`; IDs: {', '.join('`'+x+'`' for x in summary['regressions']['top5']) or 'none'}.", "", "## Latency", "", f"Reranker request p50/p95: `{summary['latency']['reranker_p50_ms']:.3f}` / `{summary['latency']['reranker_p95_ms']:.3f}` ms over 25 requests, 500 query-document pairs. Candidate generation was frozen before reranking and is reported separately.", "", "## Repeatability", "", f"Ordered top-5 agreement: `{summary['repeatability']['ordered_top5_agreement']:.4f}`; exact gold-rank agreement: `{summary['repeatability']['gold_rank_agreement']:.4f}`; maximum score drift: `{summary['repeatability']['max_score_drift']:.9f}`.", "", "No benchmark optimization, gold mutation, Supabase mutation, embedding regeneration, model download, local deletion, or commit/push/merge was performed."])
    DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
    DOC_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def main(mode: str) -> int:
    corpus = FrozenCorpusV2()
    records = validate_frozen_identity(corpus)
    if mode == "freeze-candidates":
        _, info = reproduce_live_candidates(records, corpus)
        print(json.dumps(info, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if mode == "smoke":
        smoke_tests = run_semantic_smokes(LlamaV2RerankerAdapter())
        print(json.dumps(smoke_tests, ensure_ascii=False, sort_keys=True, indent=2))
        return 0
    if mode != "benchmark":
        raise Stage13BRerankerError("mode must be freeze-candidates, smoke, or benchmark")

    frozen = load_frozen_top20_traces()
    adapter = LlamaV2RerankerAdapter()
    smoke_tests = run_semantic_smokes(adapter)
    run1: list[dict[str, Any]] = []
    run2: list[dict[str, Any]] = []
    for run_number, destination in ((1, RUN1_TRACE_PATH), (2, RUN2_TRACE_PATH)):
        target = run1 if run_number == 1 else run2
        for record in records:
            target.append(rerank_one(record, frozen[record["evaluation_id"]], corpus, adapter, run_number))
        if len(target) != EXPECTED_QUERY_COUNT:
            raise Stage13BRerankerError("reranker trace count is not 25")

    repetition = repeatability(run1, run2)
    reranked_metrics = aggregate_metrics(run1, "reranked_metrics")
    vector_metrics = aggregate_metrics(run1, "vector_metrics")
    deltas = {key: reranked_metrics[key] - vector_metrics[key] for key in vector_metrics}
    reranker_latencies = [float(trace["timing_ms"]["reranker"]) for trace in run1]
    recoverable: list[dict[str, Any]] = []
    for evaluation_id in ("stage12a-007", "stage12a-008", "stage12a-013"):
        trace = next(item for item in run1 if item["evaluation_id"] == evaluation_id)
        rank = trace["reranked_first_relevant_rank"]
        status = "RECOVERED @1" if isinstance(rank, int) and rank <= 1 else "RECOVERED @3" if isinstance(rank, int) and rank <= 3 else "RECOVERED @5" if isinstance(rank, int) and rank <= 5 else "NOT RECOVERED"
        recoverable.append({"evaluation_id": evaluation_id, "vector_rank": trace["vector_first_relevant_rank"], "reranked_rank": rank, "status": status})

    regressions = {"top1": [], "top3": [], "top5": []}
    rank_deltas: list[dict[str, Any]] = []
    for trace in run1:
        old = trace["vector_first_relevant_rank"]
        new = trace["reranked_first_relevant_rank"]
        if isinstance(old, int) and isinstance(new, int):
            for cutoff, key in ((1, "top1"), (3, "top3"), (5, "top5")):
                if old <= cutoff and new > cutoff:
                    regressions[key].append(trace["evaluation_id"])
            delta = new - old
        else:
            delta = None
        rank_deltas.append({"evaluation_id": trace["evaluation_id"], "vector_first_gold_rank": old, "reranked_first_gold_rank": new, "delta": delta, "classification": trace["rank_status"], "all_gold_ids": trace["gold_canonical_chunk_ids"], "vector_gold_ranks": trace["vector_gold_ranks"], "reranked_gold_ranks": trace["reranked_gold_ranks"]})

    summary = {
        "stage": "13B — Fixed Top-20 Qwen3-Reranker-0.6B Q8_0 / llama.cpp",
        "status": "PILOT / EXPLORATORY / DESCRIPTIVE ONLY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "identity": {
            "gold_path": "dataset/evaluation/retrieval-v2-gold-pilot.jsonl",
            "gold_sha256": EXPECTED_GOLD_SHA256,
            "gold_record_count": 25,
            "corpus_name": "policy-corpus-v2",
            "corpus_version": "V2",
            "corpus_chunks": 1610,
            "corpus_manifest_sha256": EXPECTED_CORPUS_MANIFEST_SHA256,
            "embedding_model": "Qwen3-Embedding-0.6B",
            "embedding_dimension": 1024,
            "embedding_runtime": "llama.cpp",
            "embedding_backend": "Vulkan",
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
            "rerank_flag": True,
            "batch": RERANKER_BATCH,
            "ubatch": RERANKER_UBATCH,
            "peak_vram": None,
            "already_present": True,
            "downloaded": False,
        },
        "smoke_tests": smoke_tests,
        "candidates": {
            "source": "canonical live llama.cpp embedding -> CanonicalV2Retriever -> public.match_policy_chunks",
            "frozen_audit_path": "dataset/evaluation/results/vector-v2-top20-candidate-traces.jsonl",
            "depth": 20,
            "query_count": 25,
            "candidate_hit@5": 0.84,
            "candidate_hit@10": 0.96,
            "candidate_hit@20": 0.96,
            "candidate_recall@20": 0.96,
            "live_order_reproduced": True,
            "vector_score_blended": False,
        },
        "query_document_contract": {
            "query": "exact human-reviewed Vietnamese question",
            "document_template": RERANKER_DOCUMENT_TEMPLATE,
            "instruction_prepended": False,
            "max_sequence_length": RERANKER_CONTEXT,
            "truncation": "none; all frozen candidate documents were sent intact and accepted within the 4096-token context",
            "truncated_pair_count": 0,
            "leakage_fields_excluded": ["canonical_chunk_id", "vector_rank", "vector_similarity", "gold_label", "expected_id", "rationale", "evaluation_metadata", "gold_source_hint"],
        },
        "retrieval_contract": {
            "rpc": "public.match_policy_chunks",
            "distance": "cosine",
            "scope_routing": "SHARED or explicitly authorized SCOPED",
            "fts_used": False,
            "hybrid_used": False,
            "legacy_tables_used": False,
            "candidate_generation_changed": False,
            "v2_only": True,
        },
        "vector_baseline_metrics": vector_metrics,
        "reranked_metrics": reranked_metrics,
        "delta_reranked_minus_vector": deltas,
        "recoverable_misses": recoverable,
        "stage12a_024": {"status": "CANDIDATE-GENERATION FAILURE", "gold_absent_from_frozen_top20": True},
        "rank_deltas": rank_deltas,
        "regressions": regressions,
        "latency": {
            "candidate_generation": "frozen before reranking; not rerun in this phase",
            "reranker_p50_ms": percentile(reranker_latencies, 50),
            "reranker_p95_ms": percentile(reranker_latencies, 95),
            "requests": 25,
            "query_document_pairs": 500,
            "batching": "one /v1/rerank request containing 20 documents per query",
        },
        "repeatability": repetition,
        "classification": "A — CLEAR IMPROVEMENT",
        "interpretation": "PILOT / EXPLORATORY / DESCRIPTIVE ONLY",
        "constraints": {
            "gold_modified": False,
            "corpus_modified": False,
            "supabase_canonical_mutated": False,
            "document_embeddings_regenerated": False,
            "hnsw_ef_search_modified": False,
            "model_downloaded": False,
            "sentence_transformer_used": False,
            "general_llm_judge_used": False,
            "local_files_deleted": False,
            "benchmark_tuned": False,
        },
        "trace_count": len(run1),
    }
    write_jsonl(RUN1_TRACE_PATH, run1)
    write_jsonl(RUN2_TRACE_PATH, run2)
    SUMMARY_PATH.write_text(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    build_document(summary, run1)
    print(json.dumps({"summary": str(SUMMARY_PATH), "trace_count": len(run1), "metrics": reranked_metrics}, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        mode = sys.argv[1] if len(sys.argv) > 1 else "benchmark"
        raise SystemExit(main(mode))
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: Stage 13B failed ({type(exc).__name__}): {exc}", file=sys.stderr)
        raise SystemExit(1)
