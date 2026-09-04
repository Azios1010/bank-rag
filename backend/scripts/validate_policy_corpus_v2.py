"""Validate the deterministic Stage 10A Policy Corpus V2 freeze."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from jsonschema import validate

try:  # Package import for tests.
    from scripts.build_policy_corpus_v2 import ROOT, build_manifest, _jsonl
except ModuleNotFoundError:  # Direct execution from backend/scripts.
    from build_policy_corpus_v2 import ROOT, build_manifest, _jsonl


def validate_corpus_v2(combined_path: Path, manifest_path: Path) -> list[str]:
    errors: list[str] = []
    if not combined_path.is_file() or not manifest_path.is_file():
        return ["missing Corpus V2 combined artifact or manifest"]
    try:
        actual = json.loads(manifest_path.read_text(encoding="utf-8"))
        expected = build_manifest(combined_path)
    except Exception as exc:
        return [str(exc)]
    if actual != expected:
        errors.append("manifest differs from deterministic Corpus V2 construction")
    try:
        schema = json.loads((ROOT / "dataset/schemas/policy-legal-chunk-v2.schema.json").read_text(encoding="utf-8"))
        chunks, _ = _jsonl(combined_path)
        ids: set[str] = set()
        real_count = 1573
        synthetic_contents: set[str] = set()
        real_contents: set[str] = set()
        for index, chunk in enumerate(chunks, 1):
            validate(chunk, schema)
            if chunk["canonical_chunk_id"] in ids:
                errors.append(f"duplicate canonical_chunk_id at combined record {index}")
            ids.add(chunk["canonical_chunk_id"])
            if index <= real_count:
                real_contents.add(chunk["content"])
            else:
                if chunk["content"] in synthetic_contents:
                    errors.append(f"duplicate synthetic content at combined record {index}")
                if chunk["content"] in real_contents:
                    errors.append(f"synthetic content overlaps real content at combined record {index}")
                synthetic_contents.add(chunk["content"])
    except Exception as exc:
        errors.append(f"combined chunk schema validation failed: {exc}")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--combined", type=Path, default=ROOT / "dataset/chunks/v2/policy-corpus-v2.jsonl")
    parser.add_argument("--manifest", type=Path, default=ROOT / "dataset/manifests/policy-corpus-v2-manifest.json")
    args = parser.parse_args()
    errors = validate_corpus_v2(args.combined, args.manifest)
    for error in errors:
        print(f"ERROR: {error}")
    if errors:
        return 1
    print("Stage 10A Corpus V2 manifest validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
