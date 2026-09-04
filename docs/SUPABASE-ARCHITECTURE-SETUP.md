# Supabase RAG V2 Architecture Foundation

## Current dependency map

The legacy application runtime remains available against `DATABASE_URL` and
MinIO for existing R01 behavior.  It is explicitly separate from the frozen
Stage 11D runtime: `CanonicalV2Retriever` uses llama.cpp query embeddings and
the Supabase `public.match_policy_chunks` RPC.  The legacy evaluation adapter
in `app/eval/qwen_embedding.py` still owns its SentenceTransformer path; it is
not a V2 query client.

Stage 11D does not regenerate Corpus V2 data or change legacy active-state
behavior.  Supabase already contains the immutable Corpus V2 copy and the
canonical runtime reads it only through the RPC contract below.

## Target boundaries

Supabase PostgreSQL/pgvector is the future RAG V2 system of record:

```
frozen corpus + future importer -> rag_v2.policy_documents -> rag_v2.policy_chunks (one vector)
                                                |                         |
                                                |                         +-> rag_v2.chunk_scope_access (no vector)
                                                +-> source/version identity
backend trusted retrieval -> public.match_policy_chunks -> vector-only ranked rows
Supabase Storage -> source PDFs, case documents, immutable corpus artifacts
```

The V2 tables are isolated in `rag_v2`, rather than replacing the legacy
`public.policy_documents` and `public.policy_embeddings` tables. The migration
adds `corpus_versions`, `embedding_profiles`, `policy_documents`,
`policy_chunks`, and `chunk_scope_access`; all primary keys are UUIDs. A
canonical chunk has exactly one vector in `policy_chunks`, while access is a
separate many-to-one table, so scope filtering never duplicates embeddings.

## Application persistence boundaries

Supabase PostgreSQL is also the future transactional store for the existing
application flow: user/application references, requests, cases, assessment
runs, specialist outputs, citations, and audit records. Relational columns
remain the source of truth for identifiers, ownership, status, timestamps, and
fields used for filtering; evolving assessment payloads and specialist state
belong in JSONB columns. Uploaded bytes do not belong in PostgreSQL `BYTEA`:
they belong in `case-documents`, with relational document metadata and hashes
stored in PostgreSQL. This stage does not redesign or switch the existing
legacy case/runtime models.

## Shared and scoped content semantics

Real regulation chunks are authoritative shared content. On a future import,
they must have `visibility=SHARED` and **no** `chunk_scope_access` rows; their
frozen chunk rows do not provide routing metadata, so no routing is invented.

Synthetic corpus entries are `visibility=SCOPED` and receive explicit access
rows only from their manifest scopes. The only supported specialist scopes are
`credit`, `risk_management`, `legal_compliance`, `customer_relationship`, and
`collateral_appraisal`. `BankingOperations` may be retained as source metadata,
but is never an access row or a fake specialist scope.

## Storage contract

The future buckets and object keys are constants only in Stage 11A; no object
is uploaded by this change.

| Bucket | Key pattern |
| --- | --- |
| `policy-sources` | `legal/{source_id}/{version}/source.pdf` |
| `case-documents` | `{user_id}/{case_id}/{document_id}/{filename}` |
| `corpus-artifacts` | `corpus-v2/policy-corpus-v2.jsonl` |
| `corpus-artifacts` | `corpus-v2/embeddings.parquet` |
| `corpus-artifacts` | `corpus-v2/policy-corpus-v2-manifest.json` |
| `corpus-artifacts` | `corpus-v2/embedding-manifest.json` |

## RPC contract

`public.match_policy_chunks(query_embedding vector(1024), requested_scope
text, match_count integer)` is dense, vector-only retrieval. It permits a row
when the chunk is `SHARED` or an `EXISTS` subquery finds an exact scope row,
orders by cosine distance then `canonical_chunk_id`, and clamps `match_count`
to 1–100. It returns chunk/document identity, content, headings, locator,
namespace, visibility, metadata, and similarity; it deliberately has no
hybrid search, RRF, or reranking.

The function is `SECURITY INVOKER`, uses an explicit safe search path, and its
default public execute privilege is revoked. During transition, only the
backend's trusted database path should be granted use; RLS and any
client-facing policy belong to a later authenticated access design.

## llama.cpp V2 query contract

`LlamaV2QueryEmbeddingAdapter` calls
`LLAMA_EMBEDDING_BASE_URL` (default `http://127.0.0.1:8081`) plus
`/v1/embeddings`, using model identity `Qwen3-Embedding-0.6B`. Every query is
formatted exactly as:

```text
Instruct: Given a Vietnamese banking legal question, retrieve authoritative passages that directly support the answer.
Query: {query}
```

It sends UTF-8 JSON and accepts only finite, non-zero, already unit-normalized
1024-dimensional vectors; the intended model sequence-length limit remains
3072. It does not import SentenceTransformer and does not client-normalize an
invalid server response.

## Configuration and transition sequence

Backend-only configuration is `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`,
`SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`, and the three bucket names.
The service role and database URL are `SecretStr` values and must never be
placed in frontend `NEXT_PUBLIC_*` configuration. `DATABASE_URL` and all
MinIO settings remain available for the legacy fallback.

Alembic uses `SUPABASE_DB_URL` when it is configured, and otherwise falls back
to `DATABASE_URL`; the current request/runtime SQLAlchemy session intentionally
remains on the legacy URL until an explicit cutover.

1. Provision Supabase PostgreSQL with pgvector and provide the backend-only
   environment values; do not print their values in a preflight.
2. Apply the isolated Alembic foundation/security migrations through the
   trusted admin/database path.
3. Import and hash-verify the immutable Corpus V2 source/artifact objects and
   canonical rows through the audited Stage 11C importer.
4. Use the Stage 11D runtime freeze and review before Stage 12 evaluation.
   Keep the legacy R01 and MinIO paths isolated until a separate application
   cutover is approved.

For an offline preflight in this stage, validate that the endpoint configuration
is syntactically present, run `alembic upgrade --sql head` with the trusted
database URL supplied by the deployment environment, and inspect the generated
SQL. Do not test connectivity against an unknown database and do not echo
secrets.
