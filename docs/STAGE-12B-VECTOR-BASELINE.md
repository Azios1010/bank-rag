# Stage 12B — Canonical Vector-Only Baseline

Status: **PILOT / EXPLORATORY / DESCRIPTIVE**. This document records the
first frozen vector-only measurement and is not a production SLA or a
statistically conclusive comparison.

## Frozen contract

- Gold: `dataset/evaluation/retrieval-v2-gold-pilot.jsonl` (25 REVIEWED records)
- Gold SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Corpus: `policy-corpus-v2` / 1610 chunks
- Corpus manifest SHA-256: `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`
- Embedding: `Qwen3-Embedding-0.6B`, GGUF F16, 1024D, `llama.cpp/Vulkan`
- Embedding artifact SHA-256: `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`
- Embedding manifest SHA-256: `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`
- Query instruction: `Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.`
- Query template: `Instruct: {instruction}\nQuery: {query}`
- Retriever: `CanonicalV2Retriever -> Supabase public.match_policy_chunks`
- Distance/order: cosine distance ascending, then `canonical_chunk_id` ascending
- K: `1, 3, 5`; no lexical, hybrid, RRF, reranking, expansion, or answer generation
- llama-server: `0.2.0-dev`, build `10603`, commit `c060ca974`, Vulkan on NVIDIA GeForce RTX 2050; observed `-np 1`, pooling `last`, context `3072`

## Run 1 metrics

| Metric | @1 | @3 | @5 |
| --- | ---: | ---: | ---: |
| Hit | 0.6800 | 0.8000 | 0.8400 |
| Recall | 0.6600 | 0.8000 | 0.8400 |
| MRR | 0.6800 | 0.7400 | 0.7500 |
| nDCG | 0.6800 | 0.7525 | 0.7697 |

## Latency (exploratory)

| Phase | p50 ms | p95 ms |
| --- | ---: | ---: |
| embedding | 70.808 | 96.776 |
| retrieval | 257.431 | 434.167 |
| total | 328.460 | 498.031 |

## Scope breakdown

| Scope | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| collateral_appraisal | 4 | 0.7500 | 0.7500 | 0.7500 | 0.7500 | 0.7500 |
| credit | 7 | 0.7143 | 0.7143 | 0.8571 | 0.8571 | 0.7500 |
| customer_relationship | 4 | 0.7500 | 1.0000 | 1.0000 | 1.0000 | 0.8750 |
| legal_compliance | 5 | 0.8000 | 0.8000 | 0.8000 | 0.8000 | 0.8000 |
| risk_management | 5 | 0.4000 | 0.8000 | 0.8000 | 0.8000 | 0.6000 |

## Real versus synthetic

| Set | n | Hit@1 | Hit@3 | Hit@5 | Recall@5 | MRR@5 | nDCG@5 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| real_shared | 19 | 0.6842 | 0.7895 | 0.8421 | 0.8421 | 0.7500 | 0.7691 |
| synthetic_scoped | 6 | 0.6667 | 0.8333 | 0.8333 | 0.8333 | 0.7500 | 0.7718 |

## Miss analysis

- `stage12a-007` — **embedding semantic weakness**; gold `4d11b36bf8230373ba733f43a1a956ee9831aa237b2368eff29a5384732a121d`; retrieved `511ec3a07bfc2c5a2839d27bb5c71540ba88ff8418dc81717b1fc14939337525, cacf65f29fb78465914db68e7327d40eb2ef8d8006226785589836130f4bba3d, bb54d68d09ea0a0da64db105c8507ad5d12b10aced13ecda0551ef9ffa157053, fdda9f09341a7d3fa905eaf8f7c08e84ebf42e1c3130919836f312e6bb9d14aa, 6961ba23a2763b4793d9e10c517fb1e7c8ec2d6c52552f65c3bd954ec0c34f02`.
- `stage12a-008` — **same document, wrong article**; gold `db851918c51c6e95542b44b1cf160bd15ca0b3627daffe3d9053983f9f564c17`; retrieved `a9c33ebf744710ed4092e5a860a342d84f83629075bc3d818570d1cd40db16c8, 2c9d41c83adf98dcd0152091e8edb779629a37d77128752313edd11ad7f8ee94, 21e6d15ab5cbaf1c89d289ded68f69104ef6503be1c6e049655d491caaec89e3, 22480e7c05fb71740f54bc2f5eb452236970d1c9298da65bcf07b04413c18a0c, d0402bc7a6068e9f05e390b553fb6233451210c17e7c002a38bd65384f3e6bd4`.
- `stage12a-013` — **same document, wrong article**; gold `7bfd8dde82bb3cdee31ad9ae74672ab415a5ac42ba5cd1062ae205f3dcdb9fbf`; retrieved `0ed843ba98e3640831d9119cc533d02dc3b8b7739c7c8f35e6ee6687ff004ab0, 52ac78d1ddd16ee666b8150a6319e605174b07e24c08e3235adefc866b437876, db1b0f0de46424740a7df3444907f9be13ee9caf4ff3af1be6782aaeb4432821, 7852265aaca03593c3c4e36fd2710ec5c2b0b8253e235775d5705c4863c04713, d7db66d53d2091983a7dea43446b27fb237d761c5a3377a051115eba38946753`.
- `stage12a-024` — **same document, wrong article**; gold `e08394f8133a9f1038cc4e6f23f9ad7b7c7f4b9f699861a84543336a6fc964c9`; retrieved `c5d4c2e869b5f102d8d73b1bfe2cb146aca30795dda6d2b07011f984eb00ff2e, 786c6f996d459d0cb15fde1e8557b5a760c520bc1c33a3fd6f34dd982b0c22f6, 1d275a9324a3861f63ef02fd3d84e4e9d6bf6cc44231a21d8379f69ae8169aca, a3d808aa44f60109e597c77871cbe3efca1e9f520623f26846c058510a206bb1, 5167c78b217b469cf2ae304b47460309fad37ebaad20eb21cc199bf99d01ccbb`.

Categories are descriptive trace inspection only; no gold or retrieval result was corrected.

## Repeatability

- Run 1 and Run 2 aggregate metrics equal: `True`
- Ordered top-5 agreement: `1.0000`
- Top-1 agreement: `1.0000`
- Exact top-5 set agreement: `1.0000`
- Queries with rank differences: `[]`
- Maximum corresponding-rank score drift: `0.000000000`

## Artifacts

- Summary: `dataset/evaluation/results/vector-v2-pilot-summary.json`
- Run 1 traces: `dataset/evaluation/results/vector-v2-pilot-run-1-traces.jsonl`
- Run 2 traces: `dataset/evaluation/results/vector-v2-pilot-run-2-traces.jsonl`
- Primary traces (Run 1): `dataset/evaluation/results/vector-v2-pilot-traces.jsonl`

No gold, Corpus V2, Supabase data, document vectors, or local canonical files were modified. No benchmark optimization was performed.
