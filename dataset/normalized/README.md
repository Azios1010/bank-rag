# Normalized policy records

These files are generated from the immutable PDFs in
[`../raw/policies/`](../raw/policies/):

- `policy-sources.json` is the reviewable source registry as one JSON array.
- `policy-sources.jsonl` contains the same source records, one record per line.
- `policy-chunks.jsonl` contains structure-aware article/clause chunks.
- `normalization-report.json` records parser version, counts and warnings.

The generated policy versions intentionally use `IN_REVIEW` and
`review.status=UNREVIEWED`. They must not enter active retrieval until a human
review confirms title, article locator, effective date and amendment relation.

Regenerate and validate from the repository root:

```powershell
backend\.venv\Scripts\python.exe backend\scripts\normalize_policy_dataset.py
backend\.venv\Scripts\python.exe backend\scripts\validate_normalized_policy.py
```

`page_start` and `page_end` are physical PDF page numbers. The source PDF,
not the gazette's printed page number, is the locator authority.

The current parser uses `pypdf` and does not run OCR. Some PDFs may therefore
contain embedded-font spacing artifacts (for example a Vietnamese word split
by an extra space). Treat the output as a review queue: inspect the text and
legal locator before embedding or marking a source `REVIEWED`.
