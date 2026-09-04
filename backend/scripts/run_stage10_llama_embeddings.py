"""Create and validate the canonical Stage 10 llama.cpp embedding bundle.

This intentionally does not load, download, or otherwise manage a model.  It
only speaks the OpenAI-compatible embeddings API exposed by the already-running
llama.cpp server.  A failed run never publishes a partial canonical artifact.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import struct
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pyarrow as pa
import pyarrow.parquet as pq

try:  # Package import for tests.
    from scripts.build_policy_corpus_v2 import ROOT, build_manifest
except ModuleNotFoundError:  # Direct execution from backend/scripts.
    from build_policy_corpus_v2 import ROOT, build_manifest


CORPUS_PATH = ROOT / "dataset/chunks/v2/policy-corpus-v2.jsonl"
CORPUS_MANIFEST_PATH = ROOT / "dataset/manifests/policy-corpus-v2-manifest.json"
REAL_SOURCES_PATH = ROOT / "dataset/normalized/v2/policy-sources.json"
SYNTHETIC_MANIFEST_PATH = ROOT / "dataset/synthetic/policies/v1/manifest.json"
OUTPUT_DIR = ROOT / "dataset/embeddings/v2"
PARQUET_NAME = "embeddings.parquet"
MANIFEST_NAME = "embedding-manifest.json"
EXPECTED_COUNT = 1610
DIMENSION = 1024
# llama.cpp expects the local model name, while the manifest records the
# canonical upstream model family separately.
REQUEST_MODEL = "Qwen3-Embedding-0.6B"
MODEL_FAMILY = "Qwen/Qwen3-Embedding-0.6B"
DEFAULT_ENDPOINT = "http://127.0.0.1:8081/v1/embeddings"
DOCUMENT_TEMPLATE_VERSION = "policy-title-heading-content-v1"
DOCUMENT_TEMPLATE = "Document: {title}\nSection: {heading_path}\nText:\n{content}"
NORM_TOLERANCE = 1e-4


class EmbeddingRequestError(RuntimeError):
    """A bounded, actionable llama.cpp request failure."""


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"frozen corpus has a UTF-8 BOM: {path}")
    lines = raw.splitlines(keepends=True)
    if any(not line.endswith(b"\n") or not line.strip() for line in lines):
        raise ValueError("frozen corpus must contain only newline-terminated JSON records")
    return [json.loads(line) for line in lines]


def _source_metadata() -> dict[str, dict[str, Any]]:
    """Build only the metadata that Corpus V2 did not duplicate into rows."""
    real = _read_json(REAL_SOURCES_PATH)
    synthetic = _read_json(SYNTHETIC_MANIFEST_PATH)["records"]
    result: dict[str, dict[str, Any]] = {}
    for source in real:
        result[source["source_id"]] = {
            "title": source["title"],
            "namespace": "REGULATION",
            "effective_from": source.get("effective_date") or source.get("issue_date"),
            "allowed_product_codes": [],
            "allowed_agent_scopes": [],
        }
    for source in synthetic:
        result[source["source_id"]] = {
            "title": source["title"],
            "namespace": source["namespace"],
            "effective_from": source["effective_date"],
            "allowed_product_codes": [],
            "allowed_agent_scopes": source["agent_scopes"],
        }
    return result


def _locator(chunk: dict[str, Any]) -> dict[str, Any]:
    return {
        "chapter": chunk.get("chapter"),
        "section": chunk.get("section"),
        "article": chunk.get("article"),
        "clause": chunk.get("clause"),
        "point": chunk.get("point"),
        "page_start": chunk.get("page_start"),
        "page_end": chunk.get("page_end"),
        "hierarchy_instance": chunk.get("hierarchy_instance"),
    }


def build_rows(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Turn the frozen corpus into ordered API inputs and parquet metadata."""
    source_by_id = _source_metadata()
    rows: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, chunk in enumerate(chunks):
        chunk_id = chunk["canonical_chunk_id"]
        if chunk_id in ids:
            raise ValueError(f"duplicate canonical_chunk_id in frozen corpus: {chunk_id}")
        ids.add(chunk_id)
        source = source_by_id.get(chunk["source_id"])
        if source is None:
            raise ValueError(f"missing source metadata for {chunk['source_id']}")
        if source["namespace"] == "REGULATION" and chunk["source_id"].startswith("synthetic-"):
            raise ValueError(f"synthetic source incorrectly classified as regulation: {chunk['source_id']}")
        heading_path = " > ".join(chunk["heading_path"])
        embedding_input = DOCUMENT_TEMPLATE.format(
            title=source["title"], heading_path=heading_path, content=chunk["content"]
        )
        rows.append(
            {
                "chunk_id": chunk_id,
                "source_id": chunk["source_id"],
                "version_id": chunk["version_id"],
                "namespace": source["namespace"],
                "chunk_index": index,
                "heading_path_json": json.dumps(chunk["heading_path"], ensure_ascii=False, separators=(",", ":")),
                "locator_json": json.dumps(_locator(chunk), ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                "content_hash": f"sha256:{_sha256_text(chunk['content'])}",
                "embedding_input": embedding_input,
                "embedding_input_hash": f"sha256:{_sha256_text(embedding_input)}",
                "effective_from": source["effective_from"],
                "effective_to": None,
                "allowed_product_codes_json": json.dumps(source["allowed_product_codes"], separators=(",", ":")),
                "allowed_agent_scopes_json": json.dumps(source["allowed_agent_scopes"], ensure_ascii=False, separators=(",", ":")),
            }
        )
    return rows


def _as_float32(value: float) -> float:
    return struct.unpack("<f", struct.pack("<f", float(value)))[0]


def validate_vector(vector: Iterable[Any], *, context: str) -> list[float]:
    try:
        values = [_as_float32(float(value)) for value in vector]
    except (TypeError, ValueError, OverflowError, struct.error) as exc:
        raise ValueError(f"{context}: embedding contains a non-numeric value") from exc
    if len(values) != DIMENSION:
        raise ValueError(f"{context}: expected {DIMENSION} dimensions, got {len(values)}")
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f"{context}: embedding contains NaN or infinity")
    norm = math.sqrt(math.fsum(value * value for value in values))
    if not math.isfinite(norm) or norm == 0.0:
        raise ValueError(f"{context}: embedding has zero or invalid norm")
    if abs(norm - 1.0) > NORM_TOLERANCE:
        raise ValueError(f"{context}: embedding norm is {norm}, expected 1.0 +/- {NORM_TOLERANCE}")
    # Preserve the server values after their required float32 representation
    # check.  Renormalizing here would mask a non-canonical server response.
    return values


class LlamaCppEmbeddingClient:
    def __init__(self, endpoint: str = DEFAULT_ENDPOINT, timeout_seconds: float = 60.0, model: str = REQUEST_MODEL) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self.model = model

    def _json_request(self, url: str, payload: dict[str, Any] | None = None) -> Any:
        data = None if payload is None else _canonical_json(payload)
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json; charset=utf-8"
        request = Request(url, data=data, headers=headers, method="POST" if data is not None else "GET")
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:  # no retries by design
                raw = response.read()
        except HTTPError as exc:
            body = exc.read(1024).decode("utf-8", errors="replace")
            raise EmbeddingRequestError(f"HTTP {exc.code} from {url}: {body}") from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise EmbeddingRequestError(f"request to {url} failed: {exc}") from exc
        try:
            return json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise EmbeddingRequestError(f"malformed UTF-8 JSON response from {url}") from exc

    def server_metadata(self) -> Any:
        base = self.endpoint.rsplit("/v1/embeddings", 1)[0]
        return self._json_request(f"{base}/v1/models")

    def embed_one(self, text: str) -> list[float]:
        payload = {"model": self.model, "input": [text]}
        response = self._json_request(self.endpoint, payload)
        if not isinstance(response, dict) or not isinstance(response.get("data"), list) or len(response["data"]) != 1:
            raise EmbeddingRequestError("embedding response must contain exactly one data item")
        item = response["data"][0]
        if not isinstance(item, dict) or not isinstance(item.get("embedding"), list):
            raise EmbeddingRequestError("embedding response data item is malformed")
        try:
            return validate_vector(item["embedding"], context="llama.cpp response")
        except ValueError as exc:
            raise EmbeddingRequestError(str(exc)) from exc


def _metadata_supports_last_token(metadata: Any) -> bool:
    if isinstance(metadata, dict):
        for key, value in metadata.items():
            if key.lower() in {"pooling", "pooling_type", "poolingtype"} and isinstance(value, str):
                if value.strip().upper() in {"LAST", "LAST_TOKEN"}:
                    return True
            if _metadata_supports_last_token(value):
                return True
    elif isinstance(metadata, list):
        return any(_metadata_supports_last_token(item) for item in metadata)
    return False


def _embedding_column(vectors: list[list[float]]) -> pa.FixedSizeListArray:
    flattened = [value for vector in vectors for value in vector]
    return pa.FixedSizeListArray.from_arrays(pa.array(flattened, type=pa.float32()), DIMENSION)


def _write_parquet(path: Path, rows: list[dict[str, Any]], vectors: list[list[float]], model: str) -> None:
    table = pa.table(
        {
            "chunk_id": [row["chunk_id"] for row in rows],
            "source_id": [row["source_id"] for row in rows],
            "version_id": [row["version_id"] for row in rows],
            "namespace": [row["namespace"] for row in rows],
            "chunk_index": pa.array([row["chunk_index"] for row in rows], type=pa.int32()),
            "heading_path_json": [row["heading_path_json"] for row in rows],
            "locator_json": [row["locator_json"] for row in rows],
            "content_hash": [row["content_hash"] for row in rows],
            "embedding_input_hash": [row["embedding_input_hash"] for row in rows],
            "effective_from": [row["effective_from"] for row in rows],
            "effective_to": [row["effective_to"] for row in rows],
            "allowed_product_codes_json": [row["allowed_product_codes_json"] for row in rows],
            "allowed_agent_scopes_json": [row["allowed_agent_scopes_json"] for row in rows],
            "embedding_model": [model] * len(rows),
            "embedding_revision": pa.array([None] * len(rows), type=pa.string()),
            "embedding_dimension": pa.array([DIMENSION] * len(rows), type=pa.int32()),
            "normalized": pa.array([True] * len(rows), type=pa.bool_()),
            "embedding": _embedding_column(vectors),
        }
    )
    pq.write_table(table, path, compression="zstd")


def _percentile_linear(sorted_values: list[float], percentile: float) -> float:
    """Return a deterministic percentile using linear interpolation at (n - 1) * p."""
    if not sorted_values:
        raise ValueError("cannot calculate a percentile of no values")
    index = (len(sorted_values) - 1) * percentile
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return sorted_values[lower]
    fraction = index - lower
    return sorted_values[lower] + (sorted_values[upper] - sorted_values[lower]) * fraction


def _norm_stats(vectors: list[list[float]]) -> dict[str, float]:
    norms = [math.sqrt(math.fsum(value * value for value in vector)) for vector in vectors]
    sorted_norms = sorted(norms)
    return {
        "min": min(norms),
        "p50": _percentile_linear(sorted_norms, 0.50),
        "mean": math.fsum(norms) / len(norms),
        "p95": _percentile_linear(sorted_norms, 0.95),
        "max": max(norms),
    }


def _content_input_digest(rows: list[dict[str, Any]]) -> str:
    identity = "\n".join(f"{row['chunk_id']}|{row['content_hash']}|{row['embedding_input_hash']}" for row in rows)
    return f"sha256:{_sha256_text(identity)}"


def _manifest(
    *, rows: list[dict[str, Any]], parquet_path: Path, corpus_manifest: dict[str, Any], server_metadata: Any,
    endpoint: str, model: str, elapsed_seconds: float, vectors: list[list[float]],
) -> dict[str, Any]:
    parquet_sha = _sha256_file(parquet_path)
    pooling = "LAST_TOKEN" if _metadata_supports_last_token(server_metadata) else None
    content_hash_digest = _sha256_text(
        "\n".join(f"{row['chunk_id']}|{row['content_hash']}" for row in rows)
    )
    return {
        "manifest_version": "2.0.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "index_tier": "canonical",
        "model_id": model,
        "model_family": MODEL_FAMILY,
        "requested_revision": None,
        "resolved_revision": None,
        "revision_status": "not_reported_by_server",
        "model_format": "GGUF",
        "quantization": "F16",
        "embedding_dimension": DIMENSION,
        "similarity": "cosine",
        "normalize_embeddings": True,
        "normalization": "L2",
        "pooling": pooling,
        "pooling_status": "verified_from_server_metadata" if pooling else "not_reported_by_server_metadata",
        "max_sequence_length": 3072,
        "context_length": 3072,
        "batch_size": 1,
        "input_template_version": DOCUMENT_TEMPLATE_VERSION,
        "input_template": DOCUMENT_TEMPLATE,
        "corpus_manifest_hash": f"sha256:{corpus_manifest['manifest_hash']}",
        "corpus_v2_hash": f"sha256:{corpus_manifest['corpus_v2_hash']}",
        "frozen_corpus_sha256": f"sha256:{_sha256_file(CORPUS_PATH)}",
        "input_artifact_hash": f"sha256:{_sha256_file(CORPUS_PATH)}",
        "input": {"chunk_count": len(rows), "manifest_hash": f"sha256:{corpus_manifest['manifest_hash']}"},
        "chunk_count": len(rows),
        "chunk_content_hash_digest": f"sha256:{content_hash_digest}",
        "content_input_hash_digest": _content_input_digest(rows),
        "backend": "llama.cpp",
        "endpoint": endpoint,
        "device_backend": "Vulkan",
        "gpu": "NVIDIA GeForce RTX 2050",
        "artifact_sha256": f"sha256:{parquet_sha}",
        "artifact_byte_size": parquet_path.stat().st_size,
        "server": {"backend": "llama.cpp", "endpoint": endpoint, "model_metadata": server_metadata},
        "runtime": {"backend": "llama.cpp", "acceleration": "Vulkan", "gpu": "NVIDIA GeForce RTX 2050"},
        "validation": {
            "row_count": len(rows), "expected_row_count": EXPECTED_COUNT, "id_order": "frozen policy-corpus-v2.jsonl order",
            "dimensions": DIMENSION, "all_finite": True, "nonzero_vectors": len(vectors),
            "unit_norm_tolerance": NORM_TOLERANCE,
            "norm_percentile_convention": "linear interpolation at (n - 1) * p",
            "norm": _norm_stats(vectors),
        },
        "performance": {"elapsed_seconds": elapsed_seconds, "vectors_per_second": len(rows) / elapsed_seconds if elapsed_seconds else None},
        "output": {"filename": PARQUET_NAME, "sha256": f"sha256:{parquet_sha}", "bytes": parquet_path.stat().st_size, "rows": len(rows)},
    }


def validate_bundle(parquet_path: Path, manifest_path: Path, *, expected_count: int = EXPECTED_COUNT) -> list[str]:
    """Validate the published bundle without calling the embedding endpoint."""
    errors: list[str] = []
    if not parquet_path.is_file() or not manifest_path.is_file():
        return ["missing canonical parquet or manifest"]
    try:
        manifest = _read_json(manifest_path)
        frozen_manifest = _read_json(CORPUS_MANIFEST_PATH)
        rebuilt_manifest = build_manifest(CORPUS_PATH)
        if frozen_manifest != rebuilt_manifest:
            errors.append("frozen corpus manifest no longer matches deterministic construction")
        if manifest.get("corpus_manifest_hash") != f"sha256:{frozen_manifest['manifest_hash']}":
            errors.append("corpus manifest hash mismatch")
        if manifest.get("corpus_v2_hash") != f"sha256:{frozen_manifest['corpus_v2_hash']}":
            errors.append("corpus V2 hash mismatch")
        if manifest.get("frozen_corpus_sha256") != f"sha256:{_sha256_file(CORPUS_PATH)}":
            errors.append("frozen corpus artifact hash mismatch")
        if manifest.get("input_artifact_hash") != f"sha256:{_sha256_file(CORPUS_PATH)}":
            errors.append("input artifact hash mismatch")
        output = manifest.get("output", {})
        if output.get("sha256") != f"sha256:{_sha256_file(parquet_path)}":
            errors.append("parquet artifact hash mismatch")
        if output.get("bytes") != parquet_path.stat().st_size:
            errors.append("parquet artifact byte count mismatch")
        chunks = _read_jsonl(CORPUS_PATH)
        expected_ids = [chunk["canonical_chunk_id"] for chunk in chunks]
        if len(expected_ids) != expected_count:
            errors.append(f"frozen corpus row count expected {expected_count}, got {len(expected_ids)}")
        table = pq.read_table(parquet_path)
        required = {
            "chunk_id", "embedding", "source_id", "version_id", "namespace", "chunk_index", "heading_path_json",
            "locator_json", "content_hash", "embedding_input_hash", "effective_from", "effective_to",
            "allowed_product_codes_json", "allowed_agent_scopes_json", "embedding_model", "embedding_revision",
            "embedding_dimension", "normalized",
        }
        missing = sorted(required - set(table.column_names))
        if missing:
            errors.append(f"parquet missing columns: {', '.join(missing)}")
            return errors
        embedding_type = table.schema.field("embedding").type
        if not pa.types.is_fixed_size_list(embedding_type) or embedding_type.list_size != DIMENSION or not pa.types.is_float32(embedding_type.value_type):
            errors.append("embedding column must be fixed_size_list<float32>[1024]")
        actual_ids = table.column("chunk_id").to_pylist()
        if table.num_rows != expected_count or manifest.get("chunk_count") != expected_count or output.get("rows") != expected_count:
            errors.append("row count mismatch")
        if actual_ids != expected_ids:
            errors.append("canonical chunk ID set or stable order mismatch")
        if len(actual_ids) != len(set(actual_ids)):
            errors.append("duplicate chunk IDs in parquet")
        vectors = table.column("embedding").to_pylist()
        norms: list[float] = []
        for index, vector in enumerate(vectors):
            try:
                checked = validate_vector(vector, context=f"row {index}")
                norms.append(math.sqrt(math.fsum(value * value for value in checked)))
            except ValueError as exc:
                errors.append(str(exc))
                break
        if norms and manifest.get("validation", {}).get("norm", {}).get("min") is None:
            errors.append("manifest lacks norm validation statistics")
        if manifest.get("content_input_hash_digest") != _content_input_digest(build_rows(chunks)):
            errors.append("content/input hash digest mismatch")
    except Exception as exc:
        errors.append(str(exc))
    return errors


def run_embedding_job(
    *, output_dir: Path = OUTPUT_DIR, endpoint: str = DEFAULT_ENDPOINT, timeout_seconds: float = 60.0,
    model: str = REQUEST_MODEL, expected_count: int = EXPECTED_COUNT,
    client_factory: Callable[[str, float, str], LlamaCppEmbeddingClient] = LlamaCppEmbeddingClient,
) -> dict[str, Any]:
    """Embed the frozen corpus serially, validate all vectors, then publish atomically."""
    parquet_path = output_dir / PARQUET_NAME
    manifest_path = output_dir / MANIFEST_NAME
    if parquet_path.exists() or manifest_path.exists():
        raise FileExistsError("refusing to overwrite an existing canonical Stage 10 embedding bundle")
    corpus_manifest = _read_json(CORPUS_MANIFEST_PATH)
    if corpus_manifest != build_manifest(CORPUS_PATH):
        raise ValueError("frozen corpus manifest validation failed before embedding")
    chunks = _read_jsonl(CORPUS_PATH)
    if len(chunks) != expected_count:
        raise ValueError(f"expected {expected_count} frozen chunks, got {len(chunks)}")
    rows = build_rows(chunks)
    output_dir.mkdir(parents=True, exist_ok=True)
    token = f"{os.getpid()}.{time.time_ns()}"
    temporary_parquet = output_dir / f".{PARQUET_NAME}.{token}.tmp"
    temporary_manifest = output_dir / f".{MANIFEST_NAME}.{token}.tmp"
    started = time.monotonic()
    try:
        client = client_factory(endpoint, timeout_seconds, model)
        server_metadata = client.server_metadata()
        vectors: list[list[float]] = []
        for index, row in enumerate(rows, start=1):
            try:
                vectors.append(client.embed_one(row["embedding_input"]))
            except Exception as exc:
                raise EmbeddingRequestError(f"embedding failed at frozen row {index}/{len(rows)} ({row['chunk_id']}): {exc}") from exc
        if len(vectors) != expected_count:
            raise ValueError("embedding response count mismatch")
        for index, vector in enumerate(vectors):
            validate_vector(vector, context=f"prepublish row {index}")
        _write_parquet(temporary_parquet, rows, vectors, model)
        elapsed_seconds = time.monotonic() - started
        rendered_manifest = _manifest(
            rows=rows, parquet_path=temporary_parquet, corpus_manifest=corpus_manifest, server_metadata=server_metadata,
            endpoint=endpoint, model=model, elapsed_seconds=elapsed_seconds, vectors=vectors,
        )
        temporary_manifest.write_bytes(json.dumps(rendered_manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n")
        os.replace(temporary_parquet, parquet_path)
        os.replace(temporary_manifest, manifest_path)
        errors = validate_bundle(parquet_path, manifest_path, expected_count=expected_count)
        if errors:
            # Validation after publication should never leave an invalid new canonical artifact.
            parquet_path.unlink(missing_ok=True)
            manifest_path.unlink(missing_ok=True)
            raise ValueError("published bundle failed validation: " + "; ".join(errors))
        return rendered_manifest
    finally:
        temporary_parquet.unlink(missing_ok=True)
        temporary_manifest.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--model", default=REQUEST_MODEL)
    parser.add_argument("--output-dir", type=Path, default=OUTPUT_DIR)
    parser.add_argument("--validate-only", action="store_true", help="validate an existing bundle without HTTP")
    args = parser.parse_args()
    try:
        if args.validate_only:
            errors = validate_bundle(args.output_dir / PARQUET_NAME, args.output_dir / MANIFEST_NAME)
            if errors:
                for error in errors:
                    print(f"ERROR: {error}", file=sys.stderr)
                return 1
            print("Stage 10 canonical embedding bundle validation passed.")
            return 0
        manifest = run_embedding_job(
            output_dir=args.output_dir, endpoint=args.endpoint, timeout_seconds=args.timeout_seconds, model=args.model
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    print(f"Published {args.output_dir / PARQUET_NAME} ({manifest['output']['rows']} rows).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
