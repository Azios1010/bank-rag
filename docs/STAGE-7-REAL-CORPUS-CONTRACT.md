# Stage 7 real-corpus contract

## Frozen scope and acceptance

This document freezes the Stage 6 real legal-policy corpus as the Stage 7 input contract. Stage 6 was **OpenCode MINOR accepted**. This is a documentation-only freeze: the corpus was not regenerated, no parser or chunker code was changed, no synthetic corpus data was generated, and no embeddings were created.

The authoritative artifacts are the seven normalized source records in [`dataset/normalized/v2/policy-sources.json`](../dataset/normalized/v2/policy-sources.json), the 3,341 normalized provisions in [`dataset/normalized/v2/policy-provisions.jsonl`](../dataset/normalized/v2/policy-provisions.jsonl), and the 1,573 legal chunks in [`dataset/chunks/v2/policy-legal-chunks.jsonl`](../dataset/chunks/v2/policy-legal-chunks.jsonl). The source code and schemas cited below define how those artifacts are read; they are not permission to regenerate the frozen data.

The untracked `.pytest-stage6` directory is a **5,194-byte** temporary test directory. It remains only because cleanup was policy-blocked; it is not a corpus artifact and must not be treated as part of this contract.

## Versions, normalization, and identity

| Contract item | Frozen value / rule | Source of record |
| --- | --- | --- |
| Parser version | `bank-rag-v2-pymupdf-structure-1.0.0` | [`dataset/normalized/v2/normalization-report.json`](../dataset/normalized/v2/normalization-report.json), [`backend/app/services/policy_normalization_v2.py`](../backend/app/services/policy_normalization_v2.py) |
| Chunker version | `bank-rag-v2-chunker-2.0.0` | [`dataset/chunks/v2/policy-chunking-report.json`](../dataset/chunks/v2/policy-chunking-report.json), [`backend/app/services/policy_chunking_v2.py`](../backend/app/services/policy_chunking_v2.py) |
| Content-hash normalization | Before hashing, text is Unicode NFC-normalized, BOM (`U+FEFF`) is removed, and `CRLF` and lone `CR` are converted to `LF`. No whitespace folding, trimming, or case transformation is applied by this normalizer. | [`backend/app/services/policy_normalization_v2.py`](../backend/app/services/policy_normalization_v2.py) |
| Content hash | Lowercase hexadecimal SHA-256 digest of the normalized text encoded as UTF-8. The raw digest (without a `sha256:` prefix) is stored in each normalized provision and copied into chunk provenance. | [`backend/app/services/policy_normalization_v2.py`](../backend/app/services/policy_normalization_v2.py), [`dataset/schemas/policy-normalized-provision-v2.schema.json`](../dataset/schemas/policy-normalized-provision-v2.schema.json) |
| Chunk content rule | Chunks are lossless content or lossless fragments. Splitting order is paragraph, Vietnamese legal-sentence punctuation, whitespace, then an exact hard boundary; target size is 2,400 characters and hard limit is 4,800 characters. | [`backend/app/services/policy_chunking_v2.py`](../backend/app/services/policy_chunking_v2.py), [`docs/STAGE-6-CHUNKING-REPORT.md`](STAGE-6-CHUNKING-REPORT.md) |

### `canonical_chunk_id`

`canonical_chunk_id` is the lowercase hexadecimal SHA-256 digest of the UTF-8 encoding of Python's deterministic JSON serialization of this identity object. The object is serialized with `sort_keys=True`; therefore its serialized key order is exactly:

```text
article, chapter, chunker_version, clause, content, context_mode,
fragment_index, hierarchy_classification, hierarchy_instance, is_fragment,
point, provenance, section, source_id, version_id
```

Those fields are the complete identity input: `article`, `chapter`, `chunker_version`, `clause`, `content`, `context_mode`, `fragment_index`, `hierarchy_classification`, `hierarchy_instance`, `is_fragment`, `point`, `provenance`, `section`, `source_id`, and `version_id`. The value is not a hash of text alone: the chunker version, legal hierarchy, context convention, fragment state, and source-provision provenance all participate. `heading_path`, page locators, and `is_long_unsplittable` are intentionally not inputs to this identifier. See [`PolicyChunkerV2.get_deterministic_id`](../backend/app/services/policy_chunking_v2.py) and the `canonical_chunk_id` requirement in [`dataset/schemas/policy-legal-chunk-v2.schema.json`](../dataset/schemas/policy-legal-chunk-v2.schema.json).

## Required metadata and legal semantics

The normalized-provision schema requires `source_id`, `version_id`, `chapter`, `section`, `article`, `clause`, `point`, `heading_path`, `content`, `page_start`, `page_end`, `content_hash`, `inventory_type`, and `selection_reason`. The source schema requires `source_id`, `version_id`, `document_number`, `title`, `issuer`, `issue_date`, `effective_date`, and `status`. These establish provenance, legal location, publication/version, and selection semantics before chunking.

The chunk schema requires `canonical_chunk_id`, `chunker_version`, `source_id`, `version_id`, `chapter`, `section`, `article`, `clause`, `point`, `heading_path`, `hierarchy_instance`, `hierarchy_classification`, `context_mode`, `content`, `page_start`, `page_end`, `provenance`, `is_long_unsplittable`, `is_fragment`, and `fragment_index`; additional properties are forbidden. Its semantic fields are:

- `source_id` and `version_id` identify the legal publication; chapter, section, article, clause, and point are the legal locator.
- `heading_path` supplies the inherited Part/Chapter/Section context as an ordered array of heading strings. It is metadata only: it is not prepended to `content`, and child fragments never copy a parent article or clause body into their text.
- `hierarchy_instance` distinguishes otherwise identical labels by a stable occurrence identity; `hierarchy_classification` is one of `NORMAL`, `REPEATED_LABEL_GENUINE`, or `DIRECT_ARTICLE_POINT`.
- `context_mode` is fixed to `metadata_only`; `provenance` preserves each input ordinal and normalized-provision `content_hash`; `is_fragment` and `fragment_index` record lossless fragment state. `is_long_unsplittable` is present and false for this corpus.

The exact field definitions and closed schemas are [`policy-normalized-source-v2.schema.json`](../dataset/schemas/policy-normalized-source-v2.schema.json), [`policy-normalized-provision-v2.schema.json`](../dataset/schemas/policy-normalized-provision-v2.schema.json), and [`policy-legal-chunk-v2.schema.json`](../dataset/schemas/policy-legal-chunk-v2.schema.json).

## Corpus inventory

The frozen corpus has **seven sources**, **3,341 provisions**, and **1,573 chunks**. Chunk counts by source are measured from [`dataset/chunks/v2/policy-legal-chunks.jsonl`](../dataset/chunks/v2/policy-legal-chunks.jsonl):

| Source ID | Document number | Chunks |
| --- | --- | ---: |
| `v2-01-86-vbhn-nhnn` | `86/VBHN-NHNN` | 139 |
| `v2-02-100-vbhn-vpqh` | `100/VBHN-VPQH` | 679 |
| `v2-03-27-vbhn-nhnn` | `27/VBHN-NHNN` | 139 |
| `v2-04-21-2021-nd-cp` | `21/2021/NĐ-CP` | 76 |
| `v2-05-2161-vbhn-btp` | `2161/VBHN-BTP` | 361 |
| `v2-06-80-2021-nd-cp` | `80/2021/NĐ-CP` | 134 |
| `v2-07-15-2023-tt-nhnn` | `15/2023/TT-NHNN` | 45 |
| **Total** | **seven sources** | **1,573** |

Measured as the sum of file lengths under the stated directories, the frozen normalized corpus at `dataset/normalized/v2` is **3,366,543 bytes** across four files, and the frozen chunk corpus at `dataset/chunks/v2` is **2,745,779 bytes** across three files. The latter comprises the 2,732,745-byte chunk JSONL, 12,653-byte QC JSONL, and 381-byte report recorded by Stage 6.

## Retained QC classifications

The 32 remaining QC records are intentional classifications, not unresolved chunking defects:

| Classification | Count | Why it remains |
| --- | ---: | --- |
| `REPEATED_HIERARCHY_LABEL` | 14 | Genuine consolidated, amendment, or annex material shares a hierarchy label. Each remains distinct through stable `occurrence=N` identity; none is deleted or deduplicated. |
| `DIRECT_ARTICLE_POINT` | 5 | Parser evidence places a point directly under its article with no clause. The corpus does not invent a clause merely to normalize the hierarchy. |
| `EXACT_DUPLICATE_LEGAL_TEXT` | 13 | Identical legal text occurs in different normalized provisions. It is retained as source-law repetition, rather than treated as replicated chunk context or silently deduplicated. |
| **Total** | **32** | All retained intentionally. |

The counts and classifications are frozen in [`dataset/chunks/v2/policy-chunking-report.json`](../dataset/chunks/v2/policy-chunking-report.json), [`dataset/chunks/v2/policy-chunking-qc.jsonl`](../dataset/chunks/v2/policy-chunking-qc.jsonl), and the Stage 6 acceptance report [`docs/STAGE-6-CHUNKING-REPORT.md`](STAGE-6-CHUNKING-REPORT.md).

## Verification boundary

This contract records the artifacts as found. It confirms no synthetic generation and no embedding operation were performed for Stage 7; in particular, this freeze neither consumes nor creates files under any embedding output location. Future consumers must preserve the frozen versions, required metadata, content-hash normalization, canonical ID construction, and metadata-only heading-context rule unless a separately approved corpus version is issued.
