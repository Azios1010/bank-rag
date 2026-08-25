# Retrieval Evaluation Harness (R02)

This directory implements the retrieval evaluation harness for the `bank-rag` canonical corpus.

## Architecture

The harness is strictly for **measurement only**. It evaluates the baseline vector-only pgvector retriever using the canonical `PolicyDocument` and `PolicyEmbedding` rows staged by the R01 pipeline.

### Components
1. **Metrics**: Deterministic pure functions (`Hit@K`, `Recall@K`, `MRR@K`, `nDCG@K`) in `metrics.py`. Negative queries are excluded from macro averages but kept in traces.
2. **Gold Parser**: `GoldParser` in `gold.py` parses and validates the retrieval evaluation schema, ensuring queries are well-formed and determining expected canonical chunk targets.
3. **Embedding Adapter**: `QwenEvaluationEmbeddingAdapter` ensures we use the exact `Qwen3-Embedding-0.6B` model with `max_sequence_length=3072` and `dimension=1024`.
4. **Preflight**: Validates the embedding model manifest against expected values before allowing a benchmark to run.
5. **Retriever**: `CanonicalVectorEvaluationRetriever` fetches explicitly from `canonical_chunk_id IS NOT NULL` where `PolicyDocument.active == False`, deduplicating chunk IDs across multiple active specialist copies.
6. **CLI Runner**: `python -m app.eval.retrieval vector-baseline` coordinates the pipeline, outputs `summary.json` and `traces.jsonl` into the `evaluation-results/<run-id>` directory.

## Execution

Currently, the gold file `dataset/evaluation/retrieval.jsonl` does not exist. Running the CLI will properly fast-fail with an actionable error. 

```bash
python -m app.eval.retrieval vector-baseline \
  --database-url <url> \
  --gold-path dataset/evaluation/retrieval.jsonl \
  --sources-path dataset/normalized/policy-sources.jsonl \
  --chunks-path dataset/normalized/policy-chunks.jsonl \
  --embedding-dir "dataset/output_kaggle/Qwen3 policy embeddings" \
  --output-dir evaluation-results \
  --ks 1,3,5 \
  --run-id test-run
```
