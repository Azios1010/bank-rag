# Limitations and compliance boundary

Public documents are sufficient to explain legal context and document a
reproducible demo. They are not sufficient to reconstruct a bank's internal
credit policy. Internal risk appetite, scorecards, fraud rules, pricing,
delegation limits, CIC results and exception authorities must be supplied by
the deploying institution or represented by synthetic fixtures.

The product therefore:

- presents recommendations as pre-screening, never as a final credit
  decision;
- keeps a human approval gate before operational actions;
- records policy version, effective date, evidence location and model run;
- isolates case documents by `case_id` and excludes PII from durable policy
  embeddings;
- supports correction and re-run while preserving the previous audit trail;
- fails closed on missing, conflicting or stale evidence.

Before production use, obtain a compliance review for jurisdiction, data
retention, access control, consent, model risk management, explainability and
third-party API processing. Revalidate every legal source after amendments.
The active privacy baseline is Law 91/2025/QH15 and Decree
356/2025/NĐ-CP; Decree 13/2023/NĐ-CP must not be treated as current after
2026-01-01.
