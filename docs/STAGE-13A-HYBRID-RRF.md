# Stage 13A - FTS + Vector + RRF

Status: PILOT / EXPLORATORY / DESCRIPTIVE.

## Frozen identity and configuration

- Gold: `dataset/evaluation/retrieval-v2-gold-pilot.jsonl`; SHA-256 `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`; 25 REVIEWED records.
- Corpus: `policy-corpus-v2` V2; 1610 chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`.
- Embedding: `Qwen3-Embedding-0.6B`, GGUF F16, 1024D, llama.cpp/Vulkan; artifact SHA-256 `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`.
- FTS: PostgreSQL `simple` configuration over `title, heading_path, content`; original human query text; GIN-backed derived tsvector.
- Candidate depths: vector `20`, lexical `20`; RRF constant `60`.
- RRF formula: `1/(60 + vector_rank) + 1/(60 + lexical_rank)`; final ordering is RRF score descending, then canonical_chunk_id ascending.
- Calls are sequential. No lexical score, vector similarity, gold metadata, query rewrite, expansion, reranker, or benchmark tuning was used.

## Three-arm metrics

| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Vector-only (frozen) | 0.6800 | 0.8000 | 0.8400 | 0.6600 | 0.8000 | 0.8400 | 0.6800 | 0.7400 | 0.7500 | 0.6800 | 0.7525 | 0.7697 |
| Lexical-only | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Hybrid RRF | 0.6800 | 0.8000 | 0.8400 | 0.6600 | 0.8000 | 0.8400 | 0.6800 | 0.7400 | 0.7500 | 0.6800 | 0.7525 | 0.7697 |

Metric column order is Hit, Recall, MRR, nDCG, each at K=1,3,5. Existing R02 definitions were used.
Lexical-only returned no candidates for 25 of 25 full natural-language questions under direct `plainto_tsquery` semantics; this is a measured arm outcome, not a runtime failure.

## Hybrid delta versus frozen vector

| Metric | @1 | @3 | @5 |
| --- | ---: | ---: | ---: |
| hit | +0.0000 | +0.0000 | +0.0000 |
| recall | +0.0000 | +0.0000 | +0.0000 |
| mrr | +0.0000 | +0.0000 | +0.0000 |
| ndcg | +0.0000 | +0.0000 | +0.0000 |

## Latency

Latency is local llama.cpp plus remote Supabase staging and is exploratory, not an SLA.

### Lexical-only

- fts: p50 `200.858 ms`; p95 `233.013 ms`
- total: p50 `200.875 ms`; p95 `233.028 ms`

### Hybrid RRF

- embedding: p50 `53.264 ms`; p95 `184.319 ms`
- vector: p50 `263.392 ms`; p95 `353.497 ms`
- fts: p50 `203.256 ms`; p95 `238.249 ms`
- fusion: p50 `0.152 ms`; p95 `0.230 ms`
- total: p50 `532.404 ms`; p95 `717.898 ms`

## Frozen vector misses @5

- `stage12a-007`: vector ranks `{'4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d': None}`; lexical ranks `{'4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d': None}`; hybrid ranks `{'4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d': None}`; lexical `NOT RECOVERED`; hybrid `NOT RECOVERED`.
- `stage12a-008`: vector ranks `{'db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17': None}`; lexical ranks `{'db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17': None}`; hybrid ranks `{'db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17': None}`; lexical `NOT RECOVERED`; hybrid `NOT RECOVERED`.
- `stage12a-013`: vector ranks `{'7bfd8dde82bb3cdee31ad9ae74672ab415a5ac42ba5cd1062ae205f3dcdb9fbf': None}`; lexical ranks `{'7bfd8dde82bb3cdee31ad9ae74672ab415a5ac42ba5cd1062ae205f3dcdb9fbf': None}`; hybrid ranks `{'7bfd8dde82bb3cdee31ad9ae74672ab415a5ac42ba5cd1062ae205f3dcdb9fbf': None}`; lexical `NOT RECOVERED`; hybrid `NOT RECOVERED`.
- `stage12a-024`: vector ranks `{'e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9': None}`; lexical ranks `{'e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9': None}`; hybrid ranks `{'e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9': None}`; lexical `NOT RECOVERED`; hybrid `NOT RECOVERED`.

- Frozen vector miss category `stage12a-007`: `embedding semantic weakness`.
- Frozen vector miss category `stage12a-008`: `same document, wrong article`.
- Frozen vector miss category `stage12a-013`: `same document, wrong article`.
- Frozen vector miss category `stage12a-024`: `same document, wrong article`.

## Regression and rank analysis

- No query had a worse first relevant rank in hybrid than in the frozen vector reference.

- Gold-rank analysis `stage12a-003`: vector ranks `{'822ee29f7db162578ce65ef9d6a5865a296e2c8fe42ad978a9a11f591a2534dd': 4}` -> hybrid ranks `{'822ee29f7db162578ce65ef9d6a5865a296e2c8fe42ad978a9a11f591a2534dd': 4}`: **UNCHANGED**.
- Gold-rank analysis `stage12a-004`: vector ranks `{'90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78': 1, 'a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c': 3}` -> hybrid ranks `{'a7672f0d87118cc75368aeb7e22d6536d800ac27585794bda397a81f6fa7709c': 3, '90d77090ea939eea85738a466c25ef4d6081a71c1c58ccab227d4fe388217d78': 1}`: **UNCHANGED**.
- Gold-rank analysis `stage12a-010`: vector ranks `{'739a78f5c46e72944da3174d45733326d62b466666c1921a00cf20866e39fe46': 2}` -> hybrid ranks `{'739a78f5c46e72944da3174d45733326d62b466666c1921a00cf20866e39fe46': 2}`: **UNCHANGED**.
- Gold-rank analysis `stage12a-012`: vector ranks `{'0ed843ba98e3640831d9119cc533d02dc3b8b7739c7c8f35e6ee6687ff004ab0': 2}` -> hybrid ranks `{'0ed843ba98e3640831d9119cc533d02dc3b8b7739c7c8f35e6ee6687ff004ab0': 2}`: **UNCHANGED**.
- Gold-rank analysis `stage12a-018`: vector ranks `{'88b8b7604c8547cd837abb04a72156813156d744fae6838db67f53db481ed4c2': 2}` -> hybrid ranks `{'88b8b7604c8547cd837abb04a72156813156d744fae6838db67f53db481ed4c2': 2}`: **UNCHANGED**.

## Scope and source breakdown

Scope and source subsets are descriptive small-N views.

| Scope | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| collateral_appraisal | 4 | 0.7500 | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| credit | 7 | 0.7143 | 0.7143 | 0.8571 | 0.8571 | 0.7500 |
| customer_relationship | 4 | 0.7500 | 1.0000 | 1.0000 | 1.0000 | 0.8750 |
| legal_compliance | 5 | 0.8000 | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| risk_management | 5 | 0.4000 | 0.8000 | 0.8000 | 0.8000 | 0.6000 |

| Source class | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 | nDCG@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| real_shared | 19 | 0.6842 | 0.7895 | 0.8421 | 0.8421 | 0.7500 | 0.7691 |
| synthetic_scoped | 6 | 0.6667 | 0.8333 | 0.8333 | 0.8333 | 0.7500 | 0.7718 |

## Repeatability

- Lexical-only: metrics equal `True`; ordered top-5 agreement `1.0000`; top-1 agreement `1.0000`; top-5 set agreement `1.0000`; rank-difference queries `[]`; max score drift `0.00000000`.
- Hybrid RRF: metrics equal `True`; ordered top-5 agreement `1.0000`; top-1 agreement `1.0000`; top-5 set agreement `1.0000`; rank-difference queries `[]`; max score drift `0.00000000`.

## Safety and scope contract

- FTS is additive and uses only canonical title, heading path, and content.
- Both RPCs preserve SHARED/SCOPED visibility; BankingOperations is unsupported.
- Returned IDs are validated against the frozen 1610-ID Corpus V2 set.
- Stage 12B artifacts were not overwritten; no corpus, vector, gold, Supabase canonical data, or local canonical files were changed.
- No benchmark beyond this pilot, no gold mutation, no document embedding regeneration, and no model download occurred.

## Artifacts

- Summary: `dataset/evaluation/results/hybrid-rrf-v2-pilot-summary.json`
- Hybrid run 1: `dataset/evaluation/results/hybrid-rrf-v2-pilot-run-1-traces.jsonl`
- Hybrid run 2: `dataset/evaluation/results/hybrid-rrf-v2-pilot-run-2-traces.jsonl`
- Lexical summary: `dataset/evaluation/results/lexical-v2-pilot-summary.json`
- Lexical run 1: `dataset/evaluation/results/lexical-v2-pilot-run-1-traces.jsonl`
- Lexical run 2: `dataset/evaluation/results/lexical-v2-pilot-run-2-traces.jsonl`
