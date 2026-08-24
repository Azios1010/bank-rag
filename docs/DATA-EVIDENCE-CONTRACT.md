# Data and evidence contract

The machine-readable source of truth is the
[Bank RAG dataset JSON Schema](../dataset/schemas/bank-rag-dataset.schema.json).
This document explains the business meaning; ingestion code must validate
against the versioned schema.

## Case inputs

The minimum public-demo case contains:

- borrower legal name and registration number (synthetic);
- requested amount, currency, tenor and purpose;
- management-prepared balance sheet and income statement for two periods;
- operating cash-flow statement or a clearly marked substitute;
- existing debt and scheduled debt-service declaration;
- ownership/authorized-signatory extract;
- consent and data-use record for any personal data.

All sample values and identities must be synthetic.

## Fact record

```json
{
  "fact_id": "fact_123",
  "field": "annual_revenue",
  "value": 12000000000,
  "currency": "VND",
  "period_end": "2025-12-31",
  "source": {
    "document_id": "doc_financials_2025",
    "page": 2,
    "section": "Income statement",
    "text_span": "..."
  },
  "confidence": 0.97,
  "status": "EXTRACTED"
}
```

`status` is one of `EXTRACTED`, `CONFLICTING`, `MISSING` or `REJECTED`.
Conflicting facts are retained and surfaced; they are never silently merged.

## Policy citation

```json
{
  "source_id": "law-credit-institutions-reviewed-snapshot",
  "version": "2025-10-15",
  "issuer": "National Assembly of Vietnam",
  "source_url": "https://vbpl.vn/bonoivu/Pages/vbpq-toanvan.aspx?ItemID=166170",
  "amendment_source_ids": [
    "law-43-2024-qh15",
    "law-96-2025-qh15"
  ],
  "section_id": "article-102",
  "page": null,
  "chunk_id": "chunk_0042",
  "content_hash": "sha256:...",
  "retrieved_at": "2026-07-25T00:00:00Z"
}
```

## RAG namespaces

- `REGULATION`: official, versioned legal/regulatory texts.
- `BANK_PRODUCT`: public product terms, labelled bank-specific and
  time-sensitive.
- `UNDERWRITING_POLICY`: synthetic demo thresholds or a deployer's private
  policy; never present as law.
- `CASE_DOCUMENT`: case-scoped evidence, excluded from shared durable policy
  memory.

The current implementation's `policy_documents` and `policy_embeddings` map
to the first three namespaces. Case documents remain object-storage data and
must be filtered by `case_id`.
