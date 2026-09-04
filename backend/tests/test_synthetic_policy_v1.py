from __future__ import annotations

import json
from pathlib import Path
from shutil import copytree

from app.services.synthetic_policy_v1 import (
    source_content_hash,
    validate_synthetic_policy_set,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST = REPO_ROOT / "dataset/synthetic/policies/v1/manifest.json"


def copied_manifest(tmp_path: Path) -> Path:
    copytree(REPO_ROOT / "dataset/synthetic", tmp_path / "dataset/synthetic")
    return tmp_path / "dataset/synthetic/policies/v1/manifest.json"


def source_document(manifest_path: Path, source_id: str) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    record = next(item for item in manifest["records"] if item["source_id"] == source_id)
    return manifest_path.parents[4] / record["path"]


def test_stage_8_synthetic_policy_set_is_valid() -> None:
    assert validate_synthetic_policy_set(MANIFEST) == []


def test_source_hash_uses_frozen_normalization_rule() -> None:
    assert source_content_hash("\ufeffA\r\nB\rC") == source_content_hash("A\nB\nC")


def test_manifest_hashes_match_complete_documents() -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for record in manifest["records"]:
        document = REPO_ROOT / record["path"]
        assert record["content_hash"] == source_content_hash(document.read_text(encoding="utf-8"))


def test_rejects_non_synthetic_manifest_record(tmp_path: Path) -> None:
    manifest_path = copied_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["records"][0]["synthetic"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert "synthetic-sme-working-capital-v1: synthetic must be true" in validate_synthetic_policy_set(manifest_path)


def test_rejects_regulation_namespace(tmp_path: Path) -> None:
    manifest_path = copied_manifest(tmp_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["records"][0]["namespace"] = "REGULATION"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    assert "synthetic-sme-working-capital-v1: invalid namespace" in validate_synthetic_policy_set(manifest_path)


def test_rejects_unresolved_cross_document_reference(tmp_path: Path) -> None:
    manifest_path = copied_manifest(tmp_path)
    document = source_document(manifest_path, "synthetic-sme-working-capital-v1")
    document.write_text(
        document.read_text(encoding="utf-8").replace("[[UW-IDENTITY-AND-INDUSTRY]]", "[[UW-NOT-DECLARED]]"),
        encoding="utf-8",
    )

    assert "synthetic-sme-working-capital-v1: unresolved cross-document reference UW-NOT-DECLARED" in validate_synthetic_policy_set(manifest_path)


def test_rejects_invalid_two_exception_authority_language(tmp_path: Path) -> None:
    manifest_path = copied_manifest(tmp_path)
    document = source_document(manifest_path, "synthetic-credit-approval-v1")
    document.write_text(
        document.read_text(encoding="utf-8").replace(
            "More than two soft exceptions are not permitted.",
            "More than three soft exceptions are not permitted.",
        ),
        encoding="utf-8",
    )

    assert "exception logic is not mapped to underwriting and approval authorities" in validate_synthetic_policy_set(manifest_path)


def test_rejects_boundary_gap_language(tmp_path: Path) -> None:
    manifest_path = copied_manifest(tmp_path)
    document = source_document(manifest_path, "synthetic-sme-underwriting-v1")
    document.write_text(
        document.read_text(encoding="utf-8").replace(
            "DSCR >= 1.15 and < 1.30", "DSCR 1.15 through 1.29", 1
        ),
        encoding="utf-8",
    )

    errors = validate_synthetic_policy_set(manifest_path)
    assert "synthetic-sme-underwriting-v1: boundary-gap language is not permitted: 1.15 through 1.29" in errors
