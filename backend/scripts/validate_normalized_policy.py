"""Validate normalized policy metadata and chunks without external JSON-Schema deps."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = REPO_ROOT / "dataset" / "raw" / "policies"
NORMALIZED_DIR = REPO_ROOT / "dataset" / "normalized"
IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
HASH = re.compile(r"^sha256:[a-f0-9]{64}$")


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> None:
    sources = json.loads(
        (NORMALIZED_DIR / "policy-sources.json").read_text(encoding="utf-8")
    )
    chunks = _read_jsonl(NORMALIZED_DIR / "policy-chunks.jsonl")
    provenance = json.loads(
        (RAW_DIR / "provenance.json").read_text(encoding="utf-8")
    )
    provenance_by_id = {
        document["document_id"]: document for document in provenance["documents"]
    }

    errors: list[str] = []
    source_ids = [source.get("source_id") for source in sources]
    if len(source_ids) != len(set(source_ids)):
        errors.append("duplicate source_id")

    source_versions: dict[str, str] = {}
    for source in sources:
        source_id = source.get("source_id")
        if not isinstance(source_id, str) or not IDENTIFIER.fullmatch(source_id):
            errors.append(f"invalid source_id: {source_id}")
            continue
        versions = source.get("versions", [])
        if len(versions) != 1:
            errors.append(f"{source_id}: expected exactly one version")
            continue
        version = versions[0]
        version_id = version.get("version_id")
        source_versions[source_id] = version_id
        if not isinstance(version_id, str) or not IDENTIFIER.fullmatch(version_id):
            errors.append(f"{source_id}: invalid version_id")
        if version.get("status") != "IN_REVIEW":
            errors.append(f"{source_id}: source must remain IN_REVIEW")
        if version.get("review", {}).get("status") != "UNREVIEWED":
            errors.append(f"{source_id}: review status must be UNREVIEWED")
        if not HASH.fullmatch(version.get("content_hash", "")):
            errors.append(f"{source_id}: invalid content_hash")
        object_path = version.get("object_path", "")
        path = REPO_ROOT / "dataset" / object_path
        if not path.exists():
            errors.append(f"{source_id}: missing object {object_path}")
        provenance_document = provenance_by_id.get(source_id)
        if provenance_document is None:
            errors.append(f"{source_id}: missing provenance record")
        elif version["content_hash"] != f"sha256:{provenance_document['sha256']}":
            errors.append(f"{source_id}: hash differs from provenance")

    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chunk in chunks:
        chunk_id = chunk.get("chunk_id")
        source_id = chunk.get("source_id")
        if not isinstance(chunk_id, str) or not IDENTIFIER.fullmatch(chunk_id):
            errors.append(f"invalid chunk_id: {chunk_id}")
        if source_id not in source_versions:
            errors.append(f"{chunk_id}: unknown source_id {source_id}")
            continue
        if chunk.get("version_id") != source_versions[source_id]:
            errors.append(f"{chunk_id}: wrong version_id")
        content = chunk.get("content", "")
        if not isinstance(content, str) or not 20 <= len(content) <= 12000:
            errors.append(f"{chunk_id}: invalid content length")
        expected_hash = f"sha256:{hashlib.sha256(content.encode('utf-8')).hexdigest()}"
        if chunk.get("content_hash") != expected_hash:
            errors.append(f"{chunk_id}: content hash mismatch")
        locator = chunk.get("locator", {})
        if locator.get("page_start", 0) > locator.get("page_end", 0):
            errors.append(f"{chunk_id}: invalid page range")
        if re.search(r"(?m)^\s*\d+\.\d+\s+", content):
            errors.append(f"{chunk_id}: unresolved footnote/clause artifact")
        by_source[source_id].append(chunk)

    for source_id, source_chunks in by_source.items():
        indexes = sorted(chunk["chunk_index"] for chunk in source_chunks)
        if indexes != list(range(len(indexes))):
            errors.append(f"{source_id}: chunk_index is not contiguous")

    print(
        json.dumps(
            {
                "sources": len(sources),
                "chunks": len(chunks),
                "errors": len(errors),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    if errors:
        print("\n".join(errors[:50]))
        raise SystemExit(1)


if __name__ == "__main__":
    main()
