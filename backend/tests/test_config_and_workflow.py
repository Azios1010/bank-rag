from __future__ import annotations

from pydantic import ValidationError
import pytest

from app.config import Settings
from app.workflows.loader import WorkflowLoadError, get_workflow
from app.workflows.schemas import WorkflowDefinition


def test_settings_are_valid_without_an_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)

    settings = Settings(
        _env_file=None,
        llm_api_key=None,
        embedding_api_key=None,
        embedding_provider="deterministic_test",
        environment="test",
    )

    assert settings.llm_api_key is None
    assert settings.embedding_api_key is None
    assert settings.embedding_dimension == 1024
    assert settings.embedding_provider == "deterministic_test"


def test_settings_decouple_llm_and_embedding_endpoints() -> None:
    settings = Settings(
        _env_file=None,
        llm_api_base="https://llm.example.com",
        llm_api_key="llm_secret",
        embedding_api_base="https://emb.example.com",
        embedding_api_key="emb_secret",
        embedding_provider="deterministic_test",
        environment="test",
    )
    assert settings.llm_api_base == "https://llm.example.com"
    assert settings.llm_api_key.get_secret_value() == "llm_secret"
    assert settings.embedding_api_base == "https://emb.example.com"
    assert settings.embedding_api_key.get_secret_value() == "emb_secret"


def test_settings_reject_embedding_dimension_that_does_not_match_schema() -> None:
    with pytest.raises(ValidationError, match="must remain 1024"):
        Settings(_env_file=None, embedding_dimension=1536)


def test_corporate_loan_workflow_has_expected_version_and_execution_layers() -> None:
    workflow = get_workflow("corporate_loan_v1", expected_version="1.0")

    assert workflow.version == "1.0"
    assert [[step.id for step in layer] for layer in workflow.execution_layers()] == [
        ["understand_and_plan"],
        ["customer_profile"],
        [
            "collateral_appraisal",
            "credit_analysis",
            "legal_compliance_review",
        ],
        ["risk_assessment"],
        ["reviewer_debate"],
        ["synthesize_assessment"],
        ["human_verification"],
        ["banking_operations"],
    ]


def test_workflow_version_contract_and_case_version_guard() -> None:
    workflow = get_workflow("corporate_loan_v1")
    invalid_payload = workflow.model_dump(mode="json") | {"version": "v1"}

    with pytest.raises(ValidationError, match="version"):
        WorkflowDefinition.model_validate(invalid_payload)

    with pytest.raises(WorkflowLoadError, match="version mismatch"):
        get_workflow("corporate_loan_v1", expected_version="2.0")
