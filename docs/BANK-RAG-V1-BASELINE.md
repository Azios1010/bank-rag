# BANK-RAG V1

## Status

**BASELINE COMPLETE**

V1 is a fully-local compact Vietnamese banking policy and regulatory RAG
baseline. It is an evaluation baseline, not a production-ready or legally
authoritative assistant.

## Architecture

```text
Vietnamese user query
  -> canonical query formatter
  -> Qwen3-Embedding-0.6B
  -> Supabase PostgreSQL/pgvector vector Top20
  -> Qwen3-Reranker-0.6B Q8_0
  -> final Top5 evidence (E1-E5)
  -> Qwen3.5-4B Q4_K_S local generation
  -> grounded Vietnamese answer with citations
```

The canonical retrieval service is
`backend/app/services/canonical_v2_evidence.py`. Its frozen contract is
`candidate_k=20`, `final_k=5`, reranker-score descending order, and
`canonical_chunk_id` ascending as the deterministic tie-breaker. Vector and
reranker scores are not blended. The generator receives only the question and
the ordered Top5 evidence context.

## Data and corpus

The data stack is Supabase PostgreSQL with pgvector and private Supabase
Storage. The frozen corpus is `policy-corpus-v2`:

- 10 source documents and 1,610 canonical chunks.
- 1,573 real-authoritative chunks and 37 synthetic/internal-policy chunks.
- 125 scope-access rows.
- `SHARED` chunks are available to supported scopes; `SCOPED` chunks require
  explicit matching authorization.
- Supported specialist scopes: `credit`, `risk_management`,
  `legal_compliance`, `customer_relationship`, and `collateral_appraisal`.
- `BankingOperations` is metadata-only, not a specialist scope.

## Frozen model identities

| Component | Frozen identity |
|---|---|
| Query/document embedding | Qwen3-Embedding-0.6B, GGUF F16, 1024D |
| Embedding artifact SHA-256 | `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c` |
| Embedding manifest SHA-256 | `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863` |
| Reranker | Qwen3-Reranker-0.6B Q8_0 GGUF |
| Reranker SHA-256 | `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48` |
| Generator | Qwen3.5-4B Q4_K_S GGUF |
| Generator SHA-256 | `3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b` |
| llama.cpp | build 10603, commit `c060ca974` |
| Reference device | Vulkan1 / NVIDIA RTX 2050 4 GB |

## Retrieval benchmark

Evaluation used the frozen 100-query human-reviewed gold artifact
`dataset/evaluation/retrieval-v2-gold-expanded.jsonl` with SHA-256
`1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69`.

The final Top20 + reranker architecture produced:

| Metric | Value |
|---|---:|
| Hit@1 | 0.8300 |
| Hit@3 | 0.9500 |
| Hit@5 | 0.9700 |
| Recall@1 | 0.8250 |
| Recall@3 | 0.9500 |
| Recall@5 | 0.9700 |
| MRR@5 | 0.8928 |
| nDCG@5 | 0.9118 |

Candidate coverage was Hit@5 0.8800, Hit@10 0.9500, and Hit@20 0.9700.
The 97% retrieval Hit@5 result is evidence availability, not answer
accuracy.

## Generation benchmark

Stage 14A generated one answer for each of the 100 frozen questions:

- 100 attempted and 100 generated.
- Technical failures: 0; technical retries: 0.
- 94 answers had valid E1-E5 citations, 4 had no citations, and 2 had
  invalid citation IDs.
- Structural abstentions detected: 0.

Reference local RTX 2050 latency was generation p50 13,850.037 ms, p95
25,595.020 ms, mean 14,073.420 ms, TTFT p50 1,544.523 ms, and 21.418
tokens/sec p50. These are local reference measurements, not production SLAs.

## Human semantic evaluation

The authoritative human review recorded:

- Correctness: PASS 78, PARTIAL 18, FAIL 4.
- Groundedness: FULLY_GROUNDED 87, PARTIALLY_GROUNDED 12, UNGROUNDED 1.
- Citation quality: CORRECT 81, PARTIAL 12, INCORRECT 7.
- Abstention: APPROPRIATE 0, UNNECESSARY 0, MISSING_WHEN_REQUIRED 4,
  N/A 96.
- Failure source: NONE 72, GENERATION 19, CITATION 6, MIXED 3,
  standalone RETRIEVAL 0, RERANKING 0.

The clean end-to-end baseline is **72/100**, defined as correctness PASS,
fully grounded, correct citation, and no missing-required abstention.

The generator-usable-evidence subset had 97 queries: PASS 78, PARTIAL 18,
FAIL 1. The three gold-absent cases (`stage12a-024`, `stage13e-040`, and
`stage13e-042`) all failed human review and had no correct abstention. These
figures must not be collapsed into a single unqualified “system accuracy”.

## Security model

V1 uses the validated Supabase staging design:

- RLS is enabled on canonical `rag_v2` tables.
- `public.match_policy_chunks` is the canonical vector RPC and preserves
  visibility and specialist-scope authorization.
- Anonymous/authenticated mutation is denied under the tested contract;
  canonical retrieval runs through the intended backend-only privilege path.
- Storage buckets `policy-sources`, `case-documents`, and `corpus-artifacts`
  remain private.
- Legacy MongoDB and local PostgreSQL retrieval are outside canonical V2.

## Known limitations

The following are intentionally documented, not fixed in closure:

- Candidate-generation failures beyond vector Top20:
  `stage12a-024`, `stage13e-040`, and `stage13e-042`.
- Legal-polarity interpretation failure, exemplified by `stage12a-002`.
- Insufficient abstention when supplied evidence is incomplete.
- Zero, invalid, or non-canonical citations.
- Output truncation in seven reviewed cases.
- Occasional over-answering/evidence extrapolation.
- Synthetic/internal-policy evidence can be presented as `real_regulation` in
  Stage 14 evidence serialization. Read-only diagnosis attributes this to the
  DTO `source_type` fallback when RPC metadata lacks `provenance_kind`; the
  corpus metadata itself remains correct. This is a V1.1 presentation fix,
  not a corpus mutation.

The canonical V1 path does not call `SentenceTransformer`, `PolicyEmbedding`,
`AgentKnowledgeBase`, the stale 1,709-chunk corpus, MongoDB, the legacy local
PostgreSQL store, FTS/RRF, or any legacy fallback. Historical code remains in
the repository for compatibility and audit history.

## Deferred work

All items below are **V1.1 / POST-V1 OPTIMIZATION** and are not implemented by
this closure:

- **P0 grounding:** improve evidence packaging, retain parent/article context,
  prevent polarity loss, enforce concise answers, and prevent truncation.
- **P0 citations:** strict E1-E5 validation, citation repair/rejection, and
  citation enforcement for factual claims.
- **P0 abstention:** insufficient-evidence detection and controlled refusal.
- **P1 query understanding:** rewrite, domain normalization, abbreviation
  expansion, controlled multi-query retrieval, and decomposition.
- **P1/P2 context and retrieval:** parent-context expansion and selective
  HyDE/HyPE for weak or ambiguous cases.
- **P1/P2 metadata and latency:** provenance presentation repair, model-server
  lifecycle work, appropriate batching, separate services, or stronger
  deployment hardware.

Before substantial post-V1 tuning, create a fresh independent confirmation
benchmark. Do not use only the current 100-query development benchmark as a
tuning holdout.

## Artifact index

Corpus and embeddings:

- [Corpus JSONL](../dataset/chunks/v2/policy-corpus-v2.jsonl)
- [Corpus manifest](../dataset/manifests/policy-corpus-v2-manifest.json)
- [Embedding parquet](../dataset/embeddings/v2/embeddings.parquet)
- [Embedding manifest](../dataset/embeddings/v2/embedding-manifest.json)

Gold and results:

- [Expanded reviewed gold](../dataset/evaluation/retrieval-v2-gold-expanded.jsonl)
- [Retrieval confirmation summary](../dataset/evaluation/results/reranker-depth-confirmation-v2-expanded-summary.json)
- [Generation summary](../dataset/evaluation/results/rag-answer-v2-expanded-summary.json)
- [Human semantic summary](../dataset/evaluation/results/rag-answer-v2-expanded-human-review-summary.json)
- [V1 machine summary](../dataset/evaluation/results/bank-rag-v1-baseline-summary.json)

Architecture and evaluation records:

- [Retrieval architecture freeze](STAGE-13F-RETRIEVAL-ARCHITECTURE-FREEZE.md)
- [Generation baseline](STAGE-14A-RAG-BASELINE.md)
- [Human semantic freeze](STAGE-14B-HUMAN-SEMANTIC-BASELINE-FREEZE.md)
- [Original answer review pack](STAGE-14A-RAG-ANSWER-REVIEW.md)

## Reproducibility identities

- Corpus manifest SHA-256: `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a`
- Expanded gold SHA-256: `1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69`
- Stage 12A pilot SHA-256: `c645869f205e0101cb604cdcf8712820bf0e09aeb85802b590bc695fa8ac424a`
- Embedding artifact SHA-256: `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c`
- Embedding manifest SHA-256: `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863`
- Reranker SHA-256: `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48`
- Generator SHA-256: `3a6e5e8144696a87d17f136b06fce7fe5008a42737938056df13e11ddba4a01b`

## V1 conclusion

V1 establishes a reproducible, fully-local grounded RAG baseline with frozen
data, model identities, retrieval semantics, generation parameters, and human
review results. Retrieval and generation research are closed for V1. Future
work proceeds under V1.1 with this baseline preserved for comparison.

Completion checklist:

- [x] Corpus V2 frozen
- [x] Embeddings frozen
- [x] Supabase staging validated
- [x] Canonical retrieval frozen
- [x] Reranker frozen
- [x] 100-query retrieval gold frozen
- [x] Retrieval benchmark complete
- [x] Generator baseline complete
- [x] Human semantic baseline complete
- [x] V1 known limitations documented
- [ ] Production deployment
- [ ] V1.1 optimization
- [ ] Independent post-tuning holdout
- [ ] Production monitoring
