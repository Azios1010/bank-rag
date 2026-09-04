# Stage 13F - Final Retrieval Architecture Freeze

Status: **FROZEN**.  This is an integration and contract record, not a new
retrieval experiment.  The Stage 13E3 confirmation benchmark classified the
Top20 arm as **B - TOP20 JUSTIFIED**.

## Final architecture

```text
Vietnamese question
  -> canonical query formatter
  -> Qwen3-Embedding-0.6B through llama.cpp
  -> Supabase public.match_policy_chunks, vector candidate top20
  -> Qwen3-Reranker-0.6B Q8_0 through llama.cpp
  -> reranker-only ordering
  -> final evidence top5
```

The canonical service is `app.services.canonical_v2_evidence`:
`CanonicalV2EvidenceRetriever.retrieve_evidence(query, specialist_scope,
candidate_k=20, final_k=5)`.  The public convenience function has the same
defaults.  The service rejects other candidate/final depths so pilot arms
cannot become accidental production behavior.

## Frozen identities

| Item | Frozen value |
| --- | --- |
| Gold | `dataset/evaluation/retrieval-v2-gold-expanded.jsonl` |
| Gold records | 100 `REVIEWED` |
| Gold SHA-256 | `1e6d169b220c5a35c66bd38e83af7279eb1bbe0cd2621f1c19a5fcf5c8f8ee69` |
| Corpus | `policy-corpus-v2`, 10 documents, 1610 canonical chunks |
| Corpus manifest SHA-256 | `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a` |
| Document embedding | Qwen3-Embedding-0.6B, GGUF F16, 1024D |
| Embedding artifact SHA-256 | `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c` |
| Embedding manifest SHA-256 | `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863` |
| Reranker | Qwen3-Reranker-0.6B Q8_0 GGUF |
| Reranker GGUF SHA-256 | `22c9979ce4fbcdc5acdc310c6641c32797eff1aa980b8f7a2db8a8ea23429a48` |

The document embedding runtime artifact is
`D:\llm-models\Qwen3-Embedding-0.6B-f16.gguf`.  The reranker runtime artifact
is `D:\llm-models\qwen3-reranker-0.6b-q8_0.gguf` and is 639153184 bytes.

## Query and document formatting

The query instruction is unchanged:

```text
Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.
```

The canonical query input is exactly:

```text
Instruct: {instruction}
Query: {query}
```

`LlamaV2QueryEmbeddingAdapter` sends this UTF-8 input to the local
`/v1/embeddings` endpoint and accepts only a finite, non-zero, unit-normalized
1024-dimensional vector.  It has no SentenceTransformer or fallback path.

The reranker sees each candidate as:

```text
Title: {title}
Section: {heading_path}
Text:
{content}
```

Canonical IDs, vector ranks/scores, gold labels, rationale, source hints, and
evaluation metadata are not sent to the reranker.  The reranker score is not
blended with vector similarity.  Final ordering is relevance score descending,
then `canonical_chunk_id` ascending.

## Runtime contract

- Embedding endpoint: `http://127.0.0.1:8081/v1/embeddings`.
- Reranker endpoint: `http://127.0.0.1:8082/v1/rerank`.
- llama.cpp: build 10603, commit `c060ca974`.
- Reference device: `Vulkan1` / NVIDIA RTX 2050.
- Reranker context: 4096; pooling: `rank`; parallel: 1.
- Supabase schema: `rag_v2`.
- Vector RPC: `public.match_policy_chunks`.
- Distance: cosine.
- `hnsw.ef_search`: 40; unchanged by this freeze.
- Candidate depth: exactly 20.
- Final evidence depth: at most 5, normally exactly 5 with the frozen corpus.

`CanonicalV2EvidenceResult` preserves the canonical chunk ID, document/source
and version identity, title, heading path, locator (including article/clause/
point where present), content, namespace, visibility, provenance, specialist
scope, original vector rank/similarity, and reranker score.  The
`serialize_citations` helper emits the existing final order as `E1` through
`E5` without changing it and without adding gold metadata.

## Scope and security contract

Supported specialist scopes are:

- `credit`
- `risk_management`
- `legal_compliance`
- `customer_relationship`
- `collateral_appraisal`

`BankingOperations` is rejected.  The Supabase RPC remains the sole source of
visibility and routing: `SHARED` chunks are available to every supported
scope, while `SCOPED` chunks require an explicit matching
`chunk_scope_access` row.  The existing RLS, private Storage buckets, and
backend-only RPC privilege contract remain unchanged.  The additive FTS
diagnostic migration is not imported or called by the canonical service.

The canonical V2 modules do not call `SentenceTransformer`, `PolicyEmbedding`,
`AgentKnowledgeBase`, the legacy 1709-chunk corpus, MongoDB, or the local
PostgreSQL legacy retrieval path.  Historical legacy modules remain in the
repository but are outside this contract.

The existing read-only remote verification was rerun during this freeze: the
remote state reported 10 documents, 1610 chunks, 1610 vectors, 125 scope rows,
zero vector/hash/identity failures, deterministic RPC ordering, passing
SHARED/SCOPED isolation, RLS enabled, backend-only RPC execution, anon writes
denied, and 14 verified private Storage objects.  No canonical row or Storage
object was changed.

## Confirmation reference

Stage 13E3 used the frozen 100-query human-reviewed gold set.  The selected
Top20 + reranker arm reported:

| Metric | Value |
| --- | ---: |
| Hit@5 | 0.9700 |
| Recall@5 | 0.9700 |
| MRR@5 | 0.8928 |
| nDCG@5 | 0.9118 |

Top20 candidate coverage was Hit/Recall@20 `0.9700`.  Compared with Top10,
Top20 supplied two additional Top5 successes (`stage13e-041` and
`stage13e-067`) at the cost of approximately twice the reranker pair
workload.  This is a pilot confirmation reference, not a production SLA or a
statistical claim.

Reference local RTX 2050 Top20 reranker latency was p50 `2430.854 ms` and p95
`3164.068 ms`.  These are exploratory local measurements.  Performance
optimization is deferred and must not change the frozen retrieval semantics.

## Known candidate-generation failures

The following confirmed 100-query cases were absent from vector Top20:

- `stage12a-024`
- `stage13e-040`
- `stage13e-042`

They are recorded as **KNOWN CANDIDATE-GENERATION FAILURE**.  They are not
special-cased, manually injected, widened to Top50, or repaired by the
reranker in this freeze.

## Freeze checks

- Gold, corpus, document vectors, and embedding manifests were not changed.
- No new retrieval experiment or benchmark was run for this integration
  freeze; the Stage 13E3 confirmation values above remain the reference.
- No FTS, RRF, query rewrite, query expansion, or answer-generation path is
  part of the canonical service.
- No model was downloaded and no local canonical artifact was deleted.
- No Supabase canonical data, HNSW setting, or embedding was mutated.

The next stage may use the final Top5 evidence with Qwen3.5-4B generation for
grounded Vietnamese answers and E1-E5 citations.  Retrieval architecture
optimization is closed for that stage.
