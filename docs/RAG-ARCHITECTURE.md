# RAG architecture for the MVP

**Status:** Accepted  
**Decision date:** 2026-07-25

## Decision

The MVP uses evidence-first hybrid retrieval:

```text
hard metadata filters
  -> PostgreSQL full-text search + pgvector search
  -> Reciprocal Rank Fusion (RRF)
  -> cross-encoder reranking
  -> deduplication and source diversity
  -> typed EvidencePack
  -> rule engine and specialist agent
  -> citation validation
```

Reranking is part of the MVP. HyDE is a later, evaluation-gated fallback.
Full GraphRAG is outside the MVP. A small, verified policy-relationship table
is allowed for amendments and supersession.

## Storage boundaries

### Shared policy corpus

The durable policy corpus contains:

- `REGULATION`;
- `BANK_PRODUCT`;
- `UNDERWRITING_POLICY`;
- `CALCULATION_GUIDE`.

Original files are stored in MinIO. Source/version metadata, chunks and
retrieval traces are stored in PostgreSQL. Embeddings are stored in pgvector.

### Case-scoped evidence

Customer documents are isolated by `case_id`. Their primary output is a set of
normalized facts with immutable evidence links. If case chunks are indexed,
they use a separate case-scoped namespace, retention policy and mandatory
`case_id` filter. They never enter the shared policy corpus.

## Policy ingestion

1. Register a source in the reviewed allow-list.
2. Store the original file and SHA-256 hash.
3. Resolve the active version and its amendments.
4. Parse document structure: chapter, article, clause, section and page.
5. Create structure-aware parent/child chunks.
6. Build full-text and vector representations.
7. Validate metadata and sample citations.
8. Activate the reviewed version; retain older versions for audit.

Required policy metadata:

```text
source_id, namespace, issuer, authority_level, jurisdiction
version, effective_from, effective_to, superseded_by
canonical_url, object_key, content_hash, review_status
allowed_product_codes, allowed_agent_scopes
```

Character-only fixed chunking is not sufficient for legal and policy
documents because it may split an article from its conditions or exceptions.

## Retrieval

### Hard filters

Filters run before scoring:

```text
review_status = ACTIVE
effective_from <= assessment_date
effective_to IS NULL OR assessment_date < effective_to
namespace IN allowed_namespaces
product_code = SME_UNSECURED_WORKING_CAPITAL
agent_scope includes current_agent
```

Validity and authorization are never inferred from vector similarity.

### Candidate generation and reranking

Initial defaults:

```text
full-text candidates: 30
vector candidates:    30
RRF candidate pool:   30-40
rerank candidates:    15-20
final evidence:       3-6
```

The final set should avoid duplicate chunks from the same section and include
the smallest number of sources required to support the task.

### EvidencePack

Agents receive an `EvidencePack`, not unrestricted access to the corpus:

```json
{
  "query": "Check the declared use of funds",
  "assessment_date": "2026-07-25",
  "fact_ids": ["fact_loan_purpose"],
  "citations": [
    {
      "chunk_id": "chunk_0042",
      "source_id": "lending-rules-reviewed",
      "version": "2025-12-25",
      "section_id": "article-x",
      "content_hash": "sha256:...",
      "quote": "...",
      "retrieval_score": 0.91
    }
  ],
  "coverage": "SUFFICIENT",
  "unresolved_questions": []
}
```

`coverage` is `SUFFICIENT`, `INSUFFICIENT` or `CONFLICTING`. Insufficient or
conflicting evidence cannot produce a positive pre-screening conclusion.

## RAG versus deterministic rules

RAG locates relevant policy and supporting text. It does not decide hard
eligibility gates or calculate financial ratios. The rule engine consumes
normalized facts and versioned rule configuration. The LLM may explain the
result but cannot change a threshold, source fact or rule outcome.

## HyDE decision

HyDE is disabled by default. It may be evaluated only when the initial
retrieval has low coverage, weak scores or low lexical/vector agreement.

If enabled:

- run the original, structured and hypothetical queries in parallel;
- treat hypothetical text only as query expansion;
- never expose it as evidence or citation;
- rerank the merged candidates against the original user/task query;
- measure recall gain and query-drift rate before production use.

## Graph decision

The MVP does not implement full GraphRAG. Verified relationships may be stored
in PostgreSQL:

```text
AMENDS, REPEALS, SUPERSEDES, CITES, IMPLEMENTS, APPLIES_TO
```

These relations select the correct policy version before hybrid retrieval.
Full GraphRAG is reconsidered only when the evaluation set contains a material
number of multi-document, multi-hop questions that hybrid retrieval cannot
answer reliably.

## Embedding portability

Batch embeddings may run locally, in Kaggle or through a provider. Import is
valid only when the manifest records:

```text
model name and immutable revision
embedding dimension and normalization
preprocessing and chunking versions
source and chunk hashes
generation timestamp
```

Runtime query embeddings must use the same model contract as corpus
embeddings. Moving batch generation to Kaggle must not change the retrieval
semantics.

## MVP quality gates

- No cross-case retrieval leakage.
- No inactive, future or superseded policy in final evidence.
- Gold policy chunk present in top 5 for the agreed evaluation set.
- Every material policy conclusion has a validated citation.
- Every calculated value links to its source facts.
- Missing facts are not inferred by the model.
- Retrieval runs are reproducible from model, chunk and policy versions.

Latency and exact recall thresholds should be baselined by the first
evaluation run rather than invented in advance.
