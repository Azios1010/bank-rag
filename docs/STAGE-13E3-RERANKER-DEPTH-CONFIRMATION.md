# Stage 13E3 — 100-Query Top10 vs Top20 Reranker Confirmation

Status: **CONFIRMATION BENCHMARK / PILOT / EXPLORATORY / DESCRIPTIVE ONLY**.

One canonical query vector and one canonical top-20 RPC result were collected per question. Top-10 is the exact prefix of that same top-20 list. The only arm variable is reranker candidate depth.

## Frozen identity

- Gold: `dataset/evaluation/retrieval-v2-gold-expanded.jsonl`, 100 REVIEWED, SHA-256 `1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69`.
- Corpus: `policy-corpus-v2`, 1610 chunks; manifest SHA-256 `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`.
- Embedding: `Qwen3-Embedding-0.6B`, 1024D, llama.cpp/Vulkan; artifact SHA-256 `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`; manifest SHA-256 `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`.
- Reranker: `Qwen3-Reranker-0.6B` Q8_0 GGUF; SHA-256 `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48`; `0.2.0-dev (build 10603, commit c060ca974)`; `Vulkan1 / NVIDIA GeForce RTX 2050`.

## Results

| Arm | Hit@1 | Hit@3 | Hit@5 | Recall@1 | Recall@3 | Recall@5 | MRR@1 | MRR@3 | MRR@5 | nDCG@1 | nDCG@3 | nDCG@5 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Top10 + reranker | 0.8300 | 0.9500 | 0.9500 | 0.8250 | 0.9500 | 0.9500 | 0.8300 | 0.8850 | 0.8850 | 0.8300 | 0.9010 | 0.9010 |
| Top20 + reranker | 0.8300 | 0.9500 | 0.9700 | 0.8250 | 0.9500 | 0.9700 | 0.8300 | 0.8883 | 0.8928 | 0.8300 | 0.9036 | 0.9118 |

## Candidate coverage

- Vector candidate coverage Hit@5/10/20: `0.8800` / `0.9500` / `0.9700`.
- Vector candidate coverage Recall@5/10/20: `0.8800` / `0.9500` / `0.9700`.
- First relevant vector rank groups: 1–10 `95`, 11–20 `2`, >20 `3`.

### Candidate coverage by scope

| Scope | Queries | Hit@10 | Hit@20 | Recall@10 | Recall@20 |
|---|---:|---:|---:|---:|---:|
| credit | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| risk_management | 20 | 0.8500 | 0.9000 | 0.8500 | 0.9000 |
| legal_compliance | 20 | 0.9500 | 1.0000 | 0.9500 | 1.0000 |
| customer_relationship | 20 | 1.0000 | 1.0000 | 1.0000 | 1.0000 |
| collateral_appraisal | 20 | 0.9500 | 0.9500 | 0.9500 | 0.9500 |

### Provenance diagnostic

| Provenance | Queries | Candidate Hit@10 | Candidate Hit@20 | Top10 rerank Hit@5 | Top20 rerank Hit@5 |
|---|---:|---:|---:|---:|---:|
| real_authoritative | 80 | 0.9500 | 0.9625 | 0.9500 | 0.9625 |
| synthetic | 20 | 0.9500 | 1.0000 | 0.9500 | 1.0000 |

Top10 improved first-gold rank for `stage12a-013`, `stage13e-094`, and `stage13e-098`. Top20 improved it for `stage13e-041` and `stage13e-067`; these are the two additional Top5 successes. There were no Top5 regressions from Top10 to Top20. Top1 regressions were `stage12a-013`; Top3 regressions were `stage13e-094` and `stage13e-098`, while Top20 gained `stage13e-041` and `stage13e-067` at Top3.

## Latency and workload

- Top10 reranker p50/p95: `1242.268` / `1770.946` ms; 1000 pairs/run.
- Top20 reranker p50/p95: `2430.854` / `3164.068` ms; 2000 pairs/run.
- Top10 minus Top20 p50: `1188.586` ms (48.90%).

## Repeatability and constraints

- Top10 repeat: metrics equal `True`, ordered top-5 agreement `1.0000`, max score drift `0.000000000`.
- Top20 repeat: metrics equal `True`, ordered top-5 agreement `1.0000`, max score drift `0.000000000`.
- Decision: **B — TOP20 JUSTIFIED**.
- No FTS, hybrid/RRF, query rewrite, generation model, model download, corpus mutation, embedding regeneration, gold mutation, local deletion, or Git mutation was performed.
