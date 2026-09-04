"""Build the immutable Stage 10A Policy Corpus V2 freeze artifacts.

This script never regenerates either input corpus.  It only concatenates their
already-canonical JSONL bytes in the frozen order and records their exact-byte
hashes in a deterministic manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CORPUS_VERSION = "policy-corpus-v2-freeze-1"
PARSER_VERSION = "bank-rag-v2-pymupdf-structure-1.0.0"
CHUNKER_VERSION = "bank-rag-v2-chunker-2.0.0"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _artifact(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": _sha256(data),
        "byte_size": len(data),
    }


def _json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _jsonl(path: Path) -> tuple[list[dict[str, Any]], list[bytes]]:
    """Return JSON records and their complete original JSONL line bytes."""
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        raise ValueError(f"JSONL artifact must not contain a UTF-8 BOM: {path}")
    if not raw:
        return [], []
    lines = raw.splitlines(keepends=True)
    if any(not line.endswith(b"\n") for line in lines):
        raise ValueError(f"JSONL artifact must contain newline-terminated records: {path}")
    if any(not line.strip() for line in lines):
        raise ValueError(f"JSONL artifact must not contain blank records: {path}")
    return [json.loads(line) for line in lines], lines


def _canonical_json(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _corpus_identity(lines: list[bytes], chunks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "corpus_version": CORPUS_VERSION,
        "identity_version": 1,
        "record_count": len(chunks),
        "records": [
            {
                "canonical_chunk_id": chunk["canonical_chunk_id"],
                "content_sha256": _sha256(chunk["content"].encode("utf-8")),
                "jsonl_line_sha256": _sha256(line),
            }
            for line, chunk in zip(lines, chunks, strict=True)
        ],
    }


def _source_count_map(chunks: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(chunk["source_id"] for chunk in chunks).items()))


def build_manifest(combined_path: Path) -> dict[str, Any]:
    real_sources_path = ROOT / "dataset/normalized/v2/policy-sources.json"
    real_provisions_path = ROOT / "dataset/normalized/v2/policy-provisions.jsonl"
    real_chunks_path = ROOT / "dataset/chunks/v2/policy-legal-chunks.jsonl"
    real_qc_path = ROOT / "dataset/chunks/v2/policy-chunking-qc.jsonl"
    real_report_path = ROOT / "dataset/chunks/v2/policy-chunking-report.json"
    real_normalization_report_path = ROOT / "dataset/normalized/v2/normalization-report.json"
    real_documents_manifest_path = ROOT / "dataset/raw/policies/v2/manifest.json"
    synthetic_manifest_path = ROOT / "dataset/synthetic/policies/v1/manifest.json"
    synthetic_provisions_path = ROOT / "dataset/normalized/v2/policy-synthetic-provisions.jsonl"
    synthetic_chunks_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunks.jsonl"
    synthetic_qc_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunking-qc.jsonl"
    synthetic_report_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunking-report.json"

    real_chunks, real_lines = _jsonl(real_chunks_path)
    synthetic_chunks, synthetic_lines = _jsonl(synthetic_chunks_path)
    combined_chunks, combined_lines = _jsonl(combined_path)
    expected_lines = real_lines + synthetic_lines
    if combined_lines != expected_lines:
        raise ValueError("combined JSONL is not the exact real-then-synthetic byte concatenation")
    if combined_chunks != real_chunks + synthetic_chunks:
        raise ValueError("combined JSONL records differ from its canonical inputs")
    ids = [chunk["canonical_chunk_id"] for chunk in combined_chunks]
    if len(ids) != len(set(ids)):
        raise ValueError("combined JSONL has duplicate canonical_chunk_id values")
    real_content = [chunk["content"] for chunk in real_chunks]
    synthetic_content = [chunk["content"] for chunk in synthetic_chunks]
    if len(synthetic_content) != len(set(synthetic_content)):
        raise ValueError("synthetic canonical chunks have duplicate content values")
    if set(real_content) & set(synthetic_content):
        raise ValueError("synthetic chunk content overlaps frozen real content")

    real_sources = _json(real_sources_path)
    real_documents_manifest = _json(real_documents_manifest_path)
    synthetic_manifest = _json(synthetic_manifest_path)
    if len(real_sources) != 7 or len(real_documents_manifest["records"]) != 7:
        raise ValueError("frozen real source set must contain seven records")
    if len(synthetic_manifest["records"]) != 3:
        raise ValueError("synthetic source set must contain three records")
    if len(real_chunks) != 1573 or len(synthetic_chunks) != 37:
        raise ValueError("Stage 10A requires 1,573 real and 37 synthetic chunks")

    real_document_records = []
    for record in real_documents_manifest["records"]:
        document = ROOT / record["file_path"]
        artifact = _artifact(document)
        if artifact["sha256"] != record["sha256"] or artifact["byte_size"] != record["byte_size"]:
            raise ValueError(f"frozen real document hash mismatch: {record['source_id']}")
        real_document_records.append({"source_id": record["source_id"], **artifact})
    synthetic_document_records = []
    for record in synthetic_manifest["records"]:
        document = ROOT / record["path"]
        synthetic_document_records.append({"source_id": record["source_id"], **_artifact(document)})

    synthetic_mapping = [
        {
            "source_id": record["source_id"],
            "version_id": record["version_id"],
            "namespace": record["namespace"],
            "synthetic": record["synthetic"],
            "agent_scopes": record["agent_scopes"],
            "chunk_count": _source_count_map(synthetic_chunks)[record["source_id"]],
        }
        for record in synthetic_manifest["records"]
    ]
    namespace_counts = {"REGULATION": len(real_chunks)}
    for record in synthetic_mapping:
        namespace_counts[record["namespace"]] = namespace_counts.get(record["namespace"], 0) + record["chunk_count"]
    agent_scope_counts: Counter[str] = Counter({"UNSCOPED_REGULATION": len(real_chunks)})
    for record in synthetic_mapping:
        for scope in record["agent_scopes"]:
            agent_scope_counts[scope] += record["chunk_count"]

    real_report = _json(real_report_path)
    synthetic_report = _json(synthetic_report_path)
    real_qc = _jsonl(real_qc_path)[0]
    synthetic_qc = _jsonl(synthetic_qc_path)[0]
    duplicate_classifications = {
        "real": {
            "REPEATED_HIERARCHY_LABEL": sum(item["anomaly_type"] == "REPEATED_HIERARCHY_LABEL" for item in real_qc),
            "DIRECT_ARTICLE_POINT": sum(item["anomaly_type"] == "DIRECT_ARTICLE_POINT" for item in real_qc),
            "EXACT_DUPLICATE_LEGAL_TEXT": sum(item["anomaly_type"] == "EXACT_DUPLICATE_LEGAL_TEXT" for item in real_qc),
        },
        "synthetic": {
            "REPEATED_HIERARCHY_LABEL": sum(item["anomaly_type"] == "REPEATED_HIERARCHY_LABEL" for item in synthetic_qc),
            "DIRECT_ARTICLE_POINT": sum(item["anomaly_type"] == "DIRECT_ARTICLE_POINT" for item in synthetic_qc),
            "EXACT_DUPLICATE_LEGAL_TEXT": sum(item["anomaly_type"] == "EXACT_DUPLICATE_LEGAL_TEXT" for item in synthetic_qc),
        },
    }
    if duplicate_classifications["real"] != real_report["anomalies_by_type"]:
        raise ValueError("frozen real duplicate classifications disagree with report")
    if synthetic_report["total_anomalies"] != sum(duplicate_classifications["synthetic"].values()):
        raise ValueError("synthetic duplicate classifications disagree with report")
    actual_duplicate_groups = {
        frozenset(chunk["canonical_chunk_id"] for chunk in group)
        for group in (
            [candidate for candidate in real_chunks if candidate["content"] == content]
            for content, count in Counter(real_content).items()
            if count > 1
        )
    }
    classified_duplicate_groups = {
        frozenset(item["canonical_chunk_ids"])
        for item in real_qc
        if item["anomaly_type"] == "EXACT_DUPLICATE_LEGAL_TEXT"
    }
    if actual_duplicate_groups != classified_duplicate_groups:
        raise ValueError("frozen real duplicate content groups are not exactly classified")

    artifacts = {
        "real": {
            "source_manifest": _artifact(real_documents_manifest_path),
            "sources": _artifact(real_sources_path),
            "documents": real_document_records,
            "provisions": _artifact(real_provisions_path),
            "chunks": _artifact(real_chunks_path),
            "qc": _artifact(real_qc_path),
            "report": _artifact(real_report_path),
            "normalization_report": _artifact(real_normalization_report_path),
        },
        "synthetic": {
            "source_manifest": _artifact(synthetic_manifest_path),
            "documents": synthetic_document_records,
            "provisions": _artifact(synthetic_provisions_path),
            "chunks": _artifact(synthetic_chunks_path),
            "qc": _artifact(synthetic_qc_path),
            "report": _artifact(synthetic_report_path),
        },
        "combined_chunks": _artifact(combined_path),
    }
    manifest = {
        "manifest_version": CORPUS_VERSION,
        "parser_version": PARSER_VERSION,
        "chunker_version": CHUNKER_VERSION,
        "chunk_schema": "dataset/schemas/policy-legal-chunk-v2.schema.json",
        "chunk_schema_is_closed": True,
        "corpus_v2_hash": _sha256(_canonical_json(_corpus_identity(combined_lines, combined_chunks))),
        "corpus_v2_identity": {
            "serialization": "UTF-8 JSON with ensure_ascii=false, sort_keys=true, separators=(',', ':')",
            "definition": "SHA-256 of corpus_version, identity_version, record_count, and ordered canonical_chunk_id/content_sha256/jsonl_line_sha256 records; jsonl_line_sha256 hashes each complete original line including its terminator.",
        },
        "artifacts": artifacts,
        "source_counts": {"real": len(real_sources), "synthetic": len(synthetic_manifest["records"]), "total": len(real_sources) + len(synthetic_manifest["records"])},
        "chunk_counts": {
            "real": len(real_chunks),
            "synthetic": len(synthetic_chunks),
            "total": len(combined_chunks),
            "by_source": _source_count_map(combined_chunks),
            "by_namespace": dict(sorted(namespace_counts.items())),
            "by_agent_scope": dict(sorted(agent_scope_counts.items())),
            "agent_scope_count_semantics": "UNSCOPED_REGULATION counts real chunks once; synthetic chunks are counted once for each declared source scope, so named scope counts overlap.",
        },
        "synthetic_source_metadata_mapping": synthetic_mapping,
        "duplicate_classifications": duplicate_classifications,
        "total_disk_size_bytes": len(combined_path.read_bytes()),
        "total_disk_size_definition": "Byte size of the immutable combined Corpus V2 JSONL artifact; the separately hashed manifest is not included.",
        "frozen_real_artifact_hashes": {
            "source_manifest": artifacts["real"]["source_manifest"]["sha256"],
            "sources": artifacts["real"]["sources"]["sha256"],
            "provisions": artifacts["real"]["provisions"]["sha256"],
            "chunks": artifacts["real"]["chunks"]["sha256"],
            "qc": artifacts["real"]["qc"]["sha256"],
            "report": artifacts["real"]["report"]["sha256"],
            "normalization_report": artifacts["real"]["normalization_report"]["sha256"],
        },
        "immutability_boundary": "The real Stage-7 artifacts are inputs only. Corpus V2 adds this combined JSONL and manifest without regenerating, rewriting, or embedding any real or synthetic input.",
    }
    manifest["manifest_hash"] = _sha256(_canonical_json(manifest))
    manifest["manifest_hash_definition"] = "SHA-256 of the UTF-8 deterministic JSON manifest identity with manifest_hash and manifest_hash_definition omitted, preventing self-reference."
    return manifest


def _write_if_identical_or_missing(path: Path, data: bytes) -> None:
    if path.exists() and path.read_bytes() != data:
        raise ValueError(f"refusing to overwrite different frozen output: {path}")
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)


def build(combined_path: Path, manifest_path: Path) -> dict[str, Any]:
    real_path = ROOT / "dataset/chunks/v2/policy-legal-chunks.jsonl"
    synthetic_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunks.jsonl"
    if combined_path.resolve() in {real_path.resolve(), synthetic_path.resolve()}:
        raise ValueError("combined output must not overwrite a canonical input")
    _write_if_identical_or_missing(combined_path, real_path.read_bytes() + synthetic_path.read_bytes())
    manifest = build_manifest(combined_path)
    rendered = (json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    _write_if_identical_or_missing(manifest_path, rendered)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined", type=Path, default=ROOT / "dataset/chunks/v2/policy-corpus-v2.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "dataset/manifests/policy-corpus-v2-manifest.json")
    args = parser.parse_args()
    manifest = build(args.combined, args.manifest)
    print(f"Built {args.combined.relative_to(ROOT)} ({manifest['chunk_counts']['total']} chunks).")
    print(f"Corpus V2 hash: {manifest['corpus_v2_hash']}")
    print(f"Manifest hash: {manifest['manifest_hash']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
