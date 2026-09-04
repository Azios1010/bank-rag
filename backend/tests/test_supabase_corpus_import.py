from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import unquote, urlsplit

import pytest
from pydantic import SecretStr

from app.config import Settings
from app.services.supabase_corpus_import import load_frozen_bundle
from app.services.supabase_storage import (
    SupabaseStorageClient,
    SupabaseStorageError,
    corpus_artifact_path,
    policy_source_path,
    policy_source_path_with_filename,
    synthetic_policy_source_path,
)


def test_frozen_import_plan_is_one_chunk_one_vector_and_excludes_banking_operations():
    bundle = load_frozen_bundle()

    assert len(bundle.chunks) == 1610
    assert len({chunk["canonical_chunk_id"] for chunk in bundle.chunks}) == 1610
    assert len(bundle.vectors) == 1610
    assert len(bundle.source_documents) == 10
    assert bundle.expected_scope_rows == 125
    assert set(bundle.scope_by_source["synthetic-credit-approval-v1"]) == {
        "credit",
        "risk_management",
        "legal_compliance",
    }
    assert all("banking_operations" not in scopes for scopes in bundle.scope_by_source.values())
    assert {obj.kind for obj in bundle.objects} == {
        "real_source",
        "synthetic_source",
        "corpus_jsonl",
        "corpus_manifest",
        "embedding_parquet",
        "embedding_manifest",
    }


def test_deterministic_storage_paths_preserve_source_namespace():
    assert policy_source_path("nhnn-86", "2026") == "legal/nhnn-86/2026/source.pdf"
    assert policy_source_path_with_filename("nhnn-86", "2026", "86.pdf") == "legal/nhnn-86/2026/86.pdf"
    assert synthetic_policy_source_path("internal-v1", "2026", "policy.md") == "synthetic/internal-v1/2026/policy.md"
    assert corpus_artifact_path("policy-corpus-v2-manifest.json") == "corpus-v2/policy-corpus-v2-manifest.json"


class _Response:
    def __init__(self, body: bytes = b""):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


class _MemoryStorage:
    def __init__(self):
        self.objects: dict[str, bytes] = {}
        self.uploads = 0

    def __call__(self, request, timeout=60):  # noqa: ARG002
        path = unquote(urlsplit(request.full_url).path.split("/storage/v1/object/", 1)[1])
        if request.method == "GET":
            if path not in self.objects:
                raise HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    {},
                    BytesIO(b'{"code":"NoSuchKey"}'),
                )
            return _Response(self.objects[path])
        self.objects[path] = request.data or b""
        self.uploads += 1
        return _Response(b"{}")


class _RacingStorage(_MemoryStorage):
    def __call__(self, request, timeout=60):  # noqa: ARG002
        path = unquote(urlsplit(request.full_url).path.split("/storage/v1/object/", 1)[1])
        if request.method == "POST" and path not in self.objects:
            self.objects[path] = request.data or b""
            raise HTTPError(request.full_url, 409, "Conflict", {}, BytesIO(b"{}"))
        return super().__call__(request, timeout=timeout)


def _storage_client(fake):
    return SupabaseStorageClient(
        Settings(
            supabase_url="https://example.supabase.co",
            supabase_service_role_key=SecretStr("test-service-key"),
            environment="test",
        ),
        opener=fake,
    )


def test_storage_sync_is_idempotent_and_fails_closed_on_collision():
    fake = _MemoryStorage()
    client = _storage_client(fake)
    local_path = Path("dataset/manifests/policy-corpus-v2-manifest.json")

    first = client.sync_object(
        "corpus-artifacts",
        "corpus-v2/policy-corpus-v2-manifest.json",
        local_path,
        content_type="application/json",
    )
    second = client.sync_object(
        "corpus-artifacts",
        "corpus-v2/policy-corpus-v2-manifest.json",
        local_path,
        content_type="application/json",
    )

    assert first.uploaded is True
    assert second.uploaded is False
    assert second.existing_identical is True
    assert fake.uploads == 1

    fake.objects["corpus-artifacts/corpus-v2/policy-corpus-v2-manifest.json"] = b"different"
    with pytest.raises(SupabaseStorageError, match="immutable Storage collision"):
        client.sync_object(
            "corpus-artifacts",
            "corpus-v2/policy-corpus-v2-manifest.json",
            local_path,
            content_type="application/json",
        )
    assert fake.uploads == 1


def test_storage_sync_accepts_only_an_identical_concurrent_writer():
    fake = _RacingStorage()
    client = _storage_client(fake)
    result = client.sync_object(
        "corpus-artifacts",
        "corpus-v2/policy-corpus-v2-manifest.json",
        Path("dataset/manifests/policy-corpus-v2-manifest.json"),
        content_type="application/json",
    )

    assert result.uploaded is False
    assert result.existing_identical is True
