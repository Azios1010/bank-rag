# Stage 12A-FINAL — Gold Pilot Freeze

This document freezes the explicitly human-approved retrieval gold pilot. It records identity and release metadata only; the released JSONL contains the canonical evidence records.

## Approval

- Approval state: **HUMAN_APPROVED**
- Decision: **APPROVE=25, EDIT=0, REJECT=0**
- Reviewer representation: `human_manual_approval` (manual approval event role; no individual identity was supplied)
- Freeze timestamp: `2026-09-03T00:00:00+07:00`

## Released artifact

- Path: `dataset/evaluation/retrieval-v2-gold-pilot.jsonl`
- Bytes: `107477`
- SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Records: `25`
- REVIEWED: `25`
- DRAFT: `0`
- REJECTED: `0`

## Corpus identity

- Version/name: `V2 / policy-corpus-v2`
- Chunk count: `1610`
- Corpus JSONL SHA-256: `sha256:828e31d6a9d3961badb3be96bbf064819cec4c1338c1853f9144b5b373247400`
- Corpus manifest SHA-256: `sha256:b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`
- Corpus V2 hash: `sha256:1ab9185d4123a74ddc369d5231be4245ecf0b763320d8d1b0dcafe2fcdcdaa02`
- Manifest identity hash: `sha256:796a3000864b8ffe98ff681169577def16bf2717f40d496ccba3b1f85a407a6f`

## Embedding identity

- Model: `Qwen3-Embedding-0.6B`
- Format: `GGUF F16`
- Dimension/dtype: `1024 / float32`
- Runtime/backend: `llama.cpp / Vulkan`
- Pooling/normalization: `last / L2 unit`
- Embedding artifact SHA-256: `sha256:3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`
- Embedding manifest SHA-256: `sha256:cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`

## Runtime freeze identity

- Contract: `docs/STAGE-11D-RUNTIME-FREEZE.md`
- Contract SHA-256: `4b58e245c6476f26dd9d43bc5b76fa94e394d4fb88db3ce42a40496a5926b8a8`

## Distribution

### By scope

- `collateral_appraisal`: `4`
- `credit`: `7`
- `customer_relationship`: `4`
- `legal_compliance`: `5`
- `risk_management`: `5`

### By source

- `synthetic-credit-approval-v1`: `2`
- `synthetic-sme-underwriting-v1`: `2`
- `synthetic-sme-working-capital-v1`: `2`
- `v2-01-86-vbhn-nhnn`: `5`
- `v2-02-100-vbhn-vpqh`: `2`
- `v2-03-27-vbhn-nhnn`: `2`
- `v2-04-21-2021-nd-cp`: `4`
- `v2-05-2161-vbhn-btp`: `2`
- `v2-06-80-2021-nd-cp`: `1`
- `v2-07-15-2023-tt-nhnn`: `3`

The Stage 12A DRAFT review input and local frozen Corpus V2 artifacts were retained unchanged. No benchmark or retrieval run was performed.
