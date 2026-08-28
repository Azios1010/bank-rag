import json
import argparse
import re
import hashlib
from pathlib import Path

MANIFEST_PATH = Path("dataset/raw/policies/v2/manifest.json")

def validate(output_dir: Path):
    sources_path = output_dir / "policy-sources.json"
    prov_path = output_dir / "policy-provisions.jsonl"
    ledger_path = output_dir / "removal-ledger.jsonl"
    
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        manifest = json.load(f)
    manifest_sources = {r["source_id"] for r in manifest["records"]}
    
    with open(sources_path, "r", encoding="utf-8") as f:
        sources = json.load(f)
    assert len(sources) == 7, f"Expected 7 sources, found {len(sources)}"
    
    version_ids = [s["version_id"] for s in sources]
    assert len(set(version_ids)) == 7, "Duplicate version IDs"
    
    for s in sources:
        assert s["source_id"] in manifest_sources, f"Source {s['source_id']} not in manifest"
    
    source_02_articles = set()
    source_03_lengths = []
    
    cong_bao_re = re.compile(r'CÔNG BÁO/Số .*?/Ngày \d{1,2}-\d{1,2}-\d{4}')
    
    with open(prov_path, "r", encoding="utf-8") as f:
        for line in f:
            p = json.loads(line)
            
            assert p["source_id"] in manifest_sources, f"Provision source {p['source_id']} not in manifest"
            
            content = p["content"]
            assert hashlib.sha256(content.encode('utf-8')).hexdigest() == p["content_hash"], "Content hash mismatch"
            assert p["page_end"] >= p["page_start"], "Invalid page range"
            
            assert not cong_bao_re.search(content), f"Residual noise found in {p['source_id']} article {p.get('article')}"
            
            if p["source_id"] == "v2-02-100-vbhn-vpqh" and p["article"]:
                source_02_articles.add(str(p["article"]))
            if p["source_id"] == "v2-03-27-vbhn-nhnn":
                source_03_lengths.append(len(p["content"]))
                
    with open(ledger_path, "r", encoding="utf-8") as f:
        for line in f:
            l = json.loads(line)
            assert l["source"] in manifest_sources, f"Ledger source {l['source']} not in manifest"
                
    for i in range(1, 211):
        assert str(i) in source_02_articles, f"Source 02 missing Article {i}"
        
    for length in source_03_lengths:
        assert length > 1, "Source 03 has 1-character provision"
        
    print("Validation passed.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dir", type=str, required=True)
    args = parser.parse_args()
    validate(Path(args.dir))
