import json
from pathlib import Path

import pytest
from app.eval.gold import GoldDatasetError, GoldParser


class DummyResult:
    def __init__(self, data):
        self.data = data
    def scalar(self):
        return self.data[0] if self.data else None
    def scalars(self):
        return self
    def all(self):
        return self.data

class DummyDB:
    def __init__(self, data):
        self.data = data
    def execute(self, stmt):
        # We'll just return fake data based on some substring in stmt
        compiled = stmt.compile(compile_kwargs={"literal_binds": True})
        stmt_str = str(compiled)
        if "chunk_id_1" in stmt_str:
            return DummyResult(["chunk_id_1"])
        if "chunk_id_not_found" in stmt_str:
            return DummyResult([])
        if "section_id_1" in stmt_str:
            return DummyResult(["chunk_id_2", "chunk_id_3"])
        if "section_missing" in stmt_str:
            return DummyResult([])
        return DummyResult(["mocked_chunk"])


@pytest.fixture
def dummy_db():
    return DummyDB([])


def test_missing_gold_file(dummy_db):
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="Gold retrieval dataset is missing"):
        list(parser.parse_file(Path("non_existent_file.jsonl")))


def test_valid_example(tmp_path, dummy_db):
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "POLICY_LOOKUP",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [
            {"source_id": "s1", "version_id": "v1", "section_id": "sec1", "chunk_id": "chunk_id_1"}
        ],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    
    parser = GoldParser(dummy_db)
    results = list(parser.parse_file(gold_path))
    assert len(results) == 1
    assert "chunk_id_1" in results[0]["resolved_canonical_chunk_ids"]


def test_duplicate_evaluation_id(tmp_path, dummy_db):
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "POLICY_LOOKUP",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record) + "\n" + json.dumps(record))
    
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="Duplicate evaluation_id"):
        list(parser.parse_file(gold_path))


def test_malformed_query(tmp_path, dummy_db):
    gold_path = tmp_path / "retrieval.jsonl"
    gold_path.write_text("not json")
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="Invalid JSON"):
        list(parser.parse_file(gold_path))


def test_invalid_chunk_reference(tmp_path, dummy_db):
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "POLICY_LOOKUP",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [
            {"source_id": "s1", "version_id": "v1", "section_id": "sec1", "chunk_id": "chunk_id_not_found"}
        ],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="not found"):
        list(parser.parse_file(gold_path))


def test_invalid_source_version_section(tmp_path, dummy_db):
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "POLICY_LOOKUP",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [
            {"source_id": "s1", "version_id": "v1", "section_id": "section_missing"}
        ],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="No canonical chunk matches"):
        list(parser.parse_file(gold_path))


def test_forbidden_version_contradiction(tmp_path, dummy_db):
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "POLICY_LOOKUP",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [
            {"source_id": "s1", "version_id": "v1", "section_id": "sec1", "chunk_id": "chunk_id_1"}
        ],
        "forbidden_version_ids": ["v1"],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="Contradictory"):
        list(parser.parse_file(gold_path))

def test_missing_query_type(tmp_path, dummy_db):
    import json
    import pytest
    from app.eval.gold import GoldParser, GoldDatasetError
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="Missing required field 'query_type'"):
        list(parser.parse_file(gold_path))

def test_invalid_query_type(tmp_path, dummy_db):
    import json
    import pytest
    from app.eval.gold import GoldParser, GoldDatasetError
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "INVALID_TYPE",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    parser = GoldParser(dummy_db)
    with pytest.raises(GoldDatasetError, match="Invalid query_type 'INVALID_TYPE'"):
        list(parser.parse_file(gold_path))

def test_negative_no_evidence(tmp_path, dummy_db):
    import json
    import pytest
    from app.eval.gold import GoldParser, GoldDatasetError
    gold_path = tmp_path / "retrieval.jsonl"
    record = {
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "NEGATIVE_NO_EVIDENCE",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [],
        "forbidden_version_ids": [],
        "expected_coverage": "INSUFFICIENT",
        "tags": []
    }
    gold_path.write_text(json.dumps(record))
    parser = GoldParser(dummy_db)
    results = list(parser.parse_file(gold_path))
    assert len(results) == 1
    assert results[0]["query_type"] == "NEGATIVE_NO_EVIDENCE"
