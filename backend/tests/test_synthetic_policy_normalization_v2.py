import json
from pathlib import Path

from app.services.synthetic_policy_normalization_v2 import normalize_synthetic_manifest


ROOT = Path(__file__).resolve().parents[2]
MANIFEST = ROOT / "dataset/synthetic/policies/v1/manifest.json"


def test_adapter_emits_complete_rule_sections_in_manifest_order():
    provisions = normalize_synthetic_manifest(MANIFEST)
    assert len(provisions) == 37
    assert provisions[0]["article"] == "PROD-STATUS"
    assert provisions[-1]["article"] == "APR-REAPPROVAL"
    assert all(item["page_start"] == item["page_end"] == 0 for item in provisions)
    assert all(item["inventory_type"] == "SELECTED" for item in provisions)
    assert all("thresholds" in item["selection_reason"] for item in provisions)


def test_adapter_is_deterministic_and_closed_schema_fields_only():
    first = normalize_synthetic_manifest(MANIFEST)
    second = normalize_synthetic_manifest(MANIFEST)
    assert first == second
    schema = json.loads((ROOT / "dataset/schemas/policy-normalized-provision-v2.schema.json").read_text(encoding="utf-8"))
    assert all(set(item) == set(schema["properties"]) for item in first)
