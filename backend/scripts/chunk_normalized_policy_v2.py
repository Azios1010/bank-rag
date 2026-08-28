import json
import os
import sys
from pathlib import Path

# Add backend to sys.path to import app.services
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))

from app.services.policy_chunking_v2 import PolicyChunkerV2, CHUNKER_VERSION

def main():
    root_dir = backend_dir.parent
    input_path = root_dir / "dataset" / "normalized" / "v2" / "policy-provisions.jsonl"
    out_dir = root_dir / "dataset" / "chunks" / "v2"
    out_dir.mkdir(parents=True, exist_ok=True)
    
    chunks_path = out_dir / "policy-legal-chunks.jsonl"
    report_path = out_dir / "policy-chunking-report.json"
    qc_path = out_dir / "policy-chunking-qc.jsonl"

    print(f"Reading {input_path}...")
    provisions = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                provisions.append(json.loads(line))
    
    print(f"Loaded {len(provisions)} provisions.")
    
    chunker = PolicyChunkerV2()
    chunker.process_dataset(provisions)
    
    # Save chunks
    print(f"Writing {len(chunker.chunks)} chunks to {chunks_path}...")
    with open(chunks_path, "w", encoding="utf-8") as f:
        for c in chunker.chunks:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            
    # Save anomalies
    print(f"Writing {len(chunker.anomalies)} anomalies to {qc_path}...")
    with open(qc_path, "w", encoding="utf-8") as f:
        for a in chunker.anomalies:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
            
    # Save report
    anomalies_by_type = {}
    for a in chunker.anomalies:
        atype = a["anomaly_type"]
        anomalies_by_type[atype] = anomalies_by_type.get(atype, 0) + 1
        
    report = {
        "chunker_version": CHUNKER_VERSION,
        "total_input_provisions": len(provisions),
        "total_emitted_chunks": len(chunker.chunks),
        "total_anomalies": len(chunker.anomalies),
        "anomalies_by_type": anomalies_by_type
    }
    
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        
    print("Done!")

if __name__ == "__main__":
    main()
