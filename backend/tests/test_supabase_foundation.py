from __future__ import annotations

from pathlib import Path
import json

import pytest
from sqlalchemy import CheckConstraint, UniqueConstraint

from app.config import Settings
from app.db.models import Base, EMBEDDING_DIMENSIONS
from app.db.supabase_models import (
    ChunkScopeAccess,
    PolicyChunk,
    SUPPORTED_SPECIALIST_SCOPES,
    V2PolicyDocument,
)
from app.services.supabase_storage import (
    CASE_DOCUMENTS_BUCKET,
    CORPUS_ARTIFACTS_BUCKET,
    EXPECTED_BUCKETS,
    POLICY_SOURCES_BUCKET,
    case_document_path,
    corpus_artifact_path,
    ensure_private_buckets,
    policy_source_path,
)


def _constraint_names(model: type[object], constraint_type: type[object]) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(constraint, constraint_type) and constraint.name
    }


def test_v2_schema_has_one_canonical_chunk_vector_and_access_is_vector_free() -> None:
    assert PolicyChunk.__table__.schema == "rag_v2"
    assert V2PolicyDocument.__table__.schema == "rag_v2"
    assert PolicyChunk.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS == 1024
    assert "embedding" not in ChunkScopeAccess.__table__.c
    assert "uq_rag_v2_policy_chunks_canonical_chunk_id" in _constraint_names(
        PolicyChunk, UniqueConstraint
    )


def test_v2_visibility_and_supported_scope_contract_is_explicit() -> None:
    document_checks = _constraint_names(V2PolicyDocument, CheckConstraint)
    scope_checks = _constraint_names(ChunkScopeAccess, CheckConstraint)

    assert "ck_policy_documents_visibility" in document_checks
    assert "ck_chunk_scope_access_supported_scope" in scope_checks
    assert SUPPORTED_SPECIALIST_SCOPES == (
        "credit",
        "risk_management",
        "legal_compliance",
        "customer_relationship",
        "collateral_appraisal",
    )
    assert "BankingOperations" not in SUPPORTED_SPECIALIST_SCOPES
    assert "rag_v2.policy_chunks" in Base.metadata.tables


def test_storage_contract_keys_are_exact_and_do_not_upload() -> None:
    assert POLICY_SOURCES_BUCKET == "policy-sources"
    assert CASE_DOCUMENTS_BUCKET == "case-documents"
    assert CORPUS_ARTIFACTS_BUCKET == "corpus-artifacts"
    assert policy_source_path("nhnn-86", "2026") == "legal/nhnn-86/2026/source.pdf"
    assert case_document_path("user-1", "case-2", "doc-3", "loan file.pdf") == "user-1/case-2/doc-3/loan-file.pdf"
    assert corpus_artifact_path("policy-corpus-v2.jsonl") == "corpus-v2/policy-corpus-v2.jsonl"
    assert corpus_artifact_path("embedding-manifest.json") == "corpus-v2/embedding-manifest.json"


def test_supabase_service_role_is_backend_only_configuration() -> None:
    settings = Settings(
        _env_file=None,
        environment="test",
        embedding_provider="deterministic_test",
        supabase_service_role_key="server-only-secret",
        supabase_db_url="postgresql://admin:secret@example.test/db",
    )

    assert settings.supabase_service_role_key is not None
    assert settings.supabase_service_role_key.get_secret_value() == "server-only-secret"
    assert settings.llama_embedding_base_url == "http://127.0.0.1:8081"
    env_example = (Path(__file__).resolve().parents[2] / ".env.example").read_text(encoding="utf-8")
    assert "NEXT_PUBLIC_SUPABASE_SERVICE_ROLE_KEY" not in env_example
    assert "NEXT_PUBLIC_SUPABASE_DB_URL" not in env_example


def test_admin_database_url_prefers_supabase_without_switching_legacy_runtime() -> None:
    supabase_settings = Settings(
        _env_file=None,
        environment="test",
        embedding_provider="deterministic_test",
        database_url="postgresql://legacy.invalid/db",
        supabase_db_url="postgresql://admin.invalid/supabase",
    )
    legacy_settings = Settings(
        _env_file=None,
        environment="test",
        embedding_provider="deterministic_test",
        database_url="postgresql://legacy.invalid/db",
    )

    assert supabase_settings.admin_database_url == "postgresql://admin.invalid/supabase"
    assert legacy_settings.admin_database_url == "postgresql://legacy.invalid/db"


def test_v2_migration_declares_vector_only_rpc_and_no_import() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260831_0004_supabase_policy_foundation.py"
    ).read_text(encoding="utf-8")

    assert "Vector(dim=1024)" in migration
    assert "USING hnsw (embedding vector_cosine_ops)" in migration
    assert "WHERE c.visibility = 'SHARED'" in migration
    assert "EXISTS (" in migration
    assert "access.scope = requested_scope" in migration
    assert "OPERATOR(extensions.<=>)" in migration
    assert "REVOKE ALL ON FUNCTION public.match_policy_chunks" in migration
    assert "GRANT EXECUTE ON FUNCTION public.match_policy_chunks" in migration
    assert "INSERT INTO" not in migration
    assert "BankingOperations" not in migration


def test_v2_security_migration_is_deny_by_default_for_public_roles() -> None:
    migration = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260901_0005_supabase_security.py"
    ).read_text(encoding="utf-8")

    assert "ENABLE ROW LEVEL SECURITY" in migration
    assert "REVOKE ALL ON SCHEMA rag_v2 FROM PUBLIC" in migration
    assert "rag_v2_service_role_all" in migration
    assert "REVOKE ALL ON FUNCTION public.match_policy_chunks" in migration
    assert "GRANT EXECUTE ON FUNCTION public.match_policy_chunks" in migration


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self._payload = payload

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


class _FakeStorage:
    def __init__(self) -> None:
        self.buckets: list[dict[str, object]] = []
        self.methods: list[str] = []

    def __call__(self, request: object, timeout: int) -> _FakeResponse:
        method = request.method  # type: ignore[attr-defined]
        self.methods.append(method)
        if method == "GET":
            return _FakeResponse(self.buckets)
        payload = json.loads(request.data.decode("utf-8"))  # type: ignore[attr-defined]
        self.buckets.append({"id": payload["id"], "name": payload["name"], "public": False})
        return _FakeResponse(self.buckets[-1])


def _storage_settings() -> Settings:
    return Settings(
        _env_file=None,
        environment="test",
        embedding_provider="deterministic_test",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="sb_secret_test",
        supabase_storage_policy_bucket=POLICY_SOURCES_BUCKET,
        supabase_storage_case_bucket=CASE_DOCUMENTS_BUCKET,
        supabase_storage_artifact_bucket=CORPUS_ARTIFACTS_BUCKET,
    )


def test_private_bucket_provisioning_is_idempotent_and_creates_no_files() -> None:
    fake = _FakeStorage()
    first = ensure_private_buckets(_storage_settings(), opener=fake)
    second = ensure_private_buckets(_storage_settings(), opener=fake)

    assert [item.name for item in first] == list(EXPECTED_BUCKETS)
    assert all(item.created is True and item.public is False for item in first)
    assert all(item.created is False and item.public is False for item in second)
    assert len(fake.buckets) == 3
    assert fake.methods.count("POST") == 3


def test_private_bucket_provisioning_fails_closed_on_public_bucket() -> None:
    fake = _FakeStorage()
    fake.buckets = [{"id": POLICY_SOURCES_BUCKET, "public": True}]

    with pytest.raises(RuntimeError, match="required bucket is public"):
        ensure_private_buckets(_storage_settings(), opener=fake)
