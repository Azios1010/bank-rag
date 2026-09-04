# Stage 13D — Reranker Candidate-Depth Ablation: Top10 vs Top20

Status: **PILOT / EXPLORATORY / DESCRIPTIVE ONLY**.

This experiment changes only the number of frozen canonical vector candidates sent to the already-local Qwen3 reranker. No corpus, gold, embedding, vector RPC, scope rule, or reranker configuration was changed.

## Frozen contract

- Gold SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`; 25 REVIEWED records.
- Corpus: `policy-corpus-v2`, 1610 chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`.
- Query embedding: Qwen3-Embedding-0.6B, 1024D, llama.cpp/Vulkan; artifact SHA-256 `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`.
- Reranker: `D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf`; SHA-256 `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48`; `0.2.0-dev (build 10603, commit c060ca974)`.
- Runtime: `Vulkan1`, context `4096`, `np=1`, pooling `rank`, endpoint `http://127.0.0.1:8082/v1/rerank`.
- Document format: `Title: {title}
Section: {heading_path}
Text:
{content}`; original human question; no IDs, ranks, scores, gold labels, rationale, or evaluation metadata.
- Reranker-only ordering: relevance score descending, then `canonical_chunk_id` ascending; vector scores are not blended.

## Results

| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vector top-20 + reranker (frozen) | 0.8400 | 0.9600 | 0.9600 | 0.8200 | 0.9600 | 0.9600 | 0.8400 | 0.9000 | 0.9000 | 0.8400 | 0.9125 | 0.9125 |
| Vector top-10 + reranker | 0.8800 | 0.9600 | 0.9600 | 0.8600 | 0.9600 | 0.9600 | 0.8800 | 0.9200 | 0.9200 | 0.8800 | 0.9273 | 0.9273 |

## Candidate workload and latency

- Top-10: 25 × 10 = 250 query-document pairs; reranker p50/p95 `1321.409` / `1908.104` ms.
- Top-20 frozen reference: 25 × 20 = 500 query-document pairs; reranker p50/p95 `2634.266` / `3081.723` ms.
- Reduction: p50 `1312.857` ms (49.84%), p95 `1173.619` ms (38.08%).

## Recovery and regressions

- `stage12a-007`: top-10 reranked rank `1`, frozen top-20 reranked rank `1`, **RECOVERED @1**.
- `stage12a-008`: top-10 reranked rank `1`, frozen top-20 reranked rank `1`, **RECOVERED @1**.
- `stage12a-013`: top-10 reranked rank `1`, frozen top-20 reranked rank `2`, **RECOVERED @1**.
- `stage12a-024`: candidate-generation failure in both arms; exact vector rank 49 and absent from top-10/top-20 candidates.

- Top-1 regressions: `0`; top-3: `0`; top-5: `0`.

## Repeatability

- Metrics equal: `True`; ordered top-5 agreement `1.0000`; gold-rank agreement `1.0000`; max score drift `0.000000000`.

No gold, corpus, document embedding, hnsw setting, reranker model, or local canonical file was changed. No top-50 reranking, FTS, hybrid retrieval, metric tuning, model download, commit, or push was performed.
