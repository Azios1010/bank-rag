"""Build the minimal private Kaggle Dataset used by the embedding notebook."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo


REPO_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = REPO_ROOT / "dataset" / "normalized"
KAGGLE_DIR = REPO_ROOT / "kaggle"
DIST_DIR = REPO_ROOT / "dist"
OUTPUT_PATH = DIST_DIR / "bank-rag-kaggle-private-dataset.zip"

INPUT_FILES = {
    NORMALIZED_DIR / "policy-chunks.jsonl": "policy-chunks.jsonl",
    NORMALIZED_DIR / "policy-sources.jsonl": "policy-sources.jsonl",
    NORMALIZED_DIR / "normalization-report.json": "normalization-report.json",
    KAGGLE_DIR / "embedding-job.json": "embedding-job.json",
}


def _sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _zip_info(filename: str) -> ZipInfo:
    info = ZipInfo(filename=filename, date_time=(2026, 1, 1, 0, 0, 0))
    info.compress_type = ZIP_DEFLATED
    info.external_attr = 0o644 << 16
    return info


def build_bundle() -> dict[str, object]:
    missing = [str(path) for path in INPUT_FILES if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"Missing bundle inputs: {missing}")

    entries: list[dict[str, object]] = []
    payloads: dict[str, bytes] = {}
    for source_path, archive_name in INPUT_FILES.items():
        content = source_path.read_bytes()
        payloads[archive_name] = content
        entries.append(
            {
                "path": archive_name,
                "bytes": len(content),
                "sha256": _sha256(content),
            }
        )

    bundle_manifest = {
        "bundle_version": "1.0.0",
        "visibility": "PRIVATE",
        "purpose": "offline-policy-embedding",
        "entries": entries,
    }
    payloads["bundle-manifest.json"] = (
        json.dumps(bundle_manifest, ensure_ascii=False, indent=2) + "\n"
    ).encode("utf-8")

    DIST_DIR.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT_PATH, mode="w") as archive:
        for archive_name in sorted(payloads):
            archive.writestr(_zip_info(archive_name), payloads[archive_name])

    result = {
        "output": str(OUTPUT_PATH.relative_to(REPO_ROOT)),
        "bytes": OUTPUT_PATH.stat().st_size,
        "sha256": _sha256(OUTPUT_PATH.read_bytes()),
        "entries": sorted(payloads),
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return result


if __name__ == "__main__":
    build_bundle()
