from pathlib import Path

from scripts.validate_policy_corpus_v2 import validate_corpus_v2


ROOT = Path(__file__).resolve().parents[2]


def test_stage10_corpus_v2_freeze_validates():
    assert validate_corpus_v2(
        ROOT / "dataset/chunks/v2/policy-corpus-v2.jsonl",
        ROOT / "dataset/manifests/policy-corpus-v2-manifest.json",
    ) == []
