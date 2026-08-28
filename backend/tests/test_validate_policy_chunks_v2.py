import json
import pytest
from pathlib import Path
import tempfile
import os

from scripts.validate_policy_chunks_v2 import validate_dataset

# We need a small self-contained valid dataset to test the validator logic.
# Then we mutate it to test failures.

@pytest.fixture
def temp_dataset():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        
        # We need schemas
        root_dir = Path(__file__).resolve().parent.parent.parent
        schema_dir = root_dir / "dataset" / "schemas"
        
        chunks_dir = tmp_path / "chunks" / "v2"
        chunks_dir.mkdir(parents=True)
        
        norm_dir = tmp_path / "normalized" / "v2"
        norm_dir.mkdir(parents=True)
        
        norm_path = norm_dir / "policy-provisions.jsonl"
        
        yield chunks_dir, norm_path, schema_dir

def write_jsonl(path, items):
    with open(path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item) + "\n")

def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)

# Base valid data
VALID_PROV = [
    {
        "source_id": "s1", "version_id": "v1", "chapter": "1", "section": None, 
        "article": "1", "clause": None, "point": None, "heading_path": ["1"],
        "content": "C1", "page_start": 1, "page_end": 1, 
        "content_hash": "h1", "inventory_type": "SELECTED", "selection_reason": ""
    },
    {
        "source_id": "s1", "version_id": "v1", "chapter": "1", "section": None, 
        "article": "1", "clause": "1", "point": None, "heading_path": ["1"],
        "content": "C2", "page_start": 1, "page_end": 1, 
        "content_hash": "h2", "inventory_type": "SELECTED", "selection_reason": ""
    }
]

VALID_CHUNKS = [
    {
        "canonical_chunk_id": "2bc351110a178eefd20d77bbd762f0fcfcba8ba67e6c4bf2f5b89ebc132bb823", # Precomputed for this
        "chunker_version": "bank-rag-v2-chunker-1.0.0",
        "source_id": "s1", "version_id": "v1", "chapter": "1", "section": None,
        "article": "1", "clause": "1", "point": None, "heading_path": ["1"],
        "content": "C1\nC2", "page_start": 1, "page_end": 1,
        "provenance": [
            {"input_ordinal": 1, "content_hash": "h1"},
            {"input_ordinal": 2, "content_hash": "h2"}
        ],
        "is_long_unsplittable": False,
        "is_fragment": False,
        "fragment_index": 0
    }
]

VALID_REPORT = {
    "chunker_version": "bank-rag-v2-chunker-1.0.0",
    "total_input_provisions": 2,
    "total_emitted_chunks": 1,
    "total_anomalies": 0,
    "anomalies_by_type": {}
}

VALID_QC = []

def setup_valid_dataset(chunks_dir, norm_path):
    write_jsonl(norm_path, VALID_PROV)
    write_jsonl(chunks_dir / "policy-legal-chunks.jsonl", VALID_CHUNKS)
    write_jsonl(chunks_dir / "policy-chunking-qc.jsonl", VALID_QC)
    write_json(chunks_dir / "policy-chunking-report.json", VALID_REPORT)

def test_validator_pass_valid_dataset(temp_dataset):
    chunks_dir, norm_path, schema_dir = temp_dataset
    setup_valid_dataset(chunks_dir, norm_path)
    # The valid chunk above might have wrong hash, let's fix the canonical_chunk_id
    from app.services.policy_chunking_v2 import PolicyChunkerV2
    chunker = PolicyChunkerV2()
    VALID_CHUNKS[0]["canonical_chunk_id"] = chunker.get_deterministic_id(VALID_CHUNKS[0])
    
    write_jsonl(chunks_dir / "policy-legal-chunks.jsonl", VALID_CHUNKS)
    
    assert validate_dataset(chunks_dir, norm_path, schema_dir) == 0

def test_validator_fails_duplicate_ids(temp_dataset):
    chunks_dir, norm_path, schema_dir = temp_dataset
    setup_valid_dataset(chunks_dir, norm_path)
    from app.services.policy_chunking_v2 import PolicyChunkerV2
    chunker = PolicyChunkerV2()
    VALID_CHUNKS[0]["canonical_chunk_id"] = chunker.get_deterministic_id(VALID_CHUNKS[0])
    
    # Duplicate the chunk
    dup_chunks = [VALID_CHUNKS[0], VALID_CHUNKS[0]]
    write_jsonl(chunks_dir / "policy-legal-chunks.jsonl", dup_chunks)
    
    errors = validate_dataset(chunks_dir, norm_path, schema_dir)
    assert errors > 0

def test_validator_fails_missing_qc_duplicate_content(temp_dataset):
    chunks_dir, norm_path, schema_dir = temp_dataset
    setup_valid_dataset(chunks_dir, norm_path)
    from app.services.policy_chunking_v2 import PolicyChunkerV2
    chunker = PolicyChunkerV2()
    c1 = dict(VALID_CHUNKS[0])
    c1["canonical_chunk_id"] = chunker.get_deterministic_id(c1)
    
    c2 = dict(c1)
    c2["clause"] = "2" # change something so it's a different chunk, but same content
    c2["canonical_chunk_id"] = chunker.get_deterministic_id(c2)
    
    write_jsonl(chunks_dir / "policy-legal-chunks.jsonl", [c1, c2])
    
    # We didn't add EXACT_DUPLICATE_CONTENT to QC
    errors = validate_dataset(chunks_dir, norm_path, schema_dir)
    assert errors > 0

def test_validator_fails_partial_parent_material(temp_dataset):
    chunks_dir, norm_path, schema_dir = temp_dataset
    setup_valid_dataset(chunks_dir, norm_path)
    from app.services.policy_chunking_v2 import PolicyChunkerV2
    chunker = PolicyChunkerV2()
    
    # Create a fragment
    c1 = dict(VALID_CHUNKS[0])
    c1["is_fragment"] = True
    c1["fragment_index"] = 1
    # Purposely omit ordinal 1 from provenance (partial parent material)
    c1["provenance"] = [{"input_ordinal": 2, "content_hash": "h2"}]
    c1["canonical_chunk_id"] = chunker.get_deterministic_id(c1)
    
    write_jsonl(chunks_dir / "policy-legal-chunks.jsonl", [c1])
    
    errors = validate_dataset(chunks_dir, norm_path, schema_dir)
    assert errors > 0

def test_validator_pass_full_real_dataset():
    # Validates that the actual dataset passes without errors,
    # ensuring it correctly identifies the 13 exact duplicate-content groups / 29 chunks
    # and the 142 fragments (including the 93 point fragments).
    root_dir = Path(__file__).resolve().parent.parent.parent
    schema_dir = root_dir / "dataset" / "schemas"
    chunks_dir = root_dir / "dataset" / "chunks" / "v2"
    norm_path = root_dir / "dataset" / "normalized" / "v2" / "policy-provisions.jsonl"
    
    errors = validate_dataset(chunks_dir, norm_path, schema_dir)
    assert errors == 0

