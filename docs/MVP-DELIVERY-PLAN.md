# MVP delivery plan

## Goal

Deliver one complete, measurable flow for SME unsecured working-capital loan
pre-screening. The MVP demonstrates reliable evidence retrieval and human
decision support; it is not a generic lending platform.

## MVP contents

- One product profile: `SME_UNSECURED_WORKING_CAPITAL`.
- Five to ten reviewed policy documents or consolidated source snapshots.
- At least fifteen synthetic loan cases.
- Normalized case facts with document evidence.
- Hybrid full-text/vector retrieval with reranking.
- Typed `EvidencePack` and citation validation.
- Deterministic eligibility and calculation rules.
- Reviewer checks and human approval gate.
- Offline tests using deterministic model responses.

## Not in the MVP

- Full GraphRAG.
- HyDE enabled by default.
- Live CIC, sanctions, tax, registry or core-banking APIs.
- Real customer data.
- Automatic credit approval, pricing or disbursement.
- Multiple loan products.
- Fine-tuning or complex OCR benchmarking.

## Delivery sequence

### Phase 1 — Product and evidence contracts

- Add product profile and `pre_screen_outcome`.
- Add normalized facts, evidence links and reason codes.
- Disable collateral appraisal for the unsecured profile.

Exit condition: schemas can represent all cases in
[Evaluation cases](EVALUATION-CASES.md) without free-form status invention.

### Phase 2 — Policy lifecycle and ingestion

- Implement source registry metadata and version lifecycle.
- Parse policy structure and create parent/child chunks.
- Separate regulation, product and synthetic underwriting namespaces.
- Add an embedding manifest suitable for local or Kaggle batch generation.

Exit condition: an inactive or superseded policy cannot appear in active
retrieval.

### Phase 3 — Retrieval

- Add PostgreSQL full-text search.
- Keep pgvector dense retrieval.
- Merge candidates with RRF.
- Add a cross-encoder reranker.
- Produce and persist retrieval traces and `EvidencePack`.

Exit condition: the gold policy chunk appears in the final top five for the
agreed retrieval test set.

### Phase 4 — Assessment workflow

- Implement deterministic completeness and eligibility rules.
- Calculate financial ratios only from evidence-backed facts.
- Update specialist prompts to consume typed facts and EvidencePacks.
- Validate citations before writing conclusions to the Shared Board.

Exit condition: the fifteen synthetic cases produce their expected outcomes
without invented facts.

### Phase 5 — Human review and packaging

- Separate workflow status from pre-screening outcome in the UI.
- Present source version, section and fact evidence.
- Keep mock operations behind explicit human approval.

Exit condition: the UI never renders `ELIGIBLE_FOR_MANUAL_REVIEW` as loan
approval.

## Deferred decision gates

### HyDE

Evaluate only if baseline hybrid retrieval misses relevant chunks for vague
queries. Adopt it only when recall improves without unacceptable query drift,
latency or cost.

### Full GraphRAG

Evaluate only after the corpus and test set contain recurring multi-hop
questions across amendments, regulations and product policies. Until then,
use verified policy relations in PostgreSQL.

## Definition of done

The MVP is done when:

- all synthetic business cases pass offline;
- retrieval and citations are independently testable;
- policy and case-data isolation tests pass;
- the embedding/model manifest makes indexing reproducible;
- a reviewer can trace every conclusion to source facts and policy text;
- no required runtime path depends specifically on the FPT API.
