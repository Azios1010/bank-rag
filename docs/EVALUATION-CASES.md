# Evaluation cases

Evaluation data must be synthetic, versioned and reproducible. A useful first
set contains at least these cases:

1. Complete, consistent statements; passes demo profile.
2. Missing operating cash-flow statement.
3. Unreadable or password-protected PDF.
4. Excluded or unclear loan purpose.
5. Amount above configured product limit.
6. DSCR below demo threshold.
7. Conflicting revenue between statement and bank statement.
8. Debt schedule missing a repayment.
9. Identity mismatch between registration and financial statement.
10. Missing consent for an owner's personal data.
11. Stale policy version versus current registry.
12. Citation points to the wrong section or page.
13. Reviewer finds arithmetic error and requests recalculation.
14. Related-party exposure requiring officer investigation.
15. All checks pass, but result remains `ELIGIBLE_FOR_MANUAL_REVIEW`.

For every case assert:

- the exact decision state and reason codes;
- no invented facts when an input is missing;
- all material claims have evidence or a policy citation;
- customer documents never enter shared durable policy memory;
- a human approval is required before any operations pre-check.

The test suite should run with deterministic embeddings and mocked model
responses; it must not depend on the FPT endpoint or live external services.
