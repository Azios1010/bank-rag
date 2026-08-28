import pytest
import json
from app.services.policy_chunking_v2 import PolicyChunkerV2

def test_chunking_determinism_and_hierarchy():
    provisions = [
        {
            "source_id": "test-source",
            "version_id": "test-version",
            "chapter": "I",
            "section": "1",
            "article": "1",
            "clause": None,
            "point": None,
            "heading_path": ["I", "1"],
            "content": "Article 1. General rules.",
            "page_start": 1,
            "page_end": 1,
            "content_hash": "hash1"
        },
        {
            "source_id": "test-source",
            "version_id": "test-version",
            "chapter": "I",
            "section": "1",
            "article": "1",
            "clause": "1",
            "point": None,
            "heading_path": ["I", "1"],
            "content": "1. First clause.",
            "page_start": 1,
            "page_end": 1,
            "content_hash": "hash2"
        },
        {
            "source_id": "test-source",
            "version_id": "test-version",
            "chapter": "I",
            "section": "1",
            "article": "1",
            "clause": "1",
            "point": "a",
            "heading_path": ["I", "1"],
            "content": "a) First point.",
            "page_start": 1,
            "page_end": 1,
            "content_hash": "hash3"
        }
    ]
    
    chunker = PolicyChunkerV2()
    chunker.process_dataset(provisions)
    
    assert len(chunker.chunks) == 1
    chunk = chunker.chunks[0]
    
    assert chunk["article"] == "1"
    assert chunk["clause"] is None # Whole article fit in one chunk, so clause is None
    assert "Article 1. General rules.\n1. First clause.\na) First point." == chunk["content"]
    assert len(chunk["provenance"]) == 3
    
    # Run again to ensure determinism
    chunker2 = PolicyChunkerV2()
    chunker2.process_dataset(provisions)
    assert chunker2.chunks[0]["canonical_chunk_id"] == chunk["canonical_chunk_id"]

def test_orphan_point():
    provisions = [
        {
            "source_id": "test-source",
            "version_id": "test-version",
            "chapter": "I",
            "section": "1",
            "article": "2",
            "clause": None, # Orphan
            "point": "a",
            "heading_path": ["I", "1"],
            "content": "a) Orphan point.",
            "page_start": 1,
            "page_end": 1,
            "content_hash": "hash4"
        }
    ]
    
    chunker = PolicyChunkerV2()
    chunker.process_dataset(provisions)
    
    assert len(chunker.anomalies) == 1
    assert chunker.anomalies[0]["anomaly_type"] == "ORPHAN_POINT_WITHOUT_CLAUSE"

def test_duplicate_hierarchy():
    provisions = [
        {
            "source_id": "test-source",
            "version_id": "test-version",
            "chapter": "I",
            "section": "1",
            "article": "3",
            "clause": "1",
            "point": None,
            "heading_path": ["I", "1"],
            "content": "1. Duplicate 1.",
            "page_start": 1,
            "page_end": 1,
            "content_hash": "hash5"
        },
        {
            "source_id": "test-source",
            "version_id": "test-version",
            "chapter": "I",
            "section": "1",
            "article": "3",
            "clause": "1",
            "point": None,
            "heading_path": ["I", "1"],
            "content": "1. Duplicate 2.",
            "page_start": 1,
            "page_end": 1,
            "content_hash": "hash6"
        }
    ]
    
    chunker = PolicyChunkerV2()
    chunker.process_dataset(provisions)
    
    assert len(chunker.anomalies) == 1
    assert chunker.anomalies[0]["anomaly_type"] == "DUPLICATE_HIERARCHY_KEY"
    assert len(chunker.chunks) == 1
    assert "1. Duplicate 1.\n1. Duplicate 2." in chunker.chunks[0]["content"]
