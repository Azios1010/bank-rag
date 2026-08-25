import os
import uuid

import pytest
from app.db.models import AgentKnowledgeBase, Base, PolicyDocument, PolicyEmbedding
from app.eval.contracts import RetrievalRequest
from app.eval.retrievers import CanonicalVectorEvaluationRetriever
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


class DummyEncoder:
    def embed_queries(self, queries):
        # Return a simple vector
        return [[0.1] * 1024 for _ in queries]


@pytest.fixture(scope="module")
def postgres_engine():
    db_url = os.environ.get("RETRIEVAL_EVAL_DATABASE_URL") or os.environ.get("TEST_DATABASE_URL")
    if not db_url:
        pytest.skip("No PostgreSQL URL configured (set RETRIEVAL_EVAL_DATABASE_URL or TEST_DATABASE_URL)")
    
    if "sqlite" in db_url:
        pytest.skip("Integration test requires real PostgreSQL/pgvector, not SQLite")

    engine = create_engine(db_url)
    
    # We must ensure pgvector extension is created before we can create the tables
    # But Alembic handles that normally. Since it's a test, we might just rely on the DB being set up.
    # We will try to create tables if they don't exist, but maybe the test DB is already migrated.
    # Let's just create them.
    from sqlalchemy import text
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup (drop tables after test if desired, but we can just leave it or drop data)
    Base.metadata.drop_all(engine)


@pytest.fixture
def db_session(postgres_engine):
    SessionLocal = sessionmaker(bind=postgres_engine)
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


def test_retrieval_eval_postgres_integration(db_session):
    # Setup fixture
    kb = AgentKnowledgeBase(
        id=uuid.uuid4(),
        agent_key="customer_relationship",
        name="CR Test KB",
        active=True
    )
    db_session.add(kb)
    
    # Document - inactive canonical R01-staged row
    doc = PolicyDocument(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        title="Test Canonical Policy",
        version="v1",
        sha256="fakehash",
        active=False,  # Evaluator explicitly accesses inactive
        canonical_source_id="src_1",
        canonical_version_id="ver_1"
    )
    db_session.add(doc)
    
    # Embedding
    vector = [0.1] * 1024
    vector[0] = 0.5  # slight modification
    
    emb1 = PolicyEmbedding(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=0,
        content_chunk="Canonical chunk 1",
        content_hash="hash1",
        embedding=vector,
        canonical_chunk_id="canon_1",
        metadata_={"section_id": "sec1"}
    )
    
    emb2 = PolicyEmbedding(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=1,
        content_chunk="Canonical chunk 2",
        content_hash="hash2",
        embedding=[0.2] * 1024,
        canonical_chunk_id="canon_2",
        metadata_={"section_id": "sec2"}
    )
    
    db_session.add_all([emb1, emb2])
    db_session.commit()
    
    # Run evaluation
    adapter = DummyEncoder()
    retriever = CanonicalVectorEvaluationRetriever(db_session, adapter)
    
    req = RetrievalRequest(
        evaluation_id="eval_pg",
        query="test",
        agent_scope="CustomerRelationship"
    )
    
    exec_result = retriever.retrieve(req, k=5)
    
    assert len(exec_result.results) == 2
    # Ensure they have the correct canonical IDs
    ids = [res.canonical_chunk_id for res in exec_result.results]
    assert "canon_1" in ids
    assert "canon_2" in ids
    
    # Test deduplication - Add another copy of canon_1
    emb1_copy = PolicyEmbedding(
        id=uuid.uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=2,
        content_chunk="Canonical chunk 1 duplicate",
        content_hash="hash1_dup",
        embedding=vector,
        canonical_chunk_id="canon_1", # Duplicate
        metadata_={"section_id": "sec1"}
    )
    db_session.add(emb1_copy)
    db_session.commit()
    
    exec_result2 = retriever.retrieve(req, k=5)
    # Should still only be 2 results because of deduplication
    assert len(exec_result2.results) == 2
    
    # Verify deterministic ordering
    # cosine similarity will put canon_1 higher if query matches it better, etc.
    # we just need to ensure the order is stable.
    ids2 = [res.canonical_chunk_id for res in exec_result2.results]
    assert ids == ids2
