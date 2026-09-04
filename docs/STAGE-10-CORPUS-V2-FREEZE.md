# Stage 10A Corpus V2 freeze

Corpus V2 freezes a combined retrieval artifact made by exact byte
concatenation: the untouched Stage-7 real canonical JSONL first, then the
validated Stage-9 synthetic canonical JSONL.  The chunk schema remains the
closed `policy-legal-chunk-v2` schema; synthetic namespace and agent-scope
metadata lives only in the separate manifest mapping.

## Inputs and counts

| Corpus | Sources | Chunks | Input canonical artifact |
| --- | ---: | ---: | --- |
| Real `REGULATION` | 7 | 1,573 | `dataset/chunks/v2/policy-legal-chunks.jsonl` |
| Synthetic | 3 | 37 | `dataset/chunks/v2/policy-synthetic-chunks.jsonl` |
| **Corpus V2** | **10** | **1,610** | `dataset/chunks/v2/policy-corpus-v2.jsonl` |

Synthetic namespace counts are `BANK_PRODUCT=14` and
`UNDERWRITING_POLICY=23`; real `REGULATION=1,573`.  The auditable synthetic
scope mapping is `CustomerRelationship=14`, `Credit=37`,
`RiskManagement=37`, `LegalCompliance=37`, and `BankingOperations=11`;
synthetic chunks can intentionally appear in more than one scope.  Real chunks
are recorded as `UNSCOPED_REGULATION=1,573`, not assigned synthetic scopes.

The frozen real QC classifications remain 14 `REPEATED_HIERARCHY_LABEL`, 5
`DIRECT_ARTICLE_POINT`, and 13 `EXACT_DUPLICATE_LEGAL_TEXT` groups.  Synthetic
classification counts are zero for each category; the validator permits only
the already-classified real repeated legal text and rejects ID duplication or
any synthetic/real content overlap.

## Identity and hashes

The parser is `bank-rag-v2-pymupdf-structure-1.0.0` and the chunker is
`bank-rag-v2-chunker-2.0.0`.  Corpus V2 identity is SHA-256 over UTF-8
deterministic JSON (`ensure_ascii=false`, sorted keys, compact separators) that
contains the corpus/version identity and the ordered list of every
`canonical_chunk_id`, UTF-8 content SHA-256, and complete JSONL-line SHA-256
(including each original terminator).  This makes the defined corpus hash
independent of manifest presentation while the combined artifact hash verifies
its exact stored bytes.

| Item | SHA-256 | Bytes |
| --- | --- | ---: |
| Corpus V2 identity | `1ab9185d4123a74ddc369d5231be4245ecf0b763320d8d1b0dcafe2fcdcdaa02` | — |
| Combined JSONL exact bytes | `828e31d6a9d3961badb3be96bbf064819cec4c1338c1853f9144b5b373247400` | 2,776,128 |
| Manifest identity | `796a3000864b8ffe98ff681169577def16bf2717f40d496ccba3b1f85a407a6f` | — |
| Manifest exact bytes | `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a` | 10,002 |

`manifest_hash` is SHA-256 of its deterministic JSON identity with the
`manifest_hash` and definition fields omitted, avoiding a self-referential hash.
All input and document exact-byte hashes, including the seven frozen real PDFs,
are recorded in
[`dataset/manifests/policy-corpus-v2-manifest.json`](../dataset/manifests/policy-corpus-v2-manifest.json).

## Immutability boundary

This freeze adds only the combined JSONL, its manifest, deterministic builder
and validator, and this note.  It does not regenerate or overwrite
`policy-legal-chunks.jsonl`, normalized real artifacts, raw real documents,
parser/chunker behavior, or any embedding model/output.  The combined JSONL is
the 2,776,128-byte corpus disk-size definition; the manifest is separately
hashed and excluded from that total.
