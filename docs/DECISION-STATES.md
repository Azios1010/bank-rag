# Decision states

The pre-screening outcome is a controlled vocabulary. Agents must not invent
additional outcome labels.

| Outcome | Meaning | Required next action |
| --- | --- | --- |
| `FAILED_DATA_VALIDATION` | A file is unreadable, malformed or internally invalid. | Correct or replace the file. |
| `MISSING_DOCUMENTS` | A required document or consent is absent. | Request the named document(s). |
| `INELIGIBLE_BY_RULE` | A documented hard gate fails (for example, excluded purpose). | Record the rule and stop automated analysis. |
| `REFER_TO_CREDIT_OFFICER` | Facts conflict, evidence is weak, or a configurable exception is present. | Human investigation and decision. |
| `ELIGIBLE_FOR_MANUAL_REVIEW` | Required inputs pass configured pre-screen checks. | Human underwriting; not approval. |

Every outcome must include `reason_codes`, `open_questions`, `evidence_ids`,
`policy_citations` and `generated_at`. `ELIGIBLE_FOR_MANUAL_REVIEW` must never
be rendered as “approved”.

## State transitions

```text
INGESTED -> DOCUMENT_CHECK -> FACT_EXTRACTION -> ELIGIBILITY_SCREEN
  -> CAPACITY_ANALYSIS -> REVIEWER_CHECK -> TIER3_PENDING_REVIEW
  -> APPROVED | REJECTED | REVISION_REQUESTED
```

`MISSING_DOCUMENTS`, `FAILED_DATA_VALIDATION` and `INELIGIBLE_BY_RULE` are
terminal for the current run. A new document or corrected file starts a new
run and preserves the prior audit trail.
