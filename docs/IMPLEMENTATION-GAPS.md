# Implementation gap analysis

Checked against the repository on 2026-07-25.

## Already aligned

- FastAPI/Next.js application boundary.
- PostgreSQL persistence and pgvector policy storage.
- Case document storage separated from durable policy embeddings.
- Persistent assessment runs, events and checkpoints.
- Shared Board, reviewer/debate loop and human approval gate.
- Idempotent mock operations execution after approval.
- SSE event delivery with polling fallback.

## Gaps before the product slice is complete

| Priority | Gap | Required change |
| --- | --- | --- |
| P0 | Current case statuses do not represent the five pre-screening outcomes. | Add a separate `pre_screen_outcome`; do not overload workflow status. |
| P0 | Uploaded case documents are passed as text context rather than normalized fact/evidence records. | Add parsing, validation and immutable fact provenance. |
| P0 | The workflow still executes `CollateralAppraisal`. | Disable it for the unsecured product profile and return `NOT_APPLICABLE`. |
| P0 | Existing prompts can produce conclusions without the full evidence contract. | Enforce typed evidence IDs and policy citations at schema validation. |
| P1 | The policy store lacks the complete source registry contract. | Add authority, version, effective date, URL, hash and namespace metadata. |
| P1 | Embedding configuration is tied to the current OpenAI-compatible/FPT setup. | Add a provider-independent local/Kaggle ingestion path with a fixed model/version contract. |
| P1 | The demo policy and thresholds are not cleanly separated into regulation versus synthetic product policy. | Split namespaces and label every demo threshold. |
| P1 | Retrieval is vector-only and does not rerank candidates. | Add PostgreSQL full-text search, RRF merge, cross-encoder reranking and retrieval traces. |
| P1 | Character-based chunks can split legal sections and exceptions. | Add structure-aware parent/child policy chunks. |
| P1 | Policy lifecycle metadata cannot fully exclude superseded versions. | Add `effective_to`, `superseded_by`, authority and review status filters. |
| P1 | Backend evaluation coverage is too small for the business outcomes. | Implement the synthetic cases in `EVALUATION-CASES.md` with offline mocks. |
| P2 | The UI renders workflow approval labels that can look like a credit decision. | Show pre-screen outcome separately and use “manual underwriting” language. |

## Recommended implementation order

1. Add the product profile, pre-screen outcome and evidence schemas.
2. Add normalized facts and evidence provenance.
3. Version the policy registry and implement structure-aware ingestion.
4. Add hybrid retrieval, reranking and citation validation.
5. Implement document completeness and deterministic eligibility rules.
6. Narrow the agent graph for unsecured lending.
7. Add synthetic evaluation cases.
8. Update the review UI and only then replace the demo corpus.
