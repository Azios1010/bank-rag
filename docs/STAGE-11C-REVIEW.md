# Stage 11C Independent Review

**Verdict: APPROVE**

All 12 verification criteria pass. No BLOCKER or MAJOR findings. One MINOR observation documented below.

---

## 1. Frozen Local Corpus V2 and Embeddings Unchanged

| Artifact | Verified SHA-256 | Source of truth |
| --- | --- | --- |
| `embeddings.parquet` | `3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c` | On-disk hash matches `supabase_corpus_import.py:253` trusted check and embedding manifest |
| `policy-corpus-v2.jsonl` | `828e31d6a9d3961badb3be96bbf064819cec4c1338c1853f9144b5b373247400` | On-disk hash matches Stage 10 freeze doc, corpus manifest, embedding manifest `frozen_corpus_sha256` and `input_artifact_hash` |
| `policy-corpus-v2-manifest.json` | `b8fe3f27040439f59709a77be11fca0bc697b7b96dc397185501e642e499e91a` | On-disk manifest bytes match Stage 10 freeze doc |
| Corpus V2 identity hash | `1ab9185d4123a74ddc369d5231be4245ecf0b763320d8d1b0dcafe2fcdcdaa02` | Matches both corpus manifest and embedding manifest `corpus_v2_hash` |
| Manifest identity hash | `796a3000864b8ffe98ff681169577def16bf2717f40d496ccba3b1f85a407a6f` | Matches both corpus manifest and embedding manifest `corpus_manifest_hash` |

Embedding manifest cross-bindings verified:
- `frozen_corpus_sha256` = `sha256:828e31d...` (matches JSONL bytes)
- `corpus_manifest_hash` = `sha256:796a300...` (matches manifest identity)
- `corpus_v2_hash` = `sha256:1ab9185...` (matches corpus V2 identity)
- `input_artifact_hash` = `sha256:828e31d...` (matches JSONL bytes)
- `input.manifest_hash` = `sha256:796a300...` (matches manifest identity)

Embedding profile fields verified: Qwen3-Embedding-0.6B, GGUF, F16, 1024-dim, L2 normalize, llama.cpp, Vulkan, correct input template.

## 2. Storage Object Paths, Privacy, and Hashes

- Three private buckets confirmed: `policy-sources`, `case-documents`, `corpus-artifacts` (`supabase_storage.py:22-28`)
- `verify_private_buckets()` explicitly checks `public=False` for all three
- Path patterns: `legal/{source_id}/{version}/{filename}` (real), `synthetic/{source_id}/{version}/{filename}` (synthetic), `corpus-v2/{filename}` (corpus artifacts)
- `sync_object()` performs SHA-256 read-back verification on every upload
- Collision detection: different object at same key raises `SupabaseStorageError("immutable Storage collision")` — no overwrites

## 3. Supabase rag_v2 Counts and One-to-One Invariant

- `PolicyChunk` has `UniqueConstraint("canonical_chunk_id")` enforcing one chunk per ID
- Embedding stored inline as `Vector(EMBEDDING_DIMENSIONS)` — one row = one chunk = one vector
- `validate_database()` asserts counts: 1 embedding_profile, 1 corpus_version, 10 policy_documents, 1610 policy_chunks
- `distinct_canonical_chunk_id` check: `len(set(ids)) == 1610`
- `duplicate_vector_rows` check: `len(chunks) - len(set(ids)) == 0`

## 4. 1573 SHARED Regulation and 37 SCOPED Synthetic

- Constants: `EXPECTED_REAL_CHUNKS = 1573`, `EXPECTED_SYNTHETIC_CHUNKS = 37`, `EXPECTED_TOTAL_CHUNKS = 1610`
- Corpus manifest `chunk_counts`: real=1573, synthetic=37, total=1610
- Visibility assignment: real → `SHARED`, synthetic → `SCOPED`
- `validate_database()` counts `shared=1573`, `scoped=37` and asserts against expected
- Regulation chunks have **no** `chunk_scope_access` rows (line 888: `access_by_chunk.get(actual.id)` is falsy)
- Synthetic chunks **must** have scope access rows (line 884-885: mismatch raises error)

## 5. Scope Mappings Derived from Canonical Metadata with BankingOperations Absent

- `SCOPE_MAP` at `supabase_corpus_import.py:60-67` maps `BankingOperations → None`
- `persisted_scopes` filters out None values: `tuple(SCOPE_MAP[scope] for scope in declared_scopes if SCOPE_MAP[scope] is not None)`
- Five supported specialist scopes: credit, risk_management, legal_compliance, customer_relationship, collateral_appraisal
- `SUPPORTED_SPECIALIST_SCOPES` in `supabase_models.py:37-43` matches exactly
- `ChunkScopeAccess` CHECK constraint: `scope IN ('credit', 'risk_management', 'legal_compliance', 'customer_relationship', 'collateral_appraisal')` — BankingOperations excluded
- Test `test_frozen_import_plan_is_one_chunk_one_vector_and_excludes_banking_operations` explicitly asserts `all("banking_operations" not in scopes ...)`
- Scope rows: 37+37+37+14 = 125 (BankingOperations' 11 not persisted)
- `bundle.expected_scope_rows == 125` verified in test

## 6. corpus_version and embedding_profile Identity Bindings

- `embedding_profile_id = _deterministic_uuid("embedding-profile", f"{parquet_sha}:{embedding_manifest_sha}")` — deterministic, stable
- `corpus_version_id = _deterministic_uuid("corpus-version", f"{CORPUS_NAME}:{manifest_version}:{manifest_hash}")` — deterministic, stable
- `EmbeddingProfile.metadata_` contains `profile_identity` with both SHA-256 values
- `CorpusVersion.metadata_` contains `embedding_profile_id` binding
- Identity version marker: `stage11c-v1` in both chunk metadata and profile/corpus metadata

## 7. No Orphan Rows

- `orphan_chunks` check: chunks whose `document_id` not in `document_ids` → asserted 0
- `orphan_scope_rows` check: access rows whose `policy_chunk_id` not in `chunk_ids` → asserted 0
- `orphan_documents` count computed (documents not represented by any chunk) — asserted 0 via `len({item.document_id for item in chunks}) != EXPECTED_SOURCE_DOCUMENTS`
- All 10 canonical documents are represented by chunks

## 8. Second Import Idempotency

In `run_stage11c()` (`import_supabase_corpus_v2.py:46-56`):
1. First `import_database()` committed
2. `snapshot_counts()` captured
3. Second `import_database()` committed
4. `after_first == after_second` counts verified
5. `first_import["identity_digest"] == second_import["identity_digest"]` verified
6. Second `sync_storage()`: `any(result.uploaded or not result.existing_identical)` → all False, all identical
7. Dry-run transaction rollback clean: `before == after_rollback` verified

## 9. RLS/Security and RPC Scope Isolation

**RLS (`20260901_0005_supabase_security.py`):**
- RLS enabled on all 5 rag_v2 tables
- `REVOKE ALL ON SCHEMA rag_v2 FROM PUBLIC`
- REVOKE on all tables from `anon`, `authenticated`, `service_role`
- GRANT only to `service_role`: SELECT, INSERT, UPDATE, DELETE on all 5 tables
- RLS policy `rag_v2_service_role_all`: `USING (true) WITH CHECK (true)` — only for service_role
- No public or user-facing role receives access

**RPC Scope Isolation (`20260831_0004_supabase_policy_foundation.py:132-169`):**
- `match_policy_chunks`: SECURITY INVOKER, `SET search_path = pg_catalog, rag_v2`
- Scope filter: `WHERE c.visibility = 'SHARED' OR EXISTS (SELECT 1 FROM chunk_scope_access WHERE access.scope = requested_scope)`
- EXISTS (not JOIN) prevents vector row duplication
- LIMIT clamped: `LEAST(GREATEST(COALESCE(match_count, 10), 1), 100)`
- REVOKE ALL from PUBLIC, anon, authenticated; GRANT EXECUTE only to service_role

## 10. No Secrets, No Docker, No Model Download/Rerun, No Benchmark Metrics, No Local Deletion

- `.env` in `.gitignore` (line 4) and NOT tracked by git
- `.env` never committed to git history (verified: `git log --all --oneline -- .env` → empty)
- `supabase_service_role_key: SecretStr` in config.py — never printed
- Error handler suppresses connection strings: `print(f"ERROR: Stage 11C failed ({type(exc).__name__})")` — no raw exception
- `docker-compose.yml` exists as legacy dev infrastructure, unmodified; not used by Stage 11C
- No llama.cpp/model endpoint calls in import code (only string `"llama.cpp"` in metadata)
- No benchmark/eval/metrics code in import path
- `supabase_corpus_import.py:6` docstring: "never regenerates chunks or embeddings and never deletes local or remote data"
- `verify_local_snapshot()` is read-only (SHA-256 comparison only)
- No `os.remove`, `unlink`, or `shutil.rmtree` in import code

---

## MINOR Finding

The committed `.env.example` (in git HEAD) lacks Supabase V2 configuration variables (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_DB_URL`, etc.) and contains hardcoded default passwords (`POSTGRES_PASSWORD=postgres`, `MINIO_ROOT_PASSWORD=minioadmin`). The working copy adds Supabase placeholders with sanitized defaults but is uncommitted. This is a documentation hygiene gap — the committed `.env.example` should include the Supabase V2 variables (with placeholder values) for accurate developer onboarding. No secrets are leaked.
