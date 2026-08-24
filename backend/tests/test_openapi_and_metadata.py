from __future__ import annotations

from pathlib import Path

from app.db.models import (
    EMBEDDING_DIMENSIONS,
    AgentKnowledgeBase,
    Approval,
    AssessmentEvent,
    AssessmentRun,
    AuditLog,
    Base,
    Case,
    DebateLog,
    Document,
    OperationExecution,
    PolicyDocument,
    PolicyEmbedding,
    SharedBoard,
)
from app.main import app
from sqlalchemy import CheckConstraint, ForeignKeyConstraint, UniqueConstraint


def _constraint_names(model: type[object], constraint_type: type[object]) -> set[str]:
    return {
        constraint.name
        for constraint in model.__table__.constraints  # type: ignore[attr-defined]
        if isinstance(constraint, constraint_type) and constraint.name is not None
    }


def test_fastapi_openapi_contains_foundational_routes_without_serving_requests() -> None:
    paths = set(app.openapi()["paths"])

    assert {
        "/api/v1/health/live",
        "/api/v1/health/ready",
        "/api/v1/cases",
        "/api/v1/cases/{case_id}",
        "/api/v1/orchestrator/cases/{case_id}/assessment",
        "/api/v1/orchestrator/cases/{case_id}/assessment/stop",
        "/api/v1/orchestrator/cases/{case_id}/assessment/resume",
        "/api/v1/orchestrator/cases/{case_id}/assessment/runtime",
        "/api/v1/orchestrator/cases/{case_id}/events/stream",
        "/api/v1/orchestrator/cases/{case_id}/shared-board",
        "/api/v1/orchestrator/cases/{case_id}/debates",
        "/api/v1/operations/cases/{case_id}/decision",
        "/api/v1/operations/cases/{case_id}/execute",
        "/api/v1/policies/documents",
        "/api/v1/mock-shb/onboarding-drafts",
    } <= paths


def test_model_metadata_contains_full_domain_schema_and_expected_columns() -> None:
    expected_tables = {
        "cases",
        "documents",
        "shared_boards",
        "debate_logs",
        "approvals",
        "operation_executions",
        "audit_logs",
        "agent_knowledge_bases",
        "policy_documents",
        "policy_embeddings",
        "assessment_runs",
        "assessment_events",
    }

    assert expected_tables <= set(Base.metadata.tables)
    assert "extracted_text" in Document.__table__.c
    assert "review_cycle" in SharedBoard.__table__.c
    assert PolicyEmbedding.__table__.c.embedding.type.dim == EMBEDDING_DIMENSIONS == 1024
    assert AssessmentEvent.__table__.c.id.autoincrement is True
    assert "checkpoint_stage" in AssessmentRun.__table__.c


def test_model_metadata_encodes_critical_uniqueness_scope_and_check_constraints() -> None:
    assert "uq_shared_boards_case_id" in _constraint_names(
        SharedBoard, UniqueConstraint
    )
    assert "uq_approvals_case_id" in _constraint_names(Approval, UniqueConstraint)
    assert "uq_operation_executions_case_id" in _constraint_names(
        OperationExecution, UniqueConstraint
    )

    # We replaced the uniqueness constraint on PolicyEmbedding with partial indexes.
    indexes = {index.name: index for index in PolicyEmbedding.__table__.indexes}
    assert "uq_policy_embeddings_canonical" in indexes
    assert "uq_policy_embeddings_legacy" in indexes
    assert "fk_policy_embeddings_document_scope" in _constraint_names(
        PolicyEmbedding, ForeignKeyConstraint
    )

    assert "ck_cases_requested_amount_positive" in _constraint_names(
        Case, CheckConstraint
    )
    assert "ck_debate_logs_round_positive" in _constraint_names(
        DebateLog, CheckConstraint
    )
    assert "ck_agent_knowledge_bases_authorized_agent_key" in _constraint_names(
        AgentKnowledgeBase, CheckConstraint
    )


def test_policy_vector_index_and_migration_preserve_1024d_and_append_only_audit() -> None:
    indexes = {index.name: index for index in PolicyEmbedding.__table__.indexes}
    vector_index = indexes["ix_policy_embeddings_embedding_hnsw"]

    assert vector_index.dialect_options["postgresql"]["using"] == "hnsw"
    assert vector_index.dialect_options["postgresql"]["ops"] == {
        "embedding": "vector_cosine_ops"
    }

    migration_path = (
        Path(__file__).resolve().parents[1]
        / "alembic/versions/20260718_0001_initial.py"
    )
    migration_source = migration_path.read_text(encoding="utf-8")

    assert "Vector(dim=1024)" in migration_source
    assert "audit_logs is append-only" in migration_source
    assert "BEFORE UPDATE OR DELETE ON audit_logs" in migration_source


def test_audit_and_policy_models_are_referenced_to_prevent_accidental_omission() -> None:
    assert AuditLog.__tablename__ == "audit_logs"
    assert PolicyDocument.__tablename__ == "policy_documents"
