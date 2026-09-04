# Stage 13E2 — Expanded Gold Freeze

## Purpose and authority

This document freezes the human-approved 100-query retrieval gold set.
The gold was authored evidence-first from frozen Corpus V2. No retrieval
output, vector rank, FTS rank, RRF score, reranker score, or model judgment
was used to select expected evidence IDs.

Human review is authoritative:

- Stage 12A seed: 25 / 25 REVIEWED.
- Stage 13E expansion: 75 / 75 APPROVED after R2 minor corrections.
- Total: 100 / 100 HUMAN-REVIEWED.
- Reviewer representation: `human_manual_approval`.

## Review history

- R0: 75 evidence-first DRAFT records created.
- R1: 5 evidence targets replaced, 6 substantive edits, 5 metadata/rationale edits; 59 drafts untouched.
- R2: only `stage13e-038`, `stage13e-046`, and `stage13e-059` corrected; replacements=0, rejects=0.
- R2 result: APPROVE AS-IS 72 / 75 plus 3 MINOR CORRECTIONS; final expansion approval 75 / 75.

## Released artifact

- Path: `dataset/evaluation/retrieval-v2-gold-expanded.jsonl`
- Bytes: 447571
- SHA-256: `1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69`
- Freeze timestamp: `2026-09-04T00:00:00+07:00`
- Status counts: `{'REVIEWED': 100}`

## Distribution

- Scope: `{'collateral_appraisal': 20, 'credit': 20, 'customer_relationship': 20, 'legal_compliance': 20, 'risk_management': 20}`
- Provenance: `{'real_authoritative': 80, 'synthetic': 20}`
- Visibility: `{'SCOPED': 20, 'SHARED': 80}`
- New-draft question categories at freeze: `{'consequence': 5, 'customer-facing': 3, 'direct': 13, 'distinction': 4, 'exception': 4, 'internal-policy': 8, 'multi-condition': 3, 'procedural': 18, 'role': 11, 'threshold': 6}`
- Multi-gold records: `1`
- `stage12a-004` retains both approved canonical gold IDs.
- New Stage 13E multi-gold additions: 0.

## Source coverage

- Real authoritative sources: 7 / 7.
- Synthetic sources: 3 / 3.
- Total sources: 10 / 10.

| Source ID | Records |
|---|---:|
| `synthetic-credit-approval-v1` | 7 |
| `synthetic-sme-underwriting-v1` | 6 |
| `synthetic-sme-working-capital-v1` | 7 |
| `v2-01-86-vbhn-nhnn` | 19 |
| `v2-02-100-vbhn-vpqh` | 11 |
| `v2-03-27-vbhn-nhnn` | 13 |
| `v2-04-21-2021-nd-cp` | 10 |
| `v2-05-2161-vbhn-btp` | 12 |
| `v2-06-80-2021-nd-cp` | 3 |
| `v2-07-15-2023-tt-nhnn` | 12 |

## Frozen identities

- Stage 12A pilot SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Corpus manifest SHA-256: `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`
- Embedding artifact SHA-256: `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`
- Embedding manifest SHA-256: `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`
- Corpus: `policy-corpus-v2`, 1,610 canonical chunks.
- Embedding: `Qwen3-Embedding-0.6B`, 1,024 dimensions, llama.cpp / Vulkan.

## Benchmark boundary

No vector retrieval, reranker evaluation, FTS, hybrid search, Hit@K,
Recall@K, MRR, or nDCG benchmark was run in Stage 13E2. Benchmarking begins
in Stage 13E3.
