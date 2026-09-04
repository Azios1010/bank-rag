"""Build deterministic Stage 9 synthetic provisions, chunks, QC, and report."""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.services.policy_chunking_v2 import CHUNKER_VERSION, PolicyChunkerV2
from app.services.synthetic_policy_normalization_v2 import normalize_synthetic_manifest, write_jsonl


def main() -> int:
    manifest = ROOT / "dataset/synthetic/policies/v1/manifest.json"
    provisions_path = ROOT / "dataset/normalized/v2/policy-synthetic-provisions.jsonl"
    chunks_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunks.jsonl"
    qc_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunking-qc.jsonl"
    report_path = ROOT / "dataset/chunks/v2/policy-synthetic-chunking-report.json"
    provisions = normalize_synthetic_manifest(manifest)
    write_jsonl(provisions_path, provisions)
    chunker = PolicyChunkerV2()
    chunker.process_dataset(provisions)
    write_jsonl(chunks_path, chunker.chunks)
    write_jsonl(qc_path, chunker.anomalies)
    by_type = Counter(item["anomaly_type"] for item in chunker.anomalies)
    report = {
        "chunker_version": CHUNKER_VERSION,
        "total_input_provisions": len(provisions),
        "total_emitted_chunks": len(chunker.chunks),
        "total_anomalies": len(chunker.anomalies),
        "anomalies_by_type": dict(sorted(by_type.items())),
        "context_mode": "metadata_only",
        "hard_limit": 4800,
        "max_emitted_characters": max((len(item["content"]) for item in chunker.chunks), default=0),
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"Built {len(provisions)} provisions and {len(chunker.chunks)} chunks.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
