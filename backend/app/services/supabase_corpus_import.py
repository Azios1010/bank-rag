"""Verified Corpus V2 storage and database importer.

The importer is deliberately separate from the legacy policy import path.  It
reads the frozen Corpus V2/Stage 10 artifacts, uploads immutable Storage
objects, and writes one database row and one vector per canonical chunk.  It
never regenerates chunks or embeddings and never deletes local or remote data.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from datetime import date
import hashlib
import json
import math
from pathlib import Path
import struct
from typing import Any
from uuid import NAMESPACE_URL, UUID, uuid5

import pyarrow.parquet as pq
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.db.supabase_models import (
    ChunkScopeAccess,
    CorpusVersion,
    EmbeddingProfile,
    PolicyChunk,
    V2PolicyDocument,
    SUPPORTED_SPECIALIST_SCOPES,
)
from app.services.supabase_storage import (
    CORPUS_ARTIFACTS_BUCKET,
    POLICY_SOURCES_BUCKET,
    StorageObjectSyncResult,
    SupabaseStorageClient,
    corpus_artifact_path,
    policy_source_path_with_filename,
    synthetic_policy_source_path,
)


ROOT = Path(__file__).resolve().parents[3]
CORPUS_PATH = ROOT / "dataset/chunks/v2/policy-corpus-v2.jsonl"
CORPUS_MANIFEST_PATH = ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
EMBEDDINGS_PATH = ROOT / "dataset/embeddings/v2/embeddings.parquet"
EMBEDDING_MANIFEST_PATH = ROOT / "dataset/embeddings/v2/embedding-manifest.json"

EXPECTED_REAL_CHUNKS = 1573
EXPECTED_SYNTHETIC_CHUNKS = 37
EXPECTED_TOTAL_CHUNKS = EXPECTED_REAL_CHUNKS + EXPECTED_SYNTHETIC_CHUNKS
EXPECTED_SOURCE_DOCUMENTS = 10
EXPECTED_DIMENSION = 1024
NORM_TOLERANCE = 1e-4
CORPUS_NAME = "policy-corpus-v2"
IDENTITY_NAMESPACE = uuid5(NAMESPACE_URL, "https://bank-rag.invalid/rag-v2")

SCOPE_MAP = {
    "Credit": "credit",
    "RiskManagement": "risk_management",
    "LegalCompliance": "legal_compliance",
    "CustomerRelationship": "customer_relationship",
    "CollateralAppraisal": "collateral_appraisal",
    "BankingOperations": None,
}


class CorpusImportError(RuntimeError):
    """Raised when frozen or persisted Corpus V2 identity cannot be proven."""


@dataclass(frozen=True)
class FrozenObject:
    bucket: str
    path: str
    local_path: Path
    sha256: str
    byte_size: int
    content_type: str
    kind: str


@dataclass(frozen=True)
class FrozenBundle:
    root: Path
    chunks: tuple[dict[str, Any], ...]
    vectors: tuple[tuple[float, ...], ...]
    corpus_manifest: dict[str, Any]
    embedding_manifest: dict[str, Any]
    source_documents: tuple[dict[str, Any], ...]
    objects: tuple[FrozenObject, ...]
    scope_by_source: dict[str, tuple[str, ...]]
    local_hashes: dict[str, str]
    embedding_profile_id: UUID
    corpus_version_id: UUID
    corpus_version_metadata: dict[str, Any]
    expected_scope_rows: int


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> str:
    if not path.is_file():
        raise CorpusImportError(f"missing frozen artifact: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusImportError(f"cannot read JSON artifact: {path}") from exc
    if not isinstance(value, dict):
        raise CorpusImportError(f"JSON artifact must contain an object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise CorpusImportError(f"cannot read JSONL artifact: {path}") from exc
    lines = raw.splitlines(keepends=True)
    if raw.startswith(b"\xef\xbb\xbf") or any(not line.endswith(b"\n") for line in lines):
        raise CorpusImportError(f"frozen JSONL must be UTF-8 and newline terminated: {path}")
    if any(not line.strip() for line in lines):
        raise CorpusImportError(f"frozen JSONL contains a blank line: {path}")
    try:
        records = [json.loads(line) for line in lines]
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusImportError(f"invalid JSONL record in {path}") from exc
    if not all(isinstance(record, dict) for record in records):
        raise CorpusImportError(f"JSONL records must be objects: {path}")
    return records


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _deterministic_uuid(kind: str, identity: str) -> UUID:
    return uuid5(IDENTITY_NAMESPACE, f"{kind}/{identity}")


def _vector_hash(vector: list[float] | tuple[float, ...]) -> str:
    try:
        packed = struct.pack(f"<{len(vector)}f", *[float(value) for value in vector])
    except (OverflowError, struct.error, TypeError, ValueError) as exc:
        raise CorpusImportError("cannot serialize canonical vector as float32") from exc
    return _sha256_bytes(packed)


def _parse_date(value: object, *, context: str) -> date | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise CorpusImportError(f"{context}: date must be an ISO string or null")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise CorpusImportError(f"{context}: invalid ISO date") from exc


def _source_artifact_entry(manifest: dict[str, Any], kind: str, source_id: str) -> dict[str, Any]:
    for item in manifest["artifacts"][kind]["documents"]:
        if item.get("source_id") == source_id:
            return item
    raise CorpusImportError(f"{kind} source artifact missing from Corpus V2 manifest: {source_id}")


def _validate_embedding_vector(value: object, *, context: str) -> tuple[float, ...]:
    if not isinstance(value, list) or len(value) != EXPECTED_DIMENSION:
        raise CorpusImportError(f"{context}: expected a {EXPECTED_DIMENSION}D vector")
    try:
        vector = tuple(float(item) for item in value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise CorpusImportError(f"{context}: vector contains a non-numeric value") from exc
    if not all(math.isfinite(item) for item in vector):
        raise CorpusImportError(f"{context}: vector contains NaN or infinity")
    norm = math.sqrt(math.fsum(item * item for item in vector))
    if not math.isfinite(norm) or norm == 0.0 or abs(norm - 1.0) > NORM_TOLERANCE:
        raise CorpusImportError(f"{context}: vector is not non-zero unit-normalized")
    return vector


def _artifact_object(bucket: str, path: str, local_path: Path, kind: str, content_type: str) -> FrozenObject:
    return FrozenObject(
        bucket=bucket,
        path=path,
        local_path=local_path,
        sha256=_sha256_file(local_path),
        byte_size=local_path.stat().st_size,
        content_type=content_type,
        kind=kind,
    )


def load_frozen_bundle(root: Path = ROOT) -> FrozenBundle:
    """Validate all frozen inputs and derive the canonical import plan.

    This function is read-only.  In particular, it does not call the model
    endpoint, create files, or access Supabase.
    """

    root = root.resolve()
    corpus_path = root / CORPUS_PATH.relative_to(ROOT)
    corpus_manifest_path = root / CORPUS_MANIFEST_PATH.relative_to(ROOT)
    embeddings_path = root / EMBEDDINGS_PATH.relative_to(ROOT)
    embedding_manifest_path = root / EMBEDDING_MANIFEST_PATH.relative_to(ROOT)
    corpus_manifest = _read_json(corpus_manifest_path)
    embedding_manifest = _read_json(embedding_manifest_path)
    chunks = _read_jsonl(corpus_path)

    ids = [chunk.get("canonical_chunk_id") for chunk in chunks]
    if len(chunks) != EXPECTED_TOTAL_CHUNKS or len(set(ids)) != EXPECTED_TOTAL_CHUNKS:
        raise CorpusImportError("Corpus V2 must contain exactly 1,610 unique canonical IDs")
    counts = corpus_manifest.get("chunk_counts", {})
    if counts.get("real") != EXPECTED_REAL_CHUNKS or counts.get("synthetic") != EXPECTED_SYNTHETIC_CHUNKS:
        raise CorpusImportError("Corpus V2 manifest composition is not 1,573 real + 37 synthetic")
    if counts.get("total") != EXPECTED_TOTAL_CHUNKS:
        raise CorpusImportError("Corpus V2 manifest total does not equal 1,610")
    if corpus_manifest.get("source_counts") != {"real": 7, "synthetic": 3, "total": 10}:
        raise CorpusImportError("Corpus V2 manifest source count is not 7 real + 3 synthetic")

    try:
        table = pq.read_table(embeddings_path)
    except Exception as exc:  # pyarrow exposes several format-specific exceptions.
        raise CorpusImportError("cannot read canonical embeddings.parquet") from exc
    if table.num_rows != EXPECTED_TOTAL_CHUNKS:
        raise CorpusImportError("canonical embedding row count is not 1,610")
    if "chunk_id" not in table.column_names or "embedding" not in table.column_names:
        raise CorpusImportError("canonical embedding artifact lacks chunk_id or embedding")
    embedding_ids = table.column("chunk_id").to_pylist()
    if len(set(embedding_ids)) != EXPECTED_TOTAL_CHUNKS or embedding_ids != ids:
        raise CorpusImportError("corpus and embedding canonical ID sets/order differ")
    vectors = tuple(
        _validate_embedding_vector(value, context=f"embedding row {index + 1}")
        for index, value in enumerate(table.column("embedding").to_pylist())
    )

    parquet_sha = _sha256_file(embeddings_path)
    corpus_sha = _sha256_file(corpus_path)
    corpus_manifest_sha = _sha256_file(corpus_manifest_path)
    embedding_manifest_sha = _sha256_file(embedding_manifest_path)
    combined_artifact = corpus_manifest.get("artifacts", {}).get("combined_chunks", {})
    if combined_artifact.get("sha256") != corpus_sha or combined_artifact.get("byte_size") != corpus_path.stat().st_size:
        raise CorpusImportError("Corpus V2 manifest combined artifact binding does not match local bytes")
    if parquet_sha != "3d37b455b3e7fd5a0b90dc7ab97cd79503da08e8c89a1b085950953045fb9c1c":
        raise CorpusImportError("Stage 10 embeddings.parquet SHA-256 does not match the trusted artifact")
    if embedding_manifest.get("artifact_sha256") != f"sha256:{parquet_sha}":
        raise CorpusImportError("embedding manifest artifact hash does not match embeddings.parquet")
    if embedding_manifest.get("artifact_byte_size") != embeddings_path.stat().st_size:
        raise CorpusImportError("embedding manifest artifact byte size does not match embeddings.parquet")
    if embedding_manifest.get("chunk_count") != EXPECTED_TOTAL_CHUNKS:
        raise CorpusImportError("embedding manifest row count is not 1,610")
    expected_profile = {
        "model_id": "Qwen3-Embedding-0.6B",
        "model_format": "GGUF",
        "quantization": "F16",
        "embedding_dimension": EXPECTED_DIMENSION,
        "normalize_embeddings": True,
        "normalization": "L2",
        "backend": "llama.cpp",
        "device_backend": "Vulkan",
        "input_template": "Document: {title}\nSection: {heading_path}\nText:\n{content}",
    }
    for key, expected in expected_profile.items():
        if embedding_manifest.get(key) != expected:
            raise CorpusImportError(f"embedding profile field mismatch: {key}")
    if embedding_manifest.get("frozen_corpus_sha256") != f"sha256:{corpus_sha}":
        raise CorpusImportError("embedding manifest frozen corpus hash mismatch")
    if embedding_manifest.get("input_artifact_hash") != f"sha256:{corpus_sha}":
        raise CorpusImportError("embedding manifest input artifact hash mismatch")
    if embedding_manifest.get("corpus_manifest_hash") != f"sha256:{corpus_manifest.get('manifest_hash')}":
        raise CorpusImportError("embedding manifest corpus manifest identity mismatch")
    if embedding_manifest.get("corpus_v2_hash") != f"sha256:{corpus_manifest.get('corpus_v2_hash')}":
        raise CorpusImportError("embedding manifest Corpus V2 identity mismatch")
    if embedding_manifest.get("input", {}).get("manifest_hash") != f"sha256:{corpus_manifest.get('manifest_hash')}":
        raise CorpusImportError("embedding input manifest binding mismatch")

    raw_manifest_path = root / "dataset/raw/policies/v2/manifest.json"
    real_sources_path = root / "dataset/normalized/v2/policy-sources.json"
    synthetic_manifest_path = root / "dataset/synthetic/policies/v1/manifest.json"
    raw_manifest = _read_json(raw_manifest_path)
    real_sources = json.loads(real_sources_path.read_text(encoding="utf-8"))
    synthetic_manifest = _read_json(synthetic_manifest_path)
    if not isinstance(real_sources, list) or len(real_sources) != 7:
        raise CorpusImportError("frozen normalized real source set must contain seven records")
    if len(raw_manifest.get("records", [])) != 7 or len(synthetic_manifest.get("records", [])) != 3:
        raise CorpusImportError("frozen source manifests must contain 7 real and 3 synthetic records")
    real_by_id = {record["source_id"]: record for record in real_sources}
    raw_by_id = {record["source_id"]: record for record in raw_manifest["records"]}
    synthetic_by_id = {record["source_id"]: record for record in synthetic_manifest["records"]}
    if set(real_by_id) != set(raw_by_id) or len(real_by_id) != 7:
        raise CorpusImportError("real source provenance manifests disagree")
    if set(synthetic_by_id) != {
        "synthetic-sme-working-capital-v1",
        "synthetic-sme-underwriting-v1",
        "synthetic-credit-approval-v1",
    }:
        raise CorpusImportError("synthetic source provenance is not the approved three-document set")
    if _sha256_file(raw_manifest_path) != corpus_manifest["artifacts"]["real"]["source_manifest"]["sha256"]:
        raise CorpusImportError("raw real-source manifest is not the frozen manifest input")
    if _sha256_file(real_sources_path) != corpus_manifest["artifacts"]["real"]["sources"]["sha256"]:
        raise CorpusImportError("normalized real-source artifact is not the frozen manifest input")
    if _sha256_file(synthetic_manifest_path) != corpus_manifest["artifacts"]["synthetic"]["source_manifest"]["sha256"]:
        raise CorpusImportError("synthetic source manifest is not the frozen manifest input")

    chunk_sources = {chunk.get("source_id") for chunk in chunks}
    if chunk_sources != set(real_by_id) | set(synthetic_by_id):
        raise CorpusImportError("chunk source IDs do not match the ten canonical sources")
    source_counts = Counter(chunk["source_id"] for chunk in chunks)
    scope_by_source: dict[str, tuple[str, ...]] = {}
    source_documents: list[dict[str, Any]] = []
    objects: list[FrozenObject] = []
    local_hashes: dict[str, str] = {}

    for source_id in raw_by_id:
        raw = raw_by_id[source_id]
        normalized = real_by_id[source_id]
        artifact = _source_artifact_entry(corpus_manifest, "real", source_id)
        local_path = root / raw["file_path"]
        actual_sha = _sha256_file(local_path)
        if actual_sha != raw["sha256"] or local_path.stat().st_size != raw["byte_size"]:
            raise CorpusImportError(f"real source artifact hash/size mismatch: {source_id}")
        if artifact["sha256"] != actual_sha or artifact["byte_size"] != local_path.stat().st_size:
            raise CorpusImportError(f"real source artifact differs from Corpus V2 manifest: {source_id}")
        if normalized.get("version_id") is None:
            raise CorpusImportError(f"real source has no canonical version_id: {source_id}")
        object_path = policy_source_path_with_filename(source_id, normalized["version_id"], local_path.name)
        objects.append(_artifact_object(POLICY_SOURCES_BUCKET, object_path, local_path, "real_source", "application/pdf"))
        local_hashes[str(local_path)] = actual_sha
        source_documents.append(
            {
                "source_id": source_id,
                "version_id": normalized["version_id"],
                "title": raw["title"],
                "issuer": raw["issuer"],
                "document_type": None,
                "effective_from": raw.get("effective_date"),
                "effective_to": None,
                "storage_bucket": POLICY_SOURCES_BUCKET,
                "storage_path": object_path,
                "sha256": actual_sha,
                "byte_size": local_path.stat().st_size,
                "namespace": "REGULATION",
                "visibility": "SHARED",
                "is_synthetic": False,
                "metadata": {
                    "provenance_kind": "real_regulation",
                    "document_number": raw.get("document_number"),
                    "issue_date": raw.get("issue_date"),
                    "status": raw.get("status"),
                    "official_url": raw.get("official_url"),
                    "download_url": raw.get("download_url"),
                    "version_relationships": raw.get("version_relationships", []),
                    "source_artifact_path": raw["file_path"],
                    "source_manifest_sha256": corpus_manifest["artifacts"]["real"]["source_manifest"]["sha256"],
                },
            }
        )

    for source_id in synthetic_by_id:
        synthetic = synthetic_by_id[source_id]
        artifact = _source_artifact_entry(corpus_manifest, "synthetic", source_id)
        local_path = root / synthetic["path"]
        actual_sha = _sha256_file(local_path)
        if actual_sha != synthetic["content_hash"]:
            raise CorpusImportError(f"synthetic source content hash mismatch: {source_id}")
        if artifact["sha256"] != actual_sha or artifact["byte_size"] != local_path.stat().st_size:
            raise CorpusImportError(f"synthetic source artifact differs from Corpus V2 manifest: {source_id}")
        declared_scopes = synthetic.get("agent_scopes")
        if not isinstance(declared_scopes, list) or not declared_scopes:
            raise CorpusImportError(f"synthetic source has no declared scopes: {source_id}")
        unsupported = set(declared_scopes) - set(SCOPE_MAP)
        if unsupported:
            raise CorpusImportError(f"synthetic source has unknown scope declarations: {sorted(unsupported)}")
        persisted_scopes = tuple(SCOPE_MAP[scope] for scope in declared_scopes if SCOPE_MAP[scope] is not None)
        if not persisted_scopes:
            raise CorpusImportError(f"synthetic source has zero supported persisted scopes: {source_id}")
        scope_by_source[source_id] = persisted_scopes
        object_path = synthetic_policy_source_path(source_id, synthetic["version_id"], local_path.name)
        objects.append(_artifact_object(POLICY_SOURCES_BUCKET, object_path, local_path, "synthetic_source", "text/markdown; charset=utf-8"))
        local_hashes[str(local_path)] = actual_sha
        source_documents.append(
            {
                "source_id": source_id,
                "version_id": synthetic["version_id"],
                "title": synthetic["title"],
                "issuer": synthetic["issuer"],
                "document_type": None,
                "effective_from": synthetic.get("effective_date"),
                "effective_to": None,
                "storage_bucket": POLICY_SOURCES_BUCKET,
                "storage_path": object_path,
                "sha256": actual_sha,
                "byte_size": local_path.stat().st_size,
                "namespace": synthetic["namespace"],
                "visibility": "SCOPED",
                "is_synthetic": True,
                "metadata": {
                    "provenance_kind": "synthetic_internal_policy",
                    "format": synthetic.get("format"),
                    "document_version": synthetic.get("document_version"),
                    "organization_label": synthetic.get("organization_label"),
                    "declared_agent_scopes": declared_scopes,
                    "source_artifact_path": synthetic["path"],
                    "source_manifest_sha256": corpus_manifest["artifacts"]["synthetic"]["source_manifest"]["sha256"],
                },
            }
        )

    # These provenance manifests are also frozen inputs to source discovery;
    # include them in the end-of-run immutability snapshot even though they are
    # not uploaded as separate corpus-artifact objects.
    for provenance_path in (raw_manifest_path, real_sources_path, synthetic_manifest_path):
        local_hashes[str(provenance_path)] = _sha256_file(provenance_path)

    if len(source_documents) != EXPECTED_SOURCE_DOCUMENTS:
        raise CorpusImportError("canonical source discovery did not produce ten documents")
    for source_id, expected_count in corpus_manifest["chunk_counts"]["by_source"].items():
        if source_counts[source_id] != expected_count:
            raise CorpusImportError(f"source chunk count mismatch: {source_id}")
    for source_id in synthetic_by_id:
        if source_counts[source_id] != _source_artifact_entry(corpus_manifest, "synthetic", source_id).get("chunk_count", source_counts[source_id]):
            # The document artifact intentionally has no chunk_count in the
            # current freeze; the manifest by_source count is authoritative.
            if source_counts[source_id] != corpus_manifest["chunk_counts"]["by_source"][source_id]:
                raise CorpusImportError(f"synthetic source chunk count mismatch: {source_id}")

    artifact_specs = (
        ("policy-corpus-v2.jsonl", corpus_path, "corpus_jsonl", "application/x-ndjson"),
        ("policy-corpus-v2-manifest.json", corpus_manifest_path, "corpus_manifest", "application/json"),
        ("embeddings.parquet", embeddings_path, "embedding_parquet", "application/octet-stream"),
        ("embedding-manifest.json", embedding_manifest_path, "embedding_manifest", "application/json"),
    )
    for filename, path, kind, content_type in artifact_specs:
        obj = _artifact_object(CORPUS_ARTIFACTS_BUCKET, corpus_artifact_path(filename), path, kind, content_type)
        objects.append(obj)
        local_hashes[str(path)] = obj.sha256

    for mapping in corpus_manifest["synthetic_source_metadata_mapping"]:
        source_id = mapping["source_id"]
        expected_scopes = tuple(SCOPE_MAP[scope] for scope in mapping["agent_scopes"] if SCOPE_MAP[scope] is not None)
        if tuple(scope_by_source.get(source_id, ())) != expected_scopes:
            raise CorpusImportError(f"synthetic scope mapping drift: {source_id}")
    supported_scope_rows = sum(source_counts[source_id] * len(scopes) for source_id, scopes in scope_by_source.items())
    manifest_scope_rows = sum(
        corpus_manifest["chunk_counts"]["by_source"][mapping["source_id"]]
        * sum(SCOPE_MAP[scope] is not None for scope in mapping["agent_scopes"])
        for mapping in corpus_manifest["synthetic_source_metadata_mapping"]
    )
    if supported_scope_rows != manifest_scope_rows:
        raise CorpusImportError("synthetic scope-row derivation is inconsistent")

    profile_identity = f"{parquet_sha}:{embedding_manifest_sha}"
    embedding_profile_id = _deterministic_uuid("embedding-profile", profile_identity)
    corpus_version_id = _deterministic_uuid(
        "corpus-version", f"{CORPUS_NAME}:{corpus_manifest['manifest_version']}:{corpus_manifest['manifest_hash']}"
    )
    artifact_metadata = {
        obj.kind: {
            "bucket": obj.bucket,
            "path": obj.path,
            "sha256": obj.sha256,
            "byte_size": obj.byte_size,
        }
        for obj in objects
        if obj.kind in {"corpus_jsonl", "corpus_manifest", "embedding_parquet", "embedding_manifest"}
    }
    corpus_version_metadata = {
        "identity_version": "stage11c-v1",
        "corpus_identifier": CORPUS_NAME,
        "manifest_version": corpus_manifest["manifest_version"],
        "manifest_identity_sha256": corpus_manifest["manifest_hash"],
        "manifest_artifact_sha256": corpus_manifest_sha,
        "corpus_v2_hash": corpus_manifest["corpus_v2_hash"],
        "corpus_artifacts": artifact_metadata,
        "chunk_counts": corpus_manifest["chunk_counts"],
        "source_counts": corpus_manifest["source_counts"],
        "embedding_profile_id": str(embedding_profile_id),
        "embedding_artifact_sha256": parquet_sha,
        "embedding_manifest_artifact_sha256": embedding_manifest_sha,
        "embedding_manifest_identity": {
            "model_id": embedding_manifest["model_id"],
            "model_format": embedding_manifest["model_format"],
            "quantization": embedding_manifest["quantization"],
            "dimension": embedding_manifest["embedding_dimension"],
            "normalization": embedding_manifest["normalization"],
            "pooling": embedding_manifest.get("pooling"),
            "backend": embedding_manifest["backend"],
            "device_backend": embedding_manifest["device_backend"],
            "input_template_version": embedding_manifest["input_template_version"],
        },
    }
    return FrozenBundle(
        root=root,
        chunks=tuple(chunks),
        vectors=vectors,
        corpus_manifest=corpus_manifest,
        embedding_manifest=embedding_manifest,
        source_documents=tuple(source_documents),
        objects=tuple(objects),
        scope_by_source=scope_by_source,
        local_hashes=local_hashes,
        embedding_profile_id=embedding_profile_id,
        corpus_version_id=corpus_version_id,
        corpus_version_metadata=corpus_version_metadata,
        expected_scope_rows=supported_scope_rows,
    )


def verify_local_snapshot(bundle: FrozenBundle) -> None:
    for path, expected_hash in bundle.local_hashes.items():
        actual = _sha256_file(Path(path))
        if actual != expected_hash:
            raise CorpusImportError(f"local frozen artifact changed during Stage 11C: {path}")


def sync_storage(bundle: FrozenBundle, storage: SupabaseStorageClient) -> tuple[StorageObjectSyncResult, ...]:
    storage.verify_private_buckets()
    results = tuple(
        storage.sync_object(
            obj.bucket,
            obj.path,
            obj.local_path,
            content_type=obj.content_type,
        )
        for obj in bundle.objects
    )
    if any(result.sha256 != obj.sha256 or result.byte_size != obj.byte_size for result, obj in zip(results, bundle.objects, strict=True)):
        raise CorpusImportError("Storage read-back verification did not match the local object plan")
    return results


def _date_value(value: object, *, context: str) -> date | None:
    return _parse_date(value, context=context)


def _document_expected(bundle: FrozenBundle, source: dict[str, Any], corpus_version_id: UUID) -> dict[str, Any]:
    return {
        "corpus_version_id": corpus_version_id,
        "source_id": source["source_id"],
        "version_id": source["version_id"],
        "title": source["title"],
        "issuer": source["issuer"],
        "document_type": source["document_type"],
        "effective_from": _date_value(source["effective_from"], context=f"{source['source_id']}.effective_from"),
        "effective_to": _date_value(source["effective_to"], context=f"{source['source_id']}.effective_to"),
        "storage_bucket": source["storage_bucket"],
        "storage_path": source["storage_path"],
        "sha256": source["sha256"],
        "byte_size": source["byte_size"],
        "namespace": source["namespace"],
        "visibility": source["visibility"],
        "is_synthetic": source["is_synthetic"],
        "metadata_": source["metadata"],
    }


def _assert_document(actual: V2PolicyDocument, expected: dict[str, Any]) -> None:
    for field, expected_value in expected.items():
        if getattr(actual, field) != expected_value:
            raise CorpusImportError(f"existing policy document identity conflict: {actual.source_id}")


def _assert_profile(actual: EmbeddingProfile, expected: dict[str, Any]) -> None:
    for field, expected_value in expected.items():
        if getattr(actual, field) != expected_value:
            raise CorpusImportError(f"existing embedding profile identity conflict: {field}")


def _assert_corpus_version(actual: CorpusVersion, expected: dict[str, Any]) -> None:
    for field, expected_value in expected.items():
        if getattr(actual, field) != expected_value:
            raise CorpusImportError(f"existing corpus version identity conflict: {field}")


def _chunk_metadata(chunk: dict[str, Any], index: int, vector: tuple[float, ...], source: dict[str, Any]) -> dict[str, Any]:
    canonical_fields = {key: value for key, value in chunk.items() if key != "content"}
    return {
        "identity_version": "stage11c-v1",
        "canonical_chunk_index": index,
        "canonical_source_id": source["source_id"],
        "canonical_version_id": source["version_id"],
        "embedding_vector_sha256": _vector_hash(vector),
        "canonical_chunk": canonical_fields,
    }


def _chunk_expected(
    chunk: dict[str, Any],
    index: int,
    vector: tuple[float, ...],
    source: dict[str, Any],
    document_id: UUID,
    embedding_profile_id: UUID,
    scopes: tuple[str, ...],
) -> dict[str, Any]:
    content_hash = _sha256_bytes(chunk["content"].encode("utf-8"))
    namespace = source["namespace"]
    is_synthetic = source["is_synthetic"]
    expected_visibility = "SCOPED" if is_synthetic else "SHARED"
    if not is_synthetic and scopes:
        raise CorpusImportError(f"regulation chunk has specialist scope metadata: {chunk['canonical_chunk_id']}")
    if is_synthetic and not scopes:
        raise CorpusImportError(f"synthetic chunk has no supported scope: {chunk['canonical_chunk_id']}")
    return {
        "document_id": document_id,
        "embedding_profile_id": embedding_profile_id,
        "canonical_chunk_id": chunk["canonical_chunk_id"],
        "content": chunk["content"],
        "content_hash": content_hash,
        "heading_path": chunk["heading_path"],
        "locator": {
            "chapter": chunk.get("chapter"),
            "section": chunk.get("section"),
            "article": chunk.get("article"),
            "clause": chunk.get("clause"),
            "point": chunk.get("point"),
            "page_start": chunk.get("page_start"),
            "page_end": chunk.get("page_end"),
            "hierarchy_instance": chunk.get("hierarchy_instance"),
        },
        "namespace": namespace,
        "visibility": expected_visibility,
        "is_synthetic": is_synthetic,
        "embedding": list(vector),
        "metadata_": _chunk_metadata(chunk, index, vector, source),
    }


def _assert_chunk(actual: PolicyChunk, expected: dict[str, Any]) -> None:
    for field, expected_value in expected.items():
        if field == "embedding":
            actual_vector = actual.embedding
            if actual_vector is None or len(actual_vector) != EXPECTED_DIMENSION:
                raise CorpusImportError(f"existing vector dimension conflict: {actual.canonical_chunk_id}")
            if _vector_hash(actual_vector) != _vector_hash(expected_value):
                raise CorpusImportError(f"existing vector identity conflict: {actual.canonical_chunk_id}")
            continue
        if getattr(actual, field) != expected_value:
            raise CorpusImportError(f"existing policy chunk identity conflict: {actual.canonical_chunk_id}")


def _assert_access(actual: ChunkScopeAccess, chunk_id: UUID, scope: str) -> None:
    if actual.policy_chunk_id != chunk_id or actual.scope != scope:
        raise CorpusImportError("existing chunk scope access identity conflict")


def _profile_expected(bundle: FrozenBundle) -> dict[str, Any]:
    manifest = bundle.embedding_manifest
    embeddings_path = bundle.root / "dataset/embeddings/v2/embeddings.parquet"
    embedding_manifest_path = bundle.root / "dataset/embeddings/v2/embedding-manifest.json"
    metadata = {
        "identity_version": "stage11c-v1",
        "profile_identity": {
            "embedding_artifact_sha256": _sha256_file(embeddings_path),
            "embedding_manifest_artifact_sha256": _sha256_file(embedding_manifest_path),
        },
        "artifact_bucket": CORPUS_ARTIFACTS_BUCKET,
        "artifact_path": corpus_artifact_path("embeddings.parquet"),
        "embedding_manifest_path": corpus_artifact_path("embedding-manifest.json"),
        "embedding_manifest_sha256": _sha256_file(embedding_manifest_path),
        "stage10_manifest": manifest,
    }
    return {
        "model_id": manifest["model_id"],
        "model_revision": manifest.get("resolved_revision"),
        "dimension": manifest["embedding_dimension"],
        "similarity": manifest["similarity"],
        "is_unit_normalized": manifest["normalize_embeddings"],
        "metadata_": metadata,
    }


def _corpus_expected(bundle: FrozenBundle, embedding_profile_id: UUID) -> dict[str, Any]:
    manifest_path = bundle.root / "dataset/manifests/policy-corpus-v2-manifest.json"
    return {
        "corpus_name": CORPUS_NAME,
        "version": bundle.corpus_manifest["manifest_version"],
        "manifest_sha256": _sha256_file(manifest_path),
        "metadata_": {**bundle.corpus_version_metadata, "embedding_profile_id": str(embedding_profile_id)},
    }


def _upsert_profile(session: Session, bundle: FrozenBundle) -> EmbeddingProfile:
    expected = _profile_expected(bundle)
    actual = session.get(EmbeddingProfile, bundle.embedding_profile_id)
    if actual is None:
        candidates = session.scalars(
            select(EmbeddingProfile).where(
                EmbeddingProfile.model_id == expected["model_id"],
                EmbeddingProfile.model_revision == expected["model_revision"],
            )
        ).all()
        if len(candidates) > 1:
            raise CorpusImportError("multiple existing embedding profiles match the canonical model identity")
        if candidates:
            actual = candidates[0]
        else:
            actual = EmbeddingProfile(id=bundle.embedding_profile_id, **expected)
            session.add(actual)
            session.flush()
            return actual
    _assert_profile(actual, expected)
    return actual


def _upsert_corpus_version(session: Session, bundle: FrozenBundle, profile_id: UUID) -> CorpusVersion:
    expected = _corpus_expected(bundle, profile_id)
    actual = session.get(CorpusVersion, bundle.corpus_version_id)
    if actual is None:
        actual = session.scalar(
            select(CorpusVersion).where(
                CorpusVersion.corpus_name == expected["corpus_name"],
                CorpusVersion.version == expected["version"],
            )
        )
    if actual is None:
        actual = CorpusVersion(id=bundle.corpus_version_id, **expected)
        session.add(actual)
        session.flush()
        return actual
    _assert_corpus_version(actual, expected)
    return actual


def _upsert_documents(session: Session, bundle: FrozenBundle, corpus_version_id: UUID) -> dict[tuple[str, str], V2PolicyDocument]:
    result: dict[tuple[str, str], V2PolicyDocument] = {}
    for source in bundle.source_documents:
        expected = _document_expected(bundle, source, corpus_version_id)
        actual = session.scalar(
            select(V2PolicyDocument).where(
                V2PolicyDocument.corpus_version_id == corpus_version_id,
                V2PolicyDocument.source_id == source["source_id"],
                V2PolicyDocument.version_id == source["version_id"],
            )
        )
        if actual is None:
            actual = V2PolicyDocument(id=_deterministic_uuid("document", f"{corpus_version_id}:{source['source_id']}:{source['version_id']}"), **expected)
            session.add(actual)
            session.flush()
        else:
            _assert_document(actual, expected)
        result[(source["source_id"], source["version_id"])] = actual
    return result


def _upsert_chunks(
    session: Session,
    bundle: FrozenBundle,
    documents: dict[tuple[str, str], V2PolicyDocument],
    profile_id: UUID,
) -> tuple[dict[str, PolicyChunk], list[tuple[UUID, str]]]:
    ids = [chunk["canonical_chunk_id"] for chunk in bundle.chunks]
    existing = {
        item.canonical_chunk_id: item
        for item in session.scalars(select(PolicyChunk).where(PolicyChunk.canonical_chunk_id.in_(ids))).all()
    }
    chunks: dict[str, PolicyChunk] = {}
    access_keys: list[tuple[UUID, str]] = []
    source_by_key = {(item["source_id"], item["version_id"]): item for item in bundle.source_documents}
    for index, (chunk, vector) in enumerate(zip(bundle.chunks, bundle.vectors, strict=True)):
        source = source_by_key.get((chunk["source_id"], chunk["version_id"]))
        if source is None:
            raise CorpusImportError(f"chunk has no exact source/version mapping: {chunk['canonical_chunk_id']}")
        document = documents.get((source["source_id"], source["version_id"]))
        if document is None:
            raise CorpusImportError(f"chunk has no policy document mapping: {chunk['canonical_chunk_id']}")
        scopes = bundle.scope_by_source.get(source["source_id"], ()) if source["is_synthetic"] else ()
        expected = _chunk_expected(chunk, index, vector, source, document.id, profile_id, scopes)
        actual = existing.get(chunk["canonical_chunk_id"])
        if actual is None:
            actual = PolicyChunk(id=_deterministic_uuid("chunk", chunk["canonical_chunk_id"]), **expected)
            session.add(actual)
        else:
            _assert_chunk(actual, expected)
        chunks[chunk["canonical_chunk_id"]] = actual
    session.flush()
    for chunk, source in zip(bundle.chunks, (source_by_key[(c["source_id"], c["version_id"])] for c in bundle.chunks), strict=True):
        if source["is_synthetic"]:
            for scope in bundle.scope_by_source[source["source_id"]]:
                access_keys.append((chunks[chunk["canonical_chunk_id"]].id, scope))
    return chunks, access_keys


def _upsert_access(session: Session, access_keys: list[tuple[UUID, str]]) -> None:
    chunk_ids = {chunk_id for chunk_id, _ in access_keys}
    existing = {
        (item.policy_chunk_id, item.scope): item
        for item in session.scalars(
            select(ChunkScopeAccess).where(ChunkScopeAccess.policy_chunk_id.in_(chunk_ids))
        ).all()
    } if chunk_ids else {}
    for chunk_id, scope in access_keys:
        if scope not in SUPPORTED_SPECIALIST_SCOPES:
            raise CorpusImportError(f"unsupported persisted specialist scope: {scope}")
        actual = existing.get((chunk_id, scope))
        if actual is None:
            session.add(
                ChunkScopeAccess(
                    id=_deterministic_uuid("scope-access", f"{chunk_id}:{scope}"),
                    policy_chunk_id=chunk_id,
                    scope=scope,
                )
            )
        else:
            _assert_access(actual, chunk_id, scope)
    session.flush()


def _all_db_counts(session: Session) -> dict[str, int]:
    return {
        "embedding_profiles": session.scalar(select(func.count()).select_from(EmbeddingProfile)) or 0,
        "corpus_versions": session.scalar(select(func.count()).select_from(CorpusVersion)) or 0,
        "policy_documents": session.scalar(select(func.count()).select_from(V2PolicyDocument)) or 0,
        "policy_chunks": session.scalar(select(func.count()).select_from(PolicyChunk)) or 0,
        "chunk_scope_access": session.scalar(select(func.count()).select_from(ChunkScopeAccess)) or 0,
    }


def snapshot_counts(engine: Engine) -> dict[str, int]:
    with Session(engine) as session:
        return _all_db_counts(session)


def validate_database(session: Session, bundle: FrozenBundle, profile: EmbeddingProfile, corpus: CorpusVersion) -> dict[str, Any]:
    counts = _all_db_counts(session)
    expected_counts = {
        "embedding_profiles": 1,
        "corpus_versions": 1,
        "policy_documents": EXPECTED_SOURCE_DOCUMENTS,
        "policy_chunks": EXPECTED_TOTAL_CHUNKS,
    }
    for name, expected in expected_counts.items():
        if counts[name] != expected:
            raise CorpusImportError(f"database {name} count {counts[name]} != expected {expected}")
    chunks = session.scalars(select(PolicyChunk).order_by(PolicyChunk.canonical_chunk_id)).all()
    documents = session.scalars(select(V2PolicyDocument).order_by(V2PolicyDocument.source_id)).all()
    access = session.scalars(select(ChunkScopeAccess).order_by(ChunkScopeAccess.scope, ChunkScopeAccess.policy_chunk_id)).all()
    if len(chunks) != len({item.canonical_chunk_id for item in chunks}) or len(chunks) != len({item.id for item in chunks}):
        raise CorpusImportError("canonical chunks are duplicated")
    if len(access) != len({(item.policy_chunk_id, item.scope) for item in access}):
        raise CorpusImportError("scope access rows are duplicated")
    if len(chunks) != EXPECTED_TOTAL_CHUNKS:
        raise CorpusImportError("canonical chunk/vector count is not 1,610")

    source_by_key = {(item["source_id"], item["version_id"]): item for item in bundle.source_documents}
    expected_by_id = {item["canonical_chunk_id"]: (index, item, bundle.vectors[index]) for index, item in enumerate(bundle.chunks)}
    document_ids = {item.id for item in documents}
    chunk_ids = {item.id for item in chunks}
    access_by_chunk: dict[UUID, list[str]] = {}
    for item in access:
        access_by_chunk.setdefault(item.policy_chunk_id, []).append(item.scope)
    shared = scoped = content_hash_failures = vector_hash_failures = dimension_failures = zero_vectors = nonfinite = 0
    for actual in chunks:
        expected_item = expected_by_id.get(actual.canonical_chunk_id)
        if expected_item is None:
            raise CorpusImportError(f"unknown canonical chunk in database: {actual.canonical_chunk_id}")
        index, chunk, vector = expected_item
        source = source_by_key[(chunk["source_id"], chunk["version_id"])]
        if actual.document_id not in document_ids or actual.embedding_profile_id != profile.id:
            raise CorpusImportError(f"orphan/misbound chunk: {actual.canonical_chunk_id}")
        expected_content_hash = _sha256_bytes(chunk["content"].encode("utf-8"))
        content_hash_failures += actual.content_hash != expected_content_hash
        expected_vector_hash = _vector_hash(vector)
        actual_vector = actual.embedding
        if actual_vector is None or len(actual_vector) != EXPECTED_DIMENSION:
            dimension_failures += 1
        else:
            values = [float(item) for item in actual_vector]
            nonfinite += not all(math.isfinite(item) for item in values)
            norm = math.sqrt(math.fsum(item * item for item in values))
            zero_vectors += norm == 0.0
            vector_hash_failures += _vector_hash(values) != expected_vector_hash
        metadata_hash = actual.metadata_.get("embedding_vector_sha256") if isinstance(actual.metadata_, dict) else None
        vector_hash_failures += metadata_hash != expected_vector_hash
        if source["is_synthetic"]:
            scoped += 1
            if actual.visibility != "SCOPED" or not actual.is_synthetic:
                raise CorpusImportError(f"synthetic visibility mismatch: {actual.canonical_chunk_id}")
            actual_scopes = set(access_by_chunk.get(actual.id, ()))
            expected_scopes = set(bundle.scope_by_source[source["source_id"]])
            if actual_scopes != expected_scopes:
                raise CorpusImportError(f"synthetic scope coverage mismatch: {actual.canonical_chunk_id}")
        else:
            shared += 1
            if actual.visibility != "SHARED" or actual.is_synthetic or access_by_chunk.get(actual.id):
                raise CorpusImportError(f"regulation visibility/scope mismatch: {actual.canonical_chunk_id}")
        if actual.metadata_.get("canonical_chunk_index") != index:
            raise CorpusImportError(f"canonical chunk index metadata mismatch: {actual.canonical_chunk_id}")
    if shared != EXPECTED_REAL_CHUNKS or scoped != EXPECTED_SYNTHETIC_CHUNKS:
        raise CorpusImportError(f"visibility counts are {shared} SHARED / {scoped} SCOPED")
    orphan_chunks = sum(item.document_id not in document_ids for item in chunks)
    orphan_access = sum(item.policy_chunk_id not in chunk_ids for item in access)
    if orphan_chunks or orphan_access:
        raise CorpusImportError("orphan chunks or scope access rows detected")
    if content_hash_failures or vector_hash_failures or dimension_failures or zero_vectors or nonfinite:
        raise CorpusImportError(
            "canonical content/vector validation failed: "
            f"content_hash={content_hash_failures}, vector_hash={vector_hash_failures}, "
            f"dimension={dimension_failures}, zero={zero_vectors}, nonfinite={nonfinite}"
        )
    scope_counts = Counter(item.scope for item in access)
    expected_scope_counts = Counter()
    for source_id, scopes in bundle.scope_by_source.items():
        for scope in scopes:
            expected_scope_counts[scope] += sum(1 for chunk in bundle.chunks if chunk["source_id"] == source_id)
    if scope_counts != expected_scope_counts:
        raise CorpusImportError(f"scope row counts differ: {dict(scope_counts)} != {dict(expected_scope_counts)}")
    if sum(scope_counts.values()) != bundle.expected_scope_rows:
        raise CorpusImportError(
            "persisted scope-row count differs from the canonical manifest-derived count"
        )
    if len({item.document_id for item in chunks}) != EXPECTED_SOURCE_DOCUMENTS:
        raise CorpusImportError("not all ten canonical documents are represented by chunks")
    data_digest = hashlib.sha256(
        _canonical_json(
            {
                "profile": {
                    "id": str(profile.id),
                    "model_id": profile.model_id,
                    "model_revision": profile.model_revision,
                    "dimension": profile.dimension,
                    "similarity": profile.similarity,
                    "is_unit_normalized": profile.is_unit_normalized,
                    "metadata": profile.metadata_,
                },
                "corpus": {
                    "id": str(corpus.id),
                    "corpus_name": corpus.corpus_name,
                    "version": corpus.version,
                    "manifest_sha256": corpus.manifest_sha256,
                    "metadata": corpus.metadata_,
                },
                "documents": [
                    {key: getattr(item, key) for key in (
                        "id", "corpus_version_id", "source_id", "version_id", "title", "issuer", "document_type",
                        "effective_from", "effective_to", "storage_bucket", "storage_path", "sha256", "byte_size",
                        "namespace", "visibility", "is_synthetic", "metadata_"
                    )} | {"id": str(item.id), "corpus_version_id": str(item.corpus_version_id), "effective_from": item.effective_from.isoformat() if item.effective_from else None, "effective_to": item.effective_to.isoformat() if item.effective_to else None}
                    for item in documents
                ],
                "chunks": [
                    {
                        "canonical_chunk_id": item.canonical_chunk_id,
                        "document_id": str(item.document_id),
                        "embedding_profile_id": str(item.embedding_profile_id),
                        "content_hash": item.content_hash,
                        "namespace": item.namespace,
                        "visibility": item.visibility,
                        "is_synthetic": item.is_synthetic,
                        "vector_sha256": item.metadata_.get("embedding_vector_sha256"),
                        "metadata": item.metadata_,
                    }
                    for item in chunks
                ],
                "access": [{"chunk_id": str(item.policy_chunk_id), "scope": item.scope} for item in access],
            }
        )
    ).hexdigest()
    return {
        **counts,
        "distinct_canonical_chunk_id": len({item.canonical_chunk_id for item in chunks}),
        "vectors": len(chunks),
        "duplicate_vector_rows": len(chunks) - len({item.canonical_chunk_id for item in chunks}),
        "shared": shared,
        "scoped": scoped,
        "scope_counts": dict(sorted(scope_counts.items())),
        "scope_rows": len(access),
        "synthetic_chunks_covered": scoped,
        "orphan_documents": sum(not any(chunk.document_id == document.id for chunk in chunks) for document in documents),
        "orphan_chunks": orphan_chunks,
        "orphan_scope_rows": orphan_access,
        "content_hash_failures": content_hash_failures,
        "vector_hash_failures": vector_hash_failures,
        "dimension_failures": dimension_failures,
        "zero_vectors": zero_vectors,
        "nonfinite_vectors": nonfinite,
        "regulation_scope_rows": sum(bool(access_by_chunk.get(item.id)) for item in chunks if not item.is_synthetic),
        "identity_digest": data_digest,
    }


def import_database(bundle: FrozenBundle, engine: Engine, *, dry_run: bool) -> dict[str, Any]:
    """Apply or transactionally exercise the canonical DB import."""

    with Session(engine) as session:
        transaction = session.begin()
        try:
            profile = _upsert_profile(session, bundle)
            corpus = _upsert_corpus_version(session, bundle, profile.id)
            documents = _upsert_documents(session, bundle, corpus.id)
            chunks, access_keys = _upsert_chunks(session, bundle, documents, profile.id)
            _upsert_access(session, access_keys)
            report = validate_database(session, bundle, profile, corpus)
            if dry_run:
                transaction.rollback()
            else:
                transaction.commit()
            return report
        except Exception:
            transaction.rollback()
            raise


def validate_local_preflight(root: Path = ROOT) -> FrozenBundle:
    """Convenience entry point used by the CLI and focused tests."""

    return load_frozen_bundle(root)
