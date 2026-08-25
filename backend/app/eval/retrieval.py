import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from app.eval.contracts import RetrievalRequest
from app.eval.gold import GoldDatasetError, GoldParser
from app.eval.metrics import (
    binary_ndcg_at_k,
    hit_at_k,
    mrr_at_k,
    percentile,
    recall_at_k,
)
from app.eval.retrievers import CanonicalVectorEvaluationRetriever
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Retrieval Evaluation Harness")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    baseline_parser = subparsers.add_parser("vector-baseline")
    baseline_parser.add_argument("--database-url", required=True)
    baseline_parser.add_argument("--gold-path", required=True, type=Path)
    baseline_parser.add_argument("--sources-path", required=True, type=Path)
    baseline_parser.add_argument("--chunks-path", required=True, type=Path)
    baseline_parser.add_argument("--embedding-dir", required=True, type=Path)
    baseline_parser.add_argument("--output-dir", required=True, type=Path)
    baseline_parser.add_argument("--ks", required=True, type=str)
    baseline_parser.add_argument("--run-id", required=True, type=str)

    args = parser.parse_args()

    if args.command == "vector-baseline":
        try:
            run_vector_baseline(args)
        except Exception as e:  # noqa: BLE001
            logger.error(str(e))
            sys.exit(1)


def get_git_commit() -> str:
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def get_corpus_count(db) -> int:
    from sqlalchemy import select, func
    from app.db.models import PolicyEmbedding, PolicyDocument
    stmt = (
        select(func.count(func.distinct(PolicyEmbedding.canonical_chunk_id)))
        .join(PolicyDocument, PolicyEmbedding.policy_document_id == PolicyDocument.id)
        .where(
            PolicyDocument.active.is_(False),
            PolicyEmbedding.canonical_chunk_id.is_not(None),
            PolicyDocument.canonical_source_id.is_not(None),
            PolicyDocument.canonical_version_id.is_not(None)
        )
    )
    return db.execute(stmt).scalar() or 0


def get_file_sha256(filepath: Path) -> str:
    if not filepath.exists():
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return f"sha256:{h.hexdigest()}"


def run_vector_baseline(args):
    # 1. Check gold file first before anything else
    if not args.gold_path.exists():
        print(f"Gold retrieval dataset is missing:\n{args.gold_path}\n\nA reviewed gold retrieval set is required before the vector baseline can run.", file=sys.stderr)
        sys.exit(1)

    # 2. Preflight embedding validation
    manifest_path = args.embedding_dir / "embedding-manifest.json"
    if not manifest_path.exists():
        raise RuntimeError(f"Embedding manifest missing: {manifest_path}")
    
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)
        
    from app.eval.qwen_embedding import (
        QwenEvaluationEmbeddingAdapter,
        validate_embedding_profile,
    )
    validate_embedding_profile(manifest)
    
    # 3. DB setup
    engine = create_engine(args.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    with SessionLocal() as db:
        gold_parser = GoldParser(db)
        try:
            records = list(gold_parser.parse_file(args.gold_path))
        except GoldDatasetError as e:
            print(str(e), file=sys.stderr)
            sys.exit(1)

        # 4. Load heavy model only after validation passes
        adapter = QwenEvaluationEmbeddingAdapter.create_real()
        retriever = CanonicalVectorEvaluationRetriever(db, adapter)
        
        # Warm-up query
        retriever.retrieve(RetrievalRequest(evaluation_id="warmup", query="test warmup query", agent_scope="CustomerRelationship"), k=1)
        
        k_values = [int(k) for k in args.ks.split(",")]
        max_k = max(k_values)
        
        traces = []
        metrics_by_k = {k: {"hit": [], "recall": [], "mrr": [], "ndcg": []} for k in k_values}
        
        latencies = {"embedding": [], "retrieval": [], "total": []}
        
        scored_count = 0
        excluded_count = 0
        
        for record in records:
            req = RetrievalRequest(
                evaluation_id=record["evaluation_id"],
                query=record["query"],
                agent_scope=record["agent_scope"]
            )
            
            exec_result = retriever.retrieve(req, k=max_k)
            
            latencies["embedding"].append(exec_result.embedding_latency_ms)
            latencies["retrieval"].append(exec_result.retrieval_latency_ms)
            latencies["total"].append(exec_result.total_latency_ms)
            
            retrieved_ids = [res.canonical_chunk_id for res in exec_result.results]
            gold_ids = set(record.get("resolved_canonical_chunk_ids", []))
            
            # Exclusion of negative queries
            is_negative = record.get("query_type") == "NEGATIVE_NO_EVIDENCE" or not gold_ids
            
            record_metrics = {}
            if not is_negative:
                scored_count += 1
                for k in k_values:
                    h = hit_at_k(retrieved_ids, gold_ids, k)
                    r = recall_at_k(retrieved_ids, gold_ids, k)
                    m = mrr_at_k(retrieved_ids, gold_ids, k)
                    n = binary_ndcg_at_k(retrieved_ids, gold_ids, k)
                    
                    metrics_by_k[k]["hit"].append(h)
                    metrics_by_k[k]["recall"].append(r)
                    metrics_by_k[k]["mrr"].append(m)
                    metrics_by_k[k]["ndcg"].append(n)
                    
                    record_metrics[f"hit@{k}"] = h
                    record_metrics[f"recall@{k}"] = r
                    record_metrics[f"mrr@{k}"] = m
                    record_metrics[f"ndcg@{k}"] = n
            else:
                excluded_count += 1
            
            trace_entry = {
                "evaluation_id": record["evaluation_id"],
                "query": record["query"],
                "filters": record["filters"],
                "gold_selectors": record.get("gold_evidence", []),
                "resolved_gold_canonical_chunk_ids": list(gold_ids),
                "ranked_results": [
                    {
                        "canonical_chunk_id": res.canonical_chunk_id,
                        "rank": res.rank,
                        "score": res.score,
                    } for res in exec_result.results
                ],
                "candidate_count": len(exec_result.results),
                "metrics": record_metrics,
                "latency": {
                    "embedding_ms": exec_result.embedding_latency_ms,
                    "retrieval_ms": exec_result.retrieval_latency_ms,
                    "total_ms": exec_result.total_latency_ms
                },
                "exclusion_reason": "NEGATIVE_QUERY" if is_negative else None
            }
            traces.append(trace_entry)
            
        aggregate_metrics = {}
        for k in k_values:
            aggregate_metrics[f"hit@{k}"] = sum(metrics_by_k[k]["hit"]) / scored_count if scored_count > 0 else 0
            aggregate_metrics[f"recall@{k}"] = sum(metrics_by_k[k]["recall"]) / scored_count if scored_count > 0 else 0
            aggregate_metrics[f"mrr@{k}"] = sum(metrics_by_k[k]["mrr"]) / scored_count if scored_count > 0 else 0
            aggregate_metrics[f"ndcg@{k}"] = sum(metrics_by_k[k]["ndcg"]) / scored_count if scored_count > 0 else 0

        summary = {
            "run_id": args.run_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "git_commit": get_git_commit(),
            "algorithm": "vector_cosine",
            "execution_mode": "pgvector_cosine_exact",
            "k_values": k_values,
            "total_query_count": len(records),
            "scored_count": scored_count,
            "excluded_count": excluded_count,
            "corpus_count": get_corpus_count(db),
            "aggregate_metrics": aggregate_metrics,
            "latency": {
                "embedding_p50_ms": percentile(latencies["embedding"], 50.0),
                "embedding_p95_ms": percentile(latencies["embedding"], 95.0),
                "retrieval_p50_ms": percentile(latencies["retrieval"], 50.0),
                "retrieval_p95_ms": percentile(latencies["retrieval"], 95.0),
                "total_p50_ms": percentile(latencies["total"], 50.0),
                "total_p95_ms": percentile(latencies["total"], 95.0),
            },
            "reproducibility": {
                "gold_sha256": get_file_sha256(args.gold_path),
                "sources_sha256": get_file_sha256(args.sources_path),
                "chunks_sha256": get_file_sha256(args.chunks_path),
                "embedding_manifest_hash": get_file_sha256(manifest_path),
                "embedding_model": QwenEvaluationEmbeddingAdapter.MODEL_NAME,
                "immutable_revision": QwenEvaluationEmbeddingAdapter.REVISION,
                "dimension": QwenEvaluationEmbeddingAdapter.DIMENSION,
                "normalization": True,
                "max_sequence_length": QwenEvaluationEmbeddingAdapter.MAX_SEQ_LENGTH,
                "query_instruction": QwenEvaluationEmbeddingAdapter.QUERY_INSTRUCTION,
                "input_template_version": manifest.get("input_template_version"),
                "staged_inactive": True
            }
        }
        
        run_out_dir = args.output_dir / args.run_id
        run_out_dir.mkdir(parents=True, exist_ok=True)
        
        with open(run_out_dir / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
            
        with open(run_out_dir / "traces.jsonl", "w", encoding="utf-8") as f:
            f.writelines(json.dumps(t) + "\n" for t in traces)


if __name__ == "__main__":
    main()
