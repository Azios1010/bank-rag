# Retrieval Evaluation Harness (R02)

This directory contains the retrieval evaluation contracts for the `bank-rag`
canonical corpus.  Stage 11D freezes the real Corpus V2 runtime as
`CanonicalV2Retriever` (llama.cpp query embedding followed by the Supabase
`match_policy_chunks` RPC).  The historical SQLAlchemy harness below remains
available only for R01 compatibility and is not a Corpus V2 retrieval path.

## Architecture

The harness is strictly for **measurement only**.  Stage 12 will evaluate the
frozen V2 path without changing its embedding, routing, or ranking contract.
The historical runner is explicitly tied to legacy `PolicyDocument`,
`PolicyEmbedding`, and `AgentKnowledgeBase` rows and must not be used for V2.

### Components
1. **Metrics**: Deterministic pure functions (`Hit@K`, `Recall@K`, `MRR@K`, `nDCG@K`) in `metrics.py`. Negative queries are excluded from macro averages but kept in traces.
2. **Historical Gold Parser**: `GoldParser` in `gold.py` remains the R01 compatibility parser and resolves legacy database references. It is not the Corpus V2 gold contract.
3. **Corpus V2 Gold Contract**: `CanonicalGoldValidator` in `gold_v2.py` validates evidence-first records against the frozen local Corpus V2 ID set and Stage 10 embedding identity. Stage 12A drafts are stored at `dataset/evaluation/retrieval-v2-gold-pilot.draft.jsonl`; all records are `DRAFT` and require human review.
4. **V2 Embedding Adapter**: `LlamaV2QueryEmbeddingAdapter` sends the exact
   instruction-formatted query to the local llama.cpp OpenAI-compatible API.
5. **Preflight**: Validates the embedding model manifest against expected values before allowing a benchmark to run.
6. **V2 Retriever**: `CanonicalV2Retriever` calls only Supabase
   `public.match_policy_chunks`; Python does not reproduce cosine ranking or
   scope routing.
7. **Historical Runner**: `python -m app.eval.retrieval vector-baseline` is
   retained for legacy R01 tests and is not a V2 baseline command.

## Execution

The Stage 12A pilot is a review input, not a benchmark input. Do not point the
historical runner at `retrieval-v2-gold-pilot.draft.jsonl`. Only a separate
human-reviewed export may be used for a later Stage 12 evaluation.

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
