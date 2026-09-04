# Stage 13B — Qwen3-Reranker-0.6B Q8_0 / llama.cpp

Status: **PILOT / EXPLORATORY / DESCRIPTIVE ONLY**.

This experiment tests reranking only over the frozen canonical vector top-20 candidates. It does not change candidate generation, the corpus, document embeddings, gold, or scope routing.

## Frozen identity and configuration

- Gold: `dataset/evaluation/retrieval-v2-gold-pilot.jsonl`; SHA-256 `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`.
- Corpus: `policy-corpus-v2`, 1610 chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`.
- Query embedding: Qwen3-Embedding-0.6B, 1024D, llama.cpp/Vulkan; artifact SHA-256 `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`.
- Query embedding instruction: `Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.` Exact format: `Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.\nQuery: {query}`.
- Reranker GGUF: `D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf`; 639153184 bytes; SHA-256 `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48`.
- Runtime: 0.2.0-dev (build 10603, commit c060ca974), device `Vulkan1`, context `4096`, `np=1`, pooling `rank`.
- Endpoint: `http://127.0.0.1:8082/v1/rerank`; rerank flag enabled; physical ubatch `4096`.
- Exact launch contract: `llama-server.exe -m D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf -dev Vulkan1 -ngl 99 -c 4096 -np 1 -b 4096 -ub 4096 --embedding --rerank --pooling rank --host 127.0.0.1 --port 8082`.
- Document format: `Title: {title}
Section: {heading_path}
Text:
{content}` with no IDs, ranks, scores, gold labels, rationale, or evaluation metadata.
- Max sequence length: `4096`; truncation: none; all frozen candidate documents were sent intact and accepted within the 4096-token context.
- Ordering: reranker relevance score descending, then `canonical_chunk_id` ascending. Vector scores are not blended.

## Smoke tests

- gold-independent lending contrast: relevant `0.9998422861099243` > irrelevant `7.679074769839644e-05` — PASS.
- gold-independent internal-rating contrast: relevant `0.9999719858169556` > irrelevant `1.6228728782152757e-05` — PASS.

## Results

| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Vector top-20 ordering | 0.6800 | 0.8000 | 0.8400 | 0.6600 | 0.8000 | 0.8400 | 0.6800 | 0.7400 | 0.7500 | 0.6800 | 0.7525 | 0.7697 |
| Vector top-20 + reranker | 0.8400 | 0.9600 | 0.9600 | 0.8200 | 0.9600 | 0.9600 | 0.8400 | 0.9000 | 0.9000 | 0.8400 | 0.9125 | 0.9125 |

## Recoverable misses and regressions

- `stage12a-007`: vector rank `10`, reranked rank `1`, **RECOVERED @1**.
- `stage12a-008`: vector rank `8`, reranked rank `1`, **RECOVERED @1**.
- `stage12a-013`: vector rank `7`, reranked rank `2`, **RECOVERED @3**.
- `stage12a-024`: candidate-generation failure; its approved gold is absent from frozen vector top20 and cannot be recovered by this reranker.

- Top-5 regressions: `0`; IDs: none.

## Latency

Reranker request p50/p95: `2634.266` / `3081.723` ms over 25 requests, 500 query-document pairs. Candidate generation was frozen before reranking and is reported separately.

## Repeatability

Ordered top-5 agreement: `1.0000`; exact gold-rank agreement: `1.0000`; maximum score drift: `0.000000000`.

No benchmark optimization, gold mutation, Supabase mutation, embedding regeneration, model download, local deletion, or commit/push/merge was performed.
