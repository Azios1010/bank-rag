from pathlib import Path

from scripts.validate_synthetic_policy_v2 import validate_synthetic_dataset


ROOT = Path(__file__).resolve().parents[2]


def test_stage9_synthetic_artifacts_validate():
    errors = validate_synthetic_dataset(
        ROOT / "dataset/normalized/v2/policy-synthetic-provisions.jsonl",
        ROOT / "dataset/chunks/v2/policy-synthetic-chunks.jsonl",
        ROOT / "dataset/chunks/v2/policy-synthetic-chunking-qc.jsonl",
        ROOT / "dataset/chunks/v2/policy-synthetic-chunking-report.json",
        ROOT / "dataset/synthetic/policies/v1/manifest.json",
        ROOT / "dataset/schemas",
        ROOT / "dataset/chunks/v2/policy-legal-chunks.jsonl",
    )
    assert errors == []
