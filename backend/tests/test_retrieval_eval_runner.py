import subprocess
import sys
from pathlib import Path


def test_missing_gold_file_cli(tmp_path):
    gold_path = tmp_path / "does_not_exist.jsonl"
    
    cmd = [
        sys.executable, "-m", "app.eval.retrieval", "vector-baseline",
        "--database-url", "sqlite:///:memory:",
        "--gold-path", str(gold_path),
        "--sources-path", "sources.json",
        "--chunks-path", "chunks.jsonl",
        "--embedding-dir", "embeddings",
        "--output-dir", "out",
        "--ks", "1,3,5",
        "--run-id", "test-run"
    ]
    
    import os
    env = os.environ.copy()
    backend_dir = Path(__file__).parent.parent
    env["PYTHONPATH"] = str(backend_dir)
    
    result = subprocess.run(cmd, cwd=str(backend_dir), env=env, capture_output=True, text=True, check=False)
    
    assert result.returncode != 0
    assert "Gold retrieval dataset is missing" in result.stderr
    assert "A reviewed gold retrieval set is required before the vector baseline can run" in result.stderr


def test_summary_reproducibility_fields():
    from app.eval.retrieval import get_corpus_count, get_git_commit
    
    commit = get_git_commit()
    assert isinstance(commit, str)
    assert len(commit) > 0
    
    class MockResult:
        def scalar(self):
            return 2
            
    class MockDB:
        def execute(self, stmt):
            return MockResult()
            
    assert get_corpus_count(MockDB()) == 2


def test_successful_run_creates_summary(tmp_path, monkeypatch):
    import argparse
    import json

    import app.eval.retrieval
    from app.eval.qwen_embedding import QwenEvaluationEmbeddingAdapter
    from app.eval.retrieval import run_vector_baseline
    
    class MockAdapter:
        def embed_queries(self, queries):
            return [[0.1]*1024 for _ in queries]
    
    monkeypatch.setattr(QwenEvaluationEmbeddingAdapter, "create_real", lambda: MockAdapter())
    monkeypatch.setattr(app.eval.retrieval, "get_corpus_count", lambda db: 42)
    monkeypatch.setattr("app.eval.qwen_embedding.validate_embedding_profile", lambda m: None)
    
    gold_path = tmp_path / "retrieval.jsonl"
    gold_path.write_text(json.dumps({
        "evaluation_id": "eval_1",
        "query": "query 1",
        "query_type": "POLICY_LOOKUP",
        "agent_scope": "Credit",
        "assessment_date": "2026-08-01",
        "filters": {},
        "gold_evidence": [{"source_id": "s1", "version_id": "v1", "section_id": "sec1", "chunk_id": "chunk1"}],
        "forbidden_version_ids": [],
        "expected_coverage": "SUFFICIENT",
        "tags": []
    }))
    
    manifest_dir = tmp_path / "embeddings"
    manifest_dir.mkdir()
    manifest_path = manifest_dir / "embedding-manifest.json"
    manifest_path.write_text(json.dumps({
        "input_template_version": "policy-title-heading-content-v1"
    }))
    
    sources_path = tmp_path / "sources.json"
    sources_path.write_text("")
    chunks_path = tmp_path / "chunks.jsonl"
    chunks_path.write_text("")
    
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    
    class MockResult:
        def scalar(self): return "chunk1"
        def all(self): return []
    class MockDB:
        def execute(self, stmt): return MockResult()
        def __enter__(self): return self
        def __exit__(self, exc_type, exc_val, exc_tb): pass
        
    monkeypatch.setattr("app.eval.retrieval.sessionmaker", lambda **kwargs: lambda: MockDB())
    monkeypatch.setattr("app.eval.retrieval.create_engine", lambda url: None)
    
    args = argparse.Namespace(
        database_url="sqlite:///:memory:",
        gold_path=gold_path,
        sources_path=sources_path,
        chunks_path=chunks_path,
        embedding_dir=manifest_dir,
        output_dir=out_dir,
        ks="1,3",
        run_id="test-run",
        command="vector-baseline"
    )
    
    run_vector_baseline(args)
    
    summary_file = out_dir / "test-run" / "summary.json"
    assert summary_file.exists()
    
    with open(summary_file) as f:
        summary = json.load(f)
        
    assert "git_commit" in summary
    assert "corpus_count" in summary
    assert summary["corpus_count"] == 42
