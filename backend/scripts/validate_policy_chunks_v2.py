import json
import sys
from pathlib import Path
from collections import defaultdict
from jsonschema import validate, ValidationError

# Add backend to sys.path to import app.services
backend_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_dir))
from app.services.policy_chunking_v2 import PolicyChunkerV2

def validate_dataset(chunks_dir, norm_path, schema_dir):
    chunk_schema = json.loads((schema_dir / "policy-legal-chunk-v2.schema.json").read_text(encoding="utf-8"))
    report_schema = json.loads((schema_dir / "policy-chunking-report-v2.schema.json").read_text(encoding="utf-8"))
    qc_schema = json.loads((schema_dir / "policy-chunking-qc-v2.schema.json").read_text(encoding="utf-8"))

    errors = 0

    print("Loading normalized provisions...")
    provisions = []
    with open(norm_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                provisions.append(json.loads(line))
                
    # Build lineage maps
    article_lineages = defaultdict(list)
    clause_lineages = defaultdict(list)
    point_lineages = defaultdict(list)
    for i, p in enumerate(provisions):
        src, ver, chap, sec, art, cl, pt = p.get('source_id'), p.get('version_id'), p.get('chapter'), p.get('section'), p.get('article'), p.get('clause'), p.get('point')
        akey = (src, ver, chap, sec, art)
        article_lineages[akey].append(i + 1)
        if cl is not None or pt is not None:
            clause_lineages[(src, ver, chap, sec, art, cl)].append(i + 1)
        if pt is not None:
            point_lineages[(src, ver, chap, sec, art, cl, pt)].append(i + 1)

    print("Validating chunks...")
    chunks_path = chunks_dir / "policy-legal-chunks.jsonl"
    chunks = []
    seen_ids = set()
    chunker = PolicyChunkerV2()
    
    content_groups = defaultdict(list)

    with open(chunks_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                validate(instance=data, schema=chunk_schema)
                chunks.append(data)
                
                # 1. duplicate canonical IDs
                cid = data["canonical_chunk_id"]
                if cid in seen_ids:
                    raise ValueError(f"Duplicate canonical ID found: {cid}")
                seen_ids.add(cid)
                
                # 2 & 4. input ordinal / content hash reconciliation
                for prov in data.get("provenance", []):
                    ord_idx = prov["input_ordinal"] - 1
                    if ord_idx < 0 or ord_idx >= len(provisions):
                        raise ValueError(f"Provenance input_ordinal {prov['input_ordinal']} out of range.")
                    ref_prov = provisions[ord_idx]
                    if ref_prov["content_hash"] != prov["content_hash"]:
                        raise ValueError(f"Content hash mismatch for ordinal {prov['input_ordinal']}: expected {ref_prov['content_hash']}, got {prov['content_hash']}")
                        
                # 3. recomputed canonical ID mismatch
                expected_id = chunker.get_deterministic_id(data)
                if cid != expected_id:
                    raise ValueError(f"Recomputed canonical ID mismatch. Expected {expected_id}, got {cid}")
                
                content_groups[(data.get("source_id"), data.get("version_id"), data.get("content"))].append(data)

                # Explicit check for fragment lineage vs coverage
                if data.get("is_fragment"):
                    if data.get("fragment_index", 0) <= 0:
                        raise ValueError("fragment_index must be > 0 when is_fragment is true")
                        
                    # 6. malformed fragment parent-lineage semantics, including partial parent material
                    src, ver, chap, sec, art, cl, pt = data.get('source_id'), data.get('version_id'), data.get('chapter'), data.get('section'), data.get('article'), data.get('clause'), data.get('point')
                    expected_lineage_ords = set()
                    akey = (src, ver, chap, sec, art)
                    ckey = (src, ver, chap, sec, art, cl)
                    pkey = (src, ver, chap, sec, art, cl, pt)
                    
                    if pt is not None:
                        for ord_idx in article_lineages[akey]:
                            p = provisions[ord_idx - 1]
                            if p.get('clause') is None and p.get('point') is None:
                                expected_lineage_ords.add(ord_idx)
                        for ord_idx in clause_lineages[ckey]:
                            p = provisions[ord_idx - 1]
                            if p.get('point') is None:
                                expected_lineage_ords.add(ord_idx)
                        for ord_idx in point_lineages[pkey]:
                            expected_lineage_ords.add(ord_idx)
                    elif cl is not None:
                        for ord_idx in article_lineages[akey]:
                            p = provisions[ord_idx - 1]
                            if p.get('clause') is None and p.get('point') is None:
                                expected_lineage_ords.add(ord_idx)
                        for ord_idx in clause_lineages[ckey]:
                            expected_lineage_ords.add(ord_idx)
                    else:
                        for ord_idx in article_lineages[akey]:
                            expected_lineage_ords.add(ord_idx)
                            
                    actual_ords = set(p['input_ordinal'] for p in data['provenance'])
                    if actual_ords != expected_lineage_ords:
                        raise ValueError(f"Malformed fragment parent-lineage. Expected ordinals {sorted(list(expected_lineage_ords))}, got {sorted(list(actual_ords))}")
                        
                else:
                    if data.get("fragment_index", 0) != 0:
                        raise ValueError("fragment_index must be 0 when is_fragment is false")
                        
            except Exception as e:
                print(f"Error validating chunk at line {i+1}: {e}")
                errors += 1

    print("Validating anomalies...")
    qc_path = chunks_dir / "policy-chunking-qc.jsonl"
    anomalies = []
    with open(qc_path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f):
            try:
                data = json.loads(line)
                validate(instance=data, schema=qc_schema)
                anomalies.append(data)
            except Exception as e:
                print(f"Error validating anomaly at line {i+1}: {e}")
                errors += 1

    # 5. exact duplicate-content QC group absence/mismatch
    exact_dup_groups_expected = {k: v for k, v in content_groups.items() if len(v) > 1}
    exact_dup_anomalies = [a for a in anomalies if a.get("anomaly_type") == "EXACT_DUPLICATE_CONTENT"]
    
    # check if every group in exact_dup_groups_expected has a matching anomaly
    for k, chunks_list in exact_dup_groups_expected.items():
        expected_ids = set(c["canonical_chunk_id"] for c in chunks_list)
        matched = False
        for a in exact_dup_anomalies:
            if set(a.get("canonical_chunk_ids", [])) == expected_ids:
                matched = True
                break
        if not matched:
            print(f"Missing EXACT_DUPLICATE_CONTENT anomaly for chunk IDs: {expected_ids}")
            errors += 1
            
    # check if every EXACT_DUPLICATE_CONTENT anomaly is valid
    for a in exact_dup_anomalies:
        a_ids = set(a.get("canonical_chunk_ids", []))
        matched = False
        for k, chunks_list in exact_dup_groups_expected.items():
            if set(c["canonical_chunk_id"] for c in chunks_list) == a_ids:
                matched = True
                break
        if not matched:
            print(f"Mismatch or extra EXACT_DUPLICATE_CONTENT anomaly for chunk IDs: {a_ids}")
            errors += 1

    print("Validating report...")
    report_path = chunks_dir / "policy-chunking-report.json"
    try:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        validate(instance=data, schema=report_schema)
    except Exception as e:
        print(f"Error validating report: {e}")
        errors += 1

    return errors

def main():
    root_dir = backend_dir.parent
    schema_dir = root_dir / "dataset" / "schemas"
    chunks_dir = root_dir / "dataset" / "chunks" / "v2"
    norm_path = root_dir / "dataset" / "normalized" / "v2" / "policy-provisions.jsonl"
    
    errors = validate_dataset(chunks_dir, norm_path, schema_dir)
    
    if errors > 0:
        print(f"Validation failed with {errors} errors.")
        sys.exit(1)
    else:
        print("All validations passed.")
        sys.exit(0)

if __name__ == "__main__":
    main()
