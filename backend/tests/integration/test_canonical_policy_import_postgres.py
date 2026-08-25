import os
from uuid import uuid4

import pytest
from app.db.models import AgentKnowledgeBase, PolicyDocument, PolicyEmbedding
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker

# 2. BLOCKER: must NOT reference a nonexistent db_session fixture
# Make explicitly environment-gated.
DATABASE_URL = os.environ.get("TEST_DATABASE_URL")

@pytest.fixture
def integration_db_session():
    if not DATABASE_URL:
        pytest.skip("Skipping PostgreSQL integration test because TEST_DATABASE_URL is not set.")
    
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()
    try:
        # Create schema if not exists for the test
        from app.db.models import Base
        Base.metadata.create_all(bind=engine)
        yield session
    finally:
        session.rollback()
        session.close()

@pytest.mark.integration
def test_postgres_partial_unique_indexes(integration_db_session):
    db_session = integration_db_session
    # This test verifies the alembic migration partial indexes in Postgres
    kb = AgentKnowledgeBase(id=uuid4(), agent_key="credit", name="Credit")
    db_session.add(kb)
    
    doc = PolicyDocument(
        id=uuid4(), 
        knowledge_base_id=kb.id,
        title="Test Doc",
        version="v1",
        sha256="sha256:1",
        active=False
    )
    db_session.add(doc)
    db_session.flush()

    # 1. Two chunks with identical content_hash but DIFFERENT canonical_chunk_id should succeed
    emb1 = PolicyEmbedding(
        id=uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=0,
        content_chunk="same text",
        content_hash="sha256:same",
        embedding=[0.0]*1024,
        metadata_={},
        canonical_chunk_id="chk1"
    )
    emb2 = PolicyEmbedding(
        id=uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=1,
        content_chunk="same text",
        content_hash="sha256:same",
        embedding=[0.0]*1024,
        metadata_={},
        canonical_chunk_id="chk2"
    )
    db_session.add(emb1)
    db_session.add(emb2)
    db_session.commit()
    
    # 2. Legacy rows with identical content_hash (and canonical_chunk_id IS NULL) should fail
    emb3 = PolicyEmbedding(
        id=uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=2,
        content_chunk="legacy text",
        content_hash="sha256:legacy",
        embedding=[0.0]*1024,
        metadata_={}
    )
    db_session.add(emb3)
    db_session.commit()

    emb4 = PolicyEmbedding(
        id=uuid4(),
        knowledge_base_id=kb.id,
        policy_document_id=doc.id,
        chunk_index=3,
        content_chunk="legacy text",
        content_hash="sha256:legacy",
        embedding=[0.0]*1024,
        metadata_={}
    )
    db_session.add(emb4)
    with pytest.raises(IntegrityError):
        db_session.commit()
