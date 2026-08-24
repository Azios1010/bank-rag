# Dataset contract

The canonical MVP dataset schema is
[bank-rag-dataset.schema.json](schemas/bank-rag-dataset.schema.json).
It uses JSON Schema Draft 2020-12.

The schema covers:

- reviewed and versioned policy sources;
- structure-aware policy chunks;
- synthetic SME loan cases;
- normalized case facts and document evidence;
- gold retrieval evaluations;
- reproducible embedding manifests for local, Kaggle or API runs.

The small wrapper schemas in `schemas/` expose each record type independently
for JSONL ingestion and API validation.

See [mvp-dataset.example.json](examples/mvp-dataset.example.json) for one
minimal record of every type.

## Required directory layout

```text
dataset/
  schemas/
  examples/
  raw/
    policies/
    cases/
  normalized/
    policy-sources.json
    policy-chunks.jsonl
    cases.jsonl
    case-facts.jsonl
  evaluation/
    retrieval.jsonl
  derived/
    embeddings/
```

`raw/` contains immutable source files. `normalized/` contains reviewable
records. `derived/` can always be regenerated from normalized data and an
embedding manifest.

The first official PDF snapshots and their checksums are documented in
[`raw/policies/provenance.json`](raw/policies/provenance.json). Read
[`raw/policies/README.md`](raw/policies/README.md) before parsing them because
several documents must be treated as policy bundles rather than independent
rules.

The current extraction output is in
[`normalized/`](normalized/). It is deliberately marked `IN_REVIEW`; only
reviewed source versions may be promoted to active retrieval.

For JSONL files, validate each line against its matching record schema:

| File | Record schema |
| --- | --- |
| `policy-sources.json` | `policy-source.schema.json` |
| `policy-chunks.jsonl` | `policy-chunk.schema.json` |
| `cases.jsonl` | `synthetic-case.schema.json` |
| `case-facts.jsonl` | `case-fact.schema.json` |
| `evaluation/retrieval.jsonl` | `retrieval-evaluation.schema.json` |
| embedding run manifest | `embedding-run.schema.json` |

## Dataset invariants

JSON Schema validates record shape. The ingestion validator must additionally
enforce cross-record invariants:

1. Every `version_id` references exactly one source.
2. Every chunk references an existing source and version.
3. Every fact references an existing synthetic case and case document.
4. Every gold chunk exists and belongs to its declared source/version.
5. IDs are globally unique within their record type.
6. Active policy intervals do not overlap for the same source unless explicitly
   reviewed as concurrent.
7. `effective_to` is later than `effective_from`.
8. `text_span.end` is greater than `text_span.start`.
9. Stored hashes equal the bytes/content they identify.
10. The dataset contains no real personal data.

## Release gates

The first publishable MVP dataset should contain:

- 5–10 reviewed policy sources or consolidated snapshots;
- at least 15 synthetic cases covering the documented outcome classes;
- at least 20 gold retrieval queries;
- no active chunk from an unreviewed or superseded source;
- an embedding manifest for every generated vector set.

Do not embed a document until its source/version record is reviewed and its
normalized chunks pass validation.

## Validation

Any Draft 2020-12 validator can validate a materialized dataset. For example,
with `check-jsonschema` installed:

```bash
check-jsonschema \
  --schemafile dataset/schemas/bank-rag-dataset.schema.json \
  dataset/examples/mvp-dataset.example.json
```

Production ingestion must also run the cross-record invariant checks listed
above; JSON Schema alone cannot enforce referential integrity or verify hashes.
