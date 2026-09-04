# Stage 13C1 — Candidate Generation Alternatives Audit

Status: completed exploratory candidate-availability diagnostic. No gold, corpus, document embedding, reranker, or canonical vector runtime setting was changed.

## Frozen identity

- Gold SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Corpus: `policy-corpus-v2`, 1,610 unique chunks
- Corpus manifest SHA-256: `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`
- Embedding artifact SHA-256: `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`
- Embedding manifest SHA-256: `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`

## Fixed configurations

- Vector top-20: unchanged canonical llama.cpp → `public.match_policy_chunks` path.
- Vector top-50: exact offline cosine oracle over frozen parquet vectors; no HNSW top-50 request.
- OR-FTS top-10: PostgreSQL `simple` config, canonical title/heading/content index, deterministic NFC/casefold tokenization, OR tsquery, `ts_rank_cd`, canonical ID tie-break.
- Union: vector top-20 IDs followed by lexical top-10 IDs not already present; no score fusion and no reranking.

## Candidate coverage

| Candidate generator (coverage point) | Hit | Recall | Mean candidate count |
|---|---:|---:|---:|
| Vector top20 (@20) | 0.9600 | 0.9600 | 20.00 |
| Vector top50 exact diagnostic (@50) | 1.0000 | 1.0000 | 50.00 |
| Lexical OR top10 (@10) | 0.0400 | 0.0400 | 10.00 |
| Vector20 + Lexical10 union (full) | 0.9600 | 0.9600 | 29.64 |

## Lexical coverage details

- Queries returning at least 10 OR-FTS candidates: `25/25`
- OR-FTS Hit@5 / Hit@10: `0.0400` / `0.0400`
- OR-FTS Recall@5 / Recall@10: `0.0400` / `0.0400`

## Stage12a-024

- Exact vector rank: `49`
- Vector top-20: `False`
- Exact vector top-50: `True`
- OR-FTS top-10 rank: `>10`
- Vector20 + OR-FTS10 union: `False`
- OR-FTS top-10 IDs/articles: `[{"rank": 1, "canonical_chunk_id": "f15612fd2f1e9f28fe1b10432fdabbbb65f32974a129bd2b9953d4c7e36491b6", "article": "29"}, {"rank": 2, "canonical_chunk_id": "666e287e65fa8f7051a3b1224ea9ba695021ecff517f7825057a7996c75e3019", "article": "30"}, {"rank": 3, "canonical_chunk_id": "f8ad55e34e200b83cfe0d0bb135996d7a86ce99c7e3d3c156367d84f8707df59", "article": "32"}, {"rank": 4, "canonical_chunk_id": "664c04976fd1d6306900a823a0f628b1cba4ccc39338f36aa4d8f95f5e45b2f3", "article": "32"}, {"rank": 5, "canonical_chunk_id": "4ebfee854af6b38c91b9b0423e1d2d75bb5b2d25a5d90e2ec87e9ca8f0846adf", "article": "32"}, {"rank": 6, "canonical_chunk_id": "5c080a7d3838df7ce3c426d99729abf4ca15051d1c05d968d9a2d12e9bc3bf5e", "article": "32"}, {"rank": 7, "canonical_chunk_id": "7df9ec9448ca6234c31f1bbf92fbd7791d360a529a2b52cf8f1b2fccc7bd771b", "article": "32"}, {"rank": 8, "canonical_chunk_id": "87c4c0b0342df3f060550a0a7429802e15d408c220520fcf3ad9f28002324854", "article": "31"}, {"rank": 9, "canonical_chunk_id": "30ccfcfee2ff35d3344fc1e387b075d13f265554cdf6e2c4d7bd8786573ae4cb", "article": "32"}, {"rank": 10, "canonical_chunk_id": "51db9fc8f7ac20b45fd04d7a1a431c51bb4c875f716eaea87e11c67e967c694b", "article": "32"}]`

## Scope and safety

- SHARED regulation remains eligible for every supported specialist scope.
- SCOPED synthetic chunks are returned only for explicit authorized scopes; BankingOperations is unsupported.
- Every vector top-20 ID is preserved in its union; union size is never greater than 30.
- OR-FTS RPC security: anon/authenticated denied, service role allowed — `{'exists': True, 'anon_execute': False, 'authenticated_execute': False, 'service_execute': True}`.
- Real scoped probe: `{'probe_chunk_id': '0dfa22f72acb616456e7431b1362a7f80de847ec3f3c53630c887d7876521b71', 'authorized_scope': 'credit', 'authorized_present': True, 'unauthorized_scope': 'collateral_appraisal', 'unauthorized_present': False}`.

## Latency

- Vector top-20 RPC retrieval p50/p95: `274.597` / `390.555` ms.
- OR-FTS top-10 p50/p95: `513.679` / `584.776` ms.
- Union construction p50/p95: `0.010` / `0.013` ms.

## Decision

**B — VECTOR DEPTH ONLY** — The exact vector depth diagnostic supplies the missing gold, while the fixed OR-FTS10 arm does not.

This remains a pilot/exploratory candidate-coverage result. No arm is adopted canonically here and no reranker was invoked.
