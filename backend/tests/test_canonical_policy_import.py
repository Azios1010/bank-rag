import json
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from app.db.models import AgentKnowledgeBase, PolicyDocument, PolicyEmbedding
from app.services.canonical_policy_import import CanonicalPolicyImportService


@pytest.fixture
def mock_bundle():
    td = tempfile.mkdtemp()
    bundle_dir = Path(td)
    # sources
    sources = [{
        "source_id": "src1",
        "title": "Title 1",
        "allowed_agent_scopes": ["Credit"],
        "versions": [{
            "version_id": "v1",
            "version_label": "V1",
            "content_hash": f"sha256:{'a' * 64}",
            "status": "ACTIVE"
        }]
    }]
    with open(bundle_dir / "policy-sources.jsonl", "w") as f:
        f.writelines(json.dumps(s) + "\n" for s in sources)

    # chunks
    chunks = [
        {"chunk_id": "chk1", "version_id": "v1", "content": "hello world", "chunk_index": 0},
        {"chunk_id": "chk2", "version_id": "v1", "content": "hello again", "chunk_index": 1}
    ]
    with open(bundle_dir / "policy-chunks.jsonl", "w") as f:
        f.writelines(json.dumps(c) + "\n" for c in chunks)

    # embeddings parquet
    vec1 = [0.0]*1024
    vec2 = [1.0]*1024
    table = pa.Table.from_arrays(
        [
            pa.array(["chk1", "chk2"]),
            pa.array([vec1, vec2])
        ],
        names=["chunk_id", "embedding"]
    )
    pq.write_table(table, bundle_dir / "embeddings.parquet")

    # hash the parquet
    import hashlib
    h = hashlib.sha256()
    with open(bundle_dir / "embeddings.parquet", "rb") as f:
        h.update(f.read())
    parquet_hash = f"sha256:{h.hexdigest()}"

    # manifest
    manifest = {
        "model_id": "TestModel",
        "resolved_revision": "rev1",
        "chunk_count": 2,
        "output": {"sha256": parquet_hash}
    }
    with open(bundle_dir / "embedding-manifest.json", "w") as f:
        json.dump(manifest, f)

    # report
    report = {"status": "PASS"}
    with open(bundle_dir / "embedding-run-report.json", "w") as f:
        json.dump(report, f)

    yield bundle_dir
    shutil.rmtree(td)


import hashlib
from unittest.mock import MagicMock, patch

VALID_SHA256 = "a" * 64
VALID_CHUNK_HASH = hashlib.sha256(b"hello world").hexdigest()
VALID_CHUNK_HASH2 = hashlib.sha256(b"hello again").hexdigest()

def test_canonical_import_idempotent(mock_bundle):
    # D. Idempotency (Identical import creates no duplicates)
    # A. Canonical import does not call split_text()
    with patch("app.services.rag.split_text", side_effect=RuntimeError("split_text should not be called")):
        db_session = MagicMock()
        
        kb = AgentKnowledgeBase(id=uuid4(), agent_key="credit", name="Credit")
        db_session.scalars.return_value.all.return_value = [kb]
        db_session.scalar.return_value = None  # No existing doc/chunk
    
        service = CanonicalPolicyImportService(db_session)
        service.stage(mock_bundle)
    
        # Check that add was called for PolicyDocument and PolicyEmbedding
        added_items = [call.args[0] for call in db_session.add.call_args_list]
        docs = [item for item in added_items if isinstance(item, PolicyDocument)]
        embs = [item for item in added_items if isinstance(item, PolicyEmbedding)]
        
        assert len(docs) == 1
        # G. Inactive staging
        assert docs[0].active is False  
    
        assert len(embs) == 2
        
        # B. Exact content preservation
        assert embs[0].content_chunk == "hello world"
        
        # Second pass: simulate existing document and chunks
        db_session.scalar.side_effect = [docs[0], embs[0], embs[1]]
        db_session.add.reset_mock()
        service.stage(mock_bundle)
        
        # Should be idempotent, no new adds
        assert db_session.add.call_count == 0

def test_canonical_import_hash_conflict_fails(mock_bundle):
    # E. Content conflict
    db_session = MagicMock()
    kb = AgentKnowledgeBase(id=uuid4(), agent_key="credit", name="Credit")
    db_session.scalars.return_value.all.return_value = [kb]
    
    existing_doc = PolicyDocument(id=uuid4(), sha256="b" * 64)
    db_session.scalar.side_effect = [existing_doc, None]
    
    service = CanonicalPolicyImportService(db_session)
    import pytest
    with pytest.raises(ValueError, match="Hash conflict for document"):
        service.stage(mock_bundle)

def test_canonical_import_vector_conflict_fails(mock_bundle):
    # F. Vector conflict
    db_session = MagicMock()
    kb = AgentKnowledgeBase(id=uuid4(), agent_key="credit", name="Credit")
    db_session.scalars.return_value.all.return_value = [kb]
    
    existing_doc = PolicyDocument(id=uuid4(), sha256=VALID_SHA256)
    
    existing_emb = PolicyEmbedding(id=uuid4(), content_hash=VALID_CHUNK_HASH, metadata_={"vector_hash": "different"})
    
    db_session.scalar.side_effect = [existing_doc, existing_emb]
    
    service = CanonicalPolicyImportService(db_session)
    import pytest
    with pytest.raises(ValueError, match="Vector conflict for chunk"):
        service.stage(mock_bundle)

def test_legacy_regression():
    # I. Legacy regression
    # Prove that PolicyIngestionService (manual upload) STILL uses split_text
    from app.schemas.enums import AgentID
    from app.services.rag import PolicyIngestionService
    db_session = MagicMock()
    kb = AgentKnowledgeBase(id=uuid4(), agent_key="credit", name="Credit")
    db_session.scalar.side_effect = [kb, None, None, None, None, None] # handle enough Nones
    
    provider = MagicMock()
    provider.embed.return_value = [[0.1] * 1024, [0.2] * 1024]
    
    service = PolicyIngestionService(db_session, provider)
    
    with patch("app.services.rag.split_text") as mock_split:
        # mock chunks
        from collections import namedtuple
        Chunk = namedtuple("Chunk", ["content", "index"])
        mock_split.return_value = [Chunk("hello", 0), Chunk("world", 1)]
        
        service.ingest(
            agent_id=AgentID.CREDIT,
            title="T",
            version="V",
            content="hello world",
            source_sha256="123",
            source_object_key=None,
            section_id="S1",
            page_number=1,
            effective_at=None
        )
        
        # Assert split_text was actually invoked!
        mock_split.assert_called_once_with("hello world")

def test_retrieval_exclusion():
    # H. Retrieval exclusion
    # Staged canonical rows cannot appear in active retrieval
    from app.schemas.enums import AgentID
    from app.services.rag import AgentPolicyRetriever
    from sqlalchemy import create_engine, literal_column
    from sqlalchemy.orm import sessionmaker

    # Mock pgvector cosine_distance for sqlite
    from sqlalchemy.orm.attributes import InstrumentedAttribute
    
    def mock_cosine_distance(self, other):
        return literal_column("0.0")
    
    InstrumentedAttribute.cosine_distance = mock_cosine_distance
    
    try:
        engine = create_engine("sqlite:///:memory:")
        SessionLocal = sessionmaker(bind=engine)
        session = SessionLocal()
        
        from pgvector.sqlalchemy import Vector
        from sqlalchemy.dialects.postgresql import JSONB
        from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
        from sqlalchemy.ext.compiler import compiles
        
        @compiles(JSONB, "sqlite")
        def compile_jsonb_sqlite(type_, compiler, **kw):
            return "JSON"

        @compiles(PostgreSQLUUID, "sqlite")
        def compile_uuid_sqlite(type_, compiler, **kw):
            return "TEXT"

        @compiles(Vector, "sqlite")
        def compile_vector_sqlite(type_, compiler, **kw):
            return "TEXT"
        try:
            AgentKnowledgeBase.__table__.create(engine)
            PolicyDocument.__table__.create(engine)
            PolicyEmbedding.__table__.create(engine)
        finally:
            pass
        
        kb = AgentKnowledgeBase(id=uuid4(), agent_key="credit", name="Credit", active=True)
        session.add(kb)
        
        # Construct one active
        doc_active = PolicyDocument(id=uuid4(), knowledge_base_id=kb.id, title="Active", version="v1", sha256="1", active=True)
        emb_active = PolicyEmbedding(id=uuid4(), knowledge_base_id=kb.id, policy_document_id=doc_active.id, chunk_index=0, content_chunk="active chunk", content_hash="1", embedding=[0.1]*1024, metadata_={})
        session.add(doc_active)
        session.add(emb_active)
        
        # Construct one inactive
        doc_inactive = PolicyDocument(id=uuid4(), knowledge_base_id=kb.id, title="Inactive", version="v1", sha256="2", active=False)
        emb_inactive = PolicyEmbedding(id=uuid4(), knowledge_base_id=kb.id, policy_document_id=doc_inactive.id, chunk_index=0, content_chunk="inactive chunk", content_hash="2", embedding=[0.2]*1024, metadata_={})
        session.add(doc_inactive)
        session.add(emb_inactive)
        
        session.commit()
        
        provider = MagicMock()
        provider.embed.return_value = [[0.1]*1024]
        
        retriever = AgentPolicyRetriever(session, AgentID.CREDIT, provider)
        citations = retriever.retrieve("query")
        
        assert len(citations) == 1
        assert citations[0].quote == "active chunk"
        session.close()
    finally:
        del InstrumentedAttribute.cosine_distance
