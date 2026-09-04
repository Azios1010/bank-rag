# Stage 14A Review Artifact — Frozen Human Baseline

This document freezes the authoritative Stage 14A-R1 human semantic review
without overwriting the original review pack.

The complete generated-answer review pack remains at
`docs/STAGE-14A-RAG-ANSWER-REVIEW.md` and remains unchanged with semantic
fields marked `DRAFT`. A complete mechanically available 100-row human label
map was not present, so this artifact freezes the aggregate verdict and the
explicit per-query classifications supplied by the human reviewer only.

## Authority and scope

- Semantic authority: human reviewer.
- Codex did not re-judge correctness, groundedness, citations, abstention, or
  failure source.
- The known-label JSONL is intentionally incomplete and contains 28
  records: stage12a-002, stage12a-003, stage12a-004, stage12a-008, stage12a-011, stage12a-013, stage12a-014, stage12a-019, stage12a-024, stage13e-034, stage13e-036, stage13e-037, stage13e-038, stage13e-040, stage13e-042, stage13e-043, stage13e-049, stage13e-050, stage13e-059, stage13e-065, stage13e-068, stage13e-073, stage13e-080, stage13e-083, stage13e-084, stage13e-090, stage13e-091, stage13e-099.
- Unlisted per-query semantic fields remain unassigned.

## Frozen aggregate

- Correctness: PASS 78, PARTIAL 18, FAIL 4.
- Groundedness: FULLY_GROUNDED 87, PARTIALLY_GROUNDED 12, UNGROUNDED 1.
- Citation quality: CORRECT 81, PARTIAL 12, INCORRECT 7.
- Abstention: APPROPRIATE 0, UNNECESSARY 0, MISSING_WHEN_REQUIRED 4, N/A 96.
- Failure source: NONE 72, GENERATION 19, CITATION 6, MIXED 3, RETRIEVAL 0,
  RERANKING 0.
- Clean answers: 72 / 100.

Gold-present subset is 97 queries: PASS 78, PARTIAL 18, FAIL 1. Gold-absent
queries are `stage12a-024`, `stage13e-040`, and `stage13e-042`: FAIL 3/3 and
correct abstentions 0/3.

## Preservation

Stage 14A structural totals remain: attempted 100,
generated 100, valid citations
94, zero citations
4, invalid citation answers
2, technical failures
0. No generation or retrieval benchmark was run
for Stage 14B.
