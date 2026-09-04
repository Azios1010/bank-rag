from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections.abc import Callable, Iterable, Sequence
from typing import Literal, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from pydantic import Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.tier2_board import Reviewer, SharedBoardManager
from app.agents.tier2_board.runtime import SpecialistAgentRuntime
from app.agents.tier1_orchestrator.replanner import replan_for_missing_data
from app.config import get_settings
from app.db.models import AuditOutcome, Case, CaseStatus, Document, DocumentStatus
from app.mock_apis.shb_client import HttpMockShbClient, MockShbGateway
from app.schemas import (
    AgentCitation,
    AgentID,
    AssessmentStatus,
    BoardStatus,
    DebateIssue,
    DebateRecord,
    MissingDataRequest,
    RiskSeverity,
    SharedBoardState,
    SpecialistAssessment,
    TaskState,
    TaskStatus,
)
from app.schemas.base import ContractModel
from app.services.audit import write_audit_log
from app.services.board_repository import SqlSharedBoardRepository
from app.services.llm import OpenAICompatibleStructuredLLM, StructuredLLM
from app.services.rag import (
    AgentPolicyRetriever,
    EmbeddingProvider,
    create_embedding_provider,
)
from app.workflows import WorkflowDefinition, get_workflow
from app.workflows.schemas import WorkflowStepType


class DeepAgentError(RuntimeError):
    pass


class CaseNotAssessableError(DeepAgentError):
    pass


class AssessmentPaused(DeepAgentError):
    """Raised only at a durable safe point after a stop request."""


EventCallback = Callable[
    [str, str | None, str, str, str, dict[str, object]], None
]
CheckpointCallback = Callable[[str], None]
StopChecker = Callable[[], bool]


class OrchestratorState(TypedDict, total=False):
    case_id: str
    review_route: Literal["revise", "synthesize"]
    revision_targets: list[str]


class PlanInterpretation(ContractModel):
    case_summary: str = Field(min_length=1, max_length=2_000)
    focus_areas: list[str] = Field(default_factory=list, max_length=20)
    observed_missing_sections: list[str] = Field(default_factory=list, max_length=20)


class SemanticReviewOutput(ContractModel):
    issues: list[DebateIssue] = Field(default_factory=list, max_length=20)


class AssessmentDraft(ContractModel):
    executive_summary: str = Field(min_length=1, max_length=6_000)
    overall_risk_level: Literal["LOW", "MEDIUM", "HIGH", "MANUAL_REVIEW"]
    key_strengths: list[str] = Field(default_factory=list, max_length=30)
    key_risks: list[str] = Field(default_factory=list, max_length=30)
    officer_attention_items: list[str] = Field(default_factory=list, max_length=30)
    disclaimer: str = Field(min_length=1, max_length=1_000)


LLMFactory = Callable[[], StructuredLLM]
GatewayFactory = Callable[[], MockShbGateway]


POLICY_QUERIES: dict[AgentID, tuple[str, ...]] = {
    AgentID.CUSTOMER_RELATIONSHIP: (
        "HHB-QT-01 tiếp nhận hồ sơ định danh khách hàng KHDN",
        "HHB-HS-02 danh mục hồ sơ khách hàng doanh nghiệp",
    ),
    AgentID.CREDIT: (
        "HHB-TC-04 công thức và ngưỡng DSCR khách hàng doanh nghiệp",
        "HHB-QT-02 thẩm định tín dụng báo cáo tài chính stress test",
        "HHB-TC-02 xếp hạng tín dụng nội bộ KHDN D/E CR ROE DSCR",
    ),
    AgentID.RISK_MANAGEMENT: (
        "HHB-GT-02 giới hạn dư nợ một khách hàng khẩu vị rủi ro",
        "HHB-GT-01 vốn tự có vốn điều lệ 3.500 tỷ đồng",
        "HHB-QT-05 tái thẩm định rủi ro độc lập giới hạn danh mục",
        "HHB-TC-07 ma trận quyết định tín dụng tỷ lệ bảo đảm",
    ),
    AgentID.LEGAL_COMPLIANCE: (
        "HHB-QT-04 rà soát pháp lý tuân thủ kết luận không đạt",
        "HHB-TT-01 HHB-TT-02 KYC AML cấm vận PEP",
        "HHB-DM-03 điều kiện từ chối tuyệt đối knock-out",
    ),
    AgentID.COLLATERAL_APPRAISAL: (
        "HHB-TC-05 tỷ lệ LTV tối đa theo loại tài sản bảo đảm",
        "HHB-QT-03 thẩm định tài sản giá trị định giá thanh khoản",
        "HHB-HS-03 hồ sơ tài sản bảo đảm",
    ),
}


class DeepAgentOrchestrator:
    """One LangGraph supervisor coordinating all specialists via Shared Board."""

    def __init__(
        self,
        db: Session,
        *,
        llm_factory: LLMFactory | None = None,
        embedding_provider: EmbeddingProvider | None = None,
        bank_gateway_factory: GatewayFactory | None = None,
        event_callback: EventCallback | None = None,
        checkpoint_callback: CheckpointCallback | None = None,
        stop_checker: StopChecker | None = None,
    ) -> None:
        self._db = db
        self._llm_factory = llm_factory or OpenAICompatibleStructuredLLM
        self._embedding_provider = embedding_provider
        self._bank_gateway_factory = bank_gateway_factory or (
            lambda: HttpMockShbClient(
                get_settings().mock_shb_base_url,
                get_settings().mock_shb_timeout_seconds,
            )
        )
        self._case: Case | None = None
        self._initial_case_status: str | None = None
        self._case_payload: dict[str, object] | None = None
        self._workflow: WorkflowDefinition | None = None
        self._repository: SqlSharedBoardRepository | None = None
        self._manager: SharedBoardManager | None = None
        self._policy_citations: dict[AgentID, list[AgentCitation]] = {}
        self._reviewer = Reviewer()
        self._specialist_runtime = SpecialistAgentRuntime(self._llm_factory)
        self._event_callback = event_callback
        self._checkpoint_callback = checkpoint_callback
        self._stop_checker = stop_checker

    def run(
        self,
        case_id: UUID,
        *,
        resume_from: str | None = None,
    ) -> SharedBoardState:
        case = self._db.scalar(
            select(Case).where(Case.id == case_id).with_for_update()
        )
        if case is None:
            raise LookupError(f"Case {case_id} was not found")
        if case.status in {
            CaseStatus.APPROVED.value,
            CaseStatus.REJECTED.value,
            CaseStatus.COMPLETED.value,
        }:
            raise CaseNotAssessableError(
                f"Case in {case.status} status cannot start another assessment"
            )
        self._case = case
        self._initial_case_status = case.status
        self._case_payload = self._build_case_payload(case)
        settings = get_settings()
        self._workflow = get_workflow(
            case.workflow_id,
            settings.workflow_definition.parent,
            expected_version=case.workflow_version,
        )
        if self._workflow.max_debate_rounds > settings.max_debate_rounds:
            raise CaseNotAssessableError(
                "Workflow debate limit exceeds the configured safety maximum"
            )
        self._repository = SqlSharedBoardRepository(
            self._db,
            workflow_id=self._workflow.workflow_id,
            workflow_version=self._workflow.version,
        )
        self._manager = SharedBoardManager(self._repository)

        existing = self._repository.get_by_case_id(case_id)
        if (
            existing is not None
            and existing.final_summary is not None
            and case.status == CaseStatus.TIER3_PENDING_REVIEW.value
        ):
            return existing

        synthesis_resume = (
            existing is not None
            and existing.final_summary is None
            and existing.status
            in {BoardStatus.CONSENSUS_REACHED, BoardStatus.MAX_ROUNDS_REACHED}
        )
        if case.status in {
            CaseStatus.TIER1_PLANNING.value,
            CaseStatus.TIER2_DEBATING.value,
        } and not synthesis_resume and resume_from is None:
            self._db.rollback()
            raise CaseNotAssessableError("An assessment is already in progress")
        if not synthesis_resume and resume_from is None:
            case.status = CaseStatus.TIER1_PLANNING.value
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=AgentID.BANKING_ORCHESTRATOR.value,
                action="ASSESSMENT_STARTED",
                entity_type="case",
                entity_id=str(case.id),
            )
            self._db.commit()

        try:
            self._run_stages(
                case_id,
                resume_from=("synthesize" if synthesis_resume else resume_from),
            )
        except AssessmentPaused:
            self._db.rollback()
            raise
        except Exception as exc:
            self._db.rollback()
            failed_case = self._db.get(Case, case_id)
            if failed_case is not None:
                if self._initial_case_status is not None and not synthesis_resume:
                    failed_case.status = self._initial_case_status
                write_audit_log(
                    self._db,
                    case_id=case_id,
                    actor_type="AGENT",
                    actor_id=AgentID.BANKING_ORCHESTRATOR.value,
                    action="ASSESSMENT_FAILED",
                    entity_type="case",
                    entity_id=str(case_id),
                    outcome=AuditOutcome.FAILED,
                    error=type(exc).__name__,
                )
                self._db.commit()
            raise
        return self._manager_required().get(case_id)

    def _run_stages(self, case_id: UUID, *, resume_from: str | None) -> None:
        """Explicit safe-point state machine; LangGraph nodes remain reusable units."""

        state: OrchestratorState = {"case_id": str(case_id)}
        stage = resume_from or "plan"
        if stage not in {"plan", "specialists", "review", "revise", "synthesize"}:
            stage = "plan"

        if stage == "plan":
            self._stage_started("plan", "Orchestrator đang đọc hồ sơ và lập kế hoạch")
            self._plan_node(state)
            self._stage_completed("plan", "Đã lập kế hoạch và tạo Shared Board")
            self._checkpoint("specialists")
            self._pause_if_requested()
            stage = "specialists"

        if stage == "specialists":
            self._stage_started("rag", "Đang truy xuất quy định cho từng chuyên gia")
            self._specialists_node(state)
            self._stage_completed("specialists", "Các chuyên gia đã đăng kết quả lên Shared Board")
            self._checkpoint("review")
            self._pause_if_requested()
            if self._route_after_specialists(state) == "missing_data":
                self._stage_started("missing_data", "Đang tổng hợp tài liệu còn thiếu")
                self._missing_data_node(state)
                self._stage_completed("missing_data", "Đã gửi yêu cầu bổ sung tài liệu")
                return
            stage = "review"
        elif stage in {"review", "revise", "synthesize"}:
            # Policy citations are process-local; rebuild them when a persisted run resumes.
            self._policy_citations = self._retrieve_all_policies()

        while stage in {"review", "revise"}:
            if stage == "review":
                self._stage_started("review", "Reviewer đang kiểm tra chéo bằng chứng")
                state = self._review_node(state)
                board = self._manager_required().get(case_id)
                self._stage_completed(
                    "review",
                    "Reviewer đã hoàn tất một vòng kiểm tra",
                    evidence={
                        "round": board.current_debate_round,
                        "open_issues": sum(
                            item.status.value == "OPEN" for item in board.debate_log
                        ),
                    },
                )
                stage = state["review_route"]
                self._checkpoint(stage)
                self._pause_if_requested()
            else:
                self._stage_started("revise", "Các chuyên gia đang trả lời phản biện")
                state = self._revise_node(state)
                self._stage_completed("revise", "Đã đăng phản hồi của chuyên gia")
                stage = "review"
                self._checkpoint("review")
                self._pause_if_requested()

        self._stage_started("synthesize", "Orchestrator đang tổng hợp kết luận sơ bộ")
        self._synthesize_node(state)
        self._stage_completed("synthesize", "Hồ sơ đã sẵn sàng cho chuyên viên xác minh")
        self._checkpoint("completed")

    def _emit(
        self,
        stage: str,
        *,
        agent_id: AgentID | None,
        status: str,
        title: str,
        message: str,
        evidence: dict[str, object] | None = None,
    ) -> None:
        if self._event_callback is not None:
            self._event_callback(
                stage,
                agent_id.value if agent_id is not None else None,
                status,
                title,
                message,
                evidence or {},
            )

    def _stage_started(self, stage: str, message: str) -> None:
        self._emit(
            stage,
            agent_id=AgentID.BANKING_ORCHESTRATOR,
            status="RUNNING",
            title=stage.replace("_", " ").title(),
            message=message,
        )

    def _stage_completed(
        self, stage: str, message: str, *, evidence: dict[str, object] | None = None
    ) -> None:
        self._emit(
            stage,
            agent_id=AgentID.BANKING_ORCHESTRATOR,
            status="COMPLETED",
            title=stage.replace("_", " ").title(),
            message=message,
            evidence=evidence,
        )

    def _checkpoint(self, next_stage: str) -> None:
        if self._checkpoint_callback is not None:
            self._checkpoint_callback(next_stage)

    def _pause_if_requested(self) -> None:
        if self._stop_checker is not None and self._stop_checker():
            raise AssessmentPaused("Assessment paused at a durable safe point")

    def _build_graph(self):
        builder = StateGraph(OrchestratorState)
        builder.add_node("plan", self._plan_node)
        builder.add_node("specialists", self._specialists_node)
        builder.add_node("missing_data", self._missing_data_node)
        builder.add_node("review", self._review_node)
        builder.add_node("revise", self._revise_node)
        builder.add_node("synthesize", self._synthesize_node)
        builder.add_edge(START, "plan")
        builder.add_edge("plan", "specialists")
        builder.add_conditional_edges(
            "specialists",
            self._route_after_specialists,
            {"missing_data": "missing_data", "review": "review"},
        )
        builder.add_conditional_edges(
            "review",
            lambda state: state["review_route"],
            {"revise": "revise", "synthesize": "synthesize"},
        )
        builder.add_edge("revise", "review")
        builder.add_edge("missing_data", END)
        builder.add_edge("synthesize", END)
        return builder.compile()

    def _plan_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        workflow = self._workflow_required()
        llm = self._llm_factory()
        plan = llm.invoke_structured(
            schema=PlanInterpretation,
            system_prompt=(
                "You are the single Banking Orchestrator. Understand the supplied "
                "corporate loan case and identify analytical focus areas. The workflow "
                "is already bank-approved; do not add agents, skip the human gate, or "
                "make an approval decision."
            ),
            user_prompt=json.dumps(
                {
                    "case_id": str(case.id),
                    "company_name": case.company_name,
                    "requested_amount": str(case.requested_amount),
                    "currency": case.currency,
                    "case_facts": self._case_payload_required(),
                    "workflow": workflow.model_dump(mode="json"),
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        tasks = self._workflow_tasks(workflow)
        repository = self._repository_required()
        board = repository.get_by_case_id(case.id)
        if board is None:
            board = self._manager_required().initialize(
                case.id,
                tasks,
                max_debate_rounds=workflow.max_debate_rounds,
            )
        elif self._initial_case_status in {
            CaseStatus.AWAITING_DOCS.value,
            CaseStatus.REVISION_REQUESTED.value,
        }:
            board = repository.reset_for_reassessment(
                case.id,
                tasks=tasks,
                max_debate_rounds=workflow.max_debate_rounds,
            )

        case.status = CaseStatus.TIER1_PLANNING.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="TIER1_PLAN",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=plan,
        )
        self._db.commit()
        return state

    def _specialists_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        case.status = CaseStatus.TIER2_DEBATING.value
        self._policy_citations = self._retrieve_all_policies()
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="RAG_QUERY",
            entity_type="case",
            entity_id=str(case.id),
            response={
                agent.value: [str(item.policy_chunk_id) for item in citations]
                for agent, citations in self._policy_citations.items()
            },
        )
        self._db.commit()

        assessments: dict[AgentID, SpecialistAssessment] = {}
        existing_board = self._manager_required().get(case.id)
        for agent_id, output in existing_board.specialist_outputs.items():
            if output.status in {
                AssessmentStatus.SUCCESS,
                AssessmentStatus.MANUAL_REVIEW,
                AssessmentStatus.REQUIRES_MORE_DATA,
            }:
                assessments[agent_id] = output

        def run_agent(
            agent_id: AgentID,
            *,
            payload: dict[str, object] | None = None,
            external_risks: Sequence[str] = (),
        ) -> SpecialistAssessment:
            try:
                return self._specialist_runtime.run(
                    agent_id=agent_id,
                    case_payload=payload or self._case_payload_required(),
                    policy_citations=self._policy_citations[agent_id],
                    external_risk_codes=external_risks,
                )
            except Exception as exc:
                return _error_assessment(
                    agent_id,
                    f"Agent execution failed: {type(exc).__name__}",
                )

        # HHB-QT-01 intake is completed before the three parallel B2/B3/B4 reviews.
        if AgentID.CUSTOMER_RELATIONSHIP not in assessments:
            self._mark_agent_running(AgentID.CUSTOMER_RELATIONSHIP)
            assessment = run_agent(AgentID.CUSTOMER_RELATIONSHIP)
            assessments[AgentID.CUSTOMER_RELATIONSHIP] = assessment
            self._post_agent_assessment(assessment)
            self._pause_if_requested()
        parallel_agents = [
            AgentID.CREDIT,
            AgentID.COLLATERAL_APPRAISAL,
            AgentID.LEGAL_COMPLIANCE,
        ]
        pending_parallel = [
            agent_id for agent_id in parallel_agents if agent_id not in assessments
        ]
        for agent_id in pending_parallel:
            self._mark_agent_running(agent_id)
        with ThreadPoolExecutor(max_workers=max(1, len(pending_parallel))) as executor:
            future_to_agent = {
                executor.submit(run_agent, agent_id): agent_id
                for agent_id in pending_parallel
            }
            for future in as_completed(future_to_agent):
                agent_id = future_to_agent[future]
                assessment = future.result()
                assessments[agent_id] = assessment
                self._post_agent_assessment(assessment)
                self._pause_if_requested()

        # HHB-QT-05 is an independent second-line review over B2/B3/B4 outputs.
        risk_payload = dict(self._case_payload_required())
        risk_payload["cross_domain_assessments"] = {
            agent_id.value: assessment.model_dump(mode="json")
            for agent_id, assessment in assessments.items()
        }
        cross_domain_risks = sorted(
            {
                risk.code
                for assessment in assessments.values()
                for risk in assessment.risk_flags
            }
        )
        if AgentID.RISK_MANAGEMENT not in assessments:
            self._mark_agent_running(AgentID.RISK_MANAGEMENT)
            assessment = run_agent(
                AgentID.RISK_MANAGEMENT,
                payload=risk_payload,
                external_risks=cross_domain_risks,
            )
            assessments[AgentID.RISK_MANAGEMENT] = assessment
            self._post_agent_assessment(assessment)
            self._pause_if_requested()
        return state

    def _mark_agent_running(self, agent_id: AgentID) -> None:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        task = next(
            (item for item in board.tasks.values() if item.assigned_to == agent_id),
            None,
        )
        if task is not None:
            manager.set_task_status(
                case.id,
                task.task_id,
                TaskStatus.RUNNING,
                expected_version=board.version,
                detail=f"{agent_id.value} đang phân tích hồ sơ và bằng chứng RAG",
            )
            self._db.commit()
        self._emit(
            "specialists",
            agent_id=agent_id,
            status="RUNNING",
            title=f"{agent_id.value} bắt đầu",
            message="Đang đối chiếu dữ liệu hồ sơ với quy định được truy xuất.",
            evidence={
                "policy_chunks": len(self._policy_citations.get(agent_id, [])),
            },
        )

    def _post_agent_assessment(self, assessment: SpecialistAssessment) -> None:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        manager.post_assessment(
            case.id,
            assessment,
            expected_version=board.version,
        )
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=assessment.agent_id.value,
            action="AGENT_OUTPUT_POSTED",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=assessment,
        )
        self._db.commit()
        self._emit(
            "specialists",
            agent_id=assessment.agent_id,
            status=assessment.status.value,
            title=f"{assessment.agent_id.value} đã cập nhật",
            message=(
                assessment.error_message
                or assessment.rationale_summary
                or "Đã đăng kết quả có cấu trúc lên Shared Board."
            )[:1_000],
            evidence={
                "policy_citations": len(assessment.policy_citations),
                "document_evidence": len(assessment.document_evidence),
                "risk_flags": len(assessment.risk_flags),
            },
        )

    def _route_after_specialists(
        self, state: OrchestratorState
    ) -> Literal["missing_data", "review"]:
        case_id = UUID(state["case_id"])
        board = self._manager_required().get(case_id)
        if any(
            output.status == AssessmentStatus.REQUIRES_MORE_DATA
            for output in board.specialist_outputs.values()
        ):
            return "missing_data"
        return "review"

    def _missing_data_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        missing = _unique_missing_data(
            item
            for assessment in board.specialist_outputs.values()
            for item in assessment.missing_data
        )
        replan = replan_for_missing_data(self._llm_factory(), missing)
        updated = board.model_copy(
            update={
                "missing_data": missing,
                "final_summary": {
                    "status": "AWAITING_DOCS",
                    "message": replan.officer_message,
                    "requested_document_types": replan.requested_document_types,
                    "requested_fields": replan.requested_fields,
                    "missing_data": [item.model_dump(mode="json") for item in missing],
                },
            },
            deep=True,
        )
        self._repository_required().save(updated, expected_version=board.version)
        case.status = CaseStatus.AWAITING_DOCS.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="ASSESSMENT_AWAITING_DOCUMENTS",
            entity_type="case",
            entity_id=str(case.id),
            response=missing,
        )
        self._db.commit()
        return state

    def _review_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        deterministic = self._reviewer.review(board)
        llm = self._llm_factory()
        semantic = llm.invoke_structured(
            schema=SemanticReviewOutput,
            system_prompt=(
                "You are the Reviewer Agent. Find only evidence-backed semantic "
                "contradictions or unsupported cross-domain conclusions in the Shared "
                "Board. Do not duplicate supplied deterministic issues. Do not approve "
                "or reject the loan. Target only one of the five specialist agents."
            ),
            user_prompt=json.dumps(
                {
                    "shared_board": board.model_dump(mode="json"),
                    "deterministic_issues": [
                        issue.model_dump(mode="json") for issue in deterministic.issues
                    ],
                },
                ensure_ascii=False,
                default=str,
            ),
        )
        issues = _deduplicate_issues([*deterministic.issues, *semantic.issues])
        for issue in issues:
            self._emit(
                "review",
                agent_id=AgentID.REVIEWER,
                status="CHALLENGE",
                title=f"Reviewer → {issue.target_agent.value}",
                message=issue.description,
                evidence={
                    "issue_code": issue.code,
                    "severity": issue.severity.value,
                    "target_agent": issue.target_agent.value,
                    "required_action": issue.required_action,
                },
            )
        current_issue_keys = {
            (issue.code, issue.target_agent) for issue in issues
        }
        for record in [item for item in board.debate_log if item.status.value == "OPEN"]:
            key = (record.issue.code, record.issue.target_agent)
            if key in current_issue_keys:
                continue
            board = manager.resolve_debate_issue(
                case.id,
                round_number=record.round_number,
                issue_code=record.issue.code,
                target_agent=record.issue.target_agent,
                specialist_response=(
                    record.specialist_response
                    or "The specialist posted a corrected structured assessment."
                ),
                resolution="The Reviewer independently verified this issue as corrected.",
                expected_version=board.version,
            )
        if not issues:
            manager.mark_consensus(case.id, expected_version=board.version)
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=AgentID.REVIEWER.value,
                action="CONSENSUS_REACHED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                response={"review_cycle": board.review_cycle},
            )
            self._db.commit()
            return {**state, "review_route": "synthesize", "revision_targets": []}

        if board.current_debate_round >= board.max_debate_rounds:
            records = [
                DebateRecord(
                    round_number=board.current_debate_round,
                    issue=issue,
                )
                for issue in issues
            ]
            manager.accept_for_manual_review(
                case.id,
                records,
                expected_version=board.version,
            )
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=AgentID.REVIEWER.value,
                action="MAX_DEBATE_ROUNDS_REACHED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                outcome=AuditOutcome.BLOCKED,
                response=issues,
            )
            self._db.commit()
            return {**state, "review_route": "synthesize", "revision_targets": []}

        next_round = board.current_debate_round + 1
        records = [DebateRecord(round_number=next_round, issue=issue) for issue in issues]
        manager.append_debate_round(
            case.id,
            records,
            expected_version=board.version,
        )
        targets = sorted({issue.target_agent.value for issue in issues})
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.REVIEWER.value,
            action="REVIEW_ISSUES_POSTED",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=records,
        )
        self._db.commit()
        return {**state, "review_route": "revise", "revision_targets": targets}

    def _revise_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        targets = [AgentID(value) for value in state.get("revision_targets", [])]
        for agent_id in targets:
            board = manager.get(case.id)
            open_records = [
                record
                for record in board.debate_log
                if record.status.value == "OPEN"
                and record.issue.target_agent == agent_id
                and record.round_number == board.current_debate_round
            ]
            feedback = [record.issue.required_action for record in open_records]
            external_risks = _external_risk_codes(board, exclude=agent_id)
            self._emit(
                "revise",
                agent_id=agent_id,
                status="REFINING",
                title=f"{agent_id.value} đang trả lời Reviewer",
                message="; ".join(feedback)[:1_000] or "Đang kiểm tra lại kết quả.",
                evidence={"issues": len(open_records)},
            )
            try:
                assessment = self._specialist_runtime.run(
                    agent_id=agent_id,
                    case_payload=self._case_payload_required(),
                    policy_citations=self._policy_citations[agent_id],
                    reviewer_feedback=feedback,
                    external_risk_codes=external_risks,
                )
            except Exception as exc:
                assessment = _error_assessment(
                    agent_id,
                    f"Agent refinement failed: {type(exc).__name__}",
                )
            board = manager.post_assessment(
                case.id,
                assessment,
                expected_version=board.version,
            )
            for record in open_records:
                board = manager.record_debate_response(
                    case.id,
                    round_number=record.round_number,
                    issue_code=record.issue.code,
                    target_agent=agent_id,
                    specialist_response=assessment.rationale_summary,
                    expected_version=board.version,
                )
            write_audit_log(
                self._db,
                case_id=case.id,
                actor_type="AGENT",
                actor_id=agent_id.value,
                action="AGENT_REFINED",
                entity_type="shared_board",
                entity_id=str(board.board_id),
                response=assessment,
            )
            self._db.commit()
            self._emit(
                "revise",
                agent_id=agent_id,
                status=assessment.status.value,
                title=f"{agent_id.value} đã phản hồi",
                message=assessment.rationale_summary[:1_000],
                evidence={
                    "round": board.current_debate_round,
                    "policy_citations": len(assessment.policy_citations),
                    "document_evidence": len(assessment.document_evidence),
                },
            )
            self._pause_if_requested()
        return state

    def _synthesize_node(self, state: OrchestratorState) -> OrchestratorState:
        case = self._case_required()
        manager = self._manager_required()
        board = manager.get(case.id)
        llm = self._llm_factory()
        draft = llm.invoke_structured(
            schema=AssessmentDraft,
            system_prompt=(
                "You are the Banking Orchestrator synthesizing a preliminary corporate "
                "loan assessment for a human officer. Summarize evidence, calculations, "
                "citations, and unresolved debate. Never output an approval/rejection "
                "decision and explicitly state that human verification is required."
            ),
            user_prompt=json.dumps(
                board.model_dump(mode="json"),
                ensure_ascii=False,
                default=str,
            ),
        )
        citation_map = {
            str(citation.policy_chunk_id): citation.model_dump(mode="json")
            for assessment in board.specialist_outputs.values()
            for citation in assessment.policy_citations
        }
        final_summary: dict[str, object] = {
            **draft.model_dump(mode="json"),
            "consensus_reached": board.consensus_reached,
            "review_cycle": board.review_cycle,
            "policy_citations": list(citation_map.values()),
            "manual_review_issues": [
                record.model_dump(mode="json")
                for record in board.debate_log
                if record.status.value in {"OPEN", "ACCEPTED_FOR_MANUAL_REVIEW"}
            ],
            "human_verification_required": True,
        }
        updated = board.model_copy(
            update={"final_summary": final_summary},
            deep=True,
        )
        self._repository_required().save(updated, expected_version=board.version)
        case.status = CaseStatus.TIER3_PENDING_REVIEW.value
        write_audit_log(
            self._db,
            case_id=case.id,
            actor_type="AGENT",
            actor_id=AgentID.BANKING_ORCHESTRATOR.value,
            action="SYNTHESIS_CREATED",
            entity_type="shared_board",
            entity_id=str(board.board_id),
            response=final_summary,
        )
        self._db.commit()
        return state

    def _retrieve_all_policies(self) -> dict[AgentID, list[AgentCitation]]:
        # Existing application workflow remains on legacy R01 RAG until a
        # separately approved application cutover.  Stage 11D evaluation uses
        # CanonicalV2Retriever and Supabase RPC instead.
        embedding_provider = self._embedding_provider or create_embedding_provider()
        results: dict[AgentID, list[AgentCitation]] = {}
        for agent_id, queries in POLICY_QUERIES.items():
            retriever = AgentPolicyRetriever(
                self._db,
                agent_id,
                embedding_provider,
            )
            unique: dict[UUID, AgentCitation] = {}
            for query in queries:
                for citation in retriever.retrieve(
                    query,
                    limit=3,
                    min_similarity=0.10,
                ):
                    unique[citation.policy_chunk_id] = citation
            results[agent_id] = sorted(
                unique.values(),
                key=lambda item: item.similarity_score or 0,
                reverse=True,
            )[:8]
        return results

    @staticmethod
    def _workflow_tasks(workflow: WorkflowDefinition) -> list[TaskState]:
        return [
            TaskState(
                task_id=step.id,
                assigned_to=step.agent,
                dependencies=[
                    dependency
                    for dependency in step.depends_on
                    if dependency != "understand_and_plan"
                ],
                detail=step.description,
            )
            for step in workflow.steps
            if step.type == WorkflowStepType.SPECIALIST and step.agent is not None
        ]

    def _case_required(self) -> Case:
        if self._case is None:
            raise RuntimeError("Orchestrator case is not initialized")
        return self._case

    def _case_payload_required(self) -> dict[str, object]:
        if self._case_payload is None:
            raise RuntimeError("Orchestrator case payload is not initialized")
        return self._case_payload

    def _build_case_payload(self, case: Case) -> dict[str, object]:
        """Attach parsed case documents without placing customer data in pgvector."""

        remaining = get_settings().agent_document_context_chars
        document_context: list[dict[str, object]] = []
        documents = self._db.scalars(
            select(Document)
            .where(
                Document.case_id == case.id,
                Document.status == DocumentStatus.PARSED.value,
                Document.extracted_text.is_not(None),
            )
            .order_by(Document.created_at)
        ).all()
        for document in documents:
            if remaining <= 0:
                break
            extracted_text = document.extracted_text or ""
            text = extracted_text[:remaining]
            remaining -= len(text)
            document_context.append(
                {
                    "document_id": str(document.id),
                    "document_type": document.document_type,
                    "filename": document.original_filename,
                    "content_type": document.content_type,
                    "content": text,
                    "truncated": len(extracted_text) > len(text),
                }
            )

        payload = dict(case.input_payload)
        payload["canonical_case"] = {
            "case_id": str(case.id),
            "company_name": case.company_name,
            "requested_amount": str(case.requested_amount),
            "currency": case.currency,
        }
        requested_terms = _mapping_copy(payload.get("requested_terms"))
        requested_terms["requested_amount"] = str(case.requested_amount)
        requested_terms["currency"] = case.currency
        payload["requested_terms"] = requested_terms
        borrower_profile = _mapping_copy(payload.get("borrower_profile"))
        borrower_profile["company_name"] = case.company_name
        payload["borrower_profile"] = borrower_profile
        payload["trusted_bank_context"] = self._load_trusted_bank_context(payload)
        if document_context:
            payload["case_documents"] = document_context
        return payload

    def _load_trusted_bank_context(
        self,
        payload: dict[str, object],
    ) -> dict[str, object]:
        borrower_profile = _mapping_copy(payload.get("borrower_profile"))
        customer_id = str(
            payload.get("customer_id")
            or borrower_profile.get("registration_number")
            or ""
        ).strip()
        if not customer_id:
            return {"lookup_status": "MISSING_CUSTOMER_ID"}

        gateway = self._bank_gateway_factory()
        try:
            customer = gateway.get_customer(customer_id)
            credit_ledger = gateway.get_credit_ledger(customer_id)
            compliance = gateway.get_compliance(customer_id)
            return {
                "lookup_status": "VERIFIED",
                "source": "MOCK_SHB_API",
                "customer_master": customer.model_dump(mode="json"),
                "credit_ledger": credit_ledger.model_dump(mode="json"),
                "compliance": compliance.model_dump(mode="json"),
            }
        except Exception:
            return {
                "lookup_status": "UNAVAILABLE",
                "source": "MOCK_SHB_API",
            }
        finally:
            close = getattr(gateway, "close", None)
            if callable(close):
                close()

    def _workflow_required(self) -> WorkflowDefinition:
        if self._workflow is None:
            raise RuntimeError("Orchestrator workflow is not initialized")
        return self._workflow

    def _repository_required(self) -> SqlSharedBoardRepository:
        if self._repository is None:
            raise RuntimeError("Shared Board repository is not initialized")
        return self._repository

    def _manager_required(self) -> SharedBoardManager:
        if self._manager is None:
            raise RuntimeError("Shared Board manager is not initialized")
        return self._manager


def _error_assessment(agent_id: AgentID, message: str) -> SpecialistAssessment:
    from app.schemas import (
        CollateralAppraisalAssessment,
        CreditAssessment,
        CustomerRelationshipAssessment,
        LegalComplianceAssessment,
        RiskManagementAssessment,
    )

    assessment_types = {
        AgentID.CUSTOMER_RELATIONSHIP: CustomerRelationshipAssessment,
        AgentID.CREDIT: CreditAssessment,
        AgentID.RISK_MANAGEMENT: RiskManagementAssessment,
        AgentID.LEGAL_COMPLIANCE: LegalComplianceAssessment,
        AgentID.COLLATERAL_APPRAISAL: CollateralAppraisalAssessment,
    }
    assessment_type = assessment_types[agent_id]
    return assessment_type(
        status=AssessmentStatus.ERROR,
        error_message=message,
        rationale_summary="The specialist did not produce a valid structured output.",
    )


def _unique_missing_data(
    items: Iterable[MissingDataRequest],
) -> list[MissingDataRequest]:
    unique: dict[str, MissingDataRequest] = {}
    for item in items:
        unique[item.code] = item
    return list(unique.values())


def _deduplicate_issues(issues: Sequence[DebateIssue]) -> list[DebateIssue]:
    unique: dict[tuple[str, AgentID], DebateIssue] = {}
    for issue in issues:
        unique[(issue.code, issue.target_agent)] = issue
    return list(unique.values())


def _external_risk_codes(
    board: SharedBoardState,
    *,
    exclude: AgentID,
) -> list[str]:
    return sorted(
        {
            risk.code
            for agent_id, assessment in board.specialist_outputs.items()
            if agent_id != exclude
            for risk in assessment.risk_flags
            if risk.severity in {RiskSeverity.HIGH, RiskSeverity.CRITICAL}
        }
    )


def _mapping_copy(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}
