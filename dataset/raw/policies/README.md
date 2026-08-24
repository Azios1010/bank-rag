# Official policy PDFs

This directory contains immutable PDF snapshots downloaded from the official
Vietnamese electronic gazette on 2026-07-25.

The files are grouped into three policy bundles in
[`provenance.json`](provenance.json):

1. lending rules: `21/VBHN-NHNN` + `52/2025/TT-NHNN` +
   `4033/QD-NHNN`;
2. personal-data protection: `91/2025/QH15` + `356/2025/ND-CP`;
3. the consolidated Law on Credit Institutions: `158/VBHN-VPQH`, published
   as two consecutive PDFs.

## Ingestion rules

- Treat the lending bundle as one temporal policy set. Never retrieve the 2024
  consolidated text without also considering the 2025 amendment and correction.
- Treat both `158/VBHN-VPQH` files as one logical document and preserve the
  part number in chunk metadata.
- Verify each file against the SHA-256 value in `provenance.json` before parsing.
- Preserve article, clause, point and source-page locators during chunking.
- Do not infer bank-specific approval thresholds from these public regulations.
- Do not embed a file until the source has passed legal/content review.

## Rights note

The official portal asks republishers to credit `congbao.chinhphu.vn`. The
manifest records that notice but does not assert a separate open-data license.
Re-check redistribution terms before publishing a derived corpus.
