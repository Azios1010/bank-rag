from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIMENSIONS = 1024


class CaseStatus(str, Enum):
    INGESTED = "INGESTED"
    TIER1_PLANNING = "TIER1_PLANNING"
    AWAITING_DOCS = "AWAITING_DOCS"
    TIER2_DEBATING = "TIER2_DEBATING"
    TIER3_PENDING_REVIEW = "TIER3_PENDING_REVIEW"
    REVISION_REQUESTED = "REVISION_REQUESTED"
    REJECTED = "REJECTED"
    APPROVED = "APPROVED"
    COMPLETED = "COMPLETED"


class DocumentStatus(str, Enum):
    UPLOADED = "UPLOADED"
    PARSED = "PARSED"
    REJECTED = "REJECTED"


class ApprovalDecision(str, Enum):
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REVISION_REQUESTED = "REVISION_REQUESTED"


class DebateStatus(str, Enum):
    OPEN = "OPEN"
    RESOLVED = "RESOLVED"
    ACCEPTED_FOR_MANUAL_REVIEW = "ACCEPTED_FOR_MANUAL_REVIEW"


class AuditOutcome(str, Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"


class SharedBoardStatus(str, Enum):
    INITIALIZED = "INITIALIZED"
    SPECIALISTS_RUNNING = "SPECIALISTS_RUNNING"
    DEBATE_IN_PROGRESS = "DEBATE_IN_PROGRESS"
    CONSENSUS_REACHED = "CONSENSUS_REACHED"
    MAX_ROUNDS_REACHED = "MAX_ROUNDS_REACHED"


class OperationStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"


class AssessmentRunStatus(str, Enum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    STOP_REQUESTED = "STOP_REQUESTED"
    PAUSED = "PAUSED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        CheckConstraint("requested_amount > 0", name="requested_amount_positive"),
        CheckConstraint(
            "status IN ('INGESTED', 'TIER1_PLANNING', 'AWAITING_DOCS', "
            "'TIER2_DEBATING', 'TIER3_PENDING_REVIEW', 'REVISION_REQUESTED', "
            "'REJECTED', 'APPROVED', 'COMPLETED')",
            name="valid_status",
        ),
        Index("ix_cases_status_created_at", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    requested_amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2), nullable=False
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=CaseStatus.INGESTED.value
    )
    workflow_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="corporate_loan_v1"
    )
    workflow_version: Mapped[str] = mapped_column(
        String(32), nullable=False, default="1.0"
    )
    input_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("byte_size >= 0", name="byte_size_non_negative"),
        CheckConstraint(
            "status IN ('UPLOADED', 'PARSED', 'REJECTED')",
            name="valid_status",
        ),
        Index("ix_documents_case_id_created_at", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    document_type: Mapped[str] = mapped_column(String(100), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(512), nullable=False)
    object_key: Mapped[str] = mapped_column(String(1024), nullable=False, unique=True)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DocumentStatus.UPLOADED.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AssessmentRun(Base):
    """Durable execution/checkpoint state for a single assessment attempt."""

    __tablename__ = "assessment_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('QUEUED', 'RUNNING', 'STOP_REQUESTED', 'PAUSED', "
            "'COMPLETED', 'FAILED')",
            name="valid_status",
        ),
        Index("ix_assessment_runs_case_id_created_at", "case_id", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AssessmentRunStatus.QUEUED.value
    )
    current_stage: Mapped[str] = mapped_column(
        String(64), nullable=False, default="queued"
    )
    checkpoint_stage: Mapped[str] = mapped_column(
        String(64), nullable=False, default="plan"
    )
    stop_requested: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    started_by: Mapped[str] = mapped_column(String(255), nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AssessmentEvent(Base):
    """User-safe operational events for SSE and timeline replay."""

    __tablename__ = "assessment_events"
    __table_args__ = (
        Index("ix_assessment_events_case_id_id", "case_id", "id"),
        Index("ix_assessment_events_run_id_id", "run_id", "id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("assessment_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    stage: Mapped[str] = mapped_column(String(64), nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SharedBoard(Base):
    __tablename__ = "shared_boards"
    __table_args__ = (
        CheckConstraint("current_debate_round >= 0", name="round_non_negative"),
        CheckConstraint(
            "current_debate_round <= max_debate_rounds",
            name="round_within_maximum",
        ),
        CheckConstraint("max_debate_rounds > 0", name="max_rounds_positive"),
        CheckConstraint("version >= 0", name="version_non_negative"),
        CheckConstraint("review_cycle > 0", name="review_cycle_positive"),
        CheckConstraint(
            "status IN ('INITIALIZED', 'SPECIALISTS_RUNNING', "
            "'DEBATE_IN_PROGRESS', 'CONSENSUS_REACHED', "
            "'MAX_ROUNDS_REACHED')",
            name="valid_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    workflow_id: Mapped[str] = mapped_column(String(100), nullable=False)
    workflow_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=SharedBoardStatus.INITIALIZED.value
    )
    task_breakdown: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    specialist_outputs: Mapped[dict[str, object]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    final_summary: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )
    missing_data: Mapped[list[object]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    consensus_reached: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    current_debate_round: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    review_cycle: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    max_debate_rounds: Mapped[int] = mapped_column(
        Integer, nullable=False, default=3, server_default=text("3")
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class DebateLog(Base):
    __tablename__ = "debate_logs"
    __table_args__ = (
        CheckConstraint("round_number > 0", name="round_positive"),
        CheckConstraint("review_cycle > 0", name="review_cycle_positive"),
        CheckConstraint(
            "status IN ('OPEN', 'RESOLVED', 'ACCEPTED_FOR_MANUAL_REVIEW')",
            name="valid_status",
        ),
        CheckConstraint(
            "severity IN ('LOW', 'MEDIUM', 'HIGH', 'CRITICAL')",
            name="valid_severity",
        ),
        Index(
            "ix_debate_logs_case_id_cycle_round",
            "case_id",
            "review_cycle",
            "round_number",
        ),
        UniqueConstraint(
            "case_id",
            "review_cycle",
            "round_number",
            "issue_code",
            "target_agent",
            name="uq_debate_logs_case_cycle_round_issue_target",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    round_number: Mapped[int] = mapped_column(Integer, nullable=False)
    review_cycle: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    critic_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    target_agent: Mapped[str] = mapped_column(String(100), nullable=False)
    issue_code: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    related_field: Mapped[str | None] = mapped_column(String(255), nullable=True)
    error_identified: Mapped[str] = mapped_column(Text, nullable=False)
    required_action: Mapped[str] = mapped_column(Text, nullable=False)
    specialist_response: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolution_applied: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=DebateStatus.OPEN.value
    )
    logged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Approval(Base):
    """Current human decision for a case; immutable history lives in audit_logs."""

    __tablename__ = "approvals"
    __table_args__ = (
        CheckConstraint(
            "decision IN ('APPROVED', 'REJECTED', 'REVISION_REQUESTED')",
            name="valid_decision",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    verified_by: Mapped[str] = mapped_column(String(255), nullable=False)
    decision: Mapped[str] = mapped_column(String(32), nullable=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OperationExecution(Base):
    """Exactly-once record for the post-approval Mock SHB operation."""

    __tablename__ = "operation_executions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'RUNNING', 'SUCCEEDED', 'FAILED')",
            name="valid_status",
        ),
        Index("ix_operation_executions_status_created_at", "status", "created_at"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    idempotency_key: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, default=OperationStatus.PENDING.value
    )
    request_payload: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False
    )
    response_payload: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )
    artifact_keys: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class AuditLog(Base):
    """Append-only trace. The migration installs a trigger blocking UPDATE/DELETE."""

    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint(
            "outcome IN ('STARTED', 'SUCCEEDED', 'FAILED', 'BLOCKED')",
            name="valid_outcome",
        ),
        Index("ix_audit_logs_case_id_created_at", "case_id", "created_at"),
        Index("ix_audit_logs_correlation_id", "correlation_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    case_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    correlation_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False, default=uuid4
    )
    actor_type: Mapped[str] = mapped_column(String(50), nullable=False)
    actor_id: Mapped[str] = mapped_column(String(100), nullable=False)
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(100), nullable=False)
    outcome: Mapped[str] = mapped_column(
        String(32), nullable=False, default=AuditOutcome.SUCCEEDED.value
    )
    payload_trace: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AgentKnowledgeBase(Base):
    __tablename__ = "agent_knowledge_bases"
    __table_args__ = (
        CheckConstraint(
            "agent_key IN ('customer_relationship', 'credit', "
            "'risk_management', 'legal_compliance', 'collateral_appraisal')",
            name="authorized_agent_key",
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    agent_key: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolicyDocument(Base):
    __tablename__ = "policy_documents"
    __table_args__ = (
        UniqueConstraint(
            "knowledge_base_id",
            "title",
            "version",
            name="uq_policy_documents_kb_title_version",
        ),
        UniqueConstraint(
            "id",
            "knowledge_base_id",
            name="uq_policy_documents_id_knowledge_base_id",
        ),
        Index("ix_policy_documents_knowledge_base_id", "knowledge_base_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("agent_knowledge_bases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    source_object_key: Mapped[str | None] = mapped_column(
        String(1024), nullable=True
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    effective_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canonical_source_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    canonical_version_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    canonical_metadata: Mapped[dict[str, object] | None] = mapped_column(
        JSONB, nullable=True
    )
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class PolicyEmbedding(Base):
    __tablename__ = "policy_embeddings"
    __table_args__ = (
        Index(
            "uq_policy_embeddings_canonical",
            "policy_document_id",
            "canonical_chunk_id",
            unique=True,
            postgresql_where=text("canonical_chunk_id IS NOT NULL"),
        ),
        Index(
            "uq_policy_embeddings_legacy",
            "policy_document_id",
            "content_hash",
            unique=True,
            postgresql_where=text("canonical_chunk_id IS NULL"),
        ),
        CheckConstraint("chunk_index >= 0", name="chunk_index_non_negative"),
        ForeignKeyConstraint(
            ["policy_document_id", "knowledge_base_id"],
            ["policy_documents.id", "policy_documents.knowledge_base_id"],
            name="fk_policy_embeddings_document_scope",
            ondelete="RESTRICT",
        ),
        Index("ix_policy_embeddings_knowledge_base_id", "knowledge_base_id"),
        Index("ix_policy_embeddings_policy_document_id", "policy_document_id"),
        Index(
            "ix_policy_embeddings_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    knowledge_base_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("agent_knowledge_bases.id", ondelete="RESTRICT"),
        nullable=False,
    )
    policy_document_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content_chunk: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float]] = mapped_column(
        Vector(EMBEDDING_DIMENSIONS), nullable=False
    )
    metadata_: Mapped[dict[str, object]] = mapped_column(
        "metadata", JSONB, nullable=False
    )
    canonical_chunk_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
