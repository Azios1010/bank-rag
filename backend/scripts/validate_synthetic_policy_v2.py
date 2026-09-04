"""Strict Stage 9 validator for synthetic provisions and chunks."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

from jsonschema import validate

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.policy_chunking_v2 import CHUNKER_VERSION, PolicyChunkerV2
from app.services.policy_normalization_v2 import get_hash, normalize_text
from app.services.synthetic_policy_normalization_v2 import load_manifest, normalize_synthetic_manifest
from app.services.synthetic_policy_v1 import validate_synthetic_policy_set


def _jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        raise ValueError(f"missing artifact: {path}")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def validate_synthetic_dataset(
    provisions_path: Path,
    chunks_path: Path,
    qc_path: Path,
    report_path: Path,
    manifest_path: Path,
    schema_dir: Path,
    real_chunks_path: Path,
) -> list[str]:
    errors: list[str] = []
    errors.extend(validate_synthetic_policy_set(manifest_path))
    try:
        expected = normalize_synthetic_manifest(manifest_path)
        provisions = _jsonl(provisions_path)
        chunks = _jsonl(chunks_path)
        anomalies = _jsonl(qc_path)
        report = json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as exc:
        return errors + [str(exc)]

    provision_schema = json.loads((schema_dir / "policy-normalized-provision-v2.schema.json").read_text(encoding="utf-8"))
    chunk_schema = json.loads((schema_dir / "policy-legal-chunk-v2.schema.json").read_text(encoding="utf-8"))
    qc_schema = json.loads((schema_dir / "policy-chunking-qc-v2.schema.json").read_text(encoding="utf-8"))
    report_schema = json.loads((schema_dir / "policy-chunking-report-v2.schema.json").read_text(encoding="utf-8"))

    if provisions != expected:
        errors.append("normalized provisions differ from deterministic Markdown adapter output")
    if len({(p["source_id"], p["version_id"], p["article"]) for p in provisions}) != len(provisions):
        errors.append("duplicate provision hierarchy IDs")
    if len({p["content"] for p in provisions}) != len(provisions):
        errors.append("duplicate normalized provision content")
    manifest = load_manifest(manifest_path)
    records = {item["source_id"]: item for item in manifest["records"]}
    for index, provision in enumerate(provisions, 1):
        try:
            validate(provision, provision_schema)
        except Exception as exc:
            errors.append(f"provision {index}: {exc}")
        record = records.get(provision.get("source_id"))
        if not record or record.get("synthetic") is not True or record.get("namespace") == "REGULATION":
            errors.append(f"provision {index}: synthetic manifest mapping invalid")
        if provision.get("page_start") != 0 or provision.get("page_end") != 0:
            errors.append(f"provision {index}: Markdown pages must be 0")
        if provision.get("content_hash") != get_hash(normalize_text(provision.get("content", ""))):
            errors.append(f"provision {index}: content hash mismatch")
        if not provision.get("chapter") or not provision.get("section") or not provision.get("article"):
            errors.append(f"provision {index}: malformed hierarchy")

    chunker = PolicyChunkerV2()
    chunker.process_dataset([dict(item) for item in expected])
    if chunks != chunker.chunks:
        errors.append("chunks differ from unchanged PolicyChunkerV2 deterministic output")
    if anomalies != chunker.anomalies:
        errors.append("synthetic QC differs from unchanged PolicyChunkerV2 anomalies")
    ids: set[str] = set()
    covered: set[int] = set()
    provision_by_ordinal = {i: item for i, item in enumerate(provisions, 1)}
    for index, chunk in enumerate(chunks, 1):
        try:
            validate(chunk, chunk_schema)
        except Exception as exc:
            errors.append(f"chunk {index}: {exc}")
        cid = chunk.get("canonical_chunk_id")
        if cid in ids:
            errors.append(f"chunk {index}: duplicate canonical ID")
        ids.add(cid)
        if len(chunk.get("content", "")) == 0 or len(chunk.get("content", "")) > 4800:
            errors.append(f"chunk {index}: empty or over hard limit")
        if cid != chunker.get_deterministic_id(chunk):
            errors.append(f"chunk {index}: canonical ID mismatch")
        for provenance in chunk.get("provenance", []):
            ordinal = provenance.get("input_ordinal")
            source = provision_by_ordinal.get(ordinal)
            if not source or source.get("content_hash") != provenance.get("content_hash"):
                errors.append(f"chunk {index}: invalid provenance")
            else:
                covered.add(ordinal)
                if source["source_id"] != chunk.get("source_id") or source["version_id"] != chunk.get("version_id"):
                    errors.append(f"chunk {index}: provenance/source mapping mismatch")
    if covered != set(provision_by_ordinal):
        errors.append(f"incomplete provision coverage: missing {sorted(set(provision_by_ordinal) - covered)}")
    for anomaly in anomalies:
        try:
            validate(anomaly, qc_schema)
        except Exception as exc:
            errors.append(f"QC anomaly invalid: {exc}")
    try:
        validate(report, report_schema)
    except Exception as exc:
        errors.append(f"report invalid: {exc}")
    expected_report = {
        "chunker_version": CHUNKER_VERSION,
        "total_input_provisions": len(provisions),
        "total_emitted_chunks": len(chunks),
        "total_anomalies": len(anomalies),
        "anomalies_by_type": dict(sorted(Counter(a["anomaly_type"] for a in anomalies).items())),
        "context_mode": "metadata_only",
        "hard_limit": 4800,
        "max_emitted_characters": max((len(c["content"]) for c in chunks), default=0),
    }
    if report != expected_report:
        errors.append("report counts do not match emitted artifacts")

    if real_chunks_path.is_file():
        real = _jsonl(real_chunks_path)
        real_ids = {item.get("canonical_chunk_id") for item in real}
        real_content = {item.get("content") for item in real}
        if ids & real_ids:
            errors.append("synthetic canonical ID overlaps frozen real chunks")
        if {item.get("content") for item in chunks} & real_content:
            errors.append("synthetic chunk content overlaps frozen real content")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "dataset/synthetic/policies/v1/manifest.json")
    parser.add_argument("--provisions", type=Path, default=ROOT / "dataset/normalized/v2/policy-synthetic-provisions.jsonl")
    parser.add_argument("--chunks", type=Path, default=ROOT / "dataset/chunks/v2/policy-synthetic-chunks.jsonl")
    parser.add_argument("--qc", type=Path, default=ROOT / "dataset/chunks/v2/policy-synthetic-chunking-qc.jsonl")
    parser.add_argument("--report", type=Path, default=ROOT / "dataset/chunks/v2/policy-synthetic-chunking-report.json")
    parser.add_argument("--schema-dir", type=Path, default=ROOT / "dataset/schemas")
    parser.add_argument("--real-chunks", type=Path, default=ROOT / "dataset/chunks/v2/policy-legal-chunks.jsonl")
    args = parser.parse_args()
    errors = validate_synthetic_dataset(args.provisions, args.chunks, args.qc, args.report, args.manifest, args.schema_dir, args.real_chunks)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Synthetic Stage 9 validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
