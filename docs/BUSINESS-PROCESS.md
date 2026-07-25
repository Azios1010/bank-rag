# Business process

The workflow is deliberately small and deterministic enough to evaluate.

```text
INTAKE
  -> DOCUMENT_CHECK
  -> FACT_EXTRACTION
  -> ELIGIBILITY_SCREEN
  -> CAPACITY_ANALYSIS
  -> REVIEWER_CHECK
  -> HUMAN_REVIEW
  -> (optional) OPERATIONS_PRECHECK
```

## 1. Intake

Create a case with borrower identifier, requested amount, currency, tenor and
declared purpose. Store uploaded files under the `case_id` boundary.

## 2. Document check

Check file readability, duplicate files, document type, reporting period and
required signatures/consent where applicable. Do not infer a missing number.
Return a specific missing-document request.

## 3. Fact extraction

Extract only facts that can be located in a document: legal name, registration
number, revenue, operating cash flow, existing debt service, requested amount,
tenor and purpose. Every fact has a document ID, page/section (or text span),
and extraction confidence.

## 4. Eligibility screen

Apply regulatory hard gates and the selected product profile. Examples:
lawful purpose, borrower identity consistency, facility amount/tenor limits,
and excluded-purpose rules. A failed hard gate is not overridden by an LLM.

## 5. Capacity analysis

Calculate transparent metrics from extracted values. For the demo, the
thresholds are configuration, not legal advice. If an input is unavailable or
contradictory, stop and route to manual review instead of imputing a value.

## 6. Reviewer check

The reviewer agent checks arithmetic, cross-document consistency, unsupported
claims, stale policy versions and conflicting specialist findings. It can ask
for a re-calculation, but cannot change source facts.

## 7. Human review

The credit officer sees the outcome, evidence and open issues, then records
`APPROVE_FOR_MANUAL_UNDERWRITING`, `REQUEST_DOCUMENTS` or
`DECLINE_PRE_SCREEN`. The product does not present these as an automated loan
decision.

## 8. Operations pre-check

Only after human sign-off may the mock operations flow generate a draft
package. It must not write to a production core-banking system.
