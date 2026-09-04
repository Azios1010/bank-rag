"""Supabase Storage contract and idempotent private-bucket provisioning.

Path helpers remain pure. Bucket provisioning is an explicit backend-only
operation and never uploads or reads user/corpus files.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from urllib.parse import quote

from app.config import Settings, get_settings
from app.services.storage import safe_filename


POLICY_SOURCES_BUCKET = "policy-sources"
CASE_DOCUMENTS_BUCKET = "case-documents"
CORPUS_ARTIFACTS_BUCKET = "corpus-artifacts"
EXPECTED_BUCKETS = (
    POLICY_SOURCES_BUCKET,
    CASE_DOCUMENTS_BUCKET,
    CORPUS_ARTIFACTS_BUCKET,
)


class SupabaseStorageError(RuntimeError):
    """Raised when bucket provisioning cannot prove the required contract."""


@dataclass(frozen=True)
class BucketProvisionResult:
    name: str
    created: bool
    public: bool


JsonOpener = Callable[..., object]


def policy_source_path(source_id: str, version: str) -> str:
    return policy_source_path_with_filename(source_id, version, "source.pdf")


def policy_source_path_with_filename(source_id: str, version: str, filename: str) -> str:
    """Return the deterministic key for an approved real source artifact."""

    return f"legal/{source_id}/{version}/{safe_filename(filename)}"


def synthetic_policy_source_path(source_id: str, version: str, filename: str) -> str:
    """Return a visibly separate deterministic key for an internal policy."""

    return f"synthetic/{source_id}/{version}/{safe_filename(filename)}"


def case_document_path(
    user_id: str, case_id: str, document_id: str, filename: str
) -> str:
    return f"{user_id}/{case_id}/{document_id}/{safe_filename(filename)}"


def corpus_artifact_path(filename: str) -> str:
    allowed = {
        "policy-corpus-v2.jsonl",
        "embeddings.parquet",
        "policy-corpus-v2-manifest.json",
        "corpus-manifest.json",
        "embedding-manifest.json",
    }
    if filename not in allowed:
        raise ValueError("unsupported V2 corpus artifact filename")
    return f"corpus-v2/{filename}"


@dataclass(frozen=True)
class StorageObjectSyncResult:
    bucket: str
    path: str
    sha256: str
    byte_size: int
    uploaded: bool
    existing_identical: bool


class SupabaseStorageClient:
    """Small backend-only client for immutable Stage 11C object synchronization."""

    def __init__(self, settings: Settings | None = None, *, opener: JsonOpener = urlopen) -> None:
        self.settings = settings or get_settings()
        self.opener = opener

    def verify_private_buckets(self) -> tuple[BucketProvisionResult, ...]:
        configured = _configured_buckets(self.settings)
        existing = _bucket_map(
            _storage_request(self.settings, "GET", "/storage/v1/bucket", opener=self.opener)
        )
        results: list[BucketProvisionResult] = []
        for name in configured:
            bucket = existing.get(name)
            if bucket is None:
                raise SupabaseStorageError(f"required bucket is missing: {name}")
            if bool(bucket.get("public", False)):
                raise SupabaseStorageError(f"required bucket is public: {name}")
            results.append(BucketProvisionResult(name=name, created=False, public=False))
        return tuple(results)

    def _object_url(self, bucket: str, path: str) -> str:
        return (
            self.settings.supabase_url.rstrip("/")
            + "/storage/v1/object/"
            + quote(bucket, safe="")
            + "/"
            + quote(path, safe="/")
        ) if self.settings.supabase_url else ""

    def _object_request(
        self,
        method: str,
        bucket: str,
        path: str,
        *,
        body: bytes | None = None,
        content_type: str | None = None,
    ) -> bytes:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            raise SupabaseStorageError(
                "SUPABASE_URL and backend-only SUPABASE_SERVICE_ROLE_KEY are required"
            )
        headers = {
            "Accept": "application/octet-stream",
            "apikey": self.settings.supabase_service_role_key.get_secret_value(),
        }
        if body is not None:
            headers["Content-Type"] = content_type or "application/octet-stream"
            headers["x-upsert"] = "false"
        request = Request(self._object_url(bucket, path), data=body, headers=headers, method=method)
        try:
            with self.opener(request, timeout=60) as response:  # type: ignore[operator]
                return response.read()
        except HTTPError:
            raise
        except (URLError, TimeoutError, OSError) as exc:
            raise SupabaseStorageError(
                f"Supabase Storage object request failed: {type(exc).__name__}"
            ) from None

    def read_object(self, bucket: str, path: str) -> bytes | None:
        try:
            return self._object_request("GET", bucket, path)
        except HTTPError as exc:
            # Supabase Storage's object endpoint currently reports a missing
            # key as HTTP 400 with a JSON NoSuchKey body in some deployments,
            # while others use HTTP 404.  Both are a missing-object probe; no
            # other 400 is treated as absent.
            body = exc.read(1024).decode("utf-8", errors="replace")
            if exc.code == 404 or (exc.code == 400 and '"code":"NoSuchKey"' in body):
                return None
            raise SupabaseStorageError(
                f"Supabase Storage object read failed with HTTP {exc.code}"
            ) from None

    def upload_object(self, bucket: str, path: str, data: bytes, *, content_type: str) -> None:
        try:
            self._object_request("POST", bucket, path, body=data, content_type=content_type)
        except HTTPError as exc:
            if exc.code == 409:
                raise
            raise SupabaseStorageError(
                f"Supabase Storage object upload failed with HTTP {exc.code}"
            ) from None

    def sync_object(
        self,
        bucket: str,
        path: str,
        local_path: Path,
        *,
        content_type: str,
    ) -> StorageObjectSyncResult:
        """Upload only a missing object; identical objects are read-back verified.

        A different object at the deterministic key is a hard collision.  No
        overwrite or suffixed fallback path is attempted.
        """

        data = local_path.read_bytes()
        expected_sha = hashlib.sha256(data).hexdigest()
        existing = self.read_object(bucket, path)
        if existing is not None:
            actual_sha = hashlib.sha256(existing).hexdigest()
            if actual_sha != expected_sha or len(existing) != len(data):
                raise SupabaseStorageError(f"immutable Storage collision at {bucket}/{path}")
            return StorageObjectSyncResult(
                bucket=bucket,
                path=path,
                sha256=expected_sha,
                byte_size=len(data),
                uploaded=False,
                existing_identical=True,
            )

        raced = False
        try:
            self.upload_object(bucket, path, data, content_type=content_type)
        except HTTPError as exc:
            # A concurrent writer may have won the race.  It is acceptable
            # only when the resulting bytes are exactly canonical.
            if exc.code != 409:
                raise
            raced = True
        verified = self.read_object(bucket, path)
        if verified is None:
            raise SupabaseStorageError(f"Storage object missing after upload: {bucket}/{path}")
        actual_sha = hashlib.sha256(verified).hexdigest()
        if actual_sha != expected_sha or len(verified) != len(data):
            raise SupabaseStorageError(f"Storage read-back hash mismatch at {bucket}/{path}")
        return StorageObjectSyncResult(
            bucket=bucket,
            path=path,
            sha256=expected_sha,
            byte_size=len(data),
            uploaded=not raced,
            existing_identical=raced,
        )


def _configured_buckets(settings: Settings) -> tuple[str, ...]:
    buckets = (
        settings.supabase_storage_policy_bucket,
        settings.supabase_storage_case_bucket,
        settings.supabase_storage_artifact_bucket,
    )
    if buckets != EXPECTED_BUCKETS or len(set(buckets)) != len(buckets):
        raise SupabaseStorageError(
            "Stage 11B requires exactly policy-sources, case-documents, and corpus-artifacts"
        )
    return buckets


def _storage_request(
    settings: Settings,
    method: str,
    path: str,
    *,
    body: Mapping[str, object] | None = None,
    opener: JsonOpener = urlopen,
) -> object:
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise SupabaseStorageError(
            "SUPABASE_URL and backend-only SUPABASE_SERVICE_ROLE_KEY are required"
        )
    payload = None if body is None else json.dumps(body, ensure_ascii=False).encode("utf-8")
    request = Request(
        settings.supabase_url.rstrip("/") + path,
        data=payload,
        headers={
            "Accept": "application/json",
            "apikey": settings.supabase_service_role_key.get_secret_value(),
            **({"Content-Type": "application/json"} if payload is not None else {}),
        },
        method=method,
    )
    try:
        with opener(request, timeout=10) as response:  # type: ignore[operator]
            raw = response.read()
    except HTTPError as exc:
        if exc.code == 409:
            raise
        raise SupabaseStorageError(
            f"Supabase Storage request failed with HTTP {exc.code}"
        ) from None
    except (URLError, TimeoutError) as exc:
        raise SupabaseStorageError(
            f"Supabase Storage request failed: {type(exc).__name__}"
        ) from None
    try:
        return json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SupabaseStorageError("Supabase Storage returned malformed JSON") from exc


def _bucket_map(payload: object) -> dict[str, dict[str, object]]:
    if not isinstance(payload, list):
        raise SupabaseStorageError("Supabase Storage bucket list has an invalid shape")
    result: dict[str, dict[str, object]] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise SupabaseStorageError("Supabase Storage bucket entry has an invalid shape")
        name = item.get("id") or item.get("name")
        if isinstance(name, str):
            result[name] = item
    return result


def ensure_private_buckets(
    settings: Settings | None = None,
    *,
    opener: JsonOpener = urlopen,
) -> tuple[BucketProvisionResult, ...]:
    """Create missing required buckets and prove all three are private.

    The function is intentionally idempotent. Existing public buckets are not
    silently changed; they fail closed for a human security decision.
    """

    settings = settings or get_settings()
    bucket_names = _configured_buckets(settings)
    existing = _bucket_map(
        _storage_request(settings, "GET", "/storage/v1/bucket", opener=opener)
    )
    created: set[str] = set()
    for name in bucket_names:
        if name not in existing:
            try:
                _storage_request(
                    settings,
                    "POST",
                    "/storage/v1/bucket",
                    body={"id": name, "name": name, "public": False},
                    opener=opener,
                )
                created.add(name)
            except HTTPError as exc:
                if exc.code != 409:
                    raise SupabaseStorageError(
                        f"Supabase Storage bucket creation failed with HTTP {exc.code}"
                    ) from None
        elif bool(existing[name].get("public", False)):
            raise SupabaseStorageError(f"required bucket is public: {name}")

    verified = _bucket_map(
        _storage_request(settings, "GET", "/storage/v1/bucket", opener=opener)
    )
    results: list[BucketProvisionResult] = []
    for name in bucket_names:
        bucket = verified.get(name)
        if bucket is None:
            raise SupabaseStorageError(f"required bucket was not found after provisioning: {name}")
        is_public = bool(bucket.get("public", False))
        if is_public:
            raise SupabaseStorageError(f"required bucket is public: {name}")
        results.append(BucketProvisionResult(name=name, created=name in created, public=False))
    return tuple(results)
