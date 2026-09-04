# Stage 11D — Canonical Corpus V2 Runtime Freeze

Status: frozen 2026-09-01.  This document records the runtime contract only;
it contains no credentials, corpus rows, gold questions, or benchmark output.

## Corpus identity

| Field | Frozen value |
| --- | --- |
| Corpus version | V2 / `policy-corpus-v2` |
| Canonical chunks | 1610 |
| Shared regulation chunks | 1573 |
| Scoped synthetic chunks | 37 |
| Corpus JSONL SHA-256 | `828e31d6a9d3961badb3be96bbf064819cec4c1338c1853f9144b5b373247400` |
| Corpus manifest SHA-256 | `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a` |
| Corpus V2 identity (`corpus_v2_hash`) | `1ab9185d4123a74ddc369d5231be4245ecf0b763320d8d1b0dcafe2fcdcdaa02` |
| Corpus manifest identity (`manifest_hash`) | `796a3000864b8ffe98ff681169577def16bf2717f40d496ccba3b1f85a407a6f` |

## Document embedding identity

| Field | Frozen value |
| --- | --- |
| Model | Qwen3-Embedding-0.6B |
| Format | GGUF F16 |
| Runtime | llama.cpp |
| Device backend | Vulkan |
| Dimension / dtype | 1024 / float32 |
| Pooling | last |
| Normalization | L2 unit-normalized |
| `embeddings.parquet` SHA-256 | `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c` |
| `embedding-manifest.json` SHA-256 | `cca62714c1726c16d15e9fa803cb747634b796bf05cecb0de397f8ddb4973863` |

Document vectors are already frozen in `rag_v2.policy_chunks`.  Stage 11D
does not regenerate or normalize them.

## Query embedding contract

The canonical adapter is `LlamaV2QueryEmbeddingAdapter`.  It sends UTF-8 JSON
to `LLAMA_EMBEDDING_BASE_URL` (default `http://127.0.0.1:8081`) at
`POST /v1/embeddings`, with model `Qwen3-Embedding-0.6B` and this exact input:

```text
Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.
Query: {query}
```

The adapter accepts exactly one finite, non-zero, 1024-dimensional vector with
norm `1.0 +/- 0.0001`.  It does not fall back to SentenceTransformer,
Hugging Face inference, or client-side normalization of an invalid response.

## Retrieval contract

`CanonicalV2Retriever` performs:

```text
Vietnamese query
  -> LlamaV2QueryEmbeddingAdapter
  -> 1024D query vector
  -> public.match_policy_chunks RPC
  -> rag_v2.policy_chunks citations
```

The Supabase RPC is the single ranking and routing source:

- Supabase PostgreSQL schema: `rag_v2`
- RPC: `public.match_policy_chunks`
- distance: cosine
- match count: caller-supplied `k`, bounded by the RPC to 1–100
- deterministic ordering: cosine distance, then `canonical_chunk_id`
- supported scopes: `customer_relationship`, `credit`, `risk_management`,
  `legal_compliance`, `collateral_appraisal`
- `SHARED` chunks are visible to all supported scopes
- `SCOPED` chunks require an exact `chunk_scope_access` row
- `BankingOperations` is rejected and is not a retrieval scope

No legacy `policy_embeddings`, `PolicyEmbedding`, or
`AgentKnowledgeBase` table is consulted by the canonical path.  No hybrid
search, FTS, RRF, reranking, gold data, or benchmark metrics are part of this
freeze.

## Security contract

The three Supabase Storage buckets remain private.  The five `rag_v2` tables
remain protected by RLS.  RPC invocation is backend-only through the trusted
service-role path; client roles do not receive canonical table or RPC access.
