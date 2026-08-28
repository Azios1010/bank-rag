import json
import argparse
from pathlib import Path
from backend.app.services.policy_normalization_v2 import PolicyNormalizerV2
import hashlib

MANIFEST_PATH = Path("dataset/raw/policies/v2/manifest.json")
AUDIT_PATH = Path("dataset/source-audit-v2.json")

def validate_inputs():
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    with open(AUDIT_PATH, "r", encoding="utf-8") as f:
        audit = json.load(f)
        
    assert len(manifest["records"]) == 7, "Manifest must have exactly 7 records"
    assert len(audit["records"]) == 7, "Audit must have exactly 7 records"
    
    total_bytes = 0
    for r in manifest["records"]:
        total_bytes += r["byte_size"]
        pdf_path = Path(r["file_path"])
        assert pdf_path.exists(), f"Path mismatch: {pdf_path}"
        data = pdf_path.read_bytes()
        assert len(data) == r["byte_size"], f"Size mismatch for {r['source_id']}"
        assert hashlib.sha256(data).hexdigest() == r["sha256"], f"SHA-256 mismatch for {r['source_id']}"
        
    assert total_bytes < 1024 * 1024 * 1024, "Total workflow exceeds 1GB"
    return manifest

def run_pipeline(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    
    manifest = validate_inputs()
        
    normalizer = PolicyNormalizerV2()
    
    all_sources = []
    all_provisions = []
    all_ledger = []
    
    for r in manifest["records"]:
        src_id = r["source_id"]
        issue_date = r.get("issue_date", "")
        sha_hex = r["sha256"][:12].lower()
        version_id = f"{src_id}-{issue_date}-{sha_hex}"
        
        all_sources.append({
            "source_id": src_id,
            "version_id": version_id,
            "document_number": r["document_number"],
            "title": r["title"],
            "issuer": r["issuer"],
            "issue_date": issue_date,
            "effective_date": r.get("effective_date"),
            "status": r["status"]
        })
        
        pdf_path = r["file_path"]
        source_meta = {"source_id": src_id, "version_id": version_id}
        provisions, ledger = normalizer.process_file(pdf_path, source_meta)
        
        all_provisions.extend(provisions)
        all_ledger.extend(ledger)
        
    sources_path = output_dir / "policy-sources.json"
    with open(sources_path, "w", encoding="utf-8", newline='\n') as f:
        json.dump(all_sources, f, ensure_ascii=False, indent=2)
        f.write('\n')
        
    prov_path = output_dir / "policy-provisions.jsonl"
    with open(prov_path, "w", encoding="utf-8", newline='\n') as f:
        for p in all_provisions:
            f.write(json.dumps(p, ensure_ascii=False, separators=(',', ':')) + '\n')
            
    ledger_path = output_dir / "removal-ledger.jsonl"
    with open(ledger_path, "w", encoding="utf-8", newline='\n') as f:
        for l in all_ledger:
            f.write(json.dumps(l, ensure_ascii=False, separators=(',', ':')) + '\n')
            
    report_path = output_dir / "normalization-report.json"
    report = {
        "parser_version": normalizer.parser_version,
        "total_sources": len(all_sources),
        "total_provisions": len(all_provisions),
        "total_noise_blocks_removed": len(all_ledger)
    }
    with open(report_path, "w", encoding="utf-8", newline='\n') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
        f.write('\n')

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=str, required=True)
    args = parser.parse_args()
    
    run_pipeline(Path(args.output_dir))
