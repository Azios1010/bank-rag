# Stage 13B0-R1 — Frozen Top-20 Candidate Recall Audit

Status: **FEASIBILITY DIAGNOSTIC ONLY**. The unchanged vector path was
audited at the intended top-20 reranker candidate depth. No reranker was
loaded or implemented, and no quality benchmark was run.

## Runtime

- Canonical path: `llama.cpp -> CanonicalV2Retriever -> public.match_policy_chunks`
- Candidate depth: `20`; coverage K: `5, 10, 20`
- HNSW `ef_search`: `40`; no planner/index setting was changed.
- No FTS, hybrid, sequential scan, session-local ANN tuning, query rewrite, or reranker was used.

## Frozen identity

- Gold SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Corpus: `policy-corpus-v2` / `1610` chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`
- Embedding: `Qwen3-Embedding-0.6B`, `1024D`, `llama.cpp/Vulkan`

## Candidate coverage

| Metric | @5 | @10 | @20 |
| --- | ---: | ---: | ---: |
| Hit | 0.8400 | 0.9600 | 0.9600 |
| Recall | 0.8400 | 0.9600 | 0.9600 |

## Frozen @5 misses

- `stage12a-007` — gold rank `10`; **ranking failure**; **A — HIGHLY RERANKABLE**. Top-1 `511ec3a07bfc2c5a2839d27bb5c71540ba88ff8418dc81717b1fc14939337525`, source `synthetic-sme-underwriting-v1`, article `UW-STATUS`. Same-document candidates: `2`.
- `stage12a-008` — gold rank `8`; **ranking failure**; **A — HIGHLY RERANKABLE**. Top-1 `a9c33ebf744710ed4092e5a860a342d84f83629075bc3d818570d1cd40db16c8`, source `v2-07-15-2023-tt-nhnn`, article `9`. Same-document candidates: `2`.
- `stage12a-013` — gold rank `7`; **ranking failure**; **A — HIGHLY RERANKABLE**. Top-1 `0ed843ba98e3640831d9119cc533d02dc3b8b7739c7c8f35e6ee6687ff004ab0`, source `v2-02-100-vbhn-vpqh`, article `101`. Same-document candidates: `7`.
- `stage12a-024` — gold rank `>20`; **candidate-generation failure**; **D — NOT RECOVERABLE BY A TOP-20 RERANKER**. Top-1 `c5d4c2e869b5f102d8d73b1bfe2cb146aca30795dda6d2b07011f984eb00ff2e`, source `v2-05-2161-vbhn-btp`, article `37`. Same-document candidates: `20`.

## Perfect top-20 reranker ceiling

- Frozen Stage 12B Hit@5: `0.8400`.
- Candidate Hit@20: `0.9600`.
- Maximum additional frozen @5 misses available to a perfect top-20 reranker: `3`.
- Candidate Recall@20: `0.9600`; this bounds recovery of all approved IDs, including both gold IDs for stage12a-004.
- Decision: **HIGH**.
- The ceiling is theoretical and does not predict actual reranker performance.

## Repeatability

- Ordered top-20 agreement: `1.0000`
- Ordered top-10 agreement: `1.0000`
- Ordered top-5 agreement: `1.0000`
- Exact gold-rank agreement: `1.0000`
- Metrics equal: `True`
- Rank differences: `[]`

## Latency (descriptive)

| Phase | p50 ms | p95 ms |
| --- | ---: | ---: |
| Embedding | 65.691 | 95.554 |
| Retrieval | 270.724 | 351.853 |
| Total | 339.304 | 406.411 |

## HNSW note

The unchanged remote `hnsw.ef_search=40` setting prevents reliable top-50 retrieval, but does not block this top-20 experiment. It was not modified.

No gold, corpus, embeddings, Supabase canonical rows, or local frozen files were modified.
